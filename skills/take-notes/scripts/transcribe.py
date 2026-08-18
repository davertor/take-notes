#!/usr/bin/env python3
"""Parse a subtitle file into a clean, timestamped transcript.

Two input formats, because they differ in quality rather than content:

- json3 is YouTube's raw timed-event data; cues do not overlap, so it needs no
  cleanup. Prefer it.
- vtt renders the same track for the rolling caption box, repeating the tail of
  each cue at the head of the next so the text appears to scroll. Concatenating
  those cues duplicates about half the transcript, so the vtt path strips the
  carried-over prefix.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def _to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(path: str) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    segments: list[dict] = []
    i = 0
    while i < len(lines):
        match = TS_RE.match(lines[i])
        if not match:
            i += 1
            continue

        start = _to_seconds(*match.groups()[:4])
        end = _to_seconds(*match.groups()[4:])
        i += 1

        cue_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            cleaned = TAG_RE.sub("", lines[i]).strip()
            if cleaned:
                cue_lines.append(cleaned)
            i += 1

        cue_text = " ".join(cue_lines).strip()
        if cue_text:
            segments.append({"start": round(start, 2), "end": round(end, 2), "text": cue_text})
        i += 1

    return _dedupe(segments)


def parse_json3(path: str) -> list[dict]:
    """Parse YouTube's json3 timed-text. Cues are already disjoint — no dedupe."""
    raw = json.loads(Path(path).read_text(encoding="utf-8", errors="ignore"))
    segments: list[dict] = []
    for event in raw.get("events") or []:
        segs = event.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs)
        text = TAG_RE.sub("", text.replace("\n", " ")).strip()
        if not text:
            continue
        start = event.get("tStartMs", 0) / 1000.0
        end = start + event.get("dDurationMs", 0) / 1000.0
        segments.append({"start": round(start, 2), "end": round(end, 2), "text": text})
    return segments


def parse_subtitle(path: str) -> list[dict]:
    """Parse whichever caption format was downloaded."""
    return parse_json3(path) if str(path).endswith(".json3") else parse_vtt(path)


def _longest_overlap(prev: str, cur: str) -> int:
    """Length of the longest suffix of prev that is also a prefix of cur."""
    for n in range(min(len(prev), len(cur)), 0, -1):
        if prev[-n:] == cur[:n]:
            return n
    return 0


def _dedupe(segments: list[dict]) -> list[dict]:
    """Collapse the rolling duplication in YouTube's vtt rendering.

    Handles three shapes: an identical repeat, a cue that extends the previous
    one, and the scrolling case where a cue re-states only the tail of its
    predecessor. Overlaps shorter than MIN_OVERLAP are left alone so ordinary
    repeated words ("that that") are not mistaken for scroll carry-over.
    """
    MIN_OVERLAP = 8
    out: list[dict] = []
    for seg in segments:
        if out and seg["text"] == out[-1]["text"]:
            out[-1]["end"] = seg["end"]
            continue
        if out and seg["text"].startswith(out[-1]["text"] + " "):
            out[-1]["text"] = seg["text"]
            out[-1]["end"] = seg["end"]
            continue
        if out:
            overlap = _longest_overlap(out[-1]["text"], seg["text"])
            if overlap >= MIN_OVERLAP:
                trimmed = seg["text"][overlap:].strip()
                if not trimmed:
                    out[-1]["end"] = seg["end"]
                    continue
                seg = {**seg, "text": trimmed}
        out.append(seg)
    return out


def filter_range(
    segments: list[dict],
    start_seconds: float | None,
    end_seconds: float | None,
) -> list[dict]:
    """Return segments whose time range overlaps [start, end]."""
    if start_seconds is None and end_seconds is None:
        return segments
    lo = start_seconds if start_seconds is not None else float("-inf")
    hi = end_seconds if end_seconds is not None else float("inf")
    return [seg for seg in segments if seg["end"] >= lo and seg["start"] <= hi]


def format_transcript(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        start = int(seg["start"])
        stamp = f"[{start // 60:02d}:{start % 60:02d}]"
        lines.append(f"{stamp} {seg['text']}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: transcribe.py <subtitle-path>", file=sys.stderr)
        raise SystemExit(2)
    print(format_transcript(parse_subtitle(sys.argv[1])))
