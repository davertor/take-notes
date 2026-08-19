# Security

## Reporting a vulnerability

Report privately through GitHub's
[security advisory form](https://github.com/davertor/take-notes/security/advisories/new)
rather than opening a public issue. Expect an acknowledgement within a week.

## What this skill actually does on your machine

Worth knowing before you install anything that an AI agent can invoke:

- **It runs local scripts through `uv`.** They are stdlib-only Python; there are
  no third-party packages to audit. Read them in `skills/take-notes/scripts/`.
- **It shells out to `yt-dlp` and `ffmpeg`** for video sources only, on URLs or
  local paths you supply.
- **It writes only under `~/take-notes/`** and opens files in your browser.
- **It never runs on its own.** `disable-model-invocation: true` and the Codex
  equivalent in `agents/openai.yaml` mean the agent cannot trigger it from a URL
  you happen to mention — only an explicit `/take-notes` does.
- **Optional API keys** (Groq or OpenAI, for Whisper on videos without captions)
  are read from `~/.config/watch/.env` and sent only to that provider. Nothing
  else leaves your machine except the fetches needed to acquire the source.

## Notes are derived from other people's work

A note summarises a source you do not own. Keeping notes locally for study is
ordinary use. If you republish them, that is your call to make — check the
source's licence and terms, and keep quotes short and attributed, as the skill's
own rules already require.
