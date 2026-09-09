#!/usr/bin/env -S uv run --script
"""Check the document invariants CONTRIBUTING.md claims but nothing enforces.

The scripts' `--selftest` asserts cover the scripts. These are the invariants
that live in prose, and every one of them breaks silently: a routing row the
catch-all above it swallows, a guide the table names and nobody wrote, a
second copy of the writing standard free to drift from the first, a rule that
holds the whole contract together quietly dropped in a rewrite. Nothing fails
until a note is already wrong.

Development tooling — not part of the shipped skill. From the repo root:

    uv run scripts/check-drift.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/take-notes/SKILL.md"
CHANGELOG = ROOT / "CHANGELOG.md"
REFERENCES = ROOT / "skills/take-notes/references"
CODEX_AGENT = ROOT / "skills/take-notes/agents/openai.yaml"

# Rules the output rests on, each dropped without a single assert firing.
REQUIRED_PHRASES = {
    "must be `&amp;`, `&lt;`, `&gt;`": "an unescaped & in an image URL breaks the note",
    "Never invent a tag": "keeps the tag vocabulary closed",
    "could not get the body": "never write notes from a title or a paywall stub",
    "Didactic means explaining, not compressing": "the point of the whole skill",
}

# What a copied-in section contract looks like. The writing standard has one
# copy, in SKILL.md; the guides under references/ are acquisition only.
WRITING_STANDARD_MARKERS = ("Executive summary", "The one takeaway", "Didactic means")


def main() -> int:
    errors: list[str] = []
    skill = SKILL.read_text(encoding="utf-8")

    # 1. Never-auto-invoke lives in two files, and they must move together.
    if "disable-model-invocation: true" not in skill:
        errors.append(
            "SKILL.md dropped `disable-model-invocation: true` — the skill would fire on any "
            "URL merely mentioned in conversation"
        )
    if "allow_implicit_invocation: false" not in CODEX_AGENT.read_text(encoding="utf-8"):
        errors.append(
            "agents/openai.yaml dropped `allow_implicit_invocation: false` — Codex would "
            "auto-fire; it pairs with SKILL.md's `disable-model-invocation`"
        )

    # 2. Step 1 is matched top to bottom, first match wins, so the catch-all is last.
    routed = re.findall(r"^\|.*`references/([a-z-]+\.md)`.*\|$", skill, re.M)
    if "web.md" not in routed:
        errors.append("SKILL.md Step 1 has no `references/web.md` catch-all row")
    else:
        swallowed = routed[routed.index("web.md") + 1 :]
        if swallowed:
            errors.append(
                f"SKILL.md Step 1 lists {', '.join(swallowed)} below the `web.md` catch-all, "
                "which matches http(s) first — those rows are unreachable"
            )

    # 3. The table and the directory name the same guides.
    on_disk = {p.name for p in REFERENCES.glob("*.md")}
    for missing in sorted(set(routed) - on_disk):
        errors.append(f"SKILL.md Step 1 routes to references/{missing}, which is not on disk")
    for orphan in sorted(on_disk - set(routed)):
        errors.append(f"references/{orphan} ships to users but no Step 1 row routes to it")

    # 4. Acquisition guides know nothing about how notes are written.
    for guide in sorted(REFERENCES.glob("*.md")):
        copied = [m for m in WRITING_STANDARD_MARKERS if m in guide.read_text(encoding="utf-8")]
        if copied:
            errors.append(
                f"references/{guide.name} carries the writing standard ({', '.join(copied)}) — "
                "it belongs in SKILL.md alone, or the two copies drift"
            )

    # 5. Load-bearing rules survive a rewrite.
    for phrase, why in REQUIRED_PHRASES.items():
        if phrase not in skill:
            errors.append(f"SKILL.md lost the rule {phrase!r} — {why}")

    # 6. The version that ships is a version someone can read the notes for.
    version = re.search(r'^\s*version:\s*"([^"]+)"', skill, re.M)
    if version is None:
        errors.append("SKILL.md has no `version:` in its frontmatter")
    elif f"## [{version.group(1)}]" not in CHANGELOG.read_text(encoding="utf-8"):
        errors.append(
            f"CHANGELOG.md has no `## [{version.group(1)}]` section — that version ships with "
            "nothing telling anyone what changed, or whether updating is worth it"
        )

    for e in errors:
        print(f"drift: {e}", file=sys.stderr)
    if errors:
        print(
            f"\n{len(errors)} broken invariant(s). See CONTRIBUTING.md § The four things "
            "that will bite you.",
            file=sys.stderr,
        )
        return 1
    print("ok: skill invariants hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
