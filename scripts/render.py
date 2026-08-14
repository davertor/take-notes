#!/usr/bin/env python3
"""Wrap note body HTML in a self-contained, styled document under ~/take-notes.

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


DEFAULT_OUT_DIR = Path.home() / "take-notes"

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
<footer>Notes generated from <a href="{url}">{url}</a> on {today}.</footer>
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
    return DOCUMENT.format(
        lang=html.escape(lang, quote=True),
        title=html.escape(title),
        style=STYLE,
        meta=build_meta(byline, span, url),
        body=body.strip(),
        url=html.escape(url or "", quote=True),
        today=today or datetime.date.today().isoformat(),
    )


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

    assert build_meta(None, None, None) == ""
    assert build_meta("A", None, None) == "A"
    assert "&middot;" in build_meta("A", "12:34", None)

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

    # Re-running on the same source the same day updates that note rather than
    # littering the archive with near-duplicates; say which happened.
    action = "updated" if target.exists() else "created"
    target.write_text(
        build_document(
            args.title, body,
            byline=args.byline, span=args.span, url=args.url, lang=args.lang,
        ),
        encoding="utf-8",
    )

    print(f"{action}: {target}")
    if not args.no_open:
        webbrowser.open(target.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
