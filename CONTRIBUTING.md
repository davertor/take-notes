# Contributing

Issues and pull requests are welcome. This is a small project with a deliberate
shape — the notes below are the parts that are not obvious from reading the
tree, and the constraints that keep it installable in one command.

## Set up

```sh
git clone https://github.com/davertor/take-notes
cd take-notes
./link-skill.sh          # symlinks your checkout into every tool — edits are live
```

No build, no virtualenv, no install step. `uv` provisions Python per script.

## Verify

There is no test suite. Each script with non-trivial logic carries its own
asserts behind `--selftest`, and all of them must pass before a PR:

```sh
for s in render notes gallery export transcript tags retag slides themes; do
  uv run skills/take-notes/scripts/$s.py --selftest
done
```

CI runs exactly this, plus a check that the plugin manifests parse and their
version matches `SKILL.md`'s.

## Releases

Cut from `main` after a PR merges, never inside the feature branch:

```sh
uvx --from commitizen cz bump --yes && git push --follow-tags
```

[commitizen](https://commitizen-tools.github.io/commitizen/) reads the
Conventional Commits since the last tag, decides whether that is a patch, a
minor or a major, and rewrites the version in the five files that mirror it —
`SKILL.md`, both `plugin.json`, `marketplace.json` and the README badge — then
commits `chore(release): X.Y.Z` and tags. It runs through `uvx`, so it is not a
dependency of anything: nothing is installed and no manifest mentions it. The
configuration is in [`.cz.toml`](.cz.toml).

**The CHANGELOG stays hand-written.** commitizen is told not to touch it,
because the entries here are prose explaining what changed and why, and the
generated form is a list of commit subjects. Write the section yourself;
`cz changelog --dry-run` prints the commits grouped by type as a checklist so
none is missed.

## House rules

- **Stdlib only.** Every script runs under `uv` with no dependencies. A new
  dependency is a much bigger ask of everyone who installs this than the few
  lines it saves — the bar is "the standard library genuinely cannot do it".
- **English everywhere in the repo** — identifiers, comments, commit messages,
  docs — whatever language your notes come out in.
- **Conventional Commits** for commits and PR titles: `feat(take-notes): …`,
  `fix(skills): …`, `docs: …`. This matches the whole history and is what
  [CHANGELOG.md](CHANGELOG.md) is written from.
- **A behaviour change needs an assert.** If you can't express it as one, say so
  in the PR and explain how you checked it by hand.

## The four things that will bite you

The skill follows the [Agent Skills](https://agentskills.io/specification)
layout, so `skills/take-notes/` is browsable on its own. What it won't tell you:

### 1. Never-auto-invoke lives in two files

`disable-model-invocation: true` in `SKILL.md` and its Codex counterpart in
`agents/openai.yaml` are what keep the skill user-invoked. Change one without
the other and that tool starts firing on any URL you merely mention in
conversation. They must move together.

### 2. `SKILL.md` holds the only copy of the note-writing standard

The guides under `references/` cover **acquisition only**. Each one hands back
the same five fields (title, byline, span, canonical URL, body) whatever the
source, and knows nothing about how notes are written. Adding a source means
adding one guide and one routing row — never a second copy of the writing
rules, which would immediately drift from the first.

The routing table in `SKILL.md` Step 1 is matched **top to bottom, first match
wins**. `arxiv.org`, `docs.google.com/presentation` and `github.com` are
`http(s)` pages, so they must stay above the catch-all `web.md` row or they will
never be reached.

### 3. The note templates are a machine-readable contract

`gallery.py` and `export.py` read rendered notes back through `notes.py` —
there is no index or database. That makes these landmarks a contract, not
styling:

| Landmark | In | Read by |
|---|---|---|
| `.poster`, `.kicker`, `.meta`, `.watch` | both note templates | the masthead parser |
| `.tags` / `.tag` / `.tag.is-primary`, immediately above the literal `<div id="index">` | both note templates | the tag parser, the gallery's chips, and `retag.py`'s insertion anchor |
| `<article id="body">` with a flat run of `<h2>` | both note templates | the section splitter |
| `<li><strong>term</strong> — definition</li>` | `SKILL.md` Key points / Concepts | the Anki card builder |

`.sources` — the companion links a multi-source note carries — is deliberately
**not** part of that contract and must never be given `class="watch"`: the
masthead parser takes the first `.watch` href as the note's source, and would
file a combined note under its companion instead of its primary.

Rename a class or change that list shape and `notes.py --selftest` fails, which
is the point. Run it after touching a template or the Sections part of
`SKILL.md`.

### 4. Section lookup is bilingual

Notes are written in English or Spanish, so anything that finds a section by
name matches both — see `SECTION_WORDS` in `scripts/notes.py` and the matching
regexes in the inline script of each note template under `assets/`. Adding a
language means adding to all of them, and to the string tables in `render.py`
and `gallery.py`.

### 5. A theme is values, never a catalogue

`scripts/themes.py` is the single source of truth for both the palette and the
type. A rendered note carries only the theme it was made with, resolved to a
single `:root` block — never the list of themes that exist — so a theme added
later can never leave a note on disk stale. The gallery is the one file that
holds the catalogue, and it is rebuilt on demand; it hands a note a different
value set through the card's link, which the note applies without ever learning
a name.

Adding a theme is one entry in `THEMES` (and a `STACKS` entry if it needs its
own type). `--selftest` enforces the contrast floors, that the display weight is
one the family actually loads, and that the payload survives the round trip the
gallery sends it on.

## Good first contributions

- **A source it handled badly** — open an issue with the URL and what the notes
  got wrong. This is the most useful report: the writing standard improves from
  real failures, not hypotheticals.
- **A new source guide** under `references/` — a podcast host, a PDF, a
  paywalled reader.
- **A third language**, per §4 above.
- **Design and accessibility fixes** to the templates under `assets/`.

By contributing you agree your work ships under this repository's
[MIT licence](LICENSE).
