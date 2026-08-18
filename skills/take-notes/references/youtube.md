# Acquisition — video (YouTube, any yt-dlp source, local media file)

Acquisition only. Return the fields listed in SKILL.md Step 1 and go back there
to write the notes.

`SKILL_DIR` is already resolved in SKILL.md — reuse it.

## Preflight (first invocation in a session, silent on success)

```bash
uv run "${SKILL_DIR}/scripts/setup.py" --json
```

If `first_run` is true, install any `missing_binaries` and encourage a Whisper
API key written to `~/.config/watch/.env`. A missing key is worth fixing, not a
blocker — videos with native captions work without one.

## Get the transcript

```bash
uv run "${SKILL_DIR}/scripts/transcript.py" "<url-or-path>"
```

Prints the title, channel, duration, published date, views, thumbnail, YouTube
video ID, and the timestamped transcript. Native captions when the source has
them, Whisper on audio-only when it doesn't. Frames are never extracted: notes
come from what is said, and frames are where the token cost lives.

Captions come back **in the language actually spoken**, not translated — the
script picks the untranslated track and reports which one under
`**Caption track:**`. If that line says `machine-translated`, no original-language
track was offered; say so in *Going deeper* and treat proper nouns with suspicion,
because translation mangles them.

The temporary working directory is deleted on exit. Useful flags: `--no-whisper`
to skip the fallback, `--whisper groq|openai` to force a backend, `--keep` or
`--out-dir` to retain the working files.

## Map the output to the Step 1 fields

Pass the **raw** value — the bare number before the parenthesis — for duration,
published and views. `render.py` formats them for the chosen language; the
parenthesised form is only there for you to read.

| Step 1 field | From |
|---|---|
| title | `**Title:**` |
| byline | `**Channel:**` |
| channel URL | `**Channel URL:**` — omitted when yt-dlp doesn't report one |
| duration | `**Duration:**` — the seconds, e.g. `692` |
| published | `**Published:**` — the `YYYYMMDD`, e.g. `20260816` |
| views | `**Views:**` — the integer, e.g. `13232` |
| thumbnail | `**Thumbnail:**` — omitted when yt-dlp doesn't report one |
| caption language | `**Caption track:**` — note it in *Going deeper* when machine-translated |
| canonical URL + video ID | `**Video ID:**` line, which also gives the `?t=<seconds>s` deep-link form |
| body | everything in the `## Transcript` fenced block |

The video ID is what makes the timestamped outline clickable, and what
switches Step 5's renderer to the two-pane video layout — carry it back.

## Failure

**Exit code 1 means no transcript** — captions missing and Whisper unavailable
or failed. Report that and stop. Do not write notes from the title and
description. `/yt-watch` with frames is the fallback the user can choose.
