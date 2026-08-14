# take-notes

An agent skill that turns a **YouTube video or a web article** into didactic
study notes — executive summary, the one takeaway, key points, a timestamped or
sectioned outline — written as a self-contained HTML page under `~/take-notes/`
and opened in the browser.

Not a transcript dump and not a one-paragraph summary. The notes are written to
teach: a bullet only someone who already watched the video would understand has
failed the standard.

Works in **Claude Code, Codex, Cursor, OpenCode and Gemini CLI** — one `SKILL.md`,
no per-tool variants.

## Install

Clone into whichever skills directory your tool reads, so `SKILL.md` sits one
level deep:

```sh
git clone https://github.com/davertor/take-notes ~/.claude/skills/take-notes
```

Other valid roots: `~/.codex/skills/`, `~/.cursor/skills/`,
`~/.config/opencode/skills/`, `~/.gemini/skills/`, `~/.agents/skills/`.

Then invoke it: `/take-notes <url> [focus]`. The optional focus narrows what the
notes emphasise (`"just the API design part"`).

## Requirements

| | |
|---|---|
| **Python 3** | stdlib only — no `pip install`, no Markdown parser, no template engine |
| **yt-dlp + ffmpeg** | video sources only; `scripts/setup.py` installs them via Homebrew on macOS and prints the commands elsewhere |
| **Whisper API key** | *optional*. Only needed for videos with no captions. Groq (preferred, cheaper) or OpenAI, read from `~/.config/watch/.env` |

Web articles need none of the above — that path uses the agent's own fetch tool.

## How it works

```
SKILL.md              route by source, and the note-writing standard
references/
  youtube.md          captions via yt-dlp, Whisper fallback
  web.md              fetch + extract article text
scripts/
  transcript.py       transcript entry point (captions -> Whisper)
  render.py           wraps note HTML in a styled standalone page
  ...                 vendored transcript helpers
```

Only acquisition differs per source. Both guides hand back the same five fields
— title, byline, span, canonical URL, body — and the note-writing standard lives
in `SKILL.md` alone so it can't drift into per-source copies.

The skill emits body HTML directly and `render.py` wraps it. Nothing parses
Markdown, which is why the whole thing stays stdlib-only.

Re-running on the same source the same day **updates** that note instead of
adding a near-duplicate.

## Credits

`scripts/config.py`, `download.py`, `transcribe.py`, `whisper.py` and `setup.py`
are copied verbatim from [bradautomates/claude-video](https://github.com/bradautomates/claude-video)
(MIT) so this skill runs standalone. They are kept byte-identical to upstream on
purpose — see [`scripts/VENDORED.md`](scripts/VENDORED.md) for the drift check.

MIT licensed. See [LICENSE](LICENSE).
