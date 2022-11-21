"""The Zapp runtime manifest API."""

import argparse
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


PARSER = argparse.ArgumentParser()
PARSER.add_argument("--json", action="store_const", const="json", dest="format", default="json")
PARSER.add_argument("--requirements", action="store_const", const="requirements", dest="format")


if __name__ == "__main__":
    opts, args = PARSER.parse_known_args()

    if opts.format == "json":
        print(json.dumps(manifest()))

    elif opts.format == "requirements":
        for req, rev in manifest()["requirements"].items():
            print("{}=={}".format(req, rev))


__all__ = ["manifest"]
