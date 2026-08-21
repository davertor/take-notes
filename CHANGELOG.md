# Changelog

All notable changes to this project are documented here, in the
[Keep a Changelog](https://keepachangelog.com/) style. Maintained by hand: a
release adds a section here, bumps `skills/take-notes/SKILL.md`'s `version`,
and tags — see [CONTRIBUTING.md](CONTRIBUTING.md).

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
