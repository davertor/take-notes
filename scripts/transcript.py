#!/usr/bin/env python3
"""Transcript-only entry point for /take-notes.

Prints video metadata plus a timestamped transcript to stdout. No frames: this
is the whole reason the skill vendors a transcript slice of /yt-watch instead
of shelling out to it (frames.py is 26k of code and the bulk of the token cost).

Flow: captions via yt-dlp when the source has them, Whisper on audio-only when
it doesn't. Exits non-zero when neither produces a transcript, so the skill can
stop rather than write notes from a title and a description.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from download import download, fetch_captions, is_url  # noqa: E402
from transcribe import format_transcript, parse_vtt  # noqa: E402
from whisper import load_api_key, transcribe_video  # noqa: E402


YOUTUBE_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/))([A-Za-z0-9_-]{11})"
)


def format_time(seconds: float) -> str:
    """Seconds to H:MM:SS, dropping the hour component when it is zero."""
    total = int(max(0.0, seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def youtube_id(url: str) -> str | None:
    """Video ID from a YouTube URL, so the notes can build ?t=<s>s deep links."""
    match = YOUTUBE_ID_RE.search(url or "")
    return match.group(1) if match else None


def duration_seconds(info: dict, segments: list[dict]) -> float:
    """Prefer yt-dlp's duration; fall back to the last cue so local files still
    report a length without pulling in frames.py's ffprobe helper."""
    raw = (info or {}).get("duration")
    if raw:
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    return float(segments[-1]["end"]) if segments else 0.0


def _selftest() -> int:
    assert format_time(0) == "00:00"
    assert format_time(65) == "01:05"
    assert format_time(3661) == "1:01:01"
    assert format_time(-5) == "00:00"

    assert youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s") == "dQw4w9WgXcQ"
    assert youtube_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert youtube_id("https://example.com/video.mp4") is None

    assert duration_seconds({"duration": 120}, []) == 120.0
    assert duration_seconds({}, [{"start": 0, "end": 42.5}]) == 42.5
    assert duration_seconds({"duration": None}, []) == 0.0

    # Regression: manual '.en.' must beat auto-generated '.en-orig.'. A plain
    # filename sort picks en-orig ('-' < '.'), which is the rolling-duplicate track.
    from download import _pick_subtitle  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name in ("video.en-orig.vtt", "video.en-en.vtt", "video.en.vtt"):
            (d / name).touch()
        assert _pick_subtitle(d).name == "video.en.vtt", _pick_subtitle(d).name

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "video.fr.vtt").touch()
        assert _pick_subtitle(d).name == "video.fr.vtt"

    with tempfile.TemporaryDirectory() as tmp:
        assert _pick_subtitle(Path(tmp)) is None

    print("selftest: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="transcript",
        description="Fetch a timestamped transcript for a video URL or local file.",
    )
    ap.add_argument("source", nargs="?", help="Video URL or local file path")
    ap.add_argument("--out-dir", default=None, help="Working directory (default: tmp)")
    ap.add_argument(
        "--no-whisper",
        action="store_true",
        help="Disable the Whisper fallback; fail if no captions are available.",
    )
    ap.add_argument(
        "--whisper",
        choices=["groq", "openai"],
        default=None,
        help="Force a Whisper backend. Default: prefer Groq, fall back to OpenAI.",
    )
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.source:
        ap.error("source is required")

    work = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else Path(tempfile.mkdtemp(prefix="take-notes-"))
    )
    work.mkdir(parents=True, exist_ok=True)
    print(f"[transcript] working dir: {work}", file=sys.stderr)

    segments: list[dict] = []
    source_label: str | None = None
    info: dict = {}

    if is_url(args.source):
        print("[transcript] checking metadata/captions via yt-dlp…", file=sys.stderr)
        dl = fetch_captions(args.source, work / "download")
        info = dl.get("info") or {}
        if dl.get("subtitle_path"):
            try:
                segments = parse_vtt(dl["subtitle_path"])
                source_label = "captions"
            except Exception as exc:
                print(f"[transcript] subtitle parse failed: {exc}", file=sys.stderr)
                segments = []

    if not segments:
        if args.no_whisper:
            print("[transcript] no captions and --no-whisper set", file=sys.stderr)
        else:
            backend, api_key = load_api_key(args.whisper)
            if not backend or not api_key:
                setup_py = SCRIPT_DIR / "setup.py"
                hint = (
                    f"--whisper {args.whisper} was set but its API key is missing"
                    if args.whisper
                    else "no captions and no Whisper API key found"
                )
                print(
                    f"[transcript] {hint} — run `python3 {setup_py}` to configure",
                    file=sys.stderr,
                )
            else:
                print("[transcript] no captions — downloading audio for Whisper…", file=sys.stderr)
                dl = download(args.source, work / "download", audio_only=True)
                info = dl.get("info") or info
                try:
                    segments, used = transcribe_video(
                        dl["video_path"],
                        work / "audio.mp3",
                        backend=backend,
                        api_key=api_key,
                    )
                    source_label = f"whisper ({used})"
                except SystemExit as exc:
                    print(f"[transcript] whisper fallback failed: {exc}", file=sys.stderr)

    if not segments:
        print(
            "[transcript] no transcript available — captions were missing and Whisper was "
            "unavailable or failed. Do not write notes from metadata alone.",
            file=sys.stderr,
        )
        return 1

    total = duration_seconds(info, segments)
    canonical = info.get("url") or args.source
    vid = youtube_id(canonical) or youtube_id(args.source)

    print()
    print("# transcript")
    print()
    print(f"- **Source:** {args.source}")
    if info.get("title"):
        print(f"- **Title:** {info['title']}")
    if info.get("uploader"):
        print(f"- **Channel:** {info['uploader']}")
    print(f"- **Duration:** {format_time(total)} ({total:.1f}s)")
    if vid:
        print(f"- **Video ID:** {vid} (deep links: https://youtu.be/{vid}?t=<seconds>s)")
    print(f"- **Segments:** {len(segments)} (via {source_label or 'captions'})")

    print()
    print("## Transcript")
    print()
    print(f"_Source: {source_label or 'captions'}._")
    print()
    print("```")
    print(format_transcript(segments))
    print("```")

    print()
    print("---")
    print(f"_Work dir: `{work}` — delete when done._")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
