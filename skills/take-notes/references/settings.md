# Settings management — `--tags`, `--theme`, `--retag`

Read from Step 0 of SKILL.md, only when the invocation manages the vocabulary,
the palette or the notes already on disk instead of writing a note. Do what
the matching row says, report the result, and **stop** — no source is
fetched and nothing after Step 0 applies.

| Invocation | Command |
|---|---|
| `/take-notes --tags` | `uv run "${SKILL_DIR}/scripts/tags.py"` |
| `/take-notes --add-tag "AI"` | `uv run "${SKILL_DIR}/scripts/tags.py" --add "AI"` |
| `/take-notes --remove-tag "AI"` | `uv run "${SKILL_DIR}/scripts/tags.py" --remove "AI"` |
| `/take-notes --theme` | `uv run "${SKILL_DIR}/scripts/themes.py"` |
| `/take-notes --theme "notebook"` | `uv run "${SKILL_DIR}/scripts/themes.py" --set "notebook"` |
| `/take-notes --retag` | re-files existing notes — the multi-step pass below |

Both editing forms are repeatable — pass `--add` or `--remove` once per tag.
The script prints the resulting vocabulary; report that, and nothing more. It
rewrites only the `tags` key, so `language` survives untouched.

`Unknown` cannot be removed: it is the fallback the note writer needs when a
source fits nothing. The script says so and leaves it in place.

### `--theme` — the colour the archive is painted in

`auto` (the default, following the system) or one of the named themes the
script lists. Each is a palette *and* a type stack. The script writes `theme` to the config and leaves every
other key alone; the value is baked into the gallery and into notes written from
then on. Ask for it in words too — "ponlo en petrol" is this command.

Say so when reporting: **notes already on disk keep the colours they were
written with.** The reader can still switch theme from the gallery's own menu,
which applies to that browser and rides along to any note opened from a card.

### `--retag` — re-file the notes already on disk

Filing a note under a new tag used to mean re-running `/take-notes` on its
source: a refetch and a full rewrite, to change one word in the rail. This pass
edits the rendered notes instead. Run it after adding tags to a vocabulary that
was empty or thinner when those notes were written.

1. **Read the vocabulary** — `uv run "${SKILL_DIR}/scripts/tags.py"`. If the
   only entry is `Unknown`, say so and **stop**: there is nothing to file notes
   under yet, and the user needs `--add-tag` first.
2. **List what is on disk** — `uv run "${SKILL_DIR}/scripts/retag.py" --list`.
   One JSON object per note: path, title, byline, kind, date, current `tags`,
   an `excerpt`, and `needs_tag`.
3. **Choose from the vocabulary and nothing else.** For every note with
   `"needs_tag": true`, pick the entry that fits from the list read in step 1;
   add further tags after the primary when they genuinely apply. The list is
   closed — the script rejects anything not on it rather than inventing a tag
   that would exist on one note and in no chip. Nothing fits, leave it on
   `Unknown`; a wrong file is worse than an unfiled note.
4. **Write each one** —
   `uv run "${SKILL_DIR}/scripts/retag.py" --set "<path>" --tag "<primary>" [--tag "<extra>"]`
5. **Rebuild the gallery** so the chips match the notes —
   `uv run "${SKILL_DIR}/scripts/gallery.py"`
6. Report one line per note re-filed, plus how many were left on `Unknown`.

`"needs_tag": false` means the note already carries a deliberate tag. Leave
those alone unless the user asked for every note; overwriting a filing someone
chose is not an update.

The pass rewrites only the rail's tag row. No source is fetched and no prose is
regenerated, so it costs the listing and the model's choices, nothing more.

