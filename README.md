# take-notes

Turns a **YouTube video or web article** into didactic study notes — executive
summary, the one takeaway, key points, a timestamped or sectioned outline — as
a self-contained HTML page under `~/take-notes/html_reports/`, opened in the
browser.

Works in **Claude Code, Codex, Cursor, OpenCode, and Gemini CLI** — one
`SKILL.md`, no per-tool variants.

## Install

```sh
npx skills add davertor/take-notes
```

Or clone and symlink the skill folder into whichever directory your tool
reads, so `SKILL.md` sits one level deep:

```sh
git clone https://github.com/davertor/take-notes ~/take-notes-src
ln -s ~/take-notes-src/skills/take-notes ~/.claude/skills/take-notes
```

Other valid targets: `~/.codex/skills/`, `~/.cursor/skills/`,
`~/.config/opencode/skills/`, `~/.gemini/skills/`, `~/.agents/skills/`.

Invoke with `/take-notes <url> [focus]`. The optional focus narrows what the
notes emphasise (e.g. `"just the API design part"`).

## Requirements

| | |
|---|---|
| **[uv](https://docs.astral.sh/uv/)** | runs the scripts; provisions its own Python, no separate install |
| **yt-dlp + ffmpeg** | video sources only — `scripts/setup.py` installs them via Homebrew on macOS |
| **Whisper API key** | optional, only for videos without captions — Groq or OpenAI, read from `~/.config/watch/.env` |

Web articles need none of the above — that path uses the agent's fetch tool.

## Config

Optional — notes are written in **English** unless you say otherwise.

```jsonc
// ~/take-notes/config.json
{ "language": "es" }   // "en" (default) | "es" | "ask"
```

`"ask"` restores the per-run prompt, offering the source's own language first.

Precedence is invocation → config → English: naming a language in the request
("take notes on this in English") wins for that run, and a missing or malformed
file falls back to English rather than failing. When the source's language
differs from the one used, the skill says so, so a Spanish video never quietly
becomes English notes without a word.

## Layout

```
skills/take-notes/
  SKILL.md             route by source, and the note-writing standard
  references/
    youtube.md          captions via yt-dlp, Whisper fallback
    web.md                fetch + extract article text
  scripts/
    transcript.py         transcript entry point (captions -> Whisper)
    render.py              wraps note HTML in a styled standalone page
    ...                    transcript helpers (see Credits)
```

Both reference guides hand back the same five fields (title, byline, span,
canonical URL, body); `SKILL.md` holds the only copy of the note-writing
standard. Re-running on the same source the same day updates that note
instead of duplicating it.

## Credits

`scripts/config.py`, `download.py`, `transcribe.py`, `whisper.py` and
`setup.py` originated from
[bradautomates/claude-video](https://github.com/bradautomates/claude-video) by
Bradley Bonanno (MIT). They're maintained independently here now, not kept in
sync with upstream.

MIT licensed. See [LICENSE](LICENSE).
