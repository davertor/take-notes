# Changelog

All notable changes to this project are documented here, in the
[Keep a Changelog](https://keepachangelog.com/) style. Maintained by hand: a
release adds a section here, bumps `skills/take-notes/SKILL.md`'s `version`,
and tags — see [CONTRIBUTING.md](CONTRIBUTING.md).

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
