# take-notes

Turns a **YouTube video or web article** into didactic study notes — executive
summary, the one takeaway, key points, a timestamped or sectioned outline — as
a self-contained HTML page under `~/take-notes/html_reports/`, opened in the
browser.

Works in **Claude Code, Codex, Cursor, OpenCode, and Gemini CLI** — one
`SKILL.md`, no per-tool variants.

Supported sources:

- **YouTube** — any video URL, including ones yt-dlp supports beyond YouTube
- **Local media files** — video/audio already on disk
- **Web articles** — blog posts, docs pages, news articles (any other `http(s)` page)

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
```

The optional focus narrows what the notes emphasise (e.g. `"just the API
design part"`). It writes `~/take-notes/html_reports/YYYY-MM-DD-<slug>.html`
and opens it — and re-running on the same source the same day **updates** that
note rather than leaving a near-duplicate beside it.

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

### Gallery

Notes pile up. `scripts/gallery.py` reads whatever is in
`~/take-notes/html_reports/` and writes `~/take-notes/gallery.html` — a card
per note, newest first, poster for videos and a filing plate for articles,
with a filter box (`/` focuses it, `Esc` clears it). Then it opens it.

<p align="center">
<a href="docs/gallery.png"><img src="docs/gallery.png" width="760" alt="Gallery — a grid of note cards, posters for videos and numbered filing plates for articles, above a filter bar"></a>
<br><sub><b>The gallery</b> — a page built by <code>gallery.py</code>, filled with a <b>sample archive</b>: the eight notes, their sources, and the poster art are invented, unlike the two note screenshots above.</sub>
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

## Install

Two ways in. Neither auto-updates — re-run it (or `git pull`) for the latest.

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

### What you'll need


|                                      |                                                                                               |
| ------------------------------------ | --------------------------------------------------------------------------------------------- |
| [**uv**](https://docs.astral.sh/uv/) | runs the scripts; provisions its own Python, no separate install                              |
| **yt-dlp + ffmpeg**                  | video sources only — `scripts/setup.py` installs them via Homebrew on macOS                   |
| **Whisper API key**                  | optional, only for videos without captions — Groq or OpenAI, read from `~/.config/watch/.env` |


Web articles need none of the above — that path uses the agent's fetch tool.

Both install paths land on the same `/take-notes` — neither namespaces nor
renames it.

## Contribute

Issues and pull requests are welcome. The most useful things:

- **A source it handled badly** — open an issue with the URL and what the notes
  got wrong. That's the bug report this project needs most; the writing standard
  improves from real failures, not from hypotheticals.
- **A new source guide** — a file under `references/` teaching the skill to
  acquire from somewhere else (a podcast host, a PDF, a paywalled reader).
- **A third language** — `en` and `es` are hardcoded in `SKILL.md` Step 2 and in
  the string tables at the top of `render.py` and `gallery.py`.
- **Design and accessibility fixes** to the three templates under `assets/`.

### Working on it

```sh
git clone https://github.com/davertor/take-notes
cd take-notes
./link-skill.sh          # symlinks your checkout into every tool — edits are live
```

No build, no virtualenv, no install step: `uv` provisions Python per script,
and every script is **stdlib-only**. Keep it that way — a dependency is a much
bigger ask of everyone who installs this than the few lines it saves.

There is no test suite. Each script that has non-trivial logic carries its own
asserts instead, and all three must pass before a PR:

```sh
for s in render gallery transcript; do
  uv run skills/take-notes/scripts/$s.py --selftest
done
```

Commits and PR titles follow [Conventional
Commits](https://www.conventionalcommits.org/) — `feat(take-notes): …`,
`fix(skills): …`, `docs: …` — matching the existing history. English
everywhere in the repo, whatever language your notes come out in.

### Three things that will bite you

The skill follows the [Agent Skills](https://agentskills.io/specification)
layout, so `skills/take-notes/` is browsable on its own. What it won't tell you:

- **Never-auto-invoke is two files.** `disable-model-invocation: true` in
  `SKILL.md` and `agents/openai.yaml` (its Codex counterpart) are what keep the
  skill user-invoked. Change one without the other and that tool starts firing
  on any URL you mention.
- **The note-writing standard lives only in `SKILL.md`.** The guides under
  `references/` cover acquisition and hand back the same five fields (title,
  byline, span, canonical URL, body) whatever the source. Keep it that way —
  two copies of the writing standard will drift.
- **The gallery reads the notes, not an index.** So the masthead classes in
  both note templates — `.poster`, `.kicker`, `.meta`, `.watch` — are a
  contract with `gallery.py`. Rename one and its `--selftest` fails, which is
  the point. Run it after touching a template.

## Credits

- [bradautomates/claude-video](https://github.com/bradautomates/claude-video) by Bradley Bonanno (MIT).

