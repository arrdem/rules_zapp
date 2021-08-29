"""
The Zapp compiler.
"""

import argparse
import io
import json
import os
import pathlib
import stat
import sys
import zipfile
from email.parser import Parser
from shutil import move
from tempfile import TemporaryDirectory

from zapp.support.unpack import cache_wheel_path

parser = argparse.ArgumentParser(description="The (bootstrap) Zapp compiler")
parser.add_argument("-o", "--out", dest="output", help="Output target file")
parser.add_argument("-d", "--debug", dest="debug", action="store_true", default=False)
parser.add_argument("manifest", help="The (JSON) manifest")


MAIN_TEMPLATE = """\
# -*- coding: utf-8 -*-

\"\"\"Zapp-generated __main__\""\"

from importlib import import_module
import os
import sys
# FIXME: This is absolutely implementation details.
# Execing would be somewhat nicer
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


def dsub(d1, d2):
    """Dictionary subtraction. Remove k/vs from d1 if they occur in d2."""

    return {k: v for k, v in d1.items() if k not in d2 or d2[k] != v}


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


def load_wheel(opts, manifest, path):
    """Load a single wheel, returning ..."""

    def _parse_email(msg):
        return dict(Parser().parsestr(msg).items())

    # RECORD seems to just record file reference checksums for validation
    # with open(os.path.join(path, "RECORD")) as recordf:
    #     record = recordf.read()

    with open(os.path.join(path, "METADATA")) as metaf:
        meta = _parse_email(metaf.read())

    with open(os.path.join(path, "WHEEL")) as wheelf:
        wheel = _parse_email(wheelf.read())

    prefix = os.path.dirname(path)

    sources = {k: v for k, v in manifest["sources"].items() if v.startswith(prefix)}

    return {
        # "record": record,
        "meta": meta,
        "wheel": wheel,
        "sources": sources,
    }


def wheel_name(wheel):
    """Construct the "canonical" filename of the wheel."""

    tags = wheel["wheel"].get("Tag")
    if isinstance(tags, list):
        tags = "-" + ".".join(sorted(wheel["wheel"]["Tag"]))
    elif isinstance(tags, str):
        tags = "-" + wheel["wheel"]["Tag"]
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

    wheel_file = os.path.join(tmpdir, wheel_name(wheel))

    with zipfile.ZipFile(wheel_file, "w") as whl:
        for dest, src in wheel["sources"].items():
            whl.write(src, dest)

    return wheel_file


def rezip_wheels(opts, manifest):
    """Extract unzipped wheels from the manifest's inputs, simplifying the manifest.

    Wheels which are unzipped should be re-zipped into the cache, if not present in the cache.

    Files sourced from unzipped wheels should be removed, and a single wheel reference inserted."""

    wheels = [
        load_wheel(opts, manifest, os.path.dirname(p))
        for p in manifest["sources"].values()
        if p.endswith("/WHEEL")
    ]

    # Zip up the wheels and insert wheel records to the manifest
    for w in wheels:
        # Try to cheat and hit in the local cache first rather than building wheels every time
        wf = cache_wheel_path(wheel_name(w))
        if wf.exists():
            try:
                wf.touch()
            except OSError:
                pass
        else:
            wf = zip_wheel(opts.tmpdir, w)

        # Insert a new wheel source
        manifest["wheels"][wheel_name(w)] = {"hashes": [], "source": wf}

        # Expunge sources available in the wheel
        manifest["sources"] = dsub(manifest["sources"], w["sources"])

    return manifest


def generate_dunder_inits(manifest):
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

    manifest["sources"]["zapp/manifest.json"] = opts.manifest

    return manifest


def enable_unzipping(manifest):
    """Inject unzipping behavior as needed."""

    if manifest["wheels"]:
        manifest["prelude_points"].append("zapp.support.unpack:unpack_deps")

    # FIXME:
    # if not manifest["zip_safe"]:
    # enable a similar injection for unzipping

    return manifest


def main():
    opts, args = parser.parse_known_args()

    with open(opts.manifest) as fp:
        manifest = json.load(fp)

    with TemporaryDirectory() as d:
        setattr(opts, "tmpdir", d)

        manifest = rezip_wheels(opts, manifest)
        manifest = insert_manifest_json(opts, manifest)
        manifest = enable_unzipping(manifest)
        # Patch the manifest to insert needed __init__ files
        # NOTE: This has to be the LAST thing we do
        manifest = generate_dunder_inits(manifest)

        if opts.debug:
            from pprint import pprint

            pprint(
                {
                    "opts": {
                        k: getattr(opts, k) for k in dir(opts) if not k.startswith("_")
                    },
                    "manifest": manifest,
                }
            )

        with open(opts.output, "w") as zapp:
            shebang = "#!" + manifest["shebang"] + "\n"
            zapp.write(shebang)

        if "__main__.py" in manifest["sources"]:
            print("Error: __main__.py conflict.", file=sys.stderr)
            exit(1)

        # Now we're gonna build the zapp from the manifest
        with zipfile.ZipFile(opts.output, "a") as zapp:

            # Append the __main__.py generated record
            zapp.writestr("__main__.py", make_dunder_main(manifest))

            # Append user-specified sources
            for dest, src in sorted(manifest["sources"].items(), key=lambda x: x[0]):
                if src is None:
                    zapp.writestr(dest, "")
                else:
                    zapp.write(src, dest)

            # Append user-specified libraries
            for whl, config in manifest["wheels"].items():
                zapp.write(config["source"], ".deps/" + whl)

        zapp = pathlib.Path(opts.output)
        zapp.chmod(zapp.stat().st_mode | stat.S_IEXEC)


if __name__ == "__main__" or 1:
    main()
