#!/usr/bin/env -S uv run --script
"""Build a browsable gallery of every note in ~/take-notes/html_reports.

Reads the notes themselves — no database, no sidecar index — through notes.py,
which owns the parsing. That keeps notes written before this script existed
visible, and means nothing to keep in sync when a note is deleted by hand.

    uv run gallery.py            # build ~/take-notes/gallery.html and open it
    uv run gallery.py --no-open
"""
from __future__ import annotations

import argparse
import html
import os
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notes import (  # noqa: E402
    DEFAULT_TAG, NOTES_DIR, Note, collect, fold, length_of, read_config,
)


DEFAULT_OUT = Path.home() / "take-notes" / "gallery.html"
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "gallery-template.html"

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
        "built": "{dir}",
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
        "built": "{dir}",
    },
}


def tags_of(note: Note) -> tuple[str, ...]:
    """Every tag on a note — empty when it has none.

    DEFAULT_TAG never appears here: render.py already leaves it out of the
    rendered tag row (see tags_html), so an untagged note is simply absent
    from every chip rather than filed under a fake one.
    """
    return note.tags


def card_html(note: Note, number: int, out_dir: Path, strings: dict[str, str]) -> str:
    href = html.escape(os.path.relpath(note.path, out_dir), quote=True)
    search = html.escape(fold(f"{note.title} {note.byline} {note.detail}"), quote=True)
    # Pipe-delimited, folded, with both ends closed, so the template's JS can
    # match a whole tag ("|ai|") without "ai" also hitting "|air gap|".
    tags = html.escape("|" + "|".join(fold(t) for t in tags_of(note)) + "|", quote=True)
    # The full meta line is searchable but too long for a 17rem card: the foot
    # keeps the length and the filing date, the two things you scan a shelf by.
    stamp = " &middot; ".join(html.escape(v) for v in (length_of(note.detail), note.date) if v)

    if note.thumbnail:
        plate = (
            f'<span class="plate"><img src="{html.escape(note.thumbnail, quote=True)}"'
            ' alt="" loading="lazy"></span>'
        )
    else:
        # Filing number only: the byline is already the card's kicker, and a
        # plate that repeats it just prints the same words twice.
        plate = f'<span class="plate is-blank"><span class="mark">{number:02d}</span></span>'

    parts = [
        f'<a class="card" href="{href}" data-search="{search}" data-tags="{tags}">',
        plate,
        '<span class="body">',
    ]
    if note.byline:
        parts.append(f'<span class="kicker">{html.escape(note.byline)}</span>')
    parts.append(f'<span class="title">{html.escape(note.title)}</span>')
    if note.excerpt:
        parts.append(f'<span class="excerpt">{html.escape(note.excerpt)}</span>')
    parts.append("</span>")
    # Only the primary tag on the card: the extras are still filterable through
    # data-tags, but a 17rem foot has room for one label, not four. DEFAULT_TAG
    # is excluded even though a note rendered before this check existed can
    # still carry it literally — new renders never will (see render.tags_html).
    tag = (
        f'<span class="tag">{html.escape(note.tag)}</span>'
        if note.tag and fold(note.tag) != fold(DEFAULT_TAG) else ""
    )
    parts.append(
        '<span class="foot">'
        f'<span class="kind">{html.escape(strings[note.kind])}</span>{tag}'
        f'<span class="date">{stamp}</span></span>'
    )
    parts.append("</a>")
    return "".join(parts)


def build_chips(notes: list[Note]) -> str:
    """The chip row: one button per distinct real tag across the collected
    notes, alphabetical.

    DEFAULT_TAG never gets a chip — it is the skill's internal fallback for
    "nothing fit," not a topic to filter by. A note carrying it literally
    (rendered before this check existed) is simply absent from every chip.
    """
    seen: dict[str, str] = {}
    for note in notes:
        for tag in tags_of(note):
            if fold(tag) == fold(DEFAULT_TAG):
                continue
            seen.setdefault(fold(tag), tag)
    if not seen:
        return ""
    order = sorted(seen.items())
    chips = "".join(
        f'<button class="chip" type="button" aria-pressed="false"'
        f' data-tag="{html.escape(folded, quote=True)}">{html.escape(name)}</button>'
        for folded, name in order
    )
    return f'<div class="chips" id="chips">{chips}</div>'


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
) -> str:
    strings = UI.get(lang, UI["en"])
    cards = "\n".join(card_html(n, i + 1, out_dir, strings) for i, n in enumerate(notes))
    doc = TEMPLATE_PATH.read_text(encoding="utf-8")
    for token, value in {
        "{{LANG}}": html.escape(lang, quote=True),
        "{{TITLE}}": html.escape(strings["title"]),
        "{{TALLY}}": build_tally(notes, strings),
        "{{PLACEHOLDER}}": html.escape(strings["placeholder"], quote=True),
        "{{CHIPS}}": build_chips(notes),
        "{{CARDS}}": cards or f'<p class="blank">{html.escape(strings["empty"])}</p>',
        "{{NOMATCH}}": html.escape(strings["nomatch"]),
        "{{FOOTER}}": strings["built"].format(dir=html.escape(str(notes_dir))),
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
    value = read_config().get("language")
    return value if value in UI else "en"


def _selftest() -> int:
    import render  # the templates notes.py parses are render.py's output
    from notes import parse_note

    out_dir = Path("/tmp/take-notes")
    notes_dir = out_dir / "html_reports"

    video = parse_note(
        notes_dir / "2026-08-18-rising.html",
        render.build_video_document(
            "5 > 3 & rising",
            "<h2>Executive summary</h2><p>A &amp; B argue that markets rise.</p>",
            byline="La Pizarra", channel_url="https://youtube.com/@x", span="11 min",
            url="https://youtu.be/abc123", video_id="abc123", views="13.2K views",
            tags=["Investing", "Inversión"],
        ),
    )
    article = parse_note(
        notes_dir / "2026-08-01-titulo.html",
        render.build_article_document(
            "Título ñ",
            "<h2>Executive summary</h2><p>" + ("palabra " * 80) + "</p>",
            byline="Sitio & Co", span="Jan 1, 2026", url="https://x.test/?a=1&b=2",
        ),
    )

    page = build_gallery([video, article], out_dir, notes_dir)
    assert "{{" not in page
    assert 'href="html_reports/2026-08-18-rising.html"' in page, "links are relative to the gallery"
    assert "<span class=\"title\">5 &gt; 3 &amp; rising</span>" in page, "card fields stay escaped"
    assert 'data-search="5 &gt; 3 &amp; rising la pizarra' in page, "filter haystack is folded"
    assert 'titulo n' in build_gallery([article], out_dir, notes_dir), (
        "accents are stripped from the haystack, matching the template's filter JS"
    )
    assert ">02<" in page and "is-blank" in page, "the poster-less note gets a filing plate"
    assert "2 notes &middot; 2026-08-01 – 2026-08-18" in page

    # Tags: the card shows the primary one, data-tags carries every tag folded
    # and pipe-delimited, and one chip exists per distinct real tag.
    assert '<span class="tag">Investing</span>' in page, "the card shows the primary tag"
    assert 'data-tags="|investing|inversion|"' in page, (
        "every tag, folded and pipe-delimited so the template matches whole tags"
    )
    assert f'data-tag="{DEFAULT_TAG.lower()}"' not in page, (
        "DEFAULT_TAG is an internal fallback, never a chip"
    )
    assert page.count('class="chip"') == 2, "one chip per distinct real tag, not per note"
    article_page = build_gallery([article], out_dir, notes_dir)
    assert '<span class="tag">' not in article_page, (
        "the untagged-by-default article shows no tag label on its own card"
    )

    # A note written before tags existed has no tags at all — absent from
    # every chip, same as an explicitly-untagged one.
    legacy = parse_note(notes_dir / "2026-07-01-old.html", "<html><body><p>hi</p></body></html>")
    assert tags_of(legacy) == (), "no fake DEFAULT_TAG fallback here — see tags_of"
    legacy_page = build_gallery([legacy], out_dir, notes_dir)
    assert f'data-tag="{DEFAULT_TAG.lower()}"' not in legacy_page
    assert '<span class="tag">' not in legacy_page, "no tag label on a card with no tag of its own"

    # A note rendered before this check existed can still carry DEFAULT_TAG
    # literally in its tag row — must not surface it either.
    stale = parse_note(
        notes_dir / "2026-06-01-stale.html",
        '<html><body><p class="tags"><span class="tag is-primary">Unknown</span></p></body></html>',
    )
    assert stale.tag == DEFAULT_TAG, "sanity: the parser still reads what is literally on disk"
    stale_page = build_gallery([stale], out_dir, notes_dir)
    assert '<span class="tag">' not in stale_page, "a literal Unknown row from an old render is still hidden"
    assert f'data-tag="{DEFAULT_TAG.lower()}"' not in stale_page

    page_es = build_gallery([video], out_dir, notes_dir, lang="es")
    assert "1 nota &middot; 2026-08-18" in page_es
    assert ">vídeo<" in page_es and "notes &middot;" not in page_es, "no English chrome in a Spanish gallery"

    empty = build_gallery([], out_dir, notes_dir)
    assert "No notes yet" in empty and "{{" not in empty
    assert 'class="chips"' not in empty, "no chip row at all when there is nothing to file"

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
