#!/usr/bin/env -S uv run --script
"""Read rendered notes back out of ~/take-notes/html_reports.

The one place that knows how to parse a note. Nothing here writes anything —
`gallery.py` lays these out as cards, `export.py` converts them to Markdown and
flashcards, and both read through this module so the scraping rules live once.

A note is its own database: the masthead classes (`.poster`, `.kicker`,
`.meta`, `.watch`) and the flat `<h2>`-delimited body are the contract with
assets/template.html, assets/article-template.html, and SKILL.md's
"Keep the HTML plain" rule. Break one and this module's --selftest fails,
which is the point.
"""
from __future__ import annotations

import html
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path


NOTES_DIR = Path.home() / "take-notes" / "html_reports"

EXCERPT_CHARS = 190

DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
TAGS = re.compile(r"<[^>]+>")

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
