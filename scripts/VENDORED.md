# Vendored transcript helpers

Upstream: **[bradautomates/claude-video](https://github.com/bradautomates/claude-video)**
(MIT, © 2026 Bradley Bonanno), which is also what the `yt-watch` skill packages.

These files are **byte-identical copies** of that project's transcript path, so
`/take-notes` runs without depending on another skill being installed:

| File | Role |
|---|---|
| `config.py` | `~/.config/watch/.env` reader |
| `download.py` | yt-dlp captions + metadata, audio-only download |
| `transcribe.py` | WebVTT → timestamped segments |
| `whisper.py` | Groq/OpenAI fallback when captions are missing |
| `setup.py` | ffmpeg/yt-dlp preflight, `.env` scaffolding |

**Do not edit them here.** They are kept verbatim on purpose: drift is meant to
be detectable with a plain diff.

When `yt-watch` is installed alongside (it packages the same upstream), compare
locally:

```sh
diff -r ~/skills/yt-watch/scripts ~/skills/take-notes/scripts
```

Expected output is only the files that exist on one side — `frames.py`,
`watch.py`, `build-skill.sh`, `__pycache__` (yt-watch) and `transcript.py`,
`render.py`, `VENDORED.md` (take-notes). Any difference reported *inside* one of
the five files above means the copies have diverged; re-copy and re-test.

Standalone, compare against upstream directly:

```sh
git clone --depth 1 https://github.com/bradautomates/claude-video /tmp/cv
diff -r /tmp/cv/skills/watch/scripts scripts
```

Deliberately **not** vendored: `frames.py` (frame extraction) and `watch.py`
(frame orchestration). `transcript.py` replaces `watch.py` for the captions →
Whisper flow only — this skill is transcript-only by design.

`~/.config/watch/.env` is shared with `yt-watch`, so API keys are configured
once.
