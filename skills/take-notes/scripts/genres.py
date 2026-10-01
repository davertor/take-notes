#!/usr/bin/env -S uv run --script
"""The genres a note can take, and the router that picks one.

A genre is the shape of a note's content — which sections it has — and it is
one Markdown file: a front-matter block the machine reads, then the contract
the agent reads. The three that ship live in `genres/`; a user adds their own
under `~/take-notes/genres/`, and one with the same name as a bundled genre
replaces it — copy `recipe.md` there and change its facts to have your own
recipe card.

    ---
    layout: offprint            # which template renders it; one of LAYOUTS
    label-en: meeting           # what the gallery card says
    label-es: reunión
    when: a meeting — an agenda, who was there, decisions and who owns them
    ---

`when` is the router row: one line saying what the source *is*. The agent
reads the table `--list` prints top to bottom and takes the first row that
fits, so the order is the precedence: user genres first, then the bundled
ones from the most specific to the catch-all, which is always the offprint.
A genre with no `when` is never picked by the router — it is used only when
asked for with `--genre`, which is the safe way to try a new one.

    uv run genres.py --list --lang es   # the router table, for Step 3
    uv run genres.py --selftest

The layouts are closed — a template is five hundred lines of CSS and JS with
an index, a scroll-spy and a print block, and the value of a user genre is in
its sections, not in a new stylesheet.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BUNDLED_DIR = Path(__file__).resolve().parent.parent / "genres"
USER_DIR = Path.home() / "take-notes" / "genres"

LAYOUTS = ("offprint", "fieldguide", "recipe")
DEFAULT = "offprint"
# Router precedence among the bundled genres: the specific ones first, the
# catch-all last. Every user genre goes before all of these.
BUNDLED_ORDER = ("recipe", "fieldguide", "offprint")

# A name lands in `data-genre="…"` and in a filename, so it is a slug.
NAME = re.compile(r"^[a-z][a-z0-9-]*$")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
LANGS = ("en", "es")


@dataclass(frozen=True)
class Genre:
    name: str
    layout: str
    label_en: str
    label_es: str
    when: str          # "" when the genre is on request only
    path: Path
    bundled: bool

    def label(self, lang: str) -> str:
        return self.label_es if lang == "es" else self.label_en


def parse_front_matter(text: str) -> dict[str, str]:
    """The flat `key: value` block at the top of a contract; `{}` without one.

    Flat on purpose — no YAML parser in the stdlib, and nothing here needs
    nesting. A value keeps everything after the first colon, trimmed.
    """
    match = FRONT_MATTER.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip():
            fields[key.strip()] = value.strip()
    return fields


def load(path: Path, bundled: bool) -> Genre:
    """One contract file as a Genre. Raises ValueError with the reason when
    the front-matter is missing or wrong; the caller decides whether that is
    fatal (a bundled genre) or a warning (a user's)."""
    name = path.stem
    if not NAME.match(name):
        raise ValueError(f"{path.name}: the name must be a slug like `paper-review`")
    fields = parse_front_matter(path.read_text(encoding="utf-8"))
    if not fields:
        raise ValueError(f"{path.name}: no front-matter block (---\\nlayout: …\\n---) at the top")
    layout = fields.get("layout", "")
    if layout not in LAYOUTS:
        raise ValueError(f"{path.name}: layout {layout!r} is not one of {', '.join(LAYOUTS)}")
    missing = [k for k in ("label-en", "label-es") if not fields.get(k)]
    if missing:
        raise ValueError(f"{path.name}: front-matter lacks {', '.join(missing)}")
    return Genre(
        name=name,
        layout=layout,
        label_en=fields["label-en"],
        label_es=fields["label-es"],
        when=fields.get("when", ""),
        path=path,
        bundled=bundled,
    )


@lru_cache(maxsize=None)
def installed(user_dir: Path = USER_DIR) -> tuple[Genre, ...]:
    """Every genre, in router order: the user's (by name), then the bundled
    ones in BUNDLED_ORDER. A user genre named like a bundled one takes its
    slot. A user file that fails to load is reported on stderr and skipped —
    a typo in one contract must never stop the gallery from building.

    Cached: the gallery asks once per card, and the answer is the same for the
    whole run.
    """
    bundled = {p.stem: load(p, bundled=True) for p in BUNDLED_DIR.glob("*.md")}
    for name in BUNDLED_ORDER:
        assert name in bundled, f"genres/{name}.md is missing"
    assert set(bundled) == set(BUNDLED_ORDER), (
        f"genres/ holds {sorted(bundled)} but BUNDLED_ORDER names {sorted(BUNDLED_ORDER)}"
    )

    user: dict[str, Genre] = {}
    for path in sorted(user_dir.glob("*.md")) if user_dir.is_dir() else []:
        try:
            user[path.stem] = load(path, bundled=False)
        except ValueError as error:
            print(f"genres: skipping {error}", file=sys.stderr)

    own = [g for name, g in sorted(user.items()) if name not in bundled]
    slots = [user.get(name) or bundled[name] for name in BUNDLED_ORDER]
    return (*own, *slots)


def resolve(name: str, user_dir: Path = USER_DIR) -> Genre | None:
    return next((g for g in installed(user_dir) if g.name == name), None)


def label(name: str, lang: str, user_dir: Path = USER_DIR) -> str:
    """What a card calls a genre — its label, or the bare name for a genre
    whose contract is no longer installed (the note outlives the file)."""
    genre = resolve(name, user_dir)
    return genre.label(lang) if genre else name


def router_table(genres: tuple[Genre, ...], lang: str = "en") -> str:
    """Step 3's table, as the agent reads it. Rows for the genres that
    declared a `when`, in precedence order; the rest listed as on request."""
    rows = [g for g in genres if g.when]
    lines = [
        "| The source is… | Genre | Contract |",
        "|---|---|---|",
        *(f"| {g.when} | `{g.name}` | `{g.path}` |" for g in rows),
    ]
    on_request = [g for g in genres if not g.when]
    if on_request:
        lines.append("")
        lines.append(
            "On request only (`--genre <name>`, never picked by the router): "
            + ", ".join(f"`{g.name}` ({g.label(lang)}, `{g.path}`)" for g in on_request)
        )
    return "\n".join(lines)


def _selftest() -> int:
    import tempfile

    # The bundled three: all routable, in precedence order, offprint last.
    shipped = installed()
    assert [g.name for g in shipped][-3:] == list(BUNDLED_ORDER), [g.name for g in shipped]
    assert all(g.when for g in shipped if g.bundled), "every bundled genre is routable"
    assert shipped[-1].name == DEFAULT, "the offprint is the catch-all, so it goes last"
    assert all(g.layout == g.name for g in shipped if g.bundled), (
        "a bundled genre is its own layout"
    )
    assert resolve("recipe").label("es") == "receta" and resolve("recipe").label("en") == "recipe"
    assert resolve("nonsense") is None
    assert label("nonsense", "en") == "nonsense", "a genre whose file is gone keeps its name"

    # Front-matter: flat, tolerant of spaces, keeps a colon inside a value.
    fields = parse_front_matter("---\nlayout: recipe\nwhen: a dish: with a colon\n---\n# x\n")
    assert fields == {"layout": "recipe", "when": "a dish: with a colon"}, fields
    assert parse_front_matter("# no block\n") == {}

    with tempfile.TemporaryDirectory() as tmp:
        user_dir = Path(tmp)
        (user_dir / "meeting.md").write_text(
            "---\nlayout: offprint\nlabel-en: meeting\nlabel-es: reunión\n"
            "when: a meeting — an agenda, decisions, owners\n---\n# Genre — meeting\n"
        )
        (user_dir / "tasting.md").write_text(
            "---\nlayout: fieldguide\nlabel-en: tasting\nlabel-es: cata\n---\n# Genre — tasting\n"
        )
        (user_dir / "recipe.md").write_text(
            "---\nlayout: recipe\nlabel-en: my recipe\nlabel-es: mi receta\n"
            "when: a dish, my way\n---\n# Genre — recipe, mine\n"
        )
        (user_dir / "broken.md").write_text("---\nlayout: nope\nlabel-en: x\nlabel-es: x\n---\n")
        (user_dir / "Bad Name.md").write_text("---\nlayout: offprint\n---\n")

        import io
        from contextlib import redirect_stderr

        err = io.StringIO()
        with redirect_stderr(err):
            found = installed(user_dir)
        names = [g.name for g in found]
        # User genres first, by name; the shadowing recipe sits in recipe's slot.
        assert names == ["meeting", "tasting", "recipe", "fieldguide", "offprint"], names
        assert resolve("recipe", user_dir).label_en == "my recipe", "the user's recipe shadows ours"
        assert resolve("recipe", user_dir).bundled is False
        assert resolve("meeting", user_dir).layout == "offprint"
        assert "skipping broken.md: layout 'nope'" in err.getvalue(), err.getvalue()
        assert "skipping Bad Name.md" in err.getvalue(), err.getvalue()
        assert "broken" not in names and "bad-name" not in names

        table = router_table(found, "es")
        assert table.index("| a meeting") < table.index("| a dish, my way") < table.index("| anything else")
        assert "`tasting`" not in table.split("On request")[0], "no `when` → not a router row"
        assert "On request only" in table and "`tasting` (cata," in table, table
        assert "`meeting`" in table and str(user_dir / "meeting.md") in table

        # A bundled contract that fails to load is a bug, not a warning.
        try:
            load(user_dir / "broken.md", bundled=True)
        except ValueError as error:
            assert "broken.md" in str(error)
        else:
            raise AssertionError("a broken contract must raise")

    print("selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--list", action="store_true", help="Print the router table (default)")
    ap.add_argument("--lang", default="en", help="en|es, for the labels (default: en)")
    ap.add_argument("--dir", default=None, help=f"User genres directory (default: {USER_DIR})")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    user_dir = Path(args.dir).expanduser() if args.dir else USER_DIR
    print(router_table(installed(user_dir), args.lang))
    return 0


if __name__ == "__main__":
    sys.exit(main())
