<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/hero-dark.png">
    <img src="docs/hero-light.png" width="900" alt="take·notes — turns a video, article, paper, or repo into didactic study notes, one self-contained HTML page you keep. Claude Code, Codex, Cursor, OpenCode, Gemini CLI.">
  </picture>
</p>

# take-notes

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-ab2f19?style=flat-square&labelColor=191511" alt="Version 1.0.0">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-57503f?style=flat-square&labelColor=191511" alt="MIT license"></a>
  <img src="https://img.shields.io/badge/agents-5%20supported-57503f?style=flat-square&labelColor=191511" alt="5 agent tools supported">
  <img src="https://img.shields.io/badge/output-html%20%C2%B7%20md%20%C2%B7%20anki-57503f?style=flat-square&labelColor=191511" alt="Output: HTML, Markdown, Anki">
</p>

**Notes you can actually learn from — not a transcript dump, not a one-paragraph summary.**

Point it at a video, an article, a paper, or a repo. You get a self-contained
HTML page — executive summary, the one takeaway, key points, and a timestamped
or sectioned outline — written to `~/take-notes/html_reports/` and opened in
your browser. They pile up into a browsable archive you own, on your disk, in
plain HTML that will still open in ten years.

Works in **Claude Code, Codex, Cursor, OpenCode, and Gemini CLI** — one
`SKILL.md`, no per-tool variants. Every script is stdlib-only Python run through
`uv`; there is nothing to `pip install`.

**Claude Code** (auto-updates via the marketplace):

```text
/plugin marketplace add davertor/take-notes
/plugin install take-notes@take-notes
```

**Codex, Cursor, OpenCode, Gemini CLI**, or any other [Agent Skills](https://agentskills.io) host:

```sh
npx skills add davertor/take-notes -g
```

More ways in — including a plain clone you can edit — under [Install](#install).

## Why I built it

I kept watching hour-long videos and reading long posts, feeling like I'd
learned something, and then having nothing to show for it a week later. The
summaries I could get were either a wall of transcript or three bland
sentences — both useless for actually remembering anything.

So the rule this skill follows is: **explain, don't compress.** A bullet only
someone who already watched the video would understand has failed. Order things
by what has to be understood first, not by when they were said. Say what the
source left unanswered. And keep every note as one HTML file on my own disk,
because notes that live in someone else's product stop being yours eventually.

## Sources

| | |
|---|---|
| **YouTube** | any video URL, including the many non-YouTube sites yt-dlp supports |
| **Local media** | video or audio already on disk |
| **Web articles** | blog posts, docs pages, news articles |
| **arXiv papers** | full text via arXiv's HTML rendering, not just the abstract |
| **GitHub repos** | an orientation note: what it does, how it's laid out, what to read first |

<table>

<tr>

<td align="center" width="50%">

<a href="docs/video-note.png"><img src="docs/video-note.png" width="380" alt="Video note — rail with poster, timestamped index, and scroll-spy sections">

</a>

<br><sub><b>Video note</b> — poster, timestamped index, scroll-spy</sub>

</td>

<td align="center" width="50%">

<a href="docs/article-note.png"><img src="docs/article-note.png" width="380" alt="Article note — rail with byline kicker, numbered index, and scroll-spy sections">

</a>

<br><sub><b>Article note</b> — byline kicker, numbered index, scroll-spy</sub>

</td>

</tr>

</table>

Click either thumbnail for the full-size page. Both real output — the skill
run end to end on an actual video and an actual blog post, not mockups.

## How to use

```sh
/take-notes <url> [focus] [--lang en|es]
/take-notes --tags | --add-tag "AI" | --remove-tag "AI"
```

The optional focus narrows what the notes emphasise (e.g. `"just the API
design part"`). It writes `~/take-notes/html_reports/YYYY-MM-DD-<slug>.html`
and opens it — and re-running on the same source the same day **updates** that
note rather than leaving a near-duplicate beside it.

The second line manages the [tag vocabulary](#tags) instead of writing a note.

It runs only when you ask. The skill never fires on a URL you merely mention in
conversation, in any of the five tools.

### Language

Optional — notes are written in **English** unless you say otherwise.

```jsonc
// ~/take-notes/config.json
{ "language": "es" }   // "en" (default) | "es" | "ask"
```

`"ask"` restores the per-run prompt, offering the source's own language first.

Override it for a single run with `--lang`, which beats the config — including
`"ask"`, since an explicit flag is not a question:

```sh
/take-notes https://youtu.be/… --lang en
```

Precedence is `--lang` → a language named in words ("…in English") → config →
English. A missing or malformed config falls back to English rather than
failing, and an unsupported `--lang` is reported rather than silently applied.
When the source's language differs from the one used, the skill says so, so a
Spanish video never quietly becomes English notes without a word.

### Tags

Every note is filed under one **primary tag**, plus any extras that apply. The
vocabulary lives beside `language` in the same config, and it is **closed**:
the skill picks from your list and never invents a tag, so the taxonomy stays
yours rather than whatever the model felt like that day.

```jsonc
// ~/take-notes/config.json
{ "language": "es", "tags": ["Unknown", "AI", "Investing", "Engineering"] }
```

Nothing fits — or no vocabulary is set — and the note lands on `Unknown`,
silently. You are never prompted to invent a tag mid-run.

Edit the list from the skill, or from the CLI when you're already in a terminal:

```sh
/take-notes --tags                  # list it
/take-notes --add-tag "AI"          # add, report, write no note
/take-notes --remove-tag "AI"       # remove

uv run skills/take-notes/scripts/tags.py --add AI --add Investing
uv run skills/take-notes/scripts/tags.py --remove Investing
```

Both edit the same file and leave `language` untouched. `Unknown` is the
fallback the skill needs, so it can't be removed. Re-tag a note by re-running
`/take-notes` on its source — same day, same file, new tag.

### Gallery

Notes pile up. `scripts/gallery.py` reads whatever is in
`~/take-notes/html_reports/` and writes `~/take-notes/gallery.html` — a card
per note, newest first, poster for videos and a filing plate for articles,
with a filter box (`/` focuses it, `Esc` clears it). Then it opens it.

Under the filter bar is a chip per [tag](#tags) in use: click one to narrow the
grid to that tag, click it again to clear. Chip and text filter combine.

<p align="center">
<a href="docs/gallery.png"><img src="docs/gallery.png" width="820" alt="Gallery — a grid of note cards, a poster for the video note and numbered filing plates for the articles, above a filter bar"></a>
<br><sub><b>The gallery</b> — the four notes in <a href="docs/examples"><code>docs/examples/</code></a>, every one of them real output. Browse them at <a href="https://davertor.github.io/take-notes/">davertor.github.io/take-notes</a>.</sub>
</p>

```sh
uv run ~/.claude/skills/take-notes/scripts/gallery.py   # or your checkout path
```

Worth an alias, since you'll run it more than once:

```sh
alias notes='uv run ~/.claude/skills/take-notes/scripts/gallery.py'
```

It's a **plain script, not a skill** — building an index of files on disk needs
no model in the loop, so no agent is involved and nothing is spent. Re-run it
after taking notes; it rebuilds from scratch every time, so a note you delete
by hand simply stops appearing.

Flags: `--no-open`, `--notes-dir`, `--out`, `--lang en|es` (defaults to the
`language` in `~/take-notes/config.json`).

### Export

Notes are yours, so they leave cleanly. Both exporters read the rendered notes;
neither needs an agent or costs tokens.

```sh
uv run skills/take-notes/scripts/export.py --format md     # → ~/take-notes/markdown/
uv run skills/take-notes/scripts/export.py --format anki   # → ~/take-notes/take-notes.txt
```

- **`md`** — one Markdown file per note with YAML frontmatter. Drop the folder
  into an Obsidian vault, or import it into Notion. Timestamp links survive as
  real Markdown links, and the note's tags land in the frontmatter `tags:` list,
  which is what Obsidian's tag pane reads.
- **`anki`** — a tab-separated deck file. Cards come from *Key points* (claim →
  detail), *Concepts* (term → definition), and the one takeaway. The note's tags
  join the card kind in the tags column, so a deck filters by topic too. Import
  with **File → Import** and leave *Allow HTML in fields* on.

## Install

The `/plugin` route at the top of this README is the one to use in Claude Code —
it is the only one that auto-updates. The two below are for everything else, or
for editing the skill yourself. Neither auto-updates; re-run it (or `git pull`)
for the latest.

### Option A — clone + symlink, for tinkering

```sh
git clone https://github.com/davertor/take-notes
cd take-notes
./link-skill.sh              # every tool
AGENT=claude ./link-skill.sh # one tool only
```

[`link-skill.sh`](link-skill.sh) symlinks `skills/take-notes` into each
tool's skills directory (`claude`, `codex`, `cursor`, `opencode`, `gemini`,
`agents`). Idempotent, and replaces anything already occupying a target. A
real checkout — edit `skills/take-notes/` directly, or `git pull` for
upstream changes.

### Option B — the skills CLI

```sh
npx skills add davertor/take-notes -g                  # install for your user
npx skills add davertor/take-notes -g -a claude-code   # one agent only
```

**Pass `-g`** — without it, `add` installs project-level into the current
folder instead of your user directories. Update with `npx skills update take-notes`.

### Prerequisites


|                                      |                                                                                               |
| ------------------------------------ | --------------------------------------------------------------------------------------------- |
| [**uv**](https://docs.astral.sh/uv/) | runs the scripts; provisions its own Python, no separate install                              |
| **yt-dlp + ffmpeg**                  | video sources only — `scripts/setup.py` installs them via Homebrew on macOS                   |
| **Whisper API key**                  | optional, only for videos without captions — Groq or OpenAI, read from `~/.config/watch/.env` |


Web articles need none of the above — that path uses the agent's fetch tool.

Both install paths land on the same `/take-notes` — neither namespaces nor
renames it.

## Contribute

Issues and pull requests are welcome — **[CONTRIBUTING.md](CONTRIBUTING.md)**
has the setup, the self-checks, and the four constraints that are easy to trip
over. The most useful issue you can open is a source it handled badly, with the
URL.

```sh
git clone https://github.com/davertor/take-notes && cd take-notes
./link-skill.sh                                        # edits are live in every tool

for s in render notes gallery export transcript tags; do    # the whole test suite
  uv run skills/take-notes/scripts/$s.py --selftest
done
```

Stdlib only, English everywhere, [Conventional
Commits](https://www.conventionalcommits.org/) — matching
[CHANGELOG.md](CHANGELOG.md), which is maintained by hand alongside
`skills/take-notes/SKILL.md`'s `version` field.

## Credits

- [bradautomates/claude-video](https://github.com/bradautomates/claude-video) by Bradley Bonanno (MIT).

