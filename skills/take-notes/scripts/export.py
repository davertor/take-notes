#!/usr/bin/env -S uv run --script
"""Export the note archive to Markdown or Anki flashcards.

The notes are the source of truth; this only converts. Two formats, because
they answer two different questions:

    uv run export.py --format md     # one .md per note, for Obsidian / Notion
    uv run export.py --format anki   # one .txt of cards, for spaced repetition

Markdown gets the whole note. Anki gets only the parts SKILL.md writes as
`<li><strong>term</strong> — definition</li>` — Key points and Concepts — plus
the takeaway, because those are the only sections shaped like a question with
an answer. Everything else in a note is prose that makes a terrible flashcard.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notes import (  # noqa: E402
    NOTES_DIR, Note, collect, find_section, list_pairs, parse_note, parse_sections, read, section,
    text_of,
)


DEFAULT_MD_DIR = Path.home() / "take-notes" / "markdown"
DEFAULT_ANKI_FILE = Path.home() / "take-notes" / "take-notes.txt"

ANKI_DECK = "take-notes"


# --- Markdown ---------------------------------------------------------------
# SKILL.md's "Keep the HTML plain" rule fixes the tag vocabulary a note may
# use, so this converter only has to handle that closed set — which is why it
# stays a few regexes rather than a parser or a dependency.

def _inline(fragment: str) -> str:
    """Inline HTML to Markdown: links, emphasis, code."""
    out = fragment
    out = re.sub(r'<a [^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", out, flags=re.DOTALL)
    out = re.sub(r"<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>", r"**\1**", out, flags=re.DOTALL)
    out = re.sub(r"<(?:em|i)[^>]*>(.*?)</(?:em|i)>", r"*\1*", out, flags=re.DOTALL)
    out = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", out, flags=re.DOTALL)
    out = re.sub(r"<br\s*/?>", "  \n", out)
    out = re.sub(r"<[^>]+>", "", out)
    return re.sub(r"[ \t]+", " ", html.unescape(out)).strip()


def _block(fragment: str) -> str:
    """One section's inner HTML to Markdown blocks."""
    blocks: list[str] = []
    # <pre><code> first: its contents must not be touched by the inline rules.
    for chunk in re.split(r"(<pre[^>]*>.*?</pre>|<figure[^>]*>.*?</figure>|<blockquote[^>]*>.*?</blockquote>|<[uo]l[^>]*>.*?</[uo]l>|<h3[^>]*>.*?</h3>|<p[^>]*>.*?</p>)",
                          fragment, flags=re.DOTALL):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("<pre"):
            code = re.sub(r"</?(?:pre|code)[^>]*>", "", chunk)
            blocks.append("```\n" + html.unescape(code).strip("\n") + "\n```")
        elif chunk.startswith("<figure"):
            src = re.search(r'<img[^>]*src="([^"]*)"', chunk)
            alt = re.search(r'<img[^>]*alt="([^"]*)"', chunk)
            caption = re.search(r"<figcaption[^>]*>(.*?)</figcaption>", chunk, re.DOTALL)
            if src:
                blocks.append(f"![{html.unescape(alt.group(1)) if alt else ''}]({html.unescape(src.group(1))})")
            if caption:
                blocks.append(f"*{_inline(caption.group(1))}*")
        elif chunk.startswith("<blockquote"):
            inner = re.sub(r"</?blockquote[^>]*>", "", chunk)
            text = "\n".join(_inline(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", inner, re.DOTALL)) or _inline(inner)
            blocks.append("\n".join(f"> {line}" for line in text.splitlines() if line))
        elif chunk.startswith("<ul") or chunk.startswith("<ol"):
            ordered = chunk.startswith("<ol")
            items = re.findall(r"<li[^>]*>(.*?)</li>", chunk, re.DOTALL)
            blocks.append("\n".join(
                f"{i + 1}. {_inline(it)}" if ordered else f"- {_inline(it)}"
                for i, it in enumerate(items)
            ))
        elif chunk.startswith("<h3"):
            blocks.append("### " + _inline(chunk))
        elif chunk.startswith("<p"):
            blocks.append(_inline(chunk))
        else:  # a table, or anything unexpected — keep the text, lose the tags
            text = _inline(chunk)
            if text:
                blocks.append(text)
    return "\n\n".join(b for b in blocks if b)


def _yaml(value: str) -> str:
    """Quote a frontmatter scalar. Titles routinely contain `:` and `"`."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_markdown(note: Note, doc: str) -> str:
    """A note as one Markdown file with YAML frontmatter."""
    front = [
        "---",
        f"title: {_yaml(note.title)}",
        f"source: {_yaml(note.source)}",
        f"byline: {_yaml(note.byline)}",
        f"date: {note.date or ''}",
        f"kind: {note.kind}",
        "tags: [take-notes]",
        "---",
        "",
        f"# {note.title}",
    ]
    if note.detail:
        front.append("")
        front.append(f"*{note.detail}*")

    body = [f"## {heading}\n\n{md}" for heading, inner in parse_sections(doc) if (md := _block(inner))]
    return "\n".join(front) + "\n\n" + "\n\n".join(body) + "\n"


# --- Anki -------------------------------------------------------------------
# Format per docs.ankiweb.net/importing/text-files.html: UTF-8, `#key:value`
# header lines, one note per line, fields separated by the declared separator.

def _card_field(text: str) -> str:
    """A field is one line: tabs and newlines would end it early."""
    return re.sub(r"\s+", " ", text).strip()


def to_cards(note: Note, doc: str) -> list[tuple[str, str, str]]:
    """(front, back, tags) triples for one note, or [] when it has none."""
    cards: list[tuple[str, str, str]] = []
    tag = "take-notes"

    # The note's own heading, not a hardcoded English label: a Spanish note
    # must not grow an English card front.
    heading, takeaway_html = find_section(doc, "takeaway")
    takeaway = text_of(takeaway_html)
    if takeaway:
        cards.append((f"{note.title} — {heading}", takeaway, f"{tag} takeaway"))

    for kind, label in (("key_points", "key-point"), ("concepts", "concept")):
        for term, definition in list_pairs(section(doc, kind)):
            if definition:  # a term with no definition makes an unanswerable card
                cards.append((term, definition, f"{tag} {label}"))

    return [(_card_field(f), _card_field(b), t) for f, b, t in cards]


def anki_file(rows: list[tuple[str, str, str]], deck: str = ANKI_DECK) -> str:
    header = [
        "#separator:Tab",
        "#html:true",
        f"#deck:{deck}",
        "#columns:Front\tBack\tTags",
    ]
    lines = ["\t".join((front, back, tags)) for front, back, tags in rows]
    return "\n".join(header + lines) + "\n"


# --- Driver -----------------------------------------------------------------

def export_markdown(notes: list[Note], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for note in notes:
        pair = read(note.path)
        if not pair:
            continue
        (out_dir / f"{note.path.stem}.md").write_text(to_markdown(*pair), encoding="utf-8")
        written += 1
    return written


def export_anki(notes: list[Note], out_file: Path, deck: str = ANKI_DECK) -> int:
    rows: list[tuple[str, str, str]] = []
    for note in notes:
        pair = read(note.path)
        if pair:
            rows.extend(to_cards(*pair))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(anki_file(rows, deck), encoding="utf-8")
    return len(rows)


def _selftest() -> int:
    import render

    notes_dir = Path("/tmp/take-notes/html_reports")
    doc = render.build_article_document(
        "Cache: the hard part",
        "<h2>Executive summary</h2><p>An <em>argument</em> about "
        '<a href="https://x.test/?a=1&amp;b=2">invalidation</a> &amp; naming.</p>'
        "<h2>The one takeaway</h2><p><strong>Name the owner of the moment a value stops being true.</strong></p>"
        "<h2>Key points</h2><ul>"
        "<li><strong>Ownership is the bug</strong> — nobody owns expiry</li>"
        "<li><strong>Bare claim</strong></li></ul>"
        "<h2>How it works</h2><ol><li>First step</li><li>Second step</li></ol>"
        "<pre><code>x &lt;- 1\nif x &gt; 0: pass</code></pre>"
        "<blockquote><p>Quoted line.</p></blockquote>"
        "<h2>Concepts</h2><ul><li><strong>TTL</strong> — time to live</li></ul>",
        byline="Postmortem Weekly", span="Aug 15, 2026", url="https://x.test/?a=1&b=2",
        today="2026-01-01",
    )
    note = parse_note(notes_dir / "2026-08-16-cache.html", doc)

    md = to_markdown(note, doc)
    assert md.startswith("---\n"), "frontmatter first"
    assert 'title: "Cache: the hard part"' in md, "a colon in a title must stay quoted"
    assert 'source: "https://x.test/?a=1&b=2"' in md, "URL entities decoded once, not twice"
    assert "date: 2026-08-16" in md
    assert "## Key points" in md and "## How it works" in md
    assert "- **Ownership is the bug** — nobody owns expiry" in md, md
    assert "1. First step" in md and "2. Second step" in md, "ordered lists keep their numbers"
    assert "[invalidation](https://x.test/?a=1&b=2)" in md, "links convert"
    assert "*argument*" in md, "emphasis converts"
    assert "```\nx <- 1\nif x > 0: pass\n```" in md, "code fences keep raw text"
    assert "> Quoted line." in md
    assert "<" not in md.replace("x <- 1", ""), "no HTML tags survive into Markdown"

    cards = to_cards(note, doc)
    fronts = [c[0] for c in cards]
    assert fronts[0] == "Cache: the hard part — The one takeaway", fronts[0]
    assert "Name the owner" in cards[0][1]
    assert ("Ownership is the bug", "nobody owns expiry", "take-notes key-point") in cards
    assert ("TTL", "time to live", "take-notes concept") in cards
    assert "Bare claim" not in fronts, "a term with no definition is not a card"

    text = anki_file(cards)
    assert text.startswith("#separator:Tab\n#html:true\n#deck:take-notes\n#columns:Front\tBack\tTags\n")
    body = text.splitlines()[4:]
    assert all(line.count("\t") == 2 for line in body), "exactly three fields per row"
    assert not any("\n" in line for line in body)

    # A note with no card-shaped sections yields a valid, header-only file.
    thin = render.build_article_document(
        "Thin", "<h2>Executive summary</h2><p>only prose</p>",
        byline="S", url="https://x.test", today="2026-01-01",
    )
    thin_note = parse_note(notes_dir / "2026-01-01-thin.html", thin)
    assert to_cards(thin_note, thin) == []
    assert anki_file([]).endswith("#columns:Front\tBack\tTags\n")

    # Spanish sections are found by the same code.
    es = render.build_article_document(
        "Español",
        "<h2>Resumen</h2><p>hola</p>"
        "<h2>Puntos clave</h2><ul><li><strong>Afirmación</strong> — el detalle</li></ul>",
        byline="S", url="https://x.test", lang="es", today="2026-01-01",
    )
    es_note = parse_note(notes_dir / "2026-01-01-es.html", es)
    assert ("Afirmación", "el detalle", "take-notes key-point") in to_cards(es_note, es)

    es_takeaway = render.build_article_document(
        "Español",
        "<h2>Resumen</h2><p>hola</p><h2>La idea clave</h2><p><strong>Lo esencial.</strong></p>",
        byline="S", url="https://x.test", lang="es", today="2026-01-01",
    )
    es_t = parse_note(notes_dir / "2026-01-01-es2.html", es_takeaway)
    assert to_cards(es_t, es_takeaway)[0][0] == "Español — La idea clave", (
        "the takeaway card reuses the note's own heading, never an English one"
    )

    print("selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="export",
        description="Export the note archive to Markdown (Obsidian, Notion) or Anki cards.",
    )
    ap.add_argument("--format", choices=("md", "anki"), help="Output format")
    ap.add_argument("--notes-dir", default=None, help=f"Where the notes live (default: {NOTES_DIR})")
    ap.add_argument("--out", default=None, help="Output dir (md) or file (anki)")
    ap.add_argument("--deck", default=ANKI_DECK, help=f"Anki deck name (default: {ANKI_DECK})")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.format:
        ap.error("--format is required (md or anki)")

    notes_dir = Path(args.notes_dir).expanduser() if args.notes_dir else NOTES_DIR
    if not notes_dir.is_dir():
        print(f"export: no notes directory at {notes_dir}", file=sys.stderr)
        return 1

    notes = collect(notes_dir)
    if not notes:
        print(f"export: no notes in {notes_dir}", file=sys.stderr)
        return 1

    if args.format == "md":
        out = Path(args.out).expanduser() if args.out else DEFAULT_MD_DIR
        count = export_markdown(notes, out)
        print(f"export: {count} note(s) -> {out}")
    else:
        out = Path(args.out).expanduser() if args.out else DEFAULT_ANKI_FILE
        count = export_anki(notes, out, args.deck)
        print(f"export: {count} card(s) from {len(notes)} note(s) -> {out}")
        print("  import in Anki: File > Import, keep 'Allow HTML in fields' on")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
