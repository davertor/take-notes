#!/usr/bin/env -S uv run --script
"""Build a browsable gallery of every note in ~/take-notes/html_reports.

Reads the notes themselves — no database, no sidecar index. Each rendered note
already carries its own masthead (title, byline, meta line, source link,
poster), so the gallery scrapes those few landmarks back out and lays them on
cards. That keeps notes written before this script existed visible, and means
nothing to keep in sync when a note is deleted by hand.

    uv run gallery.py            # build ~/take-notes/gallery.html and open it
    uv run gallery.py --no-open
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
import os
import re
import sys
import unicodedata
import webbrowser
from dataclasses import dataclass
from pathlib import Path


NOTES_DIR = Path.home() / "take-notes" / "html_reports"
DEFAULT_OUT = Path.home() / "take-notes" / "gallery.html"
CONFIG_FILE = Path.home() / "take-notes" / "config.json"
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "gallery-template.html"

EXCERPT_CHARS = 190

# Whole phrases, like render.py's — see the note there on why these are not
# assembled from translated fragments.
UI = {
    "en": {
        "title": "take-notes — archive",
        "tally_one": "1 note",
        "tally_many": "{n} notes",
        "range": "{first} – {last}",
        "placeholder": "Filter by title or source…",
        "empty": "No notes yet. Run /take-notes on a video or an article.",
        "nomatch": "Nothing matches.",
        "video": "video",
        "article": "article",
        "built": "{dir} &middot; built {today}",
    },
    "es": {
        "title": "take-notes — archivo",
        "tally_one": "1 nota",
        "tally_many": "{n} notas",
        "range": "{first} – {last}",
        "placeholder": "Filtrar por título o fuente…",
        "empty": "Aún no hay notas. Ejecuta /take-notes sobre un vídeo o un artículo.",
        "nomatch": "Sin coincidencias.",
        "video": "vídeo",
        "article": "artículo",
        "built": "{dir} &middot; generado el {today}",
    },
}

DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Note:
    """One rendered note, as much of it as the gallery needs."""

    path: Path
    title: str
    byline: str
    detail: str
    excerpt: str
    thumbnail: str
    source: str
    date: str
    kind: str  # "video" | "article"


def _text(fragment: str) -> str:
    """Inner HTML to plain collapsed text."""
    return re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", fragment))).strip()


def _fold(text: str) -> str:
    """Lowercase and strip accents, exactly as the template's filter JS does —
    the two must agree or typing "andres" misses "Andrés"."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _length(detail: str) -> str:
    """The one scannable number in a meta line: "11 min", "6 min read", "1 h 15 min"."""
    for part in (p.strip() for p in detail.split("·")):
        if re.search(r"\d+\s*(min|h)\b", part):
            return part
    return ""


def _find(pattern: str, doc: str) -> str:
    match = re.search(pattern, doc, re.DOTALL)
    return match.group(1) if match else ""


def _attr(pattern: str, doc: str) -> str:
    """Attribute value, decoded — a note's URLs carry `&amp;` in the file and
    would be double-escaped when written back onto a card."""
    return html.unescape(_find(pattern, doc))


def _excerpt(doc: str) -> str:
    """First paragraph of the note body, trimmed on a word boundary."""
    body = _find(r'<article id="body">(.*?)</article>', doc)
    text = _text(_find(r"<p[^>]*>(.*?)</p>", body))
    if len(text) <= EXCERPT_CHARS:
        return text
    cut = text[:EXCERPT_CHARS]
    head, _, _ = cut.rpartition(" ")
    return (head or cut).rstrip(",;:.—- ") + "…"


def parse_note(path: Path, doc: str) -> Note:
    """Pull the masthead back out of a rendered note.

    The landmarks — .poster, .kicker, .meta, .watch — are the contract with
    assets/template.html and assets/article-template.html. Change a class name
    there and --selftest here fails, which is the point.
    """
    poster = _attr(r'<a class="poster" href="([^"]*)"', doc)
    kicker = _text(_find(r'<span class="kicker">(.*?)</span>', doc))
    meta = _text(_find(r'<p class="meta">(.*?)</p>', doc))

    if kicker:  # article: byline lives in the kicker, meta is date · reading time
        byline, detail = kicker, meta
    else:       # video: meta leads with the (linked) channel
        byline, _, detail = (part.strip() for part in meta.partition("·"))

    date_match = DATE_PREFIX.match(path.name)
    return Note(
        path=path,
        title=_text(_find(r"<title>(.*?)</title>", doc)) or path.stem,
        byline=byline,
        detail=detail,
        excerpt=_excerpt(doc),
        thumbnail=_attr(r'<a class="poster".*?<img src="([^"]*)"', doc),
        source=poster or _attr(r'<a class="watch" href="([^"]*)"', doc),
        date=date_match.group(1) if date_match else "",
        kind="video" if poster else "article",
    )


def collect(notes_dir: Path) -> list[Note]:
    """Every note in the directory, newest first."""
    notes: list[Note] = []
    for path in notes_dir.glob("*.html"):
        try:
            doc = path.read_text(encoding="utf-8")
        except OSError:
            continue
        notes.append(parse_note(path, doc))
    # Filename date first, mtime as the tiebreak for same-day notes.
    return sorted(notes, key=lambda n: (n.date, n.path.stat().st_mtime), reverse=True)


def card_html(note: Note, number: int, out_dir: Path, strings: dict[str, str]) -> str:
    href = html.escape(os.path.relpath(note.path, out_dir), quote=True)
    search = html.escape(_fold(f"{note.title} {note.byline} {note.detail}"), quote=True)
    # The full meta line is searchable but too long for a 17rem card: the foot
    # keeps the length and the filing date, the two things you scan a shelf by.
    stamp = " &middot; ".join(html.escape(v) for v in (_length(note.detail), note.date) if v)

    if note.thumbnail:
        plate = (
            f'<span class="plate"><img src="{html.escape(note.thumbnail, quote=True)}"'
            ' alt="" loading="lazy"></span>'
        )
    else:
        # Filing number only: the byline is already the card's kicker, and a
        # plate that repeats it just prints the same words twice.
        plate = f'<span class="plate is-blank"><span class="mark">{number:02d}</span></span>'

    parts = [f'<a class="card" href="{href}" data-search="{search}">', plate, '<span class="body">']
    if note.byline:
        parts.append(f'<span class="kicker">{html.escape(note.byline)}</span>')
    parts.append(f'<span class="title">{html.escape(note.title)}</span>')
    if note.excerpt:
        parts.append(f'<span class="excerpt">{html.escape(note.excerpt)}</span>')
    parts.append("</span>")
    parts.append(
        '<span class="foot">'
        f'<span class="kind">{html.escape(strings[note.kind])}</span>'
        f'<span class="date">{stamp}</span></span>'
    )
    parts.append("</a>")
    return "".join(parts)


def build_tally(notes: list[Note], strings: dict[str, str]) -> str:
    if not notes:
        return ""
    count = strings["tally_one"] if len(notes) == 1 else strings["tally_many"].format(n=len(notes))
    dates = [n.date for n in notes if n.date]
    if not dates:
        return count
    span = strings["range"].format(first=min(dates), last=max(dates))
    return f"{count} &middot; {span}" if min(dates) != max(dates) else f"{count} &middot; {max(dates)}"


def build_gallery(
    notes: list[Note],
    out_dir: Path,
    notes_dir: Path,
    lang: str = "en",
    today: str | None = None,
) -> str:
    strings = UI.get(lang, UI["en"])
    today = today or datetime.date.today().isoformat()
    cards = "\n".join(card_html(n, i + 1, out_dir, strings) for i, n in enumerate(notes))
    doc = TEMPLATE_PATH.read_text(encoding="utf-8")
    for token, value in {
        "{{LANG}}": html.escape(lang, quote=True),
        "{{TITLE}}": html.escape(strings["title"]),
        "{{TALLY}}": build_tally(notes, strings),
        "{{PLACEHOLDER}}": html.escape(strings["placeholder"], quote=True),
        "{{CARDS}}": cards or f'<p class="blank">{html.escape(strings["empty"])}</p>',
        "{{NOMATCH}}": html.escape(strings["nomatch"]),
        "{{FOOTER}}": strings["built"].format(dir=html.escape(str(notes_dir)), today=today),
    }.items():
        doc = doc.replace(token, value)
    if "{{" in doc:
        stray = doc[doc.index("{{"):doc.index("{{") + 30]
        raise ValueError(f"unresolved gallery-template.html token near {stray!r}")
    return doc


def config_lang() -> str:
    """`language` from ~/take-notes/config.json; English for anything else.

    "ask" is a question for the note-writing skill, not for a static page, so
    it resolves to English here rather than blocking the build.
    """
    try:
        value = json.loads(CONFIG_FILE.read_text(encoding="utf-8")).get("language")
    except (OSError, ValueError, AttributeError):
        return "en"
    return value if value in UI else "en"


def _selftest() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import render  # the templates this script parses are render.py's output

    out_dir = Path("/tmp/take-notes")
    notes_dir = out_dir / "html_reports"

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

    page = build_gallery([video, article], out_dir, notes_dir, today="2026-01-01")
    assert "{{" not in page
    assert 'href="html_reports/2026-08-18-rising.html"' in page, "links are relative to the gallery"
    assert "<span class=\"title\">5 &gt; 3 &amp; rising</span>" in page, "card fields stay escaped"
    assert 'data-search="5 &gt; 3 &amp; rising la pizarra' in page, "filter haystack is folded"
    assert 'titulo n' in build_gallery([article], out_dir, notes_dir, today="2026-01-01"), (
        "accents are stripped from the haystack, matching the template's filter JS"
    )
    assert _length("11 min · 16 ago 2026 · 13.2K visualizaciones") == "11 min"
    assert _length("Jan 1, 2026 · 6 min read") == "6 min read"
    assert _length("1 h 15 min · 2026") == "1 h 15 min"
    assert _length("Jan 1, 2026") == ""
    assert ">02<" in page and "is-blank" in page, "the poster-less note gets a filing plate"
    assert "2 notes &middot; 2026-08-01 – 2026-08-18" in page

    page_es = build_gallery([video], out_dir, notes_dir, lang="es", today="2026-01-01")
    assert "1 nota &middot; 2026-08-18" in page_es
    assert ">vídeo<" in page_es and "notes &middot;" not in page_es, "no English chrome in a Spanish gallery"

    empty = build_gallery([], out_dir, notes_dir, today="2026-01-01")
    assert "No notes yet" in empty and "{{" not in empty

    print("selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="gallery",
        description="Build a browsable gallery of every note under ~/take-notes/html_reports.",
    )
    ap.add_argument("--notes-dir", default=None, help=f"Where the notes live (default: {NOTES_DIR})")
    ap.add_argument("--out", default=None, help=f"Gallery file to write (default: {DEFAULT_OUT})")
    ap.add_argument("--lang", default=None, help="en|es (default: ~/take-notes/config.json, else en)")
    ap.add_argument("--no-open", action="store_true", help="Do not open a browser")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    notes_dir = Path(args.notes_dir).expanduser() if args.notes_dir else NOTES_DIR
    out = Path(args.out).expanduser() if args.out else DEFAULT_OUT
    lang = args.lang if args.lang in UI else config_lang()

    if not notes_dir.is_dir():
        print(f"gallery: no notes directory at {notes_dir}", file=sys.stderr)
        return 1

    notes = collect(notes_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_gallery(notes, out.parent, notes_dir, lang=lang), encoding="utf-8")

    print(f"gallery: {len(notes)} note(s) -> {out}")
    if not args.no_open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
