#!/usr/bin/env python3
"""Download a video via yt-dlp, or resolve a local file path.

Also fetches subtitles (manual first, then auto-generated) in VTT format so
transcribe.py can parse them without needing Whisper.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv", ".wmv"}


def is_url(source: str) -> bool:
    if source.startswith("-"):
        return False
    parsed = urlparse(source)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def resolve_local(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise SystemExit(f"File not found: {p}")
    if p.suffix.lower() not in VIDEO_EXTS:
        print(
            f"[watch] warning: {p.suffix} is not a known video extension, proceeding anyway",
            file=sys.stderr,
        )
    return {
        "video_path": str(p),
        "subtitle_path": None,
        "info": {"title": p.name, "url": str(p)},
        "downloaded": False,
    }


SUBTITLE_EXTS = (".json3", ".vtt")


def _pick_subtitle(out_dir: Path) -> Path | None:
    """Pick the downloaded caption file, preferring json3 over vtt.

    json3 carries YouTube's raw timed events; its vtt rendering repeats the tail
    of each cue in the next one to animate the rolling caption box, which
    duplicates roughly half the transcript. Same track, same words — the format
    is what differs, so prefer json3 whenever it came down.
    """
    for ext in SUBTITLE_EXTS:
        candidates = sorted(out_dir.glob(f"video*{ext}"))
        if candidates:
            return candidates[0]
    return None


def choose_subtitle_lang(info: dict) -> str | None:
    """Pick the caption track closest to what was actually spoken.

    A translated track is a machine translation of a machine transcription:
    proper nouns get mangled (EHang -> "Hang") and nuance is lost. The original
    language always beats a translation, and a human-written track beats ASR.
    Returns a yt-dlp --sub-langs value, or None to let the caller fall back.
    """
    manual = list((info.get("subtitles") or {}).keys())
    auto = list((info.get("automatic_captions") or {}).keys())
    lang = (info.get("language") or "").lower()
    base = lang.split("-")[0] if lang else ""

    def same_base(pool: list[str], suffix: str = "") -> str | None:
        exact = [t for t in pool if t.lower() == lang + suffix or t.lower() == base + suffix]
        if exact:
            return exact[0]
        loose = [t for t in pool if t.split("-")[0].lower() == base and t.endswith(suffix)]
        return loose[0] if loose else None

    if base:
        # 1. human-written captions in the spoken language
        hit = same_base(manual)
        if hit:
            return hit
        # 2. ASR in the spoken language ('-orig' is YouTube's untranslated track)
        hit = same_base(auto, "-orig") or same_base(auto)
        if hit:
            return hit
    # 3. any untranslated ASR track, whatever the language
    hit = next((t for t in auto if t.endswith("-orig")), None)
    if hit:
        return hit
    # 4. any human-written track
    if manual:
        return manual[0]
    # 5. only translations left — English is the best-supported one
    return next((t for t in auto if t.split("-")[0].lower() == "en"), None)


def _pick_video(out_dir: Path) -> Path | None:
    for ext in (".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".opus"):
        for candidate in out_dir.glob(f"video*{ext}"):
            return candidate
    for candidate in out_dir.glob("video.*"):
        if candidate.suffix.lower() in VIDEO_EXTS:
            return candidate
    return None


def fetch_captions(url: str, out_dir: Path) -> dict:
    """Fetch metadata, then the caption track in the language actually spoken.

    Two passes on purpose: which track to ask for depends on the video's
    language, and that only arrives with the metadata. The first pass downloads
    no media and no subtitles, so it costs one API round trip.
    """
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")
    base_cmd = ["yt-dlp", "--skip-download", "--no-playlist", "--ignore-errors", "-o", output_template]

    subprocess.run(
        base_cmd + ["--write-info-json", "--", url], stdout=sys.stderr, stderr=sys.stderr
    )
    info_path = out_dir / "video.info.json"
    info = _read_info(info_path, url)
    tracks = _read_track_index(info_path)

    lang = choose_subtitle_lang(tracks)
    if lang:
        info["subtitle_lang"] = lang
        info["subtitle_translated"] = _is_translated(tracks, lang)
        print(
            f"[watch] captions: {lang}"
            + (" (translated — no original-language track offered)"
               if info["subtitle_translated"] else " (original language)"),
            file=sys.stderr,
        )
        subprocess.run(
            base_cmd + [
                "--write-subs", "--write-auto-subs",
                "--sub-langs", lang,
                # json3 has no rolling-cue duplication; vtt is the fallback for
                # sources that do not offer it.
                "--sub-format", "json3/vtt/best",
                "--", url,
            ],
            stdout=sys.stderr, stderr=sys.stderr,
        )

    subtitle = _pick_subtitle(out_dir)
    return {
        "video_path": None,
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "downloaded": False,
    }


def _read_track_index(info_path: Path) -> dict:
    """Just the caption-track listings and spoken language from info.json."""
    if not info_path.exists():
        return {}
    try:
        raw = json.loads(info_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[watch] info.json parse failed: {exc}", file=sys.stderr)
        return {}
    return {
        "language": raw.get("language"),
        "subtitles": raw.get("subtitles") or {},
        "automatic_captions": raw.get("automatic_captions") or {},
    }


def _is_translated(tracks: dict, lang: str) -> bool:
    """True when the chosen track is a machine translation of another language."""
    spoken = (tracks.get("language") or "").split("-")[0].lower()
    if not spoken:
        return False
    if lang in (tracks.get("subtitles") or {}):
        return False                      # human-written, take it at face value
    if lang.endswith("-orig"):
        return False
    return lang.split("-")[0].lower() != spoken


def _read_info(info_path: Path, url: str) -> dict:
    info: dict = {}
    if info_path.exists():
        try:
            raw = json.loads(info_path.read_text(encoding="utf-8"))
            info = {
                "title": raw.get("title"),
                "uploader": raw.get("uploader") or raw.get("channel"),
                "uploader_url": raw.get("channel_url") or raw.get("uploader_url"),
                "duration": raw.get("duration"),
                "upload_date": raw.get("upload_date"),
                "view_count": raw.get("view_count"),
                "thumbnail": raw.get("thumbnail"),
                "url": raw.get("webpage_url") or url,
            }
        except Exception as exc:
            print(f"[watch] info.json parse failed: {exc}", file=sys.stderr)
            info = {"url": url}
    return info


def download_url(
    url: str,
    out_dir: Path,
    audio_only: bool = False,
) -> dict:
    if shutil.which("yt-dlp") is None:
        raise SystemExit("yt-dlp is not installed. Install with: brew install yt-dlp")

    out_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(out_dir / "video.%(ext)s")

    fmt = "ba/bestaudio" if audio_only else "bv*[height<=720]+ba/b[height<=720]/bv+ba/b"
    cmd = [
        "yt-dlp",
        "-N", "8",
        "-f", fmt,
        "--merge-output-format", "mp4",
        "--write-info-json",
        "--write-subs",
        "--write-auto-subs",
        # Same preference as fetch_captions: untranslated track, unrolled format.
        "--sub-langs", ".*-orig,en.*",
        "--sub-format", "json3/vtt/best",
        "--no-playlist",
        "--ignore-errors",
        "-o", output_template,
        "--",
        url,
    ]

    # yt-dlp may exit non-zero if a subtitle variant fails (e.g. 429) even when
    # the video itself downloaded fine. Treat "video file present" as success.
    result = subprocess.run(cmd, stdout=sys.stderr, stderr=sys.stderr)
    video = _pick_video(out_dir)
    if video is None:
        raise SystemExit(
            f"yt-dlp did not produce a video file in {out_dir} (exit {result.returncode})"
        )

    subtitle = _pick_subtitle(out_dir)
    info = _read_info(out_dir / "video.info.json", url)

    return {
        "video_path": str(video),
        "subtitle_path": str(subtitle) if subtitle else None,
        "info": info or {"url": url},
        "downloaded": True,
    }


def download(
    source: str,
    out_dir: Path,
    audio_only: bool = False,
) -> dict:
    if is_url(source):
        return download_url(source, out_dir, audio_only=audio_only)
    return resolve_local(source)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: download.py <url-or-path> <out-dir>", file=sys.stderr)
        raise SystemExit(2)
    result = download(sys.argv[1], Path(sys.argv[2]))
    print(json.dumps(result, indent=2))
