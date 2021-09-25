"""An implementation of PEP-425 tag parsing, expansion and compression."""

import typing as t


class Tag(t.NamedTuple):
    python: str
    abi: str
    arch: str  # 'Platform' in the PEP


def decompress_tag(tag: str) -> t.Iterable[Tag]:
    """Decompress tag string into a sequence of compatible tuples."""

    pytags, abitags, archtags = tag.split("-", 2)
    for x in pytags.split("."):
        for y in abitags.split("."):
            for z in archtags.split("."):
                yield Tag(x, y, z)


def compress_tags(tags: t.Iterable[Tag]) -> str:
    """Compress a tag sequence into a string encoding compatible tuples."""

    tags = set(tags)
    pytags = set(t.python for t in tags)
    abitags = set(t.abi for t in tags)
    archtags = set(t.arch for t in tags)

    tag = "-".join(
        [
            ".".join(sorted(pytags)),
            ".".join(sorted(abitags)),
            ".".join(sorted(archtags)),
        ]
    )
    assert set(decompress_tag(tag)) == tags
    return tag
