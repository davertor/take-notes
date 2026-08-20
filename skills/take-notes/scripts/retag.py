#!/usr/bin/env -S uv run --script
"""Re-file already-written notes under the current tag vocabulary.

Changing a note's tag used to mean re-running `/take-notes` on its source: a
refetch, a rewrite, and the tokens for both, to change one word in the rail.
This edits the rendered note in place instead.

The judgement stays with the skill — picking which tag fits a note needs the
note read, which is a model's job. This script is the mechanical half: it
lists what is on disk and writes back what it is told, so `--list` costs
nothing and `--set` costs nothing.

    uv run retag.py --list                      # every note, as JSON
    uv run retag.py --set NOTE.html --tag AI    # first --tag becomes primary

The tag row is a contract (see CONTRIBUTING.md): `.tags`, `.tag`, and
`.tag.is-primary` are what notes.py and the gallery's chips read back. The row
written here comes from render.tags_html, the same function the templates use,
so there is only one definition of that markup to keep correct.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notes import (  # noqa: E402
    DEFAULT_TAG, NOTES_DIR, TAG_ROW, collect, configured_tags, read,
)
from render import tags_html  # noqa: E402

# Where the row goes in a note that has never had one. Both templates put
# {{TAGS}} between the source link and the index, so a note written before
# tagging existed gets its row in the same place a fresh render would.
INDEX_ANCHOR = '<div id="index">'


def set_tags(doc: str, tags: list[str]) -> str:
    """`doc` with its tag row replaced, or inserted if it never had one.

    Raises ValueError when neither the row nor the index anchor is present:
    that means the file is not a note this tool understands, and writing a
    row into an arbitrary position would corrupt it silently.
    """
    row = tags_html(tags)
    if TAG_ROW.search(doc):
        return TAG_ROW.sub(lambda _: row, doc, count=1)
    if INDEX_ANCHOR in doc:
        return doc.replace(INDEX_ANCHOR, f"{row}\n    {INDEX_ANCHOR}", 1)
    raise ValueError("no tag row and no index anchor — not a rendered note")


def unknown_tags(tags: list[str], vocabulary: list[str]) -> list[str]:
    """The requested tags that the vocabulary does not contain, in order.

    The vocabulary is closed on purpose: the skill picks from the user's list
    and never invents a tag. A typo at the CLI would otherwise create a tag
    that exists on exactly one note and in no chip.
    """
    known = {name.casefold() for name in vocabulary}
    return [name for name in tags if name.casefold() not in known]


def listing(notes_dir: Path) -> list[dict]:
    """Every note with the fields needed to choose a tag for it."""
    return [
        {
            "path": str(note.path),
            "title": note.title,
            "byline": note.byline,
            "kind": note.kind,
            "date": note.date,
            "tags": list(note.tags),
            # Untagged and Unknown are the two states worth re-filing; a note
            # already carrying a real tag was filed deliberately.
            "needs_tag": not note.tags or list(note.tags) == [DEFAULT_TAG],
            "excerpt": note.excerpt,
        }
        for note in collect(notes_dir)
    ]


def _selftest() -> int:
    import render

    doc = render.build_article_document(
        "T", body="<h2>Executive summary</h2><p>x</p>", byline="B",
        span="s", url="https://x.test", tags=["AI"], today="2026-01-01",
    )
    assert '<span class="tag is-primary">AI</span>' in doc

    moved = set_tags(doc, ["Engineering", "AI"])
    assert '<span class="tag is-primary">Engineering</span>' in moved
    assert '<span class="tag">AI</span>' in moved
    assert moved.count('<p class="tags">') == 1, "replacing a row must not add a second"

    from notes import parse_tags
    assert parse_tags(moved) == ("Engineering", ("Engineering", "AI")), parse_tags(moved)

    # A note written before tagging existed has no row at all.
    bare = doc.replace(TAG_ROW.search(doc).group(0), "")
    assert '<p class="tags">' not in bare
    filled = set_tags(bare, ["AI"])
    assert parse_tags(filled) == ("AI", ("AI",)), "a row is inserted, not just replaced"
    assert filled.index('<p class="tags">') < filled.index(INDEX_ANCHOR), "row goes above the index"

    # Idempotent: setting the same tags twice changes nothing further.
    assert set_tags(filled, ["AI"]) == filled

    try:
        set_tags("<html><body>not a note</body></html>", ["AI"])
    except ValueError:
        pass
    else:                                    # pragma: no cover
        raise AssertionError("a non-note must raise rather than be written to")

    assert unknown_tags(["AI", "Nope"], ["Unknown", "AI"]) == ["Nope"]
    assert unknown_tags(["ai"], ["Unknown", "AI"]) == [], "vocabulary match is case-insensitive"

    print("selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="retag",
        description="List rendered notes, or set the tags on one of them.",
    )
    ap.add_argument("--list", action="store_true", help="Print every note as JSON and exit")
    ap.add_argument("--set", metavar="NOTE", help="Path of the note to write tags to")
    ap.add_argument("--tag", action="append", default=[], metavar="TAG",
                    help="Tag to write (repeatable; the first becomes primary)")
    ap.add_argument("--notes-dir", type=Path, default=NOTES_DIR,
                    help=f"Where the notes live (default: {NOTES_DIR})")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    if args.list:
        print(json.dumps(listing(args.notes_dir), ensure_ascii=False, indent=2))
        return 0

    if not args.set:
        ap.error("nothing to do: pass --list or --set NOTE --tag TAG")
    if not args.tag:
        ap.error("--set needs at least one --tag")

    unknown = unknown_tags(args.tag, configured_tags())
    if unknown:
        print(
            f"retag: not in the vocabulary: {', '.join(unknown)}\n"
            f"       add it first with: tags.py --add {unknown[0]!r}",
            file=sys.stderr,
        )
        return 1

    path = Path(args.set)
    pair = read(path)
    if pair is None:
        print(f"retag: cannot read {path}", file=sys.stderr)
        return 1

    try:
        updated = set_tags(pair[1], args.tag)
    except ValueError as exc:
        print(f"retag: {path}: {exc}", file=sys.stderr)
        return 1

    path.write_text(updated, encoding="utf-8")
    print(f"{path.name}: {' · '.join(args.tag)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
