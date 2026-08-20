---
name: take-notes
description: Turn a YouTube video or a web article into didactic study notes, written as a self-contained HTML page under ~/take-notes/html_reports and opened in the browser.
license: MIT
compatibility: Requires uv. Video sources also need yt-dlp and ffmpeg, plus network access; an optional Groq or OpenAI key enables Whisper for videos without captions.
metadata:
  author: davertor
  version: "1.0.0"
# Claude Code extensions below — not in the agentskills.io spec, and read at the
# top level rather than under `metadata`, which is where Claude Code looks.
# `allowed-tools` stays comma-separated: the spec asks for spaces but marks the
# field experimental ("support may vary"), and commas are what Claude Code
# parses today. Do not "correct" either without testing in Claude Code first.
argument-hint: "<video-or-article-url> [focus] [--lang en|es] | --tags | --add-tag X | --remove-tag X"
allowed-tools: Bash, Read, WebFetch, AskUserQuestion
disable-model-invocation: true
---

# /take-notes

Turn a source into **notes you can learn from** — not a transcript dump, not a
one-paragraph summary. The output is one self-contained HTML page written to
`~/take-notes/html_reports/` and opened in the browser, so the notes accumulate
into a browsable local archive instead of scrolling away in the terminal.

Invocation: `/take-notes <url> [focus]`. If no URL is given, ask for one.
The optional focus narrows what the notes emphasise ("just the API design part").
`--tags`, `--add-tag`, and `--remove-tag` manage the tag vocabulary instead —
see Step 0.

## Resolve `SKILL_DIR` (before any command, both source types)

The scripts are bundled with this skill, a direct sibling of this file. Set
`SKILL_DIR` to the **absolute path of the directory containing THIS SKILL.md you
just Read** — your harness reported it in the Read result — and substitute it
literally in every command below:

```bash
SKILL_DIR="<absolute path of the directory containing the SKILL.md you Read>"
if [ ! -f "$SKILL_DIR/scripts/render.py" ]; then
  echo "ERROR: scripts/render.py not found under SKILL_DIR=$SKILL_DIR" >&2
  exit 1
fi
```

## Step 0 — tag management short-circuits everything else

Three invocations manage the tag vocabulary instead of writing a note. If the
invocation is one of them, run the matching command, report the result, and
**stop** — no source, no note, nothing else in this file applies:

| Invocation | Command |
|---|---|
| `/take-notes --tags` | `uv run "${SKILL_DIR}/scripts/tags.py"` |
| `/take-notes --add-tag "AI"` | `uv run "${SKILL_DIR}/scripts/tags.py" --add "AI"` |
| `/take-notes --remove-tag "AI"` | `uv run "${SKILL_DIR}/scripts/tags.py" --remove "AI"` |

Both editing forms are repeatable — pass `--add` or `--remove` once per tag.
The script prints the resulting vocabulary; report that, and nothing more. It
rewrites only the `tags` key, so `language` survives untouched.

`Unknown` cannot be removed: it is the fallback the note writer needs when a
source fits nothing. The script says so and leaves it in place.

## Step 1 — route to the right acquisition guide

Pick **one** reference by looking at the source, Read it, and follow it. Only the
acquisition differs; everything after Step 2 is identical for every source.

Match **top to bottom and stop at the first row that fits** — arXiv and GitHub
links are `http(s)` pages too, so the catch-all row would swallow them.

| Source | Read |
|---|---|
| YouTube URL, any other video URL yt-dlp supports, or a local media file | `references/youtube.md` |
| `arxiv.org` (or an `ar5iv` / arXiv DOI link) — a paper | `references/arxiv.md` |
| `github.com/<owner>/<repo>` — a repository root, not a file, PR, or issue | `references/github.md` |
| Any other `http(s)` page — blog post, docs page, news article | `references/web.md` |

Each guide hands back the same thing, and nothing more:

- **title**
- **byline** — channel for video, author or site for an article, the paper's
  authors, the repo's owner
- **span** — duration for video, publication date for an article, submission
  date for a paper, latest release for a repo
- **canonical URL** (plus the YouTube video ID when there is one)
- **body** — the timestamped transcript, the article text, the paper full text,
  or the README plus the repo's structure

Video sources also hand back, when yt-dlp reports them: **channel URL**,
**published** date, **views**, a **thumbnail** URL, and the **caption language**.
Pass these to Step 5 too — they drive the two-pane video layout. Articles never
have them; leave those flags off entirely rather than passing empty strings.

Captions arrive in the language actually spoken. When the guide reports the track
was **machine-translated** (no original-language track existed), note it in
*Going deeper*: translated captions mangle proper nouns, so names taken from them
are unreliable and quotes are twice-removed from what was said.

If a guide reports it could not get the body, **say so and stop**. Never write
notes from a title, a description, or a paywall stub.

Do not put note-writing guidance in the reference files, and do not put
acquisition detail here. Two copies of the writing standard will drift.

## Step 2 — settle the language and the tag

One read of `~/take-notes/config.json` answers both: `language` and `tags`.

### Language

This skill writes in **English or Spanish only**. Resolve which, in this order,
and stop at the first that applies:

1. **`--lang en` or `--lang es` in the invocation.** Wins over everything,
   including a config set to `"ask"` — an explicit flag is not a question.
2. **A language named in plain words** in the invocation ("take notes on this in
   English"). Same standing as the flag; if somehow both appear, the flag wins.
3. **`~/take-notes/config.json`.** Read it. `"language": "en"` or `"es"` → use
   it. `"language": "ask"` → go to the question below.
4. **Default: English.** No config, an unreadable one, or any other value — a
   broken config must never block the run.

```json
{ "language": "es", "tags": ["Unknown", "AI", "Investing", "Engineering"] }
```

`--lang` with anything other than `en` or `es` is **not** an error to stop on,
and must not be passed through: `render.py` silently falls back to English
chrome for unknown codes, which would pair English furniture with prose in a
third language. Say the value is unsupported, resolve from step 3 onward, and
name what you used instead:

> `--lang fr` is not supported (English or Spanish only) — writing in Spanish per your config.

When you resolve to a language **without asking**, say so in one short line.
Point at the config file only when the language came from the config or the
default — someone who just typed `--lang en` does not need to be told how to
set a preference they have overridden:

> Writing in English (default). Set `"language"` in `~/take-notes/config.json` to change.

**If the source is not in the language you resolved to, say that too** — a
Spanish video silently producing English notes is the one surprise worth calling
out:

> Source is in Spanish; writing in English per your config.

### When the config says `"ask"`

Ask once, with `AskUserQuestion`, before writing anything. Offer exactly two
options — English and Spanish — nothing else. Put the source's own language
first, labelled "(Recommended)" (e.g. a Spanish-language video →
`Spanish (Recommended)` before `English`); if the source is in neither, put
English first.

However it resolves, the result sets the language for Step 4's headings and
prose, and the `--lang` code for Step 5 (`en` or `es`).

### Tags

`tags` in the same file is a **closed vocabulary**, curated by hand. Pick from
it; do not extend it:

1. **One primary tag** — the single best fit for what this source is about.
   That is what the gallery card shows and files the note under.
2. **Optional extras**, only when they genuinely apply. Two is usually plenty;
   tagging a note with half the vocabulary makes every filter useless.
3. **Never invent a tag.** A name that is not in the list is not an option, no
   matter how well it fits.
4. **Nothing fits, or `tags` is absent, empty, or unreadable → `Unknown`.**
   Silently. Do not ask, do not suggest a new tag, do not explain the fallback.

Say which primary tag you chose in the same short line as the language, without
justifying it: *Writing in English (default), filed under **Engineering**.*

## Step 3 — read for teaching, not for summarising

Before writing, decide: what does someone who consumed this source now *know*
that they didn't before? That answer is the takeaway, and everything else
supports it. Note where the source explains a mechanism (goes in *How it works*),
defines jargon (*Concepts*), or leaves something unresolved (*Going deeper*).

## Step 4 — write the notes as HTML

Use the sections below. Write **body HTML only** — no `<html>`, `<head>`,
`<body>`, no `<h1>`, and no metadata line: the renderer supplies the document
shell and the masthead from the fields you collected in Step 1.

There is no Markdown step. Emit the tags directly; nothing parses Markdown here,
which is why this skill needs no conversion dependency.

## Step 5 — render it

Pipe the body HTML to the renderer, filling the flags from your Step 1 fields:

```bash
uv run "${SKILL_DIR}/scripts/render.py" \
  --title "<title>" --byline "<channel or author>" \
  --span "<duration or publication date>" --url "<canonical URL>" \
  --tag "<primary tag>" <<'HTML'
<h2>Executive summary</h2>
...
HTML
```

Pass one `--tag` per tag chosen in Step 2, **primary first** — `--tag AI --tag
Engineering`. With no `--tag` at all the note is filed under `Unknown`.

For video sources, also pass whichever of `--video-id <id>`, `--thumbnail <url>`,
`--channel-url <url>`, `--published <YYYYMMDD>`, `--views <int>`,
`--duration <seconds>` the guide reported. `--video-id` is what switches the
rail to a poster + index; without it, the same two-pane layout renders for
articles instead, with a byline kicker and a numbered index in place of the
poster and timestamps.

For videos, pass **raw** values and let the renderer localise them:
`--duration 692` (seconds), `--published 20260816`, `--views 13232`. It writes
`11 min · 16 ago 2026 · 13.2K visualizaciones` for `--lang es` and
`11 min · Aug 16, 2026 · 13.2K views` for `--lang en`. `--span` stays a free-form
string for articles, whose span is a publication date rather than a length.

It writes `~/take-notes/html_reports/YYYY-MM-DD-<slug>.html` and opens it.
Re-running on the same source the same day **updates** that file rather than
adding a near-duplicate; the script prints `created:` or `updated:` with the
path. Report that path.

That is also how a note gets re-tagged: while the body is still in context,
re-run this command with a different `--tag`. Rewriting the tag inside an
already-written file is not something this skill does — re-run the source.

Pass `--lang` matching Step 2's choice (`en` or `es`). Add `--no-open` to skip
the browser, `--out-dir` to write somewhere other than `~/take-notes/html_reports`.

## Sections

Mandatory, in this order. The title and metadata line are **not** in the body —
they come from the renderer flags.

1. `<h2>Executive summary</h2>` — 3–5 sentences: what the source covers and what
   it argues.
2. `<h2>The one takeaway</h2>` — 1–2 sentences wrapped in `<strong>`. The single
   most important insight. If you can't name one, the notes aren't ready.
3. `<h2>Key points</h2>` — a `<ul>` of 5–10 items, each
   `<li><strong>Claim</strong> — the detail that supports it</li>`.
   Cap at 10; more than that is a transcript with bullets in front of it.
4. The outline, rendered to match the source:
   - video → `<h2>Timestamped outline</h2>`, one `<li>` per topic:
     `<li><a href="https://youtu.be/<ID>?t=754s">12:34</a> — <strong>Topic</strong> — one-line summary</li>`
     Use absolute `?t=<seconds>s` URLs so the links jump to the right moment.
   - article → `<h2>Section outline</h2>`, one `<li>` per section:
     `<li><strong>Section heading</strong> — one-line summary</li>`, wrapping the
     heading in `<a href="<URL>#anchor">` when the page has stable anchors.

   Aim for 6–15 entries either way; group adjacent material covering one idea.

Optional — include only when the source actually earns it, never as an empty heading:

- `<h2>Concepts</h2>` — jargon the source assumes or introduces, as
  `<li><strong>term</strong> — definition</li>`. Include a term only if not
  knowing it blocks understanding the notes.
- `<h2>How it works</h2>` — an `<ol>` for a mechanism, pipeline, or worked example
  the source demonstrates. Code goes in `<pre><code>`.
- `<h2>Going deeper</h2>` — what the source leaves open: unanswered questions,
  claims made without evidence, and the concrete next thing to read or try.

**Article figures** — `references/web.md` returns any diagrams, charts, or
screenshots the source page had. Include one only when it is load-bearing —
the diagram *is* the explanation, the chart *is* the evidence — never a
decorative photo, a header banner, or an author headshot. Cap at 3, the same
"more than that is a dump" discipline as Key Points. Not a section of its
own: place `<figure><img src="<url>" alt="<alt text>"><figcaption>caption</figcaption></figure>`
inline, in whichever section it supports — most often *How it works*, *Key
points*, or *Concepts*.

## Rules

- **Didactic means explaining, not compressing.** A bullet only someone who already
  consumed the source would understand has failed. Expand the reference; don't
  preserve the author's shorthand.
- **Learner's order, not source order.** Only the outline follows the source's
  sequence. Everything else is ordered by what has to be understood first.
- **Quote sparingly** — one or two lines that lose meaning when paraphrased.
- **Own the notes.** No "the speaker says that…" throughout; state the content and
  attribute only genuinely contested claims.
- **No padding.** No "In conclusion", no restating the summary at the end, no bullet
  whose content is "this is important".
- **Flag the source's limits** when it asserts things without support — that belongs in
  *Going deeper*, and it's the part that makes the notes worth keeping.
- **Language:** write headings and body in whichever of English or Spanish was chosen
  in Step 2; the structure doesn't change. Pass the matching `--lang` (`en` or `es`)
  to the renderer.
- **Keep the HTML plain:** headings, paragraphs, lists, `<strong>`, `<em>`, links,
  `<pre><code>`, `<blockquote>`, simple tables, and (articles only)
  `<figure><img><figcaption>` for a source figure. No inline `style` attributes, no
  `<script>`, no classes — the stylesheet already handles presentation, and a note
  that fights it will look wrong in dark mode.
- **Escape what you write:** `&`, `<` and `>` must be `&amp;`, `&lt;`, `&gt;` —
  in prose, in code samples, and in attribute values like an `<img src>` URL
  (image URLs routinely contain an unescaped `&` in their query string). The
  renderer escapes the masthead fields but passes the body through untouched.

## Related

- `/yt-watch` — frames *and* transcript. Use it directly when the question is visual.
  `/take-notes` includes its own copy of the transcript path so it runs standalone;
  neither skill depends on the other being installed.
- `/notion-summarize-blog` — files a short *webpage* summary straight into the
  personal Notion database via MCP. `/take-notes` is the long form and stays local:
  a full study page in `~/take-notes/html_reports/`, reviewed and edited before
  anything is worth filing.
