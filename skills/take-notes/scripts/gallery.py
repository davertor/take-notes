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
import base64
import html
import json
import os
import re
import sys
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import themes  # noqa: E402
from notes import (  # noqa: E402
    DEFAULT_TAG, NOTES_DIR, Note, collect, fold, length_of, read_config,
)


DEFAULT_OUT = Path.home() / "take-notes" / "gallery.html"
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "assets" / "gallery-template.html"
SKILL_PATH = Path(__file__).resolve().parent.parent / "SKILL.md"

# Two of the three install routes never auto-update, and a stale copy has no
# symptom — it just quietly lacks whatever the README shows. The gallery is
# where the check goes: it is rebuilt on demand, so a slow or failed request
# delays nothing anyone is waiting on, unlike the note-writing path.
REPO_URL = "https://github.com/davertor/take-notes"
LATEST_URL = "https://raw.githubusercontent.com/davertor/take-notes/main/.claude-plugin/plugin.json"
NO_CHECK_ENV = "TAKE_NOTES_NO_UPDATE_CHECK"

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
        "update": "take-notes {latest} is out — you have {local}. Update: {url}",
        "theme_label": "Theme",
        "theme_auto": "Auto",
        "fieldguide": "field guide",
        "recipe": "recipe",
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
        "update": "take-notes {latest} ya está disponible — tienes la {local}. Actualiza: {url}",
        "theme_label": "Tema",
        "theme_auto": "Sistema",
        "fieldguide": "guía",
        "recipe": "receta",
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
    # The genre label only exists for the genres that have one: an offprint is
    # the default shape and gets no label on the card, so nothing to search by.
    genre = strings.get(note.genre, "") if note.genre != "offprint" else ""
    search = html.escape(fold(f"{note.title} {note.byline} {note.detail} {genre}".strip()), quote=True)
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
    genre_label = f'<span class="genre">{html.escape(genre)}</span>' if genre else ""
    parts.append(
        '<span class="foot">'
        f'<span class="kind">{html.escape(strings[note.kind])}</span>{genre_label}{tag}'
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


def build_payloads() -> str:
    """Every theme's value set, base64-JSON, for the menu to hand to a note.

    The gallery is the only file that holds the catalogue — it is rebuilt on
    demand, so a theme added later reaches it for free. A note receives values
    and never a name, which is why a note written before a theme existed can
    still be read in it.
    """
    loads = {name: themes.payload(name) for name in themes.NAMES}
    packed = {
        name: base64.b64encode(
            json.dumps(load, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        for name, load in loads.items() if load
    }
    return json.dumps(packed, separators=(",", ":"))


def build_swatches(theme: str, strings: dict[str, str]) -> str:
    """One button per theme, `auto` first, each showing the paper it prints on
    and the pen it marks with.

    `aria-pressed` is set for the theme baked into this file; the script fixes
    it up on load when the browser remembers a different one.
    """
    buttons = []
    for name in themes.NAMES:
        label = strings["theme_auto"] if name == themes.AUTO else name.capitalize()
        palette = themes.THEMES.get(name, themes.THEMES[themes.AUTO_LIGHT])
        style = f'--sw-paper: {palette["paper"]}; --sw-pen: {palette["pen"]}'
        buttons.append(
            f'        <button type="button" class="swatch" data-set-theme="{name}"'
            f' aria-pressed="{"true" if name == theme else "false"}">'
            f'<i style="{style}"></i>{html.escape(label)}</button>'
        )
    return "\n".join(buttons)


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
    theme: str = themes.AUTO,
    notice: str = "",
) -> str:
    """The whole page as a string.

    `theme` is a parameter rather than a config read, exactly like `lang`: the
    caller resolves it, so this stays a pure function of its arguments and the
    selftest does not depend on whatever is in the running user's config.
    """
    strings = UI.get(lang, UI["en"])
    cards = "\n".join(card_html(n, i + 1, out_dir, strings) for i, n in enumerate(notes))
    doc = TEMPLATE_PATH.read_text(encoding="utf-8")
    for token, value in {
        "{{LANG}}": html.escape(lang, quote=True),
        "{{THEMES}}": themes.catalogue_css(),
        "{{THEME_ATTR}}": themes.attr(theme),
        "{{THEME_LABEL}}": html.escape(strings["theme_label"]),
        "{{SWATCHES}}": build_swatches(theme, strings),
        "{{PAYLOADS}}": build_payloads(),
        "{{TITLE}}": html.escape(strings["title"]),
        "{{TALLY}}": build_tally(notes, strings),
        "{{PLACEHOLDER}}": html.escape(strings["placeholder"], quote=True),
        "{{CHIPS}}": build_chips(notes),
        "{{CARDS}}": cards or f'<p class="blank">{html.escape(strings["empty"])}</p>',
        "{{NOMATCH}}": html.escape(strings["nomatch"]),
        "{{FOOTER}}": strings["built"].format(dir=html.escape(str(notes_dir)))
        + (f" · {html.escape(notice)}" if notice else ""),
    }.items():
        doc = doc.replace(token, value)
    if "{{" in doc:
        stray = doc[doc.index("{{"):doc.index("{{") + 30]
        raise ValueError(f"unresolved gallery-template.html token near {stray!r}")
    return doc


def installed_version() -> str:
    """The `version` this copy of the skill declares, or "" if it can't be read."""
    try:
        found = re.search(r'^\s*version:\s*"([^"]+)"', SKILL_PATH.read_text(encoding="utf-8"), re.M)
    except OSError:
        return ""
    return found.group(1) if found else ""


def latest_version(timeout: float = 2.5) -> str:
    """The version on `main`, or "" when the check can't be made.

    Every failure is the same answer — say nothing. Offline, behind a proxy,
    GitHub down, a body that isn't the JSON expected: none of them are the
    user's problem, and none may keep them from reading their own notes. This
    is the one place a bare `except` is right, because the fallback is silence.
    """
    try:
        with urllib.request.urlopen(LATEST_URL, timeout=timeout) as response:  # noqa: S310
            return str(json.loads(response.read(4096))["version"])
    except Exception:
        return ""


def outdated(local: str, latest: str) -> bool:
    """True only when `local` is genuinely behind `latest`.

    Compared as numbers, not strings, so "1.10.0" is newer than "1.9.0" — and
    a working copy *ahead* of main (a release branch mid-flight) is never told
    to downgrade. An unparseable version on either side warns about nothing.
    """
    try:
        return tuple(int(p) for p in local.split(".")) < tuple(int(p) for p in latest.split("."))
    except ValueError:
        return False


def update_notice(local: str, latest: str, strings: dict[str, str]) -> str:
    """One line naming both versions, or "" when there is nothing to say."""
    if not (local and latest and outdated(local, latest)):
        return ""
    return strings["update"].format(local=local, latest=latest, url=REPO_URL)


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

    # Themes: every palette ships in the page, and the chosen one is baked onto
    # <html> so the first paint is already right.
    for name in themes.THEMES:
        assert f'html[data-theme="{name}"]' in page, f"{name} is missing from the page"
    assert 'class="themer"' in page and page.count('class="swatch"') == len(themes.NAMES)
    assert "<html lang=\"en\">" in page, "auto bakes no attribute at all"
    assert 'aria-pressed="true"' in page, "the theme in force is marked in the menu"

    baked = build_gallery([video], out_dir, notes_dir, theme="bureau")
    assert '<html lang="en" data-theme="bureau">' in baked
    assert '"bureau" aria-pressed="true"' in baked, "the baked theme is the pressed swatch"
    assert "{{" not in baked

    spanish = build_gallery([video], out_dir, notes_dir, lang="es")
    assert "<summary>Tema</summary>" in spanish, "the menu label is translated"

    # Genre: a label on the card for every genre but the offprint, searchable,
    # and never a KeyError for a note the gallery has not heard of.
    assert 'class="genre"' not in page, "an offprint carries no genre label"
    recipe = parse_note(
        notes_dir / "2026-08-20-dish.html",
        render.build_genre_document(
            "recipe", "Tortilla", "<h2>Description</h2><p>Eggs.</p>",
            byline="Chef", channel_url="https://youtube.com/@c", span="9 min",
            url="https://youtu.be/abc123", video_id="abc123", tags=["Cocina"],
        ),
    )
    shelf = build_gallery([recipe, video], out_dir, notes_dir, lang="es")
    assert '<span class="kind">vídeo</span><span class="genre">receta</span>' in shelf, (
        "the genre label follows the kind on the card foot"
    )
    assert 'data-search="tortilla chef 9 min receta"' in shelf, "the label is searchable, appended last"
    assert shelf.count('class="genre"') == 1, "the offprint on the same shelf gets none"
    assert "{{" not in shelf

    # Themes, the seam that has no other test: the gallery packs a value set
    # into a card's link and the note's inline script unpacks it. The two live
    # in different files and different languages, so assert they still agree —
    # a rename on either side is silent otherwise.
    packed = json.loads(build_payloads())
    assert set(packed) == set(themes.THEMES), "one payload per theme, and auto needs none"
    for name, blob in packed.items():
        assert json.loads(base64.b64decode(blob)) == themes.payload(name), name

    note_template = Path(__file__).resolve().parent.parent / "assets" / "template.html"
    note = note_template.read_text(encoding="utf-8")
    fragment = re.search(r"/\[#&\]t=\(\[([^\]]+)\]\+\)/", note)
    assert fragment, "the note no longer reads a #t= payload — did the head script change?"
    allowed = re.compile(f"^[{re.escape(fragment.group(1))}]+$".replace("\\-", "-"))
    for name, blob in packed.items():
        assert allowed.match(blob), f"{name}: base64 the note's own regex would not match"
    for key in ("vars", "scheme", "fonts"):
        assert f"t.{key}" in note, f"the note stopped reading {key} out of the payload"

    themed = build_gallery([video], out_dir, notes_dir, theme="bureau")
    for name in themes.THEMES:
        assert f'html[data-theme="{name}"]' in themed, (
            f"{name} missing: the gallery is the one file that carries the catalogue"
        )
    assert 'data-set-theme="barbie"' in themed and "window.themePayloads=" in themed

    # The update warning: compared as numbers, and silent unless behind. No
    # network here — latest_version() is a thin wrapper whose every failure is
    # already the same as having nothing to say.
    assert outdated("1.2.0", "1.3.0") and outdated("1.9.0", "1.10.0")
    assert not outdated("1.3.0", "1.3.0")
    assert not outdated("1.4.0", "1.3.0"), "a copy ahead of main must not be told to update"
    assert not outdated("1.2.0", ""), "a failed check must warn about nothing"
    assert not outdated("1.2.0", "next"), "an unparseable version must warn about nothing"
    assert not update_notice("1.3.0", "1.3.0", UI["en"])
    for lang in UI:
        stale = update_notice("1.2.0", "1.3.0", UI[lang])
        assert "1.2.0" in stale and "1.3.0" in stale, f"{lang}: the notice must name both versions"
        assert html.escape(stale) in build_gallery([video], out_dir, notes_dir, notice=stale), (
            f"{lang}: the notice never reached the footer"
        )

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
    ap.add_argument("--theme", default=None,
                    help=f"{'|'.join(themes.NAMES)} for this build only; themes.py --set makes it stick")
    ap.add_argument("--no-open", action="store_true", help="Do not open a browser")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    notes_dir = Path(args.notes_dir).expanduser() if args.notes_dir else NOTES_DIR
    out = Path(args.out).expanduser() if args.out else DEFAULT_OUT
    lang = args.lang if args.lang in UI else config_lang()
    # A flag beats the config for this one build, like --lang; an unknown name
    # is reported rather than silently applied.
    if args.theme is not None and args.theme not in themes.NAMES:
        print(f"gallery: unknown theme {args.theme!r} — pick one of {', '.join(themes.NAMES)}",
              file=sys.stderr)
        return 1
    theme = args.theme or themes.configured_theme()

    if not notes_dir.is_dir():
        print(f"gallery: no notes directory at {notes_dir}", file=sys.stderr)
        return 1

    notice = ""
    if not os.environ.get(NO_CHECK_ENV):
        notice = update_notice(installed_version(), latest_version(), UI.get(lang, UI["en"]))

    notes = collect(notes_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        build_gallery(notes, out.parent, notes_dir, lang=lang, theme=theme, notice=notice),
        encoding="utf-8",
    )

    print(f"gallery: {len(notes)} note(s) -> {out}")
    if notice:
        print(f"gallery: {notice}", file=sys.stderr)
    if not args.no_open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
