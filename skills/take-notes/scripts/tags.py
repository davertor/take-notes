#!/usr/bin/env -S uv run --script
"""Curate the tag vocabulary in ~/take-notes/config.json.

The vocabulary is closed and manual: the note-writing skill picks a tag from
this list and never invents one, so the taxonomy stays yours rather than
whatever the model felt like that day. `Unknown` is always in it — the escape
hatch for a source nothing else fits — and cannot be removed.

    uv run tags.py                           # list the vocabulary
    uv run tags.py --add AI --add Investing  # add (repeatable)
    uv run tags.py --remove Investing        # remove (repeatable)

Read-modify-write: every other key in the config, `language` above all, is
carried through untouched.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notes import CONFIG_FILE, DEFAULT_TAG, configured_tags, read_config  # noqa: E402


def apply(config: dict, add: list[str] | None = None, remove: list[str] | None = None) -> dict:
    """A copy of `config` with the vocabulary updated — never mutated in place.

    Adds are stripped, deduped case-insensitively against what is already
    there, and appended in the order given. Removing DEFAULT_TAG is a no-op:
    the skill has to have something to fall back to.
    """
    vocabulary = configured_tags(config)
    known = {tag.casefold() for tag in vocabulary}
    for raw in add or []:
        name = raw.strip()
        if name and name.casefold() not in known:
            known.add(name.casefold())
            vocabulary = [*vocabulary, name]
    drop = {raw.strip().casefold() for raw in remove or []} - {DEFAULT_TAG.casefold()}
    return {**config, "tags": [tag for tag in vocabulary if tag.casefold() not in drop]}


def write(config: dict, path: Path | None = None) -> None:
    """Write the config back, pretty-printed so it stays hand-editable."""
    target = path or CONFIG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _selftest() -> int:
    path = Path("/tmp/take-notes/config-selftest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"language": "es"}\n', encoding="utf-8")

    write(apply(read_config(path), add=["AI", "Investing"]), path)
    config = read_config(path)
    assert config["language"] == "es", "the language key survives a tag edit"
    assert config["tags"] == [DEFAULT_TAG, "AI", "Investing"], config["tags"]

    # Dedupe is case-insensitive, and empties are dropped rather than stored.
    write(apply(read_config(path), add=["ai", "  ", "Engineering"]), path)
    assert read_config(path)["tags"] == [DEFAULT_TAG, "AI", "Investing", "Engineering"]

    write(apply(read_config(path), remove=["investing"]), path)
    assert read_config(path)["tags"] == [DEFAULT_TAG, "AI", "Engineering"]

    write(apply(read_config(path), remove=[DEFAULT_TAG.lower()]), path)
    assert read_config(path)["tags"][0] == DEFAULT_TAG, "the fallback tag cannot be removed"
    assert read_config(path)["language"] == "es"

    # A missing or malformed config is a starting point, not a failure.
    missing = Path("/tmp/take-notes/config-absent.json")
    missing.unlink(missing_ok=True)
    assert apply(read_config(missing), add=["AI"])["tags"] == [DEFAULT_TAG, "AI"]

    path.write_text("{ not json", encoding="utf-8")
    assert apply(read_config(path), add=["AI"])["tags"] == [DEFAULT_TAG, "AI"]

    path.unlink(missing_ok=True)
    print("selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="tags",
        description=f"List or edit the tag vocabulary in {CONFIG_FILE}.",
    )
    ap.add_argument("--add", action="append", default=[], metavar="TAG", help="Add a tag (repeatable)")
    ap.add_argument("--remove", action="append", default=[], metavar="TAG", help="Remove a tag (repeatable)")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    config = read_config()
    if args.add or args.remove:
        if any(raw.strip().casefold() == DEFAULT_TAG.casefold() for raw in args.remove):
            print(f"tags: {DEFAULT_TAG} is the fallback tag and cannot be removed", file=sys.stderr)
        config = apply(config, args.add, args.remove)
        write(config)

    print("\n".join(configured_tags(config)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
