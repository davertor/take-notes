#!/usr/bin/env -S uv run --script
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
import shutil
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR))

from download import download, fetch_captions, is_url  # noqa: E402
from transcribe import format_transcript, parse_subtitle  # noqa: E402
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


MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def format_upload_date(raw: str | None) -> str | None:
    """yt-dlp's YYYYMMDD to 'Mon D, YYYY'; None when missing or malformed."""
    if not raw or len(raw) != 8 or not raw.isdigit():
        return None
    year, month, day = raw[:4], int(raw[4:6]), int(raw[6:8])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{MONTHS[month - 1]} {day}, {year}"


def format_count(n: int | None) -> str | None:
    """Abbreviate a view/like count: 13800000 -> '13.8M', 900 -> '900'."""
    if n is None:
        return None
    for div, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= div:
            text = f"{n / div:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return str(n)


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

    assert format_upload_date("20251205") == "Dec 5, 2025"
    assert format_upload_date("2025120") is None
    assert format_upload_date(None) is None
    assert format_upload_date("20251399") is None

    assert format_count(900) == "900"
    assert format_count(13_800_000) == "13.8M"
    assert format_count(1_000_000) == "1M"
    assert format_count(None) is None

    from download import _is_translated, _pick_subtitle, choose_subtitle_lang  # noqa: PLC0415

    # json3 wins over vtt: same words, but vtt duplicates ~half of them to
    # animate the rolling caption box.
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name in ("video.es-orig.vtt", "video.es-orig.json3"):
            (d / name).touch()
        assert _pick_subtitle(d).name == "video.es-orig.json3", _pick_subtitle(d).name

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "video.fr.vtt").touch()
        assert _pick_subtitle(d).name == "video.fr.vtt"

    with tempfile.TemporaryDirectory() as tmp:
        assert _pick_subtitle(Path(tmp)) is None

    # Track choice: never take a translation when the spoken language is on offer.
    spanish = {
        "language": "es-US",
        "subtitles": {},
        "automatic_captions": {"es": [], "es-orig": [], "en": [], "fr": []},
    }
    assert choose_subtitle_lang(spanish) == "es-orig"
    assert _is_translated(spanish, "es-orig") is False
    assert _is_translated(spanish, "en") is True

    # Human-written captions in the spoken language beat ASR.
    assert choose_subtitle_lang({
        "language": "es", "subtitles": {"es": []},
        "automatic_captions": {"es-orig": [], "en": []},
    }) == "es"

    # English source: the original track is still the English one.
    assert choose_subtitle_lang({
        "language": "en", "subtitles": {},
        "automatic_captions": {"en-orig": [], "es": []},
    }) == "en-orig"

    # No language reported: fall back to any untranslated track, then English.
    assert choose_subtitle_lang({
        "language": None, "subtitles": {}, "automatic_captions": {"de-orig": [], "en": []},
    }) == "de-orig"
    assert choose_subtitle_lang({
        "language": None, "subtitles": {}, "automatic_captions": {"en": [], "fr": []},
    }) == "en"
    assert choose_subtitle_lang({"language": None, "subtitles": {}, "automatic_captions": {}}) is None

    # Rolling-cue carry-over is stripped; ordinary repeated words are not.
    from transcribe import _dedupe  # noqa: PLC0415

    rolled = _dedupe([
        {"start": 0, "end": 2, "text": "welcome back to my channel. Today, while on"},
        {"start": 2, "end": 4, "text": "Today, while on vacation I have a"},
        {"start": 4, "end": 6, "text": "vacation I have a little time"},
    ])
    assert " ".join(s["text"] for s in rolled) == (
        "welcome back to my channel. Today, while on vacation I have a little time"
    ), rolled
    short = _dedupe([
        {"start": 0, "end": 1, "text": "he said that"},
        {"start": 1, "end": 2, "text": "that was the plan"},
    ])
    assert [s["text"] for s in short] == ["he said that", "that was the plan"], short

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
    ap.add_argument(
        "--keep",
        action="store_true",
        help="Keep the temporary working directory instead of deleting it on exit.",
    )
    ap.add_argument("--selftest", action="store_true", help="Run internal asserts and exit")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if not args.source:
        ap.error("source is required")

    # The transcript is piped into the skill, and a redirected stdout encodes
    # with the locale codec on Windows (cp1252) — non-ASCII captions or a
    # non-ASCII title would raise UnicodeEncodeError mid-dump.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    # An explicit --out-dir is the caller's to manage; a tempdir is ours, so we
    # delete it. Captions plus the yt-dlp metadata dump run to ~650KB per video,
    # which otherwise accumulates in /var/folders forever.
    ephemeral = not args.out_dir and not args.keep
    work = (
        Path(args.out_dir).expanduser().resolve()
        if args.out_dir
        else Path(tempfile.mkdtemp(prefix="take-notes-"))
    )
    work.mkdir(parents=True, exist_ok=True)
    print(f"[transcript] working dir: {work}", file=sys.stderr)
    try:
        return _run(args, work, ephemeral)
    finally:
        if ephemeral:
            shutil.rmtree(work, ignore_errors=True)


def _run(args, work: Path, ephemeral: bool) -> int:

    segments: list[dict] = []
    source_label: str | None = None
    info: dict = {}

    if is_url(args.source):
        print("[transcript] checking metadata/captions via yt-dlp…", file=sys.stderr)
        dl = fetch_captions(args.source, work / "download")
        info = dl.get("info") or {}
        if dl.get("subtitle_path"):
            try:
                segments = parse_subtitle(dl["subtitle_path"])
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
                    f"[transcript] {hint} — run `uv run {setup_py}` to configure",
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
    if info.get("uploader_url"):
        print(f"- **Channel URL:** {info['uploader_url']}")
    # Raw values, for passing straight to render.py, which formats them per
    # --lang. Pre-formatting here would bake one language into the pipeline.
    print(f"- **Duration:** {int(total)}  ({format_time(total)})")
    if info.get("upload_date"):
        print(f"- **Published:** {info['upload_date']}  ({format_upload_date(info['upload_date'])})")
    if info.get("view_count") is not None:
        print(f"- **Views:** {info['view_count']}  ({format_count(info['view_count'])})")
    if info.get("thumbnail"):
        print(f"- **Thumbnail:** {info['thumbnail']}")
    if info.get("subtitle_lang"):
        origin = "machine-translated" if info.get("subtitle_translated") else "original language"
        print(f"- **Caption track:** {info['subtitle_lang']} ({origin})")
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

    if not ephemeral:
        print()
        print("---")
        print(f"_Work dir: `{work}` — delete when done._")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
