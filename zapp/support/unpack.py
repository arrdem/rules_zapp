"""Conditionally unpack a zapp (and its deps)."""

import sys
import os
from pathlib import Path
from zipfile import ZipFile

from .manifest import manifest


MANIFEST = manifest()


def cache_root() -> Path:
    return Path(os.path.join(os.path.expanduser("~"))) / ".cache" / "zapp"


def cache_wheel_root():
    return cache_root() / "wheels"


def cache_wheel_path(wheel: str) -> Path:
    return cache_wheel_root() / wheel


def cache_zapp_root():
    return cache_root() / "zapps"


def cache_zapp_path(fingerprint):
    return cache_zapp_root() / fingerprint


def unpack_deps():
    """Unpack deps, populating and updating the host's cache."""

    # Create the cache dir as needed
    cache_wheel_root().mkdir(parents=True, exist_ok=True)

    # For each wheel, touch the existing cached wheel or unpack this one.
    with ZipFile(sys.argv[0], "r") as zf:
        for whl, config in MANIFEST["wheels"].items():
            cached_whl = cache_wheel_path(whl)
            if cached_whl.exists():
                cached_whl.touch()

            else:
                with open(cached_whl, "wb") as of:
                    of.write(zf.read(".deps/" + whl))

            sys.path.insert(0, str(cached_whl))


def main():
    """Inspect the manifest."""

    unpack_deps()
