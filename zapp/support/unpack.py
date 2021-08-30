"""Conditionally unpack a zapp (and its deps)."""

import os
import sys
from pathlib import Path
from tempfile import mkdtemp
from zipfile import ZipFile, is_zipfile

from zapp.support.manifest import manifest, once


@once
def cache_root() -> Path:
    """Find a root directory for cached behaviors."""

    shared_cache = Path(os.path.join(os.path.expanduser("~"))) / ".cache" / "zapp"

    # Happy path, read+write filesystem
    if os.access(shared_cache, os.X_OK | os.W_OK):
        return shared_cache

    # Unhappy path, we need a tempdir.
    # At least make one that's stable for the program's lifetime.
    else:
        return Path(os.getenv("ZAPP_TMPDIR") or mkdtemp(), "deps")


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

    if is_zipfile(sys.argv[0]):
        # Create the cache dir as needed
        cache_wheel_root().mkdir(parents=True, exist_ok=True)

        # For each wheel, touch the existing cached wheel or unpack this one.
        with ZipFile(sys.argv[0], "r") as zf:
            for whl, config in manifest()["wheels"].items():
                cached_whl = cache_wheel_path(whl)
                if cached_whl.exists():
                    cached_whl.touch()

                else:
                    with open(cached_whl, "wb") as of:
                        of.write(zf.read(".deps/" + whl))

    else:
        pass


def install_deps():
    """Validate that the PYTHONPATH has been configured correctly."""

    # FIXME: Can we reference the requirements, not specific PATH entries?
    for whl, config in manifest()["wheels"].items():
        cached_whl = cache_wheel_path(whl)
        if cached_whl.exists():
            cached_whl.touch()

        # Remove any references to the dep and shift the cached whl to the front
        p = str(cached_whl.resolve())
        try:
            sys.path.remove(p)
        except ValueError:
            pass
        sys.path.insert(0, p)


def canonicalize_path():
    """Fixup sys.path entries to use absolute paths. De-dupe in the same pass."""

    # Note that this HAS to be mutative/in-place
    shift = 0
    for i in range(len(sys.path)):
        idx = i - shift
        el = str(Path.resolve(sys.path[idx]))
        if el in sys.path:
            shift += 1
            sys.path.pop(idx)
        else:
            sys.path[idx] = el


def unpack_zapp():
    """Unzip a zapp (excluding the .deps/* tree) into a working directory.

    Note that unlike PEX, these directories are per-run which prevents local mutable state somewhat.

    """

    # Short circuit
    if is_zipfile(sys.argv[0]):
        # Extract
        tmpdir = mkdtemp()
        with ZipFile(sys.argv[0], "r") as zf:
            for src in manifest()["sources"].keys():
                ofp = Path(tmpdir, "usr", src)
                ofp.parent.mkdir(parents=True, exist_ok=True)
                with open(ofp, "wb") as of:
                    of.write(zf.read(src))

        # Re-exec the current interpreter
        args = [sys.executable, "--", os.path.join(tmpdir, "usr", "__main__.py")] + sys.argv[1:]
        os.execvpe(args[0], args[1:], {"PYTHONPATH": "", "ZAPP_TMPDIR": tmpdir})

    else:
        pass
