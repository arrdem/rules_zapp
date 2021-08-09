"""The Zapp runtime manifest API."""

from copy import deepcopy
from importlib.resources import open_text
import json

with open_text("zapp", "manifest.json") as fp:
    _MANIFEST = json.load(fp)


def manifest():
    """Return (a copy) of the runtime manifest."""

    return deepcopy(_MANIFEST)


__all__ = ["manifest"]
