# Changelog

All notable changes to this project are documented here, in the
[Keep a Changelog](https://keepachangelog.com/) style. The sections here are
written by hand; the version and the tag come from `cz bump` — see
[AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md).

## [1.6.0]

### Added

- **Your own genres.** A genre is now one Markdown file — a front-matter block
  naming its layout, its card label and the one-line "the source is…" the
  router reads, then the sections the skill writes — and `~/take-notes/genres/`
  is scanned beside the three that ship. Pick one of the three layouts, write
  the sections, and it is routable the moment it has a `when:` line; leave that
  out and it is used only by name with `--genre`, the safe way to try one. A
  file named like a bundled genre replaces it, so a copy of `recipe.md` with
  different facts on the card is your own recipe genre.
- **The router is generated, not written.** `scripts/genres.py --list` prints
  Step 3's table from the contracts' front-matter, in precedence order — user
  genres first, then `recipe`, `fieldguide`, `offprint` as the catch-all — and
  `check-drift.py` refuses a router row written back into `SKILL.md` by hand.

### Changed

- **The offprint's contract moved to `genres/offprint.md`**, in the same shape
  as the other two. `SKILL.md` is 52 lines shorter for every note, and the
  three genres are now defined the same way — the precondition for letting a
  user define a fourth.
- Every note template records its genre on `<html data-genre>`, the offprint's
  two included, so a user genre on the offprint layout reads back as itself.
- **Recipes are a cookbook page, not a study note.** Out go *The one
  takeaway*, *Concepts* and *Going deeper*; the sections are now *Description*,
  *Card*, *Ingredients*, *Steps*, *Tips*, and the optional *Gallery* and *Gaps*
  — what the source never measured or said, named and never filled in. The
  card has a fixed core on every recipe so they compare across the archive —
  *Category* (a closed list), *Yield* (*1 loaf*, *24 cookies*, not servings),
  *Active time*, *Total time*, *Setup* (oven and tin together) — plus a few
  fields per category, like *Proof* for bread. Difficulty and unit conversions
  are no longer invented. A recipe now exports no Anki cards, having neither
  a takeaway nor concepts.
- **`SKILL.md` carries only what every note needs** — 434 lines to 327 per
  invocation. Settings management (`--tags`, `--theme`, `--retag`) moved to
  `references/settings.md`, and everything about combining several URLs into
  one note — spread over Steps 1, 3 and 5 — into `references/combining.md`;
  each is read only when its case arises. The *Related* section, cross-references
  to other skills that no note needed, is gone.

## [1.5.0]

### Added

- **A stale install now says so.** Only the marketplace route auto-updates; a
  clone or an `npx` install needs the user to remember, and the version appeared
  nowhere they look. Building the gallery checks once against `main` and says so
  in the footer and on stderr, in both languages. One small file, 2.5 s timeout,
  every failure silent, `TAKE_NOTES_NO_UPDATE_CHECK=1` to skip it.
- **The invariants that live in prose are checked in CI.** `scripts/check-drift.py`
  is six stdlib checks for the rules nothing could enforce before: a routing row
  the catch-all above it swallows, a guide the table names and nobody wrote, a
  second copy of the writing standard free to drift, a rule dropped in a rewrite,
  and a version that ships without a CHANGELOG entry.
- **Releases are cut by CI.** `.github/workflows/release.yml` runs `cz bump` when
  a PR merges into `main`, and only then — the manual step after every merge was
  the one that got forgotten. A PR of only `docs` or `chore` releases nothing and
  still passes. The CHANGELOG entry now belongs in the PR, since the tag is cut
  on merge.

### Fixed

- **A combined note kept only one of its sources.** The note on disk held them
  all, but `parse_note` read just the primary out of the `class="watch"` link and
  never looked at the companion row — so a note built from a talk *and* its deck
  exported as though the deck had never been read. `Note.sources` now carries
  them all, and the Markdown frontmatter gets a `sources:` block.

## [1.4.0]

### Added

- **Notes take the shape of their source.** A genre router picks the layout:
  `offprint` (the linear argument this skill has always written) stays the
  default, `fieldguide` lays out a comparative catalogue — a matrix, a card per
  entry, a recommendation — and `recipe` gives a dish its ingredients column,
  numbered method with times and settings, and oven/power settings raised into
  the masthead. The agent classifies the content and says which genre it chose;
  `--genre` overrides it. Genre is a property of the content, not a taste, so
  there is no default to configure.
- Each genre carries its body contract (`genres/<name>.md`) next to its template,
  so adding a fourth is a row in the router, a contract and a template. The
  gallery labels a note with its genre; Markdown export carries `genre:`.

### Changed

- **Releases are cut with `cz bump`**, which reads the Conventional Commits since
  the last tag and rewrites the version in the five files that mirror it. It runs
  through `uvx`, so it is not a dependency. `AGENTS.md` is new and says so first.
- CI now cross-checks `marketplace.json`'s version, which had silently drifted a
  release behind.

## [1.3.0]

### Added

- **Themes.** A settings menu in the gallery switches colour and typography
  across the archive and every note: `paper`, `field`, `graphite`, `blueprint`,
  `bureau`, `acid`, `barbie`, `petrol` and `notebook`, plus `auto`, which follows
  the system. Each is a full editorial identity — its own display, body and UI
  faces, its own letterforms and paper texture — not a recolour. Set the default
  once in `~/take-notes/config.json`; `render.py --theme` bakes one into a note.
- **A note carries values, never a theme name.** `scripts/themes.py` is the single
  source of truth for the tokens; a rendered note gets only the resolved set
  (442 B), and the gallery — a derived file, regenerated on every note — passes a
  different set through the URL fragment when the reader switches. So a theme
  added in a year's time reaches notes written today, without rewriting them.
- Every colour pair is asserted against WCAG AA in `themes.py --selftest`, and a
  template may no longer hard-code a hex or a font family.

## [1.2.0]

### Added

- **Several sources, one note.** `/take-notes <url> <url> …` combines a talk and
  the deck it was given from, or a paper and the repo that implements it, into a
  single set of notes rather than one note per source. Each URL is routed
  through its own acquisition guide; everything after that stays as it was — one
  language, one tag, one body, one file.
- The **first URL is the primary source**: it gives the note its title, byline,
  span, canonical URL and layout, so leading with the video gets the two-pane
  note with a poster and clickable timestamps and leading with the deck gets the
  reading layout. Order is the user's control over that, deliberately in place
  of a heuristic that promotes whichever source looks richest.
- `render.py` takes `--source "<label>" "<url>"`, repeatable, and both note
  templates render the companions as a muted list under the source link.
- SKILL.md now says how to read several sources **against each other** — write
  overlap once from whichever source explains it better, treat the gaps as the
  reason the sources were combined, and attribute contradictions to both — and
  forbids organising the notes by source. The outline still follows the primary
  source alone; companions stay traceable through inline deep links (a slide's
  `#slide=id.<PAGE_ID>`, a video's `?t=<seconds>s`).
- A companion that yields no body is reported and skipped rather than failing
  the run; only a primary that yields nothing stops it.

## [1.1.0]

### Added

- **Google Slides as a source.** `/take-notes <presentation URL>` now reads a
  deck: per-slide text, speaker notes, and a rendered image for every slide.
  New `references/slides.md` guide and `scripts/slides.py`, stdlib only — Google
  exports any link-visible deck as `.pptx` without an API key, and a pptx is a
  zip of XML.
- **A deck's diagrams reach the note.** Each slide's Google page id, read out of
  the shape names on its notes page, addresses a 960×540 render at
  `export/png?pageid=<id>`. Rendering the whole slide is what catches a diagram
  drawn from native shapes — boxes and arrows that exist in no image file, and
  that extracting embedded media would miss entirely. `slides.py` reports per
  slide how many images, shapes and connectors it carries, which is the
  shortlist of what is worth a figure.
- `slides.py` says in its header whether speaker notes exist (`on 12 of 16
  slides` / `none written on any slide`), so a deck nobody annotated cannot be
  mistaken for notes that failed to parse.

### Changed

- SKILL.md's *Article figures* rule is now *Source figures*, covering articles,
  papers and decks alike, with the same cap of 3 and the same
  confirm-it-is-really-an-image check.

### Fixed

- The figure check in `references/web.md` now passes `-L`. Without it a host
  that answers a redirect (a CDN, or Google's own image export) reads as a
  failure, and a perfectly good figure gets dropped.

## [1.0.1]

### Fixed

- Windows: non-ASCII characters in a note body no longer come out
  double-encoded. `render.py` read stdin in text mode, so UTF-8 bytes were
  decoded with the locale codec (cp1252) and the UTF-8 write then baked the
  mojibake in; it now decodes stdin as UTF-8 explicitly. Reported in
  [#5](https://github.com/davertor/take-notes/issues/5).
- Windows: `transcript.py` forces UTF-8 on stdout and stderr. Its output is
  piped, and a redirected stream encodes with the locale codec, so captions or
  a title outside cp1252 raised `UnicodeEncodeError` mid-dump.

## [1.0.0]

Initial public release — the `/take-notes` skill (YouTube, local media, and
web articles as didactic HTML study notes), the video and article note
templates, the `gallery.py` archive view, and the multi-tool install path
(`link-skill.sh` / `npx skills add`). See the git history predating this file
for the detail.
