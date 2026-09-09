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
for s in render notes gallery export transcript tags retag slides themes genres; do
  uv run skills/take-notes/scripts/$s.py --selftest
done
```

Those cover the scripts. The invariants that live in prose — the ones §"The
four things that will bite you" below is about — have their own guard:

```sh
uv run scripts/check-drift.py
```

It fails if never-auto-invoke stops agreeing across its two files, if the Step 1
catch-all row moves above a more specific one, if a file under `references/`
is reachable from nowhere in `SKILL.md`, if an acquisition guide grows a copy of
the writing standard, if a genre contract re-declares the spine, or
if one of a handful of load-bearing rules disappears from `SKILL.md`. It is
development tooling and is not shipped inside the skill.

CI runs both, plus a check that the plugin manifests parse and their version
matches `SKILL.md`'s.

## Releases

Cut by CI when a PR merges into `main`, never inside the feature branch and
never by hand. [`.github/workflows/release.yml`](.github/workflows/release.yml)
runs, on the merge:

```sh
uvx --from commitizen cz bump --yes && git push --follow-tags
```

A PR whose commits are all `docs`, `chore`, `ci`, `style`, `refactor` or `test`
releases nothing and the job still passes; those changes ship with the next
`feat` or `fix`. A commit pushed straight to `main` gets no release of its own
either — it rides the next merged PR's bump.

[commitizen](https://commitizen-tools.github.io/commitizen/) reads the
Conventional Commits since the last tag, decides whether that is a patch, a
minor or a major, and rewrites the version in the five files that mirror it —
`SKILL.md`, both `plugin.json`, `marketplace.json` and the README badge — then
commits `chore(release): X.Y.Z` and tags. It runs through `uvx`, so it is not a
dependency of anything: nothing is installed and no manifest mentions it. The
configuration is in [`.cz.toml`](.cz.toml).

**The CHANGELOG stays hand-written, and its entry belongs in the PR.**
commitizen is told not to touch it, because the entries here are prose
explaining what changed and why, and the generated form is a list of commit
subjects. Since the bot cuts the version on merge, an entry written afterwards
lands in a commit the tag does not contain — so add the section to the PR under
the version the merge will produce. `cz bump --dry-run --yes` prints that
number, and `cz changelog --dry-run` groups the commits as a checklist.

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

The guides Step 1 routes to cover **acquisition only**. Each one hands back
the same five fields (title, byline, span, canonical URL, body) whatever the
source, and knows nothing about how notes are written. Adding a source means
adding one guide and one routing row — never a second copy of the writing
rules, which would immediately drift from the first.

`references/` also holds two **procedures** that are not acquisition guides
and are read only when their case arises: `settings.md` (Step 0 — `--tags`,
`--theme`, `--retag`) and `combining.md` (Step 1 — several URLs into one
note). That is the skill's progressive disclosure: `SKILL.md` carries what
every note needs, and nothing a minority of invocations needs.

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
| `<html data-genre="…">` | every note template (absent = a note older than genres, an offprint) | the genre parser, the gallery's card label, the Markdown frontmatter |
| `<article id="body">` with a flat run of `<h2>` — and no `<article>` inside it | every note template, and every genre contract | the section splitter, which ends the body at the first `</article>` |
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

### 6. A genre is a contract; a layout is a template

`SKILL.md` Step 3 routes a source's *content* to a genre. A genre is one file,
`skills/take-notes/genres/<name>.md`, for all three that ship — the offprint's
contract is no longer inline in `SKILL.md`. The file opens with a flat
front-matter block the scripts read (`genres.py` parses it; no YAML library):

```
---
layout: recipe          # offprint | fieldguide | recipe — the template
label-en: recipe        # the gallery card's label
label-es: receta
when: a dish — ingredients with quantities and a method with times
---
```

`when` is the genre's row in the router. `genres.py --list` generates the
table Step 3 reads from these lines, in precedence order — user genres first,
then `recipe`, `fieldguide`, `offprint` (`BUNDLED_ORDER`) — so the table is
never written by hand and `check-drift.py` refuses a row that is. A genre
without `when` is on request only (`--genre <name>`). Users add genres under
`~/take-notes/genres/`, and one named like a bundled genre replaces it.

Adding a **bundled genre** means:

1. `genres/<name>.md` — the front-matter above, then **only the genre's own
   sections**, in the voice of the other contracts, plus the class vocabulary
   the template styles (the one exception to "no classes"). The spine every
   genre shares — *Executive summary*, *The one takeaway*, and the optional
   *Concepts* and *Going deeper* — is declared once in `SKILL.md` Step 4; a
   contract says what its genre puts there and never writes the heading out
   again (`check-drift.py` refuses it). Add the name to `BUNDLED_ORDER` in
   `scripts/genres.py`, above `offprint`;
2. if it needs a new **layout**: `assets/<name>-template.html`, self-contained
   like the others, carrying the landmarks in the table above, `{{PALETTE}}`,
   `{{FONTS}}`, `data-genre="{{GENRE}}"`, and `{{MASTHEAD}}` where the poster
   or kicker goes; an entry in `LAYOUT_TEMPLATES` in `scripts/render.py` and in
   `LAYOUTS` in `scripts/genres.py`. Most genres do not — the layouts are a
   closed set on purpose, and a genre's value is its sections;
3. asserts in `genres.py --selftest` and `render.py --selftest`.

The theme is orthogonal: a genre template consumes the palette tokens and never
hard-codes a colour.

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
