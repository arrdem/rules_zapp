"""
The Zapp compiler.
"""

import argparse
import io
import json
import os
import sys
import zipfile
import pathlib
import stat

parser = argparse.ArgumentParser(description="The (bootstrap) Zapp compiler")
parser.add_argument("-o", "--out", dest="output", help="Output target file")
parser.add_argument("-d", "--debug", dest="debug", action="store_true", default=False)
parser.add_argument("manifest", help="The (JSON) manifest")


MAIN_TEMPLATE = """\
# -*- coding: utf-8 -*-

\"\"\"Zapp-generated __main__\""\"

from importlib import import_module
# FIXME: This is absolutely implementation details.
# Execing would be somewhat nicer
from runpy import _run_module_as_main

for script in {scripts!r}:
    print(script)
    mod, sep, fn = script.partition(':')
    mod_ok = all(part.isidentifier() for part in mod.split('.'))
    fn_ok = all(part.isidentifier() for part in fn.split('.'))

    if not mod_ok:
        raise RuntimeError("Invalid module reference {{!r}}".format(mod))
    if fn and not fn_ok:
        raise RuntimeError("Invalid function reference {{!r}}".format(fn))

    if mod and fn and False:
        mod = import_module(mod)
        getattr(mod, fn)()
    else:
        _run_module_as_main(mod)
"""


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


def generate_dunder_inits(manifest):
    """Hack the manifest to insert __init__ files as needed."""

    sources = manifest["sources"]

    for input_file in list(sources.keys()):
        for path in dir_walk_prefixes(os.path.dirname(input_file)):
            init_file = os.path.join(path, "__init__.py")
            if init_file not in sources:
                sources[init_file] = ""

    return manifest


def generate_manifest(opts, manifest):
    """Insert the manifest.json file."""

    manifest["sources"]["zapp/manifest.json"] = opts.manifest

    return manifest


def main():
    opts, args = parser.parse_known_args()

    with open(opts.manifest) as fp:
        manifest = json.load(fp)

    manifest = generate_manifest(opts, manifest)
    # Patch the manifest to insert needed __init__ files
    # NOTE: This has to be the LAST thing we do
    manifest = generate_dunder_inits(manifest)

    if opts.debug:
        from pprint import pprint
        pprint({
            "opts": {k: getattr(opts, k) for k in dir(opts) if not k.startswith("_")},
            "manifest": manifest
        })

    with open(opts.output, 'w') as zapp:
        shebang = "#!" + manifest["shebang"] + "\n"
        zapp.write(shebang)

    # Now we're gonna build the zapp from the manifest
    with zipfile.ZipFile(opts.output, 'a') as zapp:

        # Append the __main__.py generated record
        zapp.writestr("__main__.py", make_dunder_main(manifest))

        # Append user-specified sources
        for dest, src in manifest["sources"].items():
            if src == "":
                zapp.writestr(dest, "")
            else:
                zapp.write(src, dest)

        # Append user-specified libraries
        # FIXME

    zapp = pathlib.Path(opts.output)
    zapp.chmod(zapp.stat().st_mode | stat.S_IEXEC)


if __name__ == "__main__" or 1:
    main()
