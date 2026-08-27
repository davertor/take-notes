#!/usr/bin/env -S uv run --script
"""Read a Google Slides deck as per-slide text, speaker notes, and image URLs.

Google exports any link-visible deck as `.pptx` without an API key, and a pptx
is a zip of XML — so this is stdlib only, same as the rest of the skill.

The one thing the export gives that nothing else does is the **page id** of each
slide, hidden in the shape names of its notes page (`Google Shape;117;<id>:notes`).
That id is what `export/png?pageid=<id>` needs, which is how a diagram built from
native shapes — boxes and arrows that exist in no image file — reaches the note.

    uv run slides.py https://docs.google.com/presentation/d/<ID>/edit
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET


A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

EXPORT = "https://docs.google.com/presentation/d/{id}/export/{fmt}"
PNG = "https://docs.google.com/presentation/d/{id}/export/png?pageid={page}"
PPTX_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

# A notes page names its own slide's page id in every shape name it carries.
PAGE_ID = re.compile(r'name="Google Shape;\d+;([^";:]+):notes"')
# Content-Disposition: the RFC 5987 form first, since it survives non-ASCII.
FILENAME_STAR = re.compile(r"filename\*=UTF-8''([^;]+)", re.I)
FILENAME = re.compile(r'filename="([^"]+)"', re.I)


def presentation_id(source: str) -> str:
    """Pull the deck id out of any Slides URL, or pass a bare id through."""
    match = re.search(r"/(?:presentation|d)/(?:d/)?([A-Za-z0-9_-]{20,})", source)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", source.strip()):
        return source.strip()
    raise SystemExit(f"Not a Google Slides URL or id: {source}")


def fetch_pptx(deck_id: str) -> tuple[bytes, str | None]:
    """Download the deck's pptx export. Returns the bytes and the deck title.

    Google puts the real title only in the Content-Disposition filename — its
    pptx export carries no docProps/core.xml to read it from.
    """
    url = EXPORT.format(id=deck_id, fmt="pptx")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310 — fixed https host
            content_type = response.headers.get("Content-Type", "")
            payload = response.read()
            disposition = response.headers.get("Content-Disposition", "")
    except urllib.error.HTTPError as exc:
        raise SystemExit(_no_access(deck_id, f"HTTP {exc.code}")) from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not reach docs.google.com: {exc.reason}") from exc

    if PPTX_TYPE not in content_type:
        # A deck the link cannot open answers with a sign-in page, not an error.
        raise SystemExit(_no_access(deck_id, f"got {content_type or 'no content type'}"))
    return payload, _title_from(disposition)


def _title_from(disposition: str) -> str | None:
    match = FILENAME_STAR.search(disposition)
    name = urllib.parse.unquote(match.group(1)) if match else None
    if name is None:
        plain = FILENAME.search(disposition)
        name = plain.group(1) if plain else None
    if not name:
        return None
    return re.sub(r"\.pptx$", "", name).strip() or None


def _no_access(deck_id: str, detail: str) -> str:
    return (
        f"Cannot export presentation {deck_id} ({detail}).\n"
        "The deck is not readable without signing in. Set its sharing to "
        '"Anyone with the link → Viewer", or paste the content directly.'
    )


def slide_order(archive: zipfile.ZipFile) -> list[str]:
    """Slide parts in presentation order, not filename order.

    slide12.xml sorts before slide2.xml, and a reordered deck keeps its original
    filenames — so the order has to come from sldIdLst, via the relationship ids.
    """
    rels = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
    targets = {
        rel.get("Id"): "ppt/" + rel.get("Target", "").removeprefix("../")
        for rel in rels.iter(f"{REL}Relationship")
    }
    presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
    parts = [
        targets.get(entry.get(f"{R}id"))
        for entry in presentation.iter(f"{P}sldId")
    ]
    return [part for part in parts if part and part in archive.namelist()]


def notes_part(archive: zipfile.ZipFile, slide_part: str) -> str | None:
    name = slide_part.rsplit("/", 1)[-1]
    rels_path = f"ppt/slides/_rels/{name}.rels"
    if rels_path not in archive.namelist():
        return None
    rels = ET.fromstring(archive.read(rels_path))
    for rel in rels.iter(f"{REL}Relationship"):
        if rel.get("Type", "").endswith("/notesSlide"):
            return "ppt/" + rel.get("Target", "").removeprefix("../")
    return None


def _paragraphs(node: ET.Element) -> list[str]:
    """Every non-empty paragraph under `node`, in document order.

    Iterating paragraphs rather than shapes picks up table cells and grouped
    shapes for free — they nest the same `a:p` elements.
    """
    lines = []
    for paragraph in node.iter(f"{A}p"):
        text = "".join(run.text or "" for run in paragraph.iter(f"{A}t")).strip()
        if text:
            lines.append(text)
    return lines


def slide_visuals(root: ET.Element) -> dict[str, int]:
    """What is drawn on a slide, as the counts that say whether it is worth a figure.

    `a:blip` rather than `p:pic`: Google exports a pasted image as a picture
    fill on an ordinary shape, so a deck full of screenshots has no `p:pic` at
    all. Connectors are the tell for a hand-drawn diagram — boxes alone are a
    layout, boxes joined by arrows are an explanation.
    """
    return {
        "images": sum(1 for _ in root.iter(f"{A}blip")),
        "shapes": sum(1 for _ in root.iter(f"{P}sp")),
        "connectors": sum(1 for _ in root.iter(f"{P}cxnSp")),
    }


def slide_text(archive: zipfile.ZipFile, part: str) -> tuple[list[str], dict[str, int]]:
    """A slide's text lines and its visual counts."""
    root = ET.fromstring(archive.read(part))
    return _paragraphs(root), slide_visuals(root)


def notes_text(archive: zipfile.ZipFile, part: str) -> tuple[str | None, list[str]]:
    """A notes page's slide page id and the speaker notes written on it."""
    raw = archive.read(part)
    match = PAGE_ID.search(raw.decode("utf-8", "ignore"))
    page_id = match.group(1) if match else None

    root = ET.fromstring(raw)
    lines: list[str] = []
    for shape in root.iter(f"{P}sp"):
        placeholder = shape.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
        # The slide-number placeholder is furniture, not notes.
        if placeholder is not None and placeholder.get("type") == "sldNum":
            continue
        lines.extend(_paragraphs(shape))
    return page_id, lines


def read_deck(payload: bytes) -> list[dict]:
    """The pptx bytes to one dict per slide, in presentation order."""
    archive = zipfile.ZipFile(BytesIO(payload))
    slides = []
    for number, part in enumerate(slide_order(archive), start=1):
        lines, visuals = slide_text(archive, part)
        notes_path = notes_part(archive, part)
        page_id, notes = notes_text(archive, notes_path) if notes_path else (None, [])
        slides.append({
            "number": number,
            "page_id": page_id,
            "lines": lines,
            "notes": notes,
            "visuals": visuals,
        })
    return slides


def notes_summary(slides: list[dict]) -> str:
    """How many slides carry speaker notes, said out loud in the header.

    Without this the two cases read identically: a deck whose presenter wrote
    nothing, and a deck whose notes never got parsed. The first is a fact about
    the source; the second would be a bug quietly costing the note its best
    material.
    """
    written = sum(1 for slide in slides if slide["notes"])
    if not written:
        return "none written on any slide"
    return f"on {written} of {len(slides)} slides — read them, they carry the explanation"


def render(deck_id: str, title: str | None, slides: list[dict], source: str) -> str:
    out = [
        f"- **Source:** {source}",
        f"- **Title:** {title or '(untitled)'}",
        f"- **Slides:** {len(slides)}",
        f"- **Speaker notes:** {notes_summary(slides)}",
        f"- **Deck URL:** https://docs.google.com/presentation/d/{deck_id}/edit",
        f"- **Slide images:** {PNG.format(id=deck_id, page='<PAGE_ID>')}",
        "",
        "## Slides",
    ]
    for slide in slides:
        counts = ", ".join(
            f"{n} {name if n != 1 else name.removesuffix('s')}"
            for name, n in slide["visuals"].items() if n
        ) or "text only"
        page_id = slide["page_id"]
        out += ["", f"### Slide {slide['number']} — page id `{page_id or 'unknown'}` ({counts})"]
        if page_id:
            out.append(
                f"Deep link: https://docs.google.com/presentation/d/{deck_id}/edit#slide=id.{page_id}"
            )
        out += ["", *(slide["lines"] or ["*(no text)*"])]
        if slide["notes"]:
            out += ["", "**Speaker notes:** " + " ".join(slide["notes"])]
    return "\n".join(out) + "\n"


def _selftest() -> int:
    assert presentation_id(
        "https://docs.google.com/presentation/d/1hcGZ4U9TjZZzcGNbH2K6wYD45qwZTyo_gosCQsnHlnc/edit?pli=1#slide=id.g33e"
    ) == "1hcGZ4U9TjZZzcGNbH2K6wYD45qwZTyo_gosCQsnHlnc"
    assert presentation_id("1hcGZ4U9TjZZzcGNbH2K6wYD45qwZTyo_gosCQsnHlnc") == (
        "1hcGZ4U9TjZZzcGNbH2K6wYD45qwZTyo_gosCQsnHlnc"
    )
    try:
        presentation_id("https://example.com/deck")
    except SystemExit:
        pass
    else:
        raise AssertionError("a non-Slides URL must not resolve to an id")

    assert _title_from(
        "attachment; filename=\"Deck.pptx\"; filename*=UTF-8''Mi%20Presentaci%C3%B3n.pptx"
    ) == "Mi Presentación", "the RFC 5987 field wins, so accents survive"
    assert _title_from('attachment; filename="Deck.pptx"') == "Deck"
    assert _title_from("attachment") is None

    # A minimal deck: two slides in reverse filename order, so a naive sort fails.
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr(
            "ppt/_rels/presentation.xml.rels",
            f'<Relationships xmlns="{REL[1:-1]}">'
            '<Relationship Id="rA" Target="slides/slide2.xml"/>'
            '<Relationship Id="rB" Target="slides/slide1.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "ppt/presentation.xml",
            f'<p:presentation xmlns:p="{P[1:-1]}" xmlns:r="{R[1:-1]}"><p:sldIdLst>'
            '<p:sldId r:id="rA"/><p:sldId r:id="rB"/>'
            "</p:sldIdLst></p:presentation>",
        )
        for name, text in (("slide2.xml", "Second file, first slide"), ("slide1.xml", "Second slide")):
            z.writestr(
                f"ppt/slides/{name}",
                f'<p:sld xmlns:p="{P[1:-1]}" xmlns:a="{A[1:-1]}"><p:cSld><p:spTree>'
                f'<p:sp><p:spPr><a:blipFill><a:blip/></a:blipFill></p:spPr>'
                f"<p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p>"
                "<a:p></a:p></p:txBody></p:sp><p:cxnSp/>"
                "</p:spTree></p:cSld></p:sld>",
            )
        z.writestr(
            "ppt/slides/_rels/slide2.xml.rels",
            f'<Relationships xmlns="{REL[1:-1]}"><Relationship Id="r1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" '
            'Target="../notesSlides/notesSlide2.xml"/></Relationships>',
        )
        z.writestr(
            "ppt/notesSlides/notesSlide2.xml",
            f'<p:notes xmlns:p="{P[1:-1]}" xmlns:a="{A[1:-1]}"><p:cSld><p:spTree>'
            '<p:sp><p:nvSpPr><p:cNvPr id="1" name="Google Shape;117;gABC_0_1:notes"/>'
            '<p:nvPr><p:ph type="sldNum"/></p:nvPr></p:nvSpPr>'
            "<p:txBody><a:p><a:r><a:t>2</a:t></a:r></a:p></p:txBody></p:sp>"
            '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Google Shape;118;gABC_0_1:notes"/>'
            "<p:nvPr><p:ph type=\"body\"/></p:nvPr></p:nvSpPr>"
            "<p:txBody><a:p><a:r><a:t>Say this out loud</a:t></a:r></a:p></p:txBody></p:sp>"
            "</p:spTree></p:cSld></p:notes>",
        )

    slides = read_deck(buffer.getvalue())
    assert [s["number"] for s in slides] == [1, 2]
    assert slides[0]["lines"] == ["Second file, first slide"], "sldIdLst order wins over filenames"
    assert slides[1]["lines"] == ["Second slide"]
    assert slides[0]["visuals"] == {"images": 1, "shapes": 1, "connectors": 1}, (
        "a picture fill counts as an image; Google exports pasted images that way"
    )
    assert slides[0]["page_id"] == "gABC_0_1", "the page id comes off the notes page"
    assert slides[0]["notes"] == ["Say this out loud"], "the slide-number placeholder is not a note"
    assert slides[1]["page_id"] is None, "a slide with no notes page has no id to offer"

    assert notes_summary(slides).startswith("on 1 of 2 slides")
    assert notes_summary([{"notes": []}]) == "none written on any slide", (
        "a deck nobody annotated must say so, so it cannot be read as a parse failure"
    )

    report = render("DECK", "Título", slides, "https://x.test")
    assert "**Title:** Título" in report
    assert "**Speaker notes:** on 1 of 2 slides" in report
    assert "export/png?pageid=gABC_0_1" not in report, "the report gives the template, not 16 URLs"
    assert "page id `gABC_0_1`" in report
    assert "page id `unknown`" in report
    assert "Say this out loud" in report

    print("selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="slides",
        description="Read a Google Slides deck as text, speaker notes, and image URLs.",
    )
    ap.add_argument("source", nargs="?", help="Google Slides URL or presentation id")
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.source:
        ap.error("source is required")

    # Same reason as transcript.py: a redirected stdout follows the locale codec
    # on Windows, and deck text is routinely non-ASCII.
    sys.stdout.reconfigure(encoding="utf-8")

    deck_id = presentation_id(args.source)
    payload, title = fetch_pptx(deck_id)
    slides = read_deck(payload)
    if not slides:
        raise SystemExit(f"Presentation {deck_id} exported no slides.")
    sys.stdout.write(render(deck_id, title, slides, args.source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
