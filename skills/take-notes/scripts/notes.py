#!/usr/bin/env -S uv run --script
"""Read rendered notes back out of ~/take-notes/html_reports.

The one place that knows how to parse a note. Nothing here writes anything —
`gallery.py` lays these out as cards, `export.py` converts them to Markdown and
flashcards, and both read through this module so the scraping rules live once.

A note is its own database: the masthead classes (`.poster`, `.kicker`,
`.meta`, `.watch`, `.tag`) and the flat `<h2>`-delimited body are the contract
with assets/template.html, assets/article-template.html, and SKILL.md's
"Keep the HTML plain" rule. Break one and this module's --selftest fails,
which is the point.

It also owns `~/take-notes/config.json`, the one file the user edits by hand:
the note language and the manual tag vocabulary. One reader, so gallery.py and
tags.py cannot disagree about what a malformed config means.
"""
from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


NOTES_DIR = Path.home() / "take-notes" / "html_reports"
CONFIG_FILE = Path.home() / "take-notes" / "config.json"

EXCERPT_CHARS = 190

# The tag every note falls back to. The vocabulary is curated by hand, so the
# agent needs an escape hatch it can always reach for without inventing one.
DEFAULT_TAG = "Unknown"

DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
TAGS = re.compile(r"<[^>]+>")
TAG_ROW = re.compile(r'<p class="tags">(.*?)</p>', re.DOTALL)
TAG_SPAN = re.compile(r'<span class="tag([^"]*)">(.*?)</span>', re.DOTALL)

# Section headings, both languages. SKILL.md fixes the English names and their
# Spanish equivalents; matching on words rather than exact strings keeps a note
# readable even when the agent titled a section slightly differently.
SECTION_WORDS = {
    "takeaway": r"\b(takeaway|conclusion|conclusi[oó]n|idea clave|lo esencial)\b",
    "key_points": r"\b(key points|puntos clave|claves)\b",
    "concepts": r"\b(concepts|conceptos|glosario|glossary)\b",
    "outline": r"\b(outline|contents|esquema|guion|gui[oó]n|indice|[ií]ndice|contenido)\b",
}


@dataclass(frozen=True)
class Note:
    """One rendered note, as much of it as a reader of the archive needs."""

    path: Path
    title: str
    byline: str
    detail: str
    excerpt: str
    thumbnail: str
    source: str
    date: str
    kind: str  # "video" | "article"
    tag: str = ""                     # primary tag, the one a card shows
    tags: tuple[str, ...] = ()        # every tag, primary first


def read_config(path: Path | None = None) -> dict:
    """`~/take-notes/config.json` as a dict; `{}` when absent or malformed.

    Tolerant on purpose: a hand-edited file with a stray comma must never stop
    a note from being written. Every caller has a working default.
    """
    try:
        value = json.loads((path or CONFIG_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def configured_tags(config: dict | None = None) -> list[str]:
    """The manual tag vocabulary, with DEFAULT_TAG guaranteed first.

    Closed by design — the note-writing skill picks from this list and never
    invents a tag, so the taxonomy stays the user's rather than the model's.
    """
    raw = (read_config() if config is None else config).get("tags")
    names = [t.strip() for t in raw if isinstance(t, str) and t.strip()] if isinstance(raw, list) else []
    seen = {DEFAULT_TAG.casefold()}
    vocabulary = [DEFAULT_TAG]
    for name in names:
        if name.casefold() not in seen:
            seen.add(name.casefold())
            vocabulary.append(name)
    return vocabulary


def text_of(fragment: str) -> str:
    """Inner HTML to plain collapsed text."""
    return re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", fragment))).strip()


def fold(text: str) -> str:
    """Lowercase and strip accents, exactly as the gallery template's filter JS
    does — the two must agree or typing "andres" misses "Andrés"."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def length_of(detail: str) -> str:
    """The one scannable number in a meta line: "11 min", "6 min read", "1 h 15 min"."""
    for part in (p.strip() for p in detail.split("·")):
        if re.search(r"\d+\s*(min|h)\b", part):
            return part
    return ""


def find(pattern: str, doc: str) -> str:
    match = re.search(pattern, doc, re.DOTALL)
    return match.group(1) if match else ""


def attr(pattern: str, doc: str) -> str:
    """Attribute value, decoded — a note's URLs carry `&amp;` in the file and
    would be double-escaped when written back out."""
    return html.unescape(find(pattern, doc))


def body_html(doc: str) -> str:
    """Everything between <article id="body"> and </article>."""
    return find(r'<article id="body">(.*?)</article>', doc)


def parse_sections(doc: str) -> list[tuple[str, str]]:
    """The note body as (heading, inner HTML) pairs, in document order.

    The body is a flat run of <h2>-delimited prose — SKILL.md's plain-HTML
    contract — so splitting on <h2> is the whole job. This mirrors what the
    note templates' own JS does at runtime to build sections; doing it in
    Python here means exporters see the same structure a reader does.
    """
    body = body_html(doc)
    if not body:
        return []
    parts = re.split(r"<h2[^>]*>(.*?)</h2>", body, flags=re.DOTALL)
    # re.split with one group yields [before, heading, chunk, heading, chunk...].
    return [
        (text_of(parts[i]), parts[i + 1].strip())
        for i in range(1, len(parts) - 1, 2)
    ]


def find_section(doc: str, kind: str) -> tuple[str, str]:
    """(heading, inner HTML) of the first section whose heading matches `kind`.

    The heading comes back as the note wrote it, so callers can reuse the
    note's own wording instead of hardcoding an English label onto a Spanish
    note.
    """
    pattern = SECTION_WORDS[kind]
    for heading, inner in parse_sections(doc):
        if re.search(pattern, heading, re.IGNORECASE):
            return heading, inner
    return "", ""


def section(doc: str, kind: str) -> str:
    """The inner HTML of the first section whose heading matches `kind`."""
    return find_section(doc, kind)[1]


def list_pairs(fragment: str) -> list[tuple[str, str]]:
    """`<li><strong>term</strong> — definition</li>` items as (term, definition).

    The shape SKILL.md mandates for Key points and Concepts alike. An item with
    no <strong> is returned whole as the term with an empty definition rather
    than dropped — a malformed bullet is still information.
    """
    pairs: list[tuple[str, str]] = []
    for item in re.findall(r"<li[^>]*>(.*?)</li>", fragment, re.DOTALL):
        match = re.search(r"<strong[^>]*>(.*?)</strong>(.*)", item, re.DOTALL)
        if not match:
            whole = text_of(item)
            if whole:
                pairs.append((whole, ""))
            continue
        term = text_of(match.group(1))
        rest = text_of(match.group(2))
        # Strip the em dash SKILL.md puts between the two halves.
        rest = re.sub(r"^[—–-]\s*", "", rest).strip()
        if term:
            pairs.append((term, rest))
    return pairs


def excerpt_of(doc: str) -> str:
    """First paragraph of the note body, trimmed on a word boundary."""
    text = text_of(find(r"<p[^>]*>(.*?)</p>", body_html(doc)))
    if len(text) <= EXCERPT_CHARS:
        return text
    cut = text[:EXCERPT_CHARS]
    head, _, _ = cut.rpartition(" ")
    return (head or cut).rstrip(",;:.—- ") + "…"


def parse_tags(doc: str) -> tuple[str, tuple[str, ...]]:
    """The rail's tag row as (primary, all tags with primary first).

    The primary is the span carrying `is-primary`, falling back to document
    order. A note written before tags existed has no row at all and comes back
    as ("", ()) rather than a guessed tag — the gallery decides what an
    untagged note is filed under, not the parser.
    """
    row = TAG_ROW.search(doc)
    if not row:
        return "", ()
    found = [(cls, text_of(inner)) for cls, inner in TAG_SPAN.findall(row.group(1))]
    names = [name for _, name in found if name]
    if not names:
        return "", ()
    primary = next((name for cls, name in found if "is-primary" in cls and name), names[0])
    return primary, (primary, *[n for n in names if n != primary])


def parse_note(path: Path, doc: str) -> Note:
    """Pull the masthead back out of a rendered note."""
    poster = attr(r'<a class="poster" href="([^"]*)"', doc)
    kicker = text_of(find(r'<span class="kicker">(.*?)</span>', doc))
    meta = text_of(find(r'<p class="meta">(.*?)</p>', doc))

    if kicker:  # article: byline lives in the kicker, meta is date · reading time
        byline, detail = kicker, meta
    else:       # video: meta leads with the (linked) channel
        byline, _, detail = (part.strip() for part in meta.partition("·"))

    date_match = DATE_PREFIX.match(path.name)
    tag, tags = parse_tags(doc)
    return Note(
        path=path,
        title=text_of(find(r"<title>(.*?)</title>", doc)) or path.stem,
        byline=byline,
        detail=detail,
        excerpt=excerpt_of(doc),
        thumbnail=attr(r'<a class="poster".*?<img src="([^"]*)"', doc),
        source=poster or attr(r'<a class="watch" href="([^"]*)"', doc),
        date=date_match.group(1) if date_match else "",
        kind="video" if poster else "article",
        tag=tag,
        tags=tags,
    )


def read(path: Path) -> tuple[Note, str] | None:
    """A note and its raw document, or None when the file cannot be read."""
    try:
        doc = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_note(path, doc), doc


def collect(notes_dir: Path) -> list[Note]:
    """Every note in the directory, newest first."""
    notes = [pair[0] for path in notes_dir.glob("*.html") if (pair := read(path))]
    # Filename date first, mtime as the tiebreak for same-day notes.
    return sorted(notes, key=lambda n: (n.date, n.path.stat().st_mtime), reverse=True)


def _selftest() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import render  # the documents this module parses are render.py's output

    notes_dir = Path("/tmp/take-notes/html_reports")

    video_doc = render.build_video_document(
        "5 > 3 & rising",
        "<h2>Executive summary</h2><p>A &amp; B argue that markets rise.</p>",
        byline="La Pizarra",
        channel_url="https://youtube.com/@x",
        span="11 min",
        url="https://youtu.be/abc123",
        video_id="abc123",
        views="13.2K views",
        today="2026-01-01",
    )
    video = parse_note(notes_dir / "2026-08-18-rising.html", video_doc)
    assert video.kind == "video"
    assert video.title == "5 > 3 & rising", video.title
    assert video.byline == "La Pizarra", video.byline
    assert video.detail == "11 min · 13.2K views", video.detail
    assert video.thumbnail == "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
    assert video.source == "https://youtu.be/abc123"
    assert video.date == "2026-08-18"
    assert video.excerpt == "A & B argue that markets rise."

    article_doc = render.build_article_document(
        "Título ñ",
        "<h2>Executive summary</h2><p>" + ("palabra " * 80) + "</p>",
        byline="Sitio & Co",
        span="Jan 1, 2026",
        url="https://x.test/?a=1&b=2",
        today="2026-01-01",
    )
    article = parse_note(notes_dir / "2026-08-01-titulo.html", article_doc)
    assert article.kind == "article"
    assert article.byline == "Sitio & Co", article.byline
    assert article.detail.startswith("Jan 1, 2026 ·"), article.detail
    assert article.thumbnail == ""
    assert article.source == "https://x.test/?a=1&b=2"
    assert len(article.excerpt) <= EXCERPT_CHARS + 1 and article.excerpt.endswith("…")

    # A note with no masthead at all must degrade, not explode.
    bare = parse_note(notes_dir / "stray.html", "<html><body><p>hi</p></body></html>")
    assert bare.title == "stray" and bare.kind == "article" and bare.date == ""
    assert (bare.tag, bare.tags) == ("", ()), "a note written before tags existed still parses"

    # Tags round-trip: the primary is the is-primary span, extras follow in
    # document order, and both templates carry the row.
    tagged = parse_note(
        notes_dir / "2026-08-18-tagged.html",
        render.build_article_document(
            "Tagged", "<h2>Executive summary</h2><p>ok</p>",
            byline="S", url="https://x.test", tags=["AI", "Engineering"], today="2026-01-01",
        ),
    )
    assert tagged.tag == "AI", tagged.tag
    assert tagged.tags == ("AI", "Engineering"), tagged.tags
    assert video.tag == "" and video.tags == (), (
        "an untagged render carries no tag row (see render.tags_html) and so parses as untagged"
    )
    assert parse_tags('<p class="tags"><span class="tag">R &amp; D</span></p>') == ("R & D", ("R & D",)), (
        "entities decode, and document order stands in for a missing is-primary"
    )
    assert parse_tags("<p>no tag row</p>") == ("", ())

    # Config: tolerant read, vocabulary always led by DEFAULT_TAG.
    assert read_config(Path("/tmp/take-notes/does-not-exist.json")) == {}
    assert configured_tags({}) == [DEFAULT_TAG]
    assert configured_tags({"tags": "AI"}) == [DEFAULT_TAG], "a non-list `tags` is ignored, not fatal"
    assert configured_tags({"tags": ["AI", " ", "Investing"]}) == [DEFAULT_TAG, "AI", "Investing"]
    assert configured_tags({"tags": ["AI", "ai", DEFAULT_TAG]}) == [DEFAULT_TAG, "AI"], (
        "case-insensitive dedupe, and DEFAULT_TAG is never listed twice"
    )

    assert length_of("11 min · 16 ago 2026 · 13.2K visualizaciones") == "11 min"
    assert length_of("Jan 1, 2026 · 6 min read") == "6 min read"
    assert length_of("1 h 15 min · 2026") == "1 h 15 min"
    assert length_of("Jan 1, 2026") == ""
    assert fold("La Pizarra de Andrés") == "la pizarra de andres"

    # Sections: split on <h2>, both languages, and the <li><strong>x</strong> — y shape.
    sectioned = render.build_article_document(
        "Sections",
        "<h2>Executive summary</h2><p>intro</p>"
        "<h2>The one takeaway</h2><p><strong>Big idea.</strong></p>"
        "<h2>Key points</h2><ul>"
        "<li><strong>Claim &amp; co</strong> — the detail</li>"
        "<li><strong>Second</strong> – en dash works too</li>"
        "<li>no strong at all</li></ul>"
        "<h2>Concepts</h2><ul><li><strong>term</strong> — definition</li></ul>",
        byline="S", url="https://x.test", today="2026-01-01",
    )
    headings = [h for h, _ in parse_sections(sectioned)]
    assert headings == ["Executive summary", "The one takeaway", "Key points", "Concepts"], headings
    assert "Big idea." in text_of(section(sectioned, "takeaway"))
    points = list_pairs(section(sectioned, "key_points"))
    assert points[0] == ("Claim & co", "the detail"), points[0]
    assert points[1] == ("Second", "en dash works too"), points[1]
    assert points[2] == ("no strong at all", ""), points[2]
    assert list_pairs(section(sectioned, "concepts")) == [("term", "definition")]
    assert section(sectioned, "outline") == "", "absent section returns empty, never raises"

    spanish = render.build_article_document(
        "Secciones",
        "<h2>Resumen ejecutivo</h2><p>hola</p>"
        "<h2>Puntos clave</h2><ul><li><strong>Afirmación</strong> — el detalle</li></ul>"
        "<h2>Conceptos</h2><ul><li><strong>término</strong> — definición</li></ul>",
        byline="S", url="https://x.test", lang="es", today="2026-01-01",
    )
    assert list_pairs(section(spanish, "key_points")) == [("Afirmación", "el detalle")]
    assert list_pairs(section(spanish, "concepts")) == [("término", "definición")]

    assert parse_sections("<html><body><p>no body div</p></body></html>") == []

    print("selftest: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest() if "--selftest" in sys.argv else 0)
