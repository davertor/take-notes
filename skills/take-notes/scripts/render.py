#!/usr/bin/env -S uv run --script
"""Wrap note body HTML in a self-contained, styled document under
~/take-notes/html_reports.

Body HTML arrives on stdin; the header (title, byline, span, source link) is
rendered from the flags so every note gets an identical masthead. Nothing is
parsed: the skill writes semantic HTML directly, which is why this stays
stdlib-only and needs no Markdown dependency.

    ... | render.py --title "…" --byline "…" --span "…" --url "…"
"""
from __future__ import annotations

import argparse
import datetime
import html
import re
import sys
import unicodedata
import webbrowser
from pathlib import Path


DEFAULT_OUT_DIR = Path.home() / "take-notes" / "html_reports"
TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"

# The only two languages Step 2 ever offers (see SKILL.md). Whole sentences,
# not word-by-word substitution: concatenating translated fragments breaks
# grammar across languages with different word order.
FOOTER_SENTENCE = {
    "en": "Notes generated from {link} on {today}.",
    "es": "Notas generadas a partir de {link} el {today}.",
}
VIDEO_FOOTER_SENTENCE = {
    "en": "Noted from {link} &middot; {today}",
    "es": "Notas de {link} &middot; {today}",
}
UI_STRINGS = {
    "en": {"watch": "Watch", "open": "Open original"},
    "es": {"watch": "Ver", "open": "Ver original"},
}
MONTHS = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "es": ("ene", "feb", "mar", "abr", "may", "jun",
           "jul", "ago", "sep", "oct", "nov", "dic"),
}
DATE_ORDER = {"en": "{mon} {day}, {year}", "es": "{day} {mon} {year}"}
VIEWS_LABEL = {"en": "{n} views", "es": "{n} visualizaciones"}
MINUTES_LABEL = {"en": "{n} min", "es": "{n} min"}


def format_date(raw: str | None, lang: str) -> str | None:
    """yt-dlp's YYYYMMDD (or ISO) to a date written the way `lang` writes dates."""
    if not raw:
        return None
    digits = raw.replace("-", "").strip()
    if len(digits) != 8 or not digits.isdigit():
        return None
    year, month, day = digits[:4], int(digits[4:6]), int(digits[6:8])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    months = MONTHS.get(lang, MONTHS["en"])
    return DATE_ORDER.get(lang, DATE_ORDER["en"]).format(
        mon=months[month - 1], day=day, year=year
    )


def format_count(n: int | str | None, lang: str) -> str | None:
    """Abbreviate a view count and label it in `lang`: 13200 -> '13.2K views'."""
    if n is None or n == "":
        return None
    try:
        value = int(n)
    except (TypeError, ValueError):
        return None
    for div, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= div:
            text = f"{value / div:.1f}".rstrip("0").rstrip(".") + suffix
            break
    else:
        text = str(value)
    return VIEWS_LABEL.get(lang, VIEWS_LABEL["en"]).format(n=text)


def format_duration(seconds: int | str | None, lang: str) -> str | None:
    """Seconds to a reading-length phrase: 692 -> '11 min', 4500 -> '1 h 15 min'."""
    if seconds is None or seconds == "":
        return None
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    # Floor, not round: an 11:32 video is "11 min", the way people say it.
    hours, minutes = divmod(total // 60, 60)
    if hours and minutes:
        return f"{hours} h {minutes} min"
    if hours:
        return f"{hours} h"
    return MINUTES_LABEL.get(lang, MINUTES_LABEL["en"]).format(n=max(1, minutes))


def footer_html(lang: str, url: str | None, today: str) -> str:
    safe_url = html.escape(url or "", quote=True)
    link = f'<a href="{safe_url}">{safe_url}</a>'
    return FOOTER_SENTENCE.get(lang, FOOTER_SENTENCE["en"]).format(link=link, today=today)


def video_footer_html(lang: str, url: str | None, today: str) -> str:
    safe_url = html.escape(url or "", quote=True)
    link = f'<a href="{safe_url}">{safe_url}</a>'
    return VIDEO_FOOTER_SENTENCE.get(lang, VIDEO_FOOTER_SENTENCE["en"]).format(link=link, today=today)

STYLE = """
:root {
  --bg: #fdfdfc; --fg: #1c1b19; --muted: #6b6862;
  --rule: #e3e0da; --accent: #8a5a2b; --code-bg: #f4f2ee;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161513; --fg: #e8e5df; --muted: #9b968d;
    --rule: #2e2c28; --accent: #d0a06a; --code-bg: #211f1c;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 3rem 1.25rem 6rem;
  background: var(--bg); color: var(--fg);
  font: 17px/1.65 ui-serif, Georgia, "Iowan Old Style", serif;
}
main { max-width: 42rem; margin: 0 auto; }
h1 { font-size: 1.9rem; line-height: 1.2; margin: 0 0 .4rem; letter-spacing: -.01em; }
h2 {
  font-size: 1.15rem; margin: 2.4rem 0 .7rem; padding-top: .9rem;
  border-top: 1px solid var(--rule); letter-spacing: .02em; text-transform: uppercase;
  font-family: ui-sans-serif, system-ui, sans-serif; color: var(--muted);
}
h3 { font-size: 1.02rem; margin: 1.5rem 0 .4rem; }
.meta {
  font-family: ui-sans-serif, system-ui, sans-serif;
  font-size: .82rem; color: var(--muted); margin: 0 0 2rem;
}
.meta a { color: inherit; }
p, li { margin: .6rem 0; }
ul, ol { padding-left: 1.3rem; }
li::marker { color: var(--accent); }
a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }
strong { font-weight: 650; }
code {
  font: .87em ui-monospace, SFMono-Regular, Menlo, monospace;
  background: var(--code-bg); padding: .12em .35em; border-radius: 3px;
}
pre {
  background: var(--code-bg); padding: .9rem 1rem; border-radius: 6px;
  overflow-x: auto; font-size: .87rem; line-height: 1.5;
}
pre code { background: none; padding: 0; }
blockquote {
  margin: 1rem 0; padding-left: 1rem;
  border-left: 3px solid var(--rule); color: var(--muted);
}
table { border-collapse: collapse; width: 100%; font-size: .93rem; margin: 1rem 0; }
th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid var(--rule); }
th { font-family: ui-sans-serif, system-ui, sans-serif; font-size: .8rem;
     text-transform: uppercase; letter-spacing: .03em; color: var(--muted); }
footer {
  margin-top: 3.5rem; padding-top: 1rem; border-top: 1px solid var(--rule);
  font-family: ui-sans-serif, system-ui, sans-serif;
  font-size: .78rem; color: var(--muted);
}
@media print {
  body { padding: 0; font-size: 11pt; }
  h2 { break-after: avoid; }
  footer { display: none; }
}
"""

DOCUMENT = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{style}</style>
</head>
<body>
<main>
<h1>{title}</h1>
<p class="meta">{meta}</p>
{body}
<footer>{footer}</footer>
</main>
</body>
</html>
"""


def slugify(title: str, maxlen: int = 60) -> str:
    """Filename-safe ASCII slug; falls back to 'notes' when nothing survives."""
    folded = unicodedata.normalize("NFKD", title)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return slug[:maxlen].strip("-") or "notes"


def build_meta(byline: str | None, span: str | None, url: str | None) -> str:
    """The masthead line: byline · span · linked host, skipping empty parts."""
    parts: list[str] = []
    if byline:
        parts.append(html.escape(byline))
    if span:
        parts.append(html.escape(span))
    if url:
        safe = html.escape(url, quote=True)
        parts.append(f'<a href="{safe}">{safe}</a>')
    return " &middot; ".join(parts)


def build_document(
    title: str,
    body: str,
    byline: str | None = None,
    span: str | None = None,
    url: str | None = None,
    lang: str = "en",
    today: str | None = None,
) -> str:
    today = today or datetime.date.today().isoformat()
    return DOCUMENT.format(
        lang=html.escape(lang, quote=True),
        title=html.escape(title),
        style=STYLE,
        meta=build_meta(byline, span, url),
        body=body.strip(),
        footer=footer_html(lang, url, today),
    )


def build_video_meta(
    byline: str | None,
    channel_url: str | None,
    span: str | None,
    published: str | None,
    views: str | None,
) -> str:
    """Video masthead: linked channel · duration · published · views.

    No source link here — template.html gives the source its own action, and
    the poster is a link too; a third copy in the meta line is noise.
    """
    parts: list[str] = []
    if byline:
        safe = html.escape(byline)
        parts.append(
            f'<a href="{html.escape(channel_url, quote=True)}">{safe}</a>' if channel_url else safe
        )
    for value in (span, published, views):
        if value:
            parts.append(html.escape(value))
    return " &middot; ".join(parts)


def build_video_document(
    title: str,
    body: str,
    byline: str | None = None,
    channel_url: str | None = None,
    span: str | None = None,
    url: str | None = None,
    video_id: str | None = None,
    thumbnail: str | None = None,
    published: str | None = None,
    views: str | None = None,
    lang: str = "en",
    today: str | None = None,
) -> str:
    thumb = thumbnail or (f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "")
    today = today or datetime.date.today().isoformat()
    strings = UI_STRINGS.get(lang, UI_STRINGS["en"])
    doc = TEMPLATE_PATH.read_text(encoding="utf-8")
    for token, value in {
        "{{LANG}}": html.escape(lang, quote=True),
        "{{TITLE}}": html.escape(title),
        "{{THUMBNAIL}}": html.escape(thumb, quote=True),
        "{{URL}}": html.escape(url or "", quote=True),
        "{{META}}": build_video_meta(byline, channel_url, span, published, views),
        "{{BODY}}": body.strip(),
        "{{WATCH}}": html.escape(strings["watch"]),
        "{{OPEN}}": html.escape(strings["open"]),
        "{{FOOTER}}": video_footer_html(lang, url, today),
    }.items():
        doc = doc.replace(token, value)
    if "{{" in doc:
        stray = doc[doc.index("{{"):doc.index("{{") + 30]
        raise ValueError(f"unresolved template.html token near {stray!r}")
    return doc


def _selftest() -> int:
    assert slugify("Never Gonna Give You Up (4K)") == "never-gonna-give-you-up-4k"
    assert slugify("¿Qué es un LLM?") == "que-es-un-llm"
    assert slugify("!!!") == "notes"
    assert slugify("") == "notes"
    assert len(slugify("x" * 200)) <= 60
    assert not slugify("a" + "-" * 80 + "b").endswith("-")

    # Header fields are escaped; body HTML is passed through by design.
    doc = build_document(
        "5 > 3 & rising",
        "<h2>Summary</h2><p>ok</p>",
        byline="A & B",
        url="https://x.test/?a=1&b=2",
        today="2026-01-01",
    )
    assert "<title>5 &gt; 3 &amp; rising</title>" in doc
    assert "A &amp; B" in doc
    assert "a=1&amp;b=2" in doc
    assert "<h2>Summary</h2><p>ok</p>" in doc
    assert "<script" not in doc.lower()
    assert "Notes generated from" in doc, "footer defaults to English"

    doc_es = build_document(
        "Título", "<p>ok</p>", url="https://x.test", lang="es", today="2026-01-01",
    )
    assert "Notas generadas a partir de" in doc_es, "footer localises to Spanish"
    assert "Notes generated" not in doc_es, "no English leaking into the Spanish footer"

    assert build_meta(None, None, None) == ""
    assert build_meta("A", None, None) == "A"
    assert "&middot;" in build_meta("A", "12:34", None)

    # Raw metadata localises rather than being pre-formatted by the caller.
    assert format_date("20251205", "en") == "Dec 5, 2025"
    assert format_date("20251205", "es") == "5 dic 2025"
    assert format_date("2025-12-05", "es") == "5 dic 2025"
    assert format_date("20251399", "en") is None
    assert format_date(None, "en") is None

    assert format_count(13_200, "en") == "13.2K views"
    assert format_count(13_200, "es") == "13.2K visualizaciones"
    assert format_count("900", "en") == "900 views"
    assert format_count(1_000_000, "en") == "1M views"
    assert format_count(None, "en") is None
    assert format_count("n/a", "en") is None

    assert format_duration(692, "en") == "11 min"
    assert format_duration(4500, "en") == "1 h 15 min"
    assert format_duration(3600, "en") == "1 h"
    assert format_duration(20, "en") == "1 min"        # never "0 min"
    assert format_duration(None, "en") is None

    # Video path: no --thumbnail falls back to the YouTube thumbnail for
    # --video-id, header fields stay escaped, and the tab/rail scaffolding
    # from template.html is present.
    video_doc = build_video_document(
        "5 > 3 & rising",
        "<h2>Executive summary</h2><p>ok</p><h2>Timestamped outline</h2><ul><li>x</li></ul>",
        byline="A & B",
        url="https://youtu.be/abc123",
        video_id="abc123",
        today="2026-01-01",
    )
    assert "<title>5 &gt; 3 &amp; rising</title>" in video_doc
    assert "A &amp; B" in video_doc
    assert "https://i.ytimg.com/vi/abc123/hqdefault.jpg" in video_doc
    assert 'id="index"' in video_doc
    assert 'id="spy"' in video_doc
    assert "{{" not in video_doc
    assert ">Watch<" in video_doc, "poster badge defaults to English"
    assert ">Open original <" in video_doc, "watch link defaults to English"
    assert "Noted from" in video_doc, "footer defaults to English"

    video_doc_es = build_video_document(
        "Título", "<h2>Resumen</h2><p>ok</p>",
        url="https://youtu.be/abc123", video_id="abc123", lang="es", today="2026-01-01",
    )
    assert ">Ver<" in video_doc_es, "poster badge localises to Spanish"
    assert ">Ver original <" in video_doc_es, "watch link localises to Spanish"
    assert "Notas de" in video_doc_es, "footer localises to Spanish"
    assert "Watch" not in video_doc_es and "Open original" not in video_doc_es and "Noted from" not in video_doc_es, (
        "no English chrome leaking into a Spanish note"
    )
    assert "{{" not in video_doc_es

    assert "&middot;" in build_video_meta("A", None, "12:34", "Jan 1, 2026", "1K")
    assert '<a href="https://x.test">A</a>' in build_video_meta("A", "https://x.test", None, None, None)
    assert build_video_meta(None, None, None, None, None) == ""

    print("selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="render",
        description="Wrap note body HTML (stdin) in a self-contained styled document.",
    )
    ap.add_argument("--title", help="Note title, used for <h1> and the filename")
    ap.add_argument("--byline", default=None, help="Channel, author, or site")
    ap.add_argument("--span", default=None, help="Duration for video, date for an article")
    ap.add_argument("--url", default=None, help="Canonical source URL")
    ap.add_argument(
        "--video-id", default=None,
        help="YouTube video ID; presence switches to the two-pane video layout",
    )
    ap.add_argument("--thumbnail", default=None, help="Thumbnail URL (default: YouTube's for --video-id)")
    ap.add_argument("--channel-url", default=None, help="Video only: links the byline")
    # Raw in, localised out: pass what transcript.py printed and let --lang
    # decide how it reads. Strings are still accepted and passed through.
    ap.add_argument("--published", default=None, help="Video only: YYYYMMDD (or a ready-made string)")
    ap.add_argument("--views", default=None, help="Video only: view count as an integer")
    ap.add_argument("--duration", default=None, help="Video only: length in seconds; overrides --span")
    ap.add_argument("--lang", default="en", help="Document language (default: en)")
    ap.add_argument("--out-dir", default=None, help=f"Output dir (default: {DEFAULT_OUT_DIR})")
    ap.add_argument("--no-open", action="store_true", help="Do not open a browser")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.title:
        ap.error("--title is required")

    body = sys.stdin.read()
    if not body.strip():
        print("render: no body HTML on stdin", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{datetime.date.today().isoformat()}-{slugify(args.title)}.html"

    if args.video_id:
        # Localise raw values; anything already human-readable passes through.
        published = format_date(args.published, args.lang) or args.published
        views = format_count(args.views, args.lang) or args.views
        span = format_duration(args.duration, args.lang) or args.span
        document = build_video_document(
            args.title, body,
            byline=args.byline, channel_url=args.channel_url, span=span, url=args.url,
            video_id=args.video_id, thumbnail=args.thumbnail,
            published=published, views=views, lang=args.lang,
        )
    else:
        document = build_document(
            args.title, body,
            byline=args.byline, span=args.span, url=args.url, lang=args.lang,
        )

    # Re-running on the same source the same day updates that note rather than
    # littering the archive with near-duplicates; say which happened.
    action = "updated" if target.exists() else "created"
    target.write_text(document, encoding="utf-8")

    print(f"{action}: {target}")
    if not args.no_open:
        webbrowser.open(target.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
