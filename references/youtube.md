# Acquisition — video (YouTube, any yt-dlp source, local media file)

Acquisition only. Return the fields listed in SKILL.md Step 1 and go back there
to write the notes.

`SKILL_DIR` is already resolved in SKILL.md — reuse it.

## Preflight (first invocation in a session, silent on success)

```bash
python3 "${SKILL_DIR}/scripts/setup.py" --json
```

If `first_run` is true, install any `missing_binaries` and encourage a Whisper
API key written to `~/.config/watch/.env`. A missing key is worth fixing, not a
blocker — videos with native captions work without one.

## Get the transcript

```bash
python3 "${SKILL_DIR}/scripts/transcript.py" "<url-or-path>"
```

Prints the title, channel, duration, YouTube video ID, and the timestamped
transcript. Native captions when the source has them, Whisper on audio-only
when it doesn't. Frames are never extracted: notes come from what is said, and
frames are where the token cost lives.

Useful flags: `--no-whisper` to skip the fallback, `--whisper groq|openai` to
force a backend, `--out-dir` to keep the working directory.

## Map the output to the Step 1 fields

| Step 1 field | From |
|---|---|
| title | `**Title:**` |
| byline | `**Channel:**` |
| span | `**Duration:**` |
| canonical URL + video ID | `**Video ID:**` line, which also gives the `?t=<seconds>s` deep-link form |
| body | everything in the `## Transcript` fenced block |

The video ID is what makes the timestamped outline clickable — carry it back.

## Failure

**Exit code 1 means no transcript** — captions missing and Whisper unavailable
or failed. Report that and stop. Do not write notes from the title and
description. `/yt-watch` with frames is the fallback the user can choose.
