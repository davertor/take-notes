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


sys.path.insert(0, str(Path(__file__).resolve().parent))
# The one import from the rest of the skill, and deliberately a leaf: themes.py
# is pure palette data at import time, so this pulls in no note parsing. The
# alternative was the same block of CSS copied into every template.
import themes  # noqa: E402


DEFAULT_OUT_DIR = Path.home() / "take-notes" / "html_reports"
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "template.html"
ARTICLE_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "article-template.html"

# Genres beyond the offprint: one template each, resolving video vs article
# inside (only the masthead differs — poster or kicker). The offprint keeps its
# two files and its own pair of builders below; these go through
# build_genre_document. Adding a genre is one entry here, one template, one
# contract under genres/, and one row in SKILL.md's Step 3 table.
GENRE_TEMPLATES = {
    "fieldguide": Path(__file__).resolve().parent.parent / "assets" / "fieldguide-template.html",
    "recipe": Path(__file__).resolve().parent.parent / "assets" / "recipe-template.html",
}
DEFAULT_GENRE = "offprint"
GENRES = (DEFAULT_GENRE, *GENRE_TEMPLATES)

# Kept in step with notes.DEFAULT_TAG, but not imported from it: render.py
# depends on nothing but the leaf palette module, and stays that way.
DEFAULT_TAG = "Unknown"

# The only two languages Step 2 ever offers (see SKILL.md). Whole sentences,
# not word-by-word substitution: concatenating translated fragments breaks
# grammar across languages with different word order. Shared by both rail
# templates (video and article) — the phrasing isn't video-specific.
RAIL_FOOTER_SENTENCE = {
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
READING_LABEL = {"en": "{n} min read", "es": "{n} min de lectura"}
WORDS_PER_MINUTE = 220


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


def format_reading_time(word_count: int, lang: str) -> str | None:
    """Word count to a reading-length phrase: 1300 -> '6 min read'.

    Rounds up, unlike format_duration's floor: a stated video length is exact,
    but a reading estimate is a ceiling on how long the article might take.
    """
    if not word_count or word_count <= 0:
        return None
    minutes = max(1, -(-word_count // WORDS_PER_MINUTE))  # ceil division
    return READING_LABEL.get(lang, READING_LABEL["en"]).format(n=minutes)


def _word_count(body_html: str) -> int:
    """Rough word count of rendered body HTML, tags and entities stripped."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", body_html))
    return len(text.split())


def rail_footer_html(lang: str, url: str | None, today: str) -> str:
    safe_url = html.escape(url or "", quote=True)
    link = f'<a href="{safe_url}">{safe_url}</a>'
    return RAIL_FOOTER_SENTENCE.get(lang, RAIL_FOOTER_SENTENCE["en"]).format(link=link, today=today)


def tags_html(tags: list[str] | None) -> str:
    """The rail's tag row, or nothing when there is no real tag to show.

    First tag wins `is-primary` — the one a gallery card shows and files the
    note under. DEFAULT_TAG ("Unknown") is the skill's internal fallback for
    "nothing fit," never a tag worth displaying, so a note that only has it
    gets no tag row at all rather than an "Unknown" badge.

    A dumb renderer otherwise: nothing here checks the vocabulary in
    config.json. The skill owns that choice, and a `--out-dir` test run has
    to keep working with whatever values it is handed.
    """
    names = [
        t.strip() for t in (tags or [])
        if t and t.strip() and t.strip().casefold() != DEFAULT_TAG.casefold()
    ]
    if not names:
        return ""
    spans = "".join(
        f'<span class="tag{" is-primary" if i == 0 else ""}">{html.escape(name)}</span>'
        for i, name in enumerate(names)
    )
    return f'<p class="tags">{spans}</p>'


def sources_html(sources: list[tuple[str, str]] | None) -> str:
    """The rail's companion-source row: one muted link per extra source.

    A note can combine several sources — a talk and its deck, a paper and the
    repo that implements it. `--url` stays the primary one: it drives the
    layout, the poster, and what the gallery files the note under. These are
    the others, in the order the skill passed them, and they deliberately do
    **not** carry `class="watch"` — notes.py reads the primary source back out
    of that class.
    """
    links = "".join(
        f'<a href="{html.escape(url.strip(), quote=True)}" target="_blank" rel="noopener">'
        f"{html.escape(label.strip())}</a>"
        for label, url in (sources or [])
        if label and label.strip() and url and url.strip()
    )
    return f'<p class="sources">{links}</p>' if links else ""


def fonts_link(theme: str) -> str:
    """The stylesheet link for the faces this theme is set in.

    A note links only its own; the gallery hands over a second link with the
    payload when it sends the reader a theme set in different type.
    """
    return f'<link rel="stylesheet" href="{html.escape(themes.fonts_url(theme), quote=True)}">'


def slugify(title: str, maxlen: int = 60) -> str:
    """Filename-safe ASCII slug; falls back to 'notes' when nothing survives."""
    folded = unicodedata.normalize("NFKD", title)
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return slug[:maxlen].strip("-") or "notes"


def build_article_meta(span: str | None, reading_time: str | None) -> str:
    """Article masthead: published · reading time. Byline lives in the kicker."""
    return " &middot; ".join(html.escape(v) for v in (span, reading_time) if v)


def build_article_document(
    title: str,
    body: str,
    byline: str | None = None,
    span: str | None = None,
    url: str | None = None,
    lang: str = "en",
    tags: list[str] | None = None,
    sources: list[tuple[str, str]] | None = None,
    today: str | None = None,
    theme: str = themes.AUTO,
) -> str:
    today = today or datetime.date.today().isoformat()
    strings = UI_STRINGS.get(lang, UI_STRINGS["en"])
    reading_time = format_reading_time(_word_count(body), lang)
    doc = ARTICLE_TEMPLATE_PATH.read_text(encoding="utf-8")
    for token, value in {
        "{{LANG}}": html.escape(lang, quote=True),
        "{{PALETTE}}": themes.palette_css(theme),
        "{{FONTS}}": fonts_link(theme),
        "{{TITLE}}": html.escape(title),
        "{{BYLINE}}": html.escape(byline) if byline else "",
        "{{URL}}": html.escape(url or "", quote=True),
        "{{META}}": build_article_meta(span, reading_time),
        "{{SOURCES}}": sources_html(sources),
        "{{TAGS}}": tags_html(tags),
        "{{BODY}}": body.strip(),
        "{{OPEN}}": html.escape(strings["open"]),
        "{{FOOTER}}": rail_footer_html(lang, url, today),
    }.items():
        doc = doc.replace(token, value)
    if "{{" in doc:
        stray = doc[doc.index("{{"):doc.index("{{") + 30]
        raise ValueError(f"unresolved article-template.html token near {stray!r}")
    return doc


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
    tags: list[str] | None = None,
    sources: list[tuple[str, str]] | None = None,
    today: str | None = None,
    theme: str = themes.AUTO,
) -> str:
    thumb = thumbnail or (f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "")
    today = today or datetime.date.today().isoformat()
    strings = UI_STRINGS.get(lang, UI_STRINGS["en"])
    doc = TEMPLATE_PATH.read_text(encoding="utf-8")
    for token, value in {
        "{{LANG}}": html.escape(lang, quote=True),
        "{{PALETTE}}": themes.palette_css(theme),
        "{{FONTS}}": fonts_link(theme),
        "{{TITLE}}": html.escape(title),
        "{{THUMBNAIL}}": html.escape(thumb, quote=True),
        "{{URL}}": html.escape(url or "", quote=True),
        "{{META}}": build_video_meta(byline, channel_url, span, published, views),
        "{{SOURCES}}": sources_html(sources),
        "{{TAGS}}": tags_html(tags),
        "{{BODY}}": body.strip(),
        "{{WATCH}}": html.escape(strings["watch"]),
        "{{OPEN}}": html.escape(strings["open"]),
        "{{FOOTER}}": rail_footer_html(lang, url, today),
    }.items():
        doc = doc.replace(token, value)
    if "{{" in doc:
        stray = doc[doc.index("{{"):doc.index("{{") + 30]
        raise ValueError(f"unresolved template.html token near {stray!r}")
    return doc


def masthead_html(
    strings: dict[str, str],
    url: str | None,
    byline: str | None,
    video_id: str | None = None,
    thumbnail: str | None = None,
) -> str:
    """The one masthead element that tells video from article: the poster or
    the byline kicker, in the exact markup the offprint templates use, so
    notes.py reads a genre note back with the same parser.

    No kicker at all when there is no byline: the parser takes the *presence*
    of `.kicker` as "this is an article", and an empty one would send it down
    the video branch to read the date as an author.
    """
    if video_id or thumbnail:
        thumb = thumbnail or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        return (
            f'<a class="poster" href="{html.escape(url or "", quote=True)}" target="_blank" rel="noopener">'
            f'<img src="{html.escape(thumb, quote=True)}" alt="" loading="lazy">'
            f'<span class="cue">{html.escape(strings["watch"])}</span></a>'
        )
    return f'<span class="kicker">{html.escape(byline)}</span>' if byline else ""


def build_genre_document(
    genre: str,
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
    tags: list[str] | None = None,
    sources: list[tuple[str, str]] | None = None,
    today: str | None = None,
    theme: str = themes.AUTO,
) -> str:
    """A note in any genre but the offprint. `video_id` (or a thumbnail) picks
    the poster masthead and the video meta line; otherwise the kicker and the
    article one, reading time included."""
    template = GENRE_TEMPLATES[genre]
    today = today or datetime.date.today().isoformat()
    strings = UI_STRINGS.get(lang, UI_STRINGS["en"])
    if video_id or thumbnail:
        meta = build_video_meta(byline, channel_url, span, published, views)
    else:
        meta = build_article_meta(span, format_reading_time(_word_count(body), lang))
    doc = template.read_text(encoding="utf-8")
    for token, value in {
        "{{LANG}}": html.escape(lang, quote=True),
        "{{PALETTE}}": themes.palette_css(theme),
        "{{FONTS}}": fonts_link(theme),
        "{{GENRE}}": genre,
        "{{TITLE}}": html.escape(title),
        "{{MASTHEAD}}": masthead_html(strings, url, byline, video_id, thumbnail),
        "{{URL}}": html.escape(url or "", quote=True),
        "{{META}}": meta,
        "{{SOURCES}}": sources_html(sources),
        "{{TAGS}}": tags_html(tags),
        "{{BODY}}": body.strip(),
        "{{OPEN}}": html.escape(strings["open"]),
        "{{FOOTER}}": rail_footer_html(lang, url, today),
    }.items():
        doc = doc.replace(token, value)
    if "{{" in doc:
        stray = doc[doc.index("{{"):doc.index("{{") + 30]
        raise ValueError(f"unresolved {template.name} token near {stray!r}")
    return doc


def _selftest() -> int:
    assert slugify("Never Gonna Give You Up (4K)") == "never-gonna-give-you-up-4k"
    assert slugify("¿Qué es un LLM?") == "que-es-un-llm"
    assert slugify("!!!") == "notes"
    assert slugify("") == "notes"
    assert len(slugify("x" * 200)) <= 60
    assert not slugify("a" + "-" * 80 + "b").endswith("-")

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

    assert format_reading_time(1300, "en") == "6 min read"       # ceil(1300/220) = 6
    assert format_reading_time(220, "en") == "1 min read"
    assert format_reading_time(50, "en") == "1 min read"         # never "0 min read"
    assert format_reading_time(1300, "es") == "6 min de lectura"
    assert format_reading_time(0, "en") is None
    assert format_reading_time(None, "en") is None

    assert _word_count("<p>one <strong>two</strong></p><p>three</p>") == 3
    assert _word_count("<p>a &amp; b</p>") == 3  # entity decodes before counting
    assert _word_count("") == 0

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

    # Article path: no --video-id, so this is what main() now dispatches to by
    # default. Header fields stay escaped, no stray tokens, chrome localises,
    # and the byline lives in the kicker rather than the meta line.
    article_body = (
        "<h2>Executive summary</h2><p>" + ("word " * 300) + "</p>"
        "<h2>Section outline</h2><ul>"
        "<li><a href=\"https://x.test#a\"><strong>First</strong></a> — one</li>"
        "<li><strong>Second</strong> — two</li>"  # no anchor: page has no stable anchors
        "</ul>"
    )
    article_doc = build_article_document(
        "5 > 3 & rising", article_body,
        byline="A & B", url="https://x.test/?a=1&b=2", today="2026-01-01",
    )
    assert "<title>5 &gt; 3 &amp; rising</title>" in article_doc
    assert "A &amp; B" in article_doc  # the kicker
    assert 'id="index"' in article_doc
    assert 'id="spy"' in article_doc
    assert "{{" not in article_doc
    assert ">Open original <" in article_doc, "watch link defaults to English"
    assert "Noted from" in article_doc, "footer defaults to English"
    assert "2 min read" in article_doc  # ceil(300/220) = 2

    article_doc_es = build_article_document(
        "Título", "<h2>Resumen</h2><p>ok</p>",
        byline="Sitio", url="https://x.test", lang="es", today="2026-01-01",
    )
    assert ">Ver original <" in article_doc_es, "watch link localises to Spanish"
    assert "Notas de" in article_doc_es, "footer localises to Spanish"
    assert "Open original" not in article_doc_es and "Noted from" not in article_doc_es, (
        "no English chrome leaking into a Spanish note"
    )
    assert "{{" not in article_doc_es

    # Tags: first is primary, the rest are extras, and no --tag at all still
    # produces a row so every note is filed somewhere.
    assert tags_html(["AI", "Engineering"]) == (
        '<p class="tags"><span class="tag is-primary">AI</span>'
        '<span class="tag">Engineering</span></p>'
    )
    assert tags_html(None) == "", "no tags at all means no tag row, not an Unknown badge"
    assert tags_html([DEFAULT_TAG]) == "", "DEFAULT_TAG alone is still nothing to show"
    assert tags_html(["unknown"]) == "", "the filter is case-insensitive"
    assert tags_html([DEFAULT_TAG, "AI"]) == '<p class="tags"><span class="tag is-primary">AI</span></p>', (
        "DEFAULT_TAG is dropped even mixed with a real tag, which promotes AI to primary"
    )
    assert tags_html(["  ", "AI"]) == '<p class="tags"><span class="tag is-primary">AI</span></p>'
    assert '<span class="tag is-primary">R &amp; D</span>' in tags_html(["R & D"]), "tag names are escaped"
    assert '<span class="tag is-primary">AI</span>' in build_video_document(
        "T", "<h2>S</h2><p>ok</p>", url="https://youtu.be/a", video_id="a",
        tags=["AI"], today="2026-01-01",
    ), "the video rail carries the tag row"
    assert '<p class="tags">' not in article_doc, (
        "an untagged render gets no tag row at all, not an Unknown badge"
    )

    # Companion sources: one muted link each, never class="watch" — notes.py
    # reads the primary source back out of that class and would pick the wrong
    # one. No --source at all leaves the rail exactly as it was.
    combined = sources_html([("Slides", "https://docs.google.test/d/1?a=1&b=2")])
    assert combined.startswith('<p class="sources">') and ">Slides</a>" in combined
    assert "a=1&amp;b=2" in combined, "companion URLs are escaped"
    assert 'class="watch"' not in combined
    both = sources_html([("Slides", "https://deck.test/d/1"), ("Repo", "https://github.test/r")])
    assert both.count("<a ") == 2, "every companion is rendered, not just the first"
    assert both.index(">Slides<") < both.index(">Repo<"), "in the order the skill passed them"
    assert sources_html(None) == "" and sources_html([]) == ""
    assert sources_html([("  ", "https://x.test")]) == "", "a label-less source is dropped"
    assert sources_html([("Deck", "  ")]) == "", "a URL-less source is dropped"
    assert '<p class="sources">' not in article_doc, "no --source means no companion row"
    assert '<p class="sources">' not in video_doc
    for doc in (
        build_video_document(
            "T", "<h2>S</h2><p>ok</p>", url="https://youtu.be/a", video_id="a",
            sources=[("Slides", "https://docs.google.test/d/1")], today="2026-01-01",
        ),
        build_article_document(
            "T", "<h2>S</h2><p>ok</p>", url="https://x.test",
            sources=[("Slides", "https://docs.google.test/d/1")], today="2026-01-01",
        ),
    ):
        assert '<p class="sources">' in doc, "both layouts carry the companion row"
        assert "{{" not in doc

    # Themes: a note carries the values it was rendered with and no catalogue,
    # which is what keeps a note written today from going stale when a theme is
    # added tomorrow. It never learns a theme's name.
    builders = {
        "video": lambda **kw: build_video_document("T", "<p>ok</p>", video_id="abc123", **kw),
        "article": lambda **kw: build_article_document("T", "<p>ok</p>", **kw),
    }
    for layout, build in builders.items():
        auto = build(today="2026-01-01")
        assert auto.count(":root {") >= 2 and "prefers-color-scheme: dark" in auto, (
            f"{layout}: auto bakes the light/dark pair — it cannot resolve to one set"
        )
        assert "data-theme" not in auto, "a note names no theme"
        for name, palette in themes.THEMES.items():
            doc = build(theme=name, today="2026-01-01")
            where = f"{name} in {layout}"
            assert "{{" not in doc, where
            for token in ("paper", "ink", "pen"):
                assert f"--{token}: {palette[token]};" in doc, f"{where}: --{token}"
            stack = themes.STACKS[palette["stack"]]
            assert f"--font-display: {stack['display']};" in doc, where
            assert f"--display-weight: {stack['weight']};" in doc, where
            assert fonts_link(name) in doc, f"{where}: wrong font stylesheet"
            for other, sibling in themes.THEMES.items():
                if other != name:
                    assert sibling["paper"] not in doc, f"{where}: {other} leaked in"
        assert build(theme="nonsense", today="2026-01-01").count(":root {") == auto.count(":root {"), (
            "an unknown name degrades to auto"
        )

    assert build_article_meta(None, None) == ""
    assert build_article_meta("Jan 1, 2026", None) == "Jan 1, 2026"
    assert "&middot;" in build_article_meta("Jan 1, 2026", "6 min read")

    # Genres: one template each; the masthead decides video (poster) or
    # article (kicker), and the whole parse contract notes.py relies on holds.
    for genre in GENRE_TEMPLATES:
        as_video = build_genre_document(
            genre, "T", "<h2>Description</h2><p>ok</p>",
            byline="Chef", channel_url="https://youtube.com/@x", span="11 min",
            url="https://youtu.be/abc123", video_id="abc123", lang="es", tags=["Cocina"],
            today="2026-01-01",
        )
        assert f'<html lang="es" data-genre="{genre}">' in as_video, genre
        assert '<a class="poster"' in as_video and '<span class="cue">Ver</span>' in as_video, (
            "video masthead, with the cue localised by the builder itself"
        )
        assert '<span class="kicker">' not in as_video
        assert '<article id="body">' in as_video and 'id="index"' in as_video
        assert as_video.index('<p class="tags">') < as_video.index('<div id="index">'), (
            "the tag row sits right above the index — retag.py's insertion anchor"
        )
        assert ">Ver original <" in as_video and "Notas de" in as_video, "Spanish chrome"
        assert "{{" not in as_video

        as_article = build_genre_document(
            genre, "T", "<p>" + ("word " * 300) + "</p>",
            byline="Sitio", span="Jan 1, 2026", url="https://x.test", today="2026-01-01",
        )
        assert '<span class="kicker">Sitio</span>' in as_article
        assert '<a class="poster"' not in as_article
        assert "Jan 1, 2026 &middot; 2 min read" in as_article, "article meta, reading time included"

        bare = build_genre_document(genre, "T", "<p>x</p>", url="https://x.test", today="2026-01-01")
        assert '<span class="kicker">' not in bare, (
            "no byline, no kicker — an empty one would send notes.py down the video branch"
        )
        themed = build_genre_document(genre, "T", "<p>x</p>", theme="barbie", today="2026-01-01")
        assert f'<html lang="en" data-genre="{genre}">' in themed, "genre yes, theme name no"
        assert "--paper: #fff0f6;" in themed, "the genre templates take resolved values too"

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
    ap.add_argument("--url", default=None, help="Canonical URL of the primary source")
    ap.add_argument(
        "--source", action="append", nargs=2, metavar=("LABEL", "URL"), default=None,
        help="Companion source combined into this note; repeatable",
    )
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
    ap.add_argument(
        "--tag", action="append", default=None,
        help=f"Topic tag; repeatable, first is the primary one (default: {DEFAULT_TAG})",
    )
    ap.add_argument("--out-dir", default=None, help=f"Output dir (default: {DEFAULT_OUT_DIR})")
    ap.add_argument("--theme", default=None,
                    help=f"{'|'.join(themes.NAMES)} (default: ~/take-notes/config.json, else auto)")
    ap.add_argument("--genre", default=DEFAULT_GENRE,
                    help=f"{'|'.join(GENRES)}: the note's content shape (default: {DEFAULT_GENRE})")
    ap.add_argument("--no-open", action="store_true", help="Do not open a browser")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.title:
        ap.error("--title is required")

    # Decode explicitly: text-mode stdin follows the locale on Windows (cp1252),
    # which turns UTF-8 body bytes into mojibake the UTF-8 write then bakes in.
    body = sys.stdin.buffer.read().decode("utf-8")
    if not body.strip():
        print("render: no body HTML on stdin", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{datetime.date.today().isoformat()}-{slugify(args.title)}.html"

    # A flag beats the config for this note, like --lang; an unknown name is
    # reported rather than silently applied.
    if args.theme is not None and args.theme not in themes.NAMES:
        print(f"render: unknown theme {args.theme!r} — pick one of {', '.join(themes.NAMES)}",
              file=sys.stderr)
        return 1
    theme = args.theme or themes.configured_theme()
    if args.genre not in GENRES:
        print(f"render: unknown genre {args.genre!r} — pick one of {', '.join(GENRES)}",
              file=sys.stderr)
        return 1

    # Localise raw video values; anything already human-readable passes through.
    # Done before the dispatch so every genre's video masthead reads the same.
    published = format_date(args.published, args.lang) or args.published
    views = format_count(args.views, args.lang) or args.views
    span = format_duration(args.duration, args.lang) or args.span

    if args.genre != DEFAULT_GENRE:
        document = build_genre_document(
            args.genre, args.title, body,
            byline=args.byline, channel_url=args.channel_url, span=span, url=args.url,
            video_id=args.video_id, thumbnail=args.thumbnail,
            published=published, views=views, lang=args.lang, tags=args.tag,
            sources=args.source, theme=theme,
        )
    elif args.video_id:
        document = build_video_document(
            args.title, body,
            byline=args.byline, channel_url=args.channel_url, span=span, url=args.url,
            video_id=args.video_id, thumbnail=args.thumbnail,
            published=published, views=views, lang=args.lang, tags=args.tag,
            sources=args.source, theme=theme,
        )
    else:
        document = build_article_document(
            args.title, body,
            byline=args.byline, span=args.span, url=args.url, lang=args.lang,
            tags=args.tag, sources=args.source, theme=theme,
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
