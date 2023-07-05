"""
The Zapp! compiler.
"""

import argparse
import json
import os
import pathlib
import re
import stat
import sys
import zipfile
from collections import defaultdict
from email.parser import Parser
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory

from zapp.support.pep425 import compress_tags, decompress_tag
from zapp.support.unpack import cache_wheel_path

parser = argparse.ArgumentParser(description="The (bootstrap) Zapp compiler")
parser.add_argument("-o", "--out", dest="output", help="Output target file")
parser.add_argument("-d", "--debug", dest="debug", action="store_true", default=False)
parser.add_argument(
    "--use-wheels", dest="use_wheels", action="store_true", default=False
)
parser.add_argument("manifest", help="The (JSON) manifest")


MAIN_TEMPLATE = """\
# -*- coding: utf-8 -*-

\"\"\"Zapp!-generated __main__\""\"

from importlib import import_module
import os
import sys
from runpy import _run_module_as_main

for script in {scripts!r}:
    mod, sep, fn = script.partition(':')
    mod_ok = all(part.isidentifier() for part in mod.split('.'))
    fn_ok = all(part.isidentifier() for part in fn.split('.'))

    if not mod_ok:
        raise RuntimeError("Invalid module reference {{!r}}".format(mod))
    if fn and not fn_ok:
        raise RuntimeError("Invalid function reference {{!r}}".format(fn))

    if mod and fn:
        mod = import_module(mod)
        getattr(mod, fn)()
    else:
        _run_module_as_main(mod)
"""


whl_workspace_pattern = re.compile(r"^external/(?P<workspace>[^/]*?)/site-packages/")


def dsub(d1: dict, d2: dict) -> dict:
    """Dictionary subtraction. Remove k/vs from d1 if they occur in d2."""

    return {k: v for k, v in d1.items() if k not in d2 or v != d2[k]}


def make_dunder_main(manifest):
    """Generate a __main__.py file for the given manifest."""

    prelude = manifest.get("prelude_points", [])
    main = manifest.get("entry_point")
    scripts = prelude + [main]
    return MAIN_TEMPLATE.format(**locals())


def dir_walk_prefixes(path):
    """Helper. Walk all slices of a path."""

    segments = []
    yield ""
    for segment in path.split("/"):
        segments.append(segment)
        yield os.path.join(*segments)


def load_wheel(opts, path):
    """Load a single wheel, returning ..."""

    def _parse_email(msg):
        msg = Parser().parsestr(msg)

        def _get(k):
            v = msg.get_all(k)
            if len(v) == 1:
                return v[0]
            else:
                return v

        return {k: _get(k) for k in msg.keys()}

    with open(os.path.join(path, "METADATA")) as metaf:
        meta = _parse_email(metaf.read())

    with open(os.path.join(path, "WHEEL")) as wheelf:
        wheel = _parse_email(wheelf.read())

    # Naive glob of sources; note that bazel may hvae inserted empty __init__.py trash
    sources = []

    # Retain only manifest-listed sources (dealing with __init__.py trash, but maybe not all conflicts)
    with open(os.path.join(path, "RECORD")) as recordf:
        known_srcs = set()
        for line in recordf:
            srcname, *_ = line.split(",")
            known_srcs.add(srcname)

        sources = {
            dest: spec
            for dest, spec in sources
            if dest in known_srcs or not dest.endswith("__init__.py")
        }

        # FIXME: Check hashes & sizes of manifest-listed sources and abort on error/conflict.

    # FIXME: Check for .so files or other compiled artifacts, adjust tags accordingly.

    return {
        # "record": record,
        "meta": meta,
        "wheel": wheel,
        "sources": sources,
    }


def wheel_name(wheel):
    """Construct the "canonical" filename of the wheel."""

    # https://www.python.org/dev/peps/pep-0425/
    tags = wheel["wheel"].get("Tag")
    if isinstance(tags, list):
        tags = "-" + compress_tags(chain(*[decompress_tag(t) for t in tags]))
    elif isinstance(tags, str):
        tags = "-" + tags
    else:
        tags = ""

    return "".join(
        [
            wheel["meta"]["Name"],
            "-",
            wheel["meta"]["Version"],
            tags,
            ".whl",
        ]
    )


def zip_wheel(tmpdir, wheel):
    """Build a 'tempfile' containing the proper contents of the wheel."""

    wn = wheel_name(wheel)
    cached_path = cache_wheel_path(wn)
    wheel_file = os.path.join(tmpdir, wn)

    with zipfile.ZipFile(wheel_file, "w") as whl:
        for dest, src in wheel["sources"].items():
            whl.write(src["source"], dest)

    try:
        # Attempt to enter the (re)built wheel into the cache. This could fail
        # due to coss-device rename problems, or due to something else having
        # concurrently built the same wheel and won the race.
        #
        # FIXME: This probably needs some guardrails to ensure that we only put
        # architecture-independent wheels into the cache this way to avoid the
        # plethora of "missbehaved wheels" problems that pip deals with.
        Path(wheel_file).rename(cached_path)
        return str(cached_path)
    except OSError:
        return wheel_file


def rezip_wheels(opts, manifest):
    """Extract unzipped wheels from the manifest's inputs, simplifying the manifest.

    Wheels which are unzipped should be re-zipped into the cache, if not present in the cache.

    Files sourced from unzipped wheels should be removed, and a single wheel reference inserted.
    """

    whl_srcs = defaultdict(dict)
    for k, s in list(manifest["sources"].items()):
        src = s["source"]
        m = re.match(whl_workspace_pattern, src)
        if m:
            whl_srcs[m.group(1)][re.sub(whl_workspace_pattern, "", src)] = s
            del manifest["sources"][k]

    wheels = []
    for bundle in whl_srcs.values():
        whlk = next((k for k in bundle.keys() if k.endswith("WHEEL")), None)
        whl_manifest = load_wheel(opts, os.path.dirname(bundle[whlk]["source"]))
        whl_manifest["sources"].update(bundle)
        wheels.append(whl_manifest)

    manifest["requirements"] = {}

    # Zip up the wheels and insert wheel records to the manifest
    for w in wheels:
        # Try to cheat and hit in the local cache first rather than building wheels every time
        wn = wheel_name(w)

        # We may have a double-path dependency.
        # If we DON'T, we have to zip
        if wn not in manifest["wheels"]:
            wf = cache_wheel_path(wn)
            if wf.exists():
                try:
                    wf.touch()
                except OSError:
                    pass
                wf = str(wf)
            else:
                if opts.debug and False:
                    print("\n---")
                    json.dump({"$type": "whl", **w}, sys.stdout, indent=2)

                wf = zip_wheel(opts.tmpdir, w)

            # Insert a new wheel source
            manifest["wheels"][wn] = {"hashes": [], "source": wf, "manifest": w}

            # Insert the requirement
            manifest["requirements"][w["meta"]["Name"]] = w["meta"]["Version"]

    return manifest


def ensure_srcs_map(opts, manifest):
    manifest["sources"] = dict(manifest["sources"])

    return manifest


def generate_dunder_inits(opts, manifest):
    """Hack the manifest to insert __init__ files as needed."""

    sources = manifest["sources"]

    for input_file in list(sources.keys()):
        for path in dir_walk_prefixes(os.path.dirname(input_file)):
            init_file = os.path.join(path, "__init__.py")
            if init_file not in sources:
                sources[init_file] = None

    return manifest


def insert_manifest_json(opts, manifest):
    """Insert the manifest.json file."""

    tempf = os.path.join(opts.tmpdir, "manifest.json")

    # Note ordering to enable somewhat self-referential manifest
    manifest["sources"]["zapp/manifest.json"] = {"source": tempf, "hashes": []}

    with open(tempf, "w") as fp:
        fp.write(json.dumps(manifest))

    return manifest


def generate_dunder_main(opts, manifest):
    """Insert the __main__.py to the manifest."""

    if "__main__.py" in manifest["sources"]:
        print("Error: __main__.py conflict.", file=sys.stderr)
        exit(1)

    tempf = os.path.join(opts.tmpdir, "__main__.py")
    # Note ordering to enable somewhat self-referential manifest
    manifest["sources"]["__main__.py"] = {"source": tempf, "hashes": []}
    with open(tempf, "w") as fp:
        fp.write(make_dunder_main(manifest))

    return manifest


def enable_unzipping(opts, manifest):
    """Inject unzipping behavior as needed."""

    if manifest["wheels"]:
        manifest["prelude_points"].extend(
            [
                "zapp.support.unpack:unpack_deps",
                "zapp.support.unpack:install_deps",
            ]
        )

    if not manifest["zip_safe"]:
        manifest["prelude_points"].extend(
            [
                "zapp.support.unpack:unpack_zapp",
            ]
        )

    return manifest


def fix_sources(opts, manifest):
    manifest["sources"] = {f: m for f, m in manifest["sources"]}

    return manifest


def main():
    opts, args = parser.parse_known_args()

    with open(opts.manifest) as fp:
        manifest = json.load(fp)

    with TemporaryDirectory() as d:
        setattr(opts, "tmpdir", d)

        manifest = fix_sources(opts, manifest)
        if opts.use_wheels:
            manifest = rezip_wheels(opts, manifest)
        manifest = ensure_srcs_map(opts, manifest)
        manifest = enable_unzipping(opts, manifest)
        # Patch the manifest to insert needed __init__ files
        manifest = generate_dunder_inits(opts, manifest)
        manifest = generate_dunder_main(opts, manifest)
        # Generate and insert the manifest
        # NOTE: This has to be the LAST thing we do
        manifest = insert_manifest_json(opts, manifest)

        if opts.debug:
            print("\n---")
            json.dump(
                {
                    "$type": "zapp",
                    "opts": {
                        k: getattr(opts, k) for k in dir(opts) if not k.startswith("_")
                    },
                    "manifest": manifest,
                },
                sys.stdout,
                indent=2,
            )

        with open(opts.output, "w") as zapp:
            shebang = manifest["shebang"]
            if not shebang.endswith("\n"):
                shebang = shebang + "\n"
            if not shebang.startswith("#!"):
                shebang = "#!" + shebang
            zapp.write(shebang)

        # Now we're gonna build the zapp from the manifest
        with zipfile.ZipFile(opts.output, "a") as zapp:
            # Append user-specified sources
            for dest, src in sorted(manifest["sources"].items(), key=lambda x: x[0]):
                if src is None:
                    zapp.writestr(dest, "")
                else:
                    zapp.write(src["source"], dest)

            # Append user-specified libraries
            for whl, config in manifest["wheels"].items():
                zapp.write(config["source"], ".deps/" + whl)

        zapp = pathlib.Path(opts.output)
        zapp.chmod(zapp.stat().st_mode | stat.S_IEXEC)


if __name__ == "__main__" or 1:
    main()
