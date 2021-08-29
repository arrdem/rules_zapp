"""The Zapp runtime manifest API."""

import json
from copy import deepcopy
from importlib.resources import open_text


def once(f):
    singleton = object()
    state = singleton

    def helper(*args, **kwargs):
        nonlocal state
        if state is singleton:
            state = f(*args, **kwargs)
        return state

    return helper


def copied(f):
    def helper(*args, **kwargs):
        val = f(*args, **kwargs)
        return deepcopy(val)

    return helper


@copied
@once
def manifest():
    """Return (a copy) of the runtime manifest."""

    with open_text("zapp", "manifest.json") as fp:
        return json.load(fp)


__all__ = ["manifest"]
