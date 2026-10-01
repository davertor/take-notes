---
name: take-notes
description: Turn a YouTube video, a web article, or several sources at once into one set of didactic study notes, written as a self-contained HTML page under ~/take-notes/html_reports and opened in the browser.
license: MIT
compatibility: Requires uv. Video sources also need yt-dlp and ffmpeg, plus network access; an optional Groq or OpenAI key enables Whisper for videos without captions.
metadata:
  author: davertor
  version: "1.6.0"
# Claude Code extensions below — not in the agentskills.io spec, and read at the
# top level rather than under `metadata`, which is where Claude Code looks.
# `allowed-tools` stays comma-separated: the spec asks for spaces but marks the
# field experimental ("support may vary"), and commas are what Claude Code
# parses today. Do not "correct" either without testing in Claude Code first.
argument-hint: "<url> [more-urls…] [focus] [--lang en|es] [--genre <name>] | --tags | --add-tag X | --remove-tag X | --retag | --theme [name]"
allowed-tools: Bash, Read, WebFetch, AskUserQuestion
disable-model-invocation: true
---

# /take-notes

Turn a source into **notes you can learn from** — not a transcript dump, not a
one-paragraph summary. The output is one self-contained HTML page written to
`~/take-notes/html_reports/` and opened in the browser, so the notes accumulate
into a browsable local archive instead of scrolling away in the terminal.

Invocation: `/take-notes <url> [more urls…] [focus]`. If no URL is given, ask for
one. Several URLs are **one note about one subject from several sources** — a
talk and the deck it was given from, a paper and the repo that implements it —
not one note each; `references/combining.md` says how.
The optional focus does two things: it narrows what Step 1 asks the source for
— on a long or multi-topic source, that's the difference between fetching the
whole thing and fetching only the part that matters — and it narrows what the
finished notes emphasise in Step 3-4. Skip it to cover a source in full; add it
("just the API design part") when only part of a long source is relevant.
`--tags`, `--add-tag`, and `--remove-tag` manage the tag vocabulary instead, and
`--theme` the colour palette — see Step 0. `--genre` forces the note's shape
when the router's own call is not what you want — see Step 3.

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

## Step 0 — settings management short-circuits everything else

`--tags`, `--add-tag`, `--remove-tag`, `--theme` and `--retag` manage the tag
vocabulary, the colour palette or the notes already on disk instead of writing
a note. If the invocation is one of them — as a flag or in words ("ponlo en
petrol", "re-file my notes") — Read `references/settings.md`, do what it says,
and **stop**: no source, no note, nothing else in this file applies.

## Step 1 — route to the right acquisition guide

Pick **one** reference per source by looking at it, Read it, and follow it. Only
the acquisition differs; everything after Step 2 is the same for every source —
within the genre Step 3 picks from the content.

Match **top to bottom and stop at the first row that fits** — arXiv, Slides and
GitHub links are `http(s)` pages too, so the catch-all row would swallow them.

| Source | Read |
|---|---|
| YouTube URL, any other video URL yt-dlp supports, or a local media file | `references/youtube.md` |
| `arxiv.org` (or an `ar5iv` / arXiv DOI link) — a paper | `references/arxiv.md` |
| `docs.google.com/presentation/...` — a slide deck | `references/slides.md` |
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
  the deck's slides and speaker notes, or the README plus the repo's structure

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

### More than one source

Route **each** URL through its own row above and collect the same field set
for each. Then Read `references/combining.md` before going on: it says which
source is primary, what a companion that yields nothing means, how the set is
read as one note, and the `--source` flags Step 5 takes.

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
{ "language": "es", "tags": ["Unknown", "AI", "Investing", "Engineering"], "theme": "notebook" }
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

## Step 3 — read for teaching, and pick the genre

Before writing, decide: what does someone who consumed this source now *know*
that they didn't before? That answer is the takeaway, and everything else
supports it. Note where the source explains a mechanism (goes in *How it works*),
defines jargon (*Concepts*), or leaves something unresolved (*Going deeper*).

### Genre

A note's **genre** is the shape of its content — which sections it has and
which template renders them. It is a property of the source, not a taste, so
you pick it after reading. Print the router:

```bash
uv run "${SKILL_DIR}/scripts/genres.py" --list --lang <en|es>
```

It is a table of every installed genre — the bundled `recipe`, `fieldguide`
and `offprint`, plus any the user added under `~/take-notes/genres/` — with a
one-line "the source is…" per row and the path of its contract. Read it **top
to bottom, first row that fits**; the offprint is the last row and the
catch-all. A genre listed as *on request only* is never picked here — it is
used when asked for by name.

Resolution order, stop at the first that applies: `--genre <name>` in the
invocation, or a request in words ("write it as a recipe", "hazla como guía")
→ the table → `offprint`. **When in doubt, `offprint`**: a wrong genre is worse
than the default, the same rule as for tags. With several sources the genre
comes from the set as a whole, not from the first URL.

Now Read the contract at the path the table gives. It holds the sections for
Step 4 and nothing else — `## Rules` still applies in full. Say which genre
you chose in the same short line as the language and the tag, only when it is
not the offprint:

> Writing in Spanish per your config, filed under **Cooking**, as a **recipe**.

With several sources, `references/combining.md` § Read applies before you write.

## Step 4 — write the notes as HTML

Use the sections of the contract you read in Step 3, in its order. Whatever
the genre, the body **opens with a section whose first element is a `<p>`**:
the gallery card quotes that paragraph. The title and metadata line are **not**
in the body — they come from the renderer flags.

Write **body HTML only** — no `<html>`, `<head>`,
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
  --tag "<primary tag>" --genre "<genre>" <<'HTML'
<h2>Executive summary</h2>
...
HTML
```

Pass one `--tag` per tag chosen in Step 2, **primary first** — `--tag AI --tag
Engineering`. With no `--tag` at all the note is filed under `Unknown`.

`--genre` is Step 3's choice, by name; leave it off for an offprint.
`--video-id` still decides the masthead in every genre: a poster with it, a
byline kicker without.

The masthead flags describe the **primary** source; with several sources, add
the `--source` flags `references/combining.md` § Render describes.

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
  *Going deeper* (a recipe's *Gaps*), and it's the part that makes the notes worth keeping.
- **Language:** write headings and body in whichever of English or Spanish was chosen
  in Step 2; the structure doesn't change. Pass the matching `--lang` (`en` or `es`)
  to the renderer.
- **Keep the HTML plain:** headings, paragraphs, lists, `<strong>`, `<em>`, links,
  `<pre><code>`, `<blockquote>`, simple tables, and (every source but video)
  `<figure><img><figcaption>` for a source figure. No inline `style` attributes, no
  `<script>`, no classes beyond the ones the genre's contract names — the
  stylesheet already handles presentation, and a note that fights it will look
  wrong in dark mode.
- **Escape what you write:** `&`, `<` and `>` must be `&amp;`, `&lt;`, `&gt;` —
  in prose, in code samples, and in attribute values like an `<img src>` URL
  (image URLs routinely contain an unescaped `&` in their query string). The
  renderer escapes the masthead fields but passes the body through untouched.
