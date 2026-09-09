# AGENTS.md

Notes for AI agents working in this repo. The full contributor guide is
[CONTRIBUTING.md](CONTRIBUTING.md) — this file is the short list of things that
are easy to get wrong from the outside.

## Cut the release, or the version never moves

**A feature branch does not touch the version by hand.** After a PR is merged,
on `main`:

```sh
uvx --from commitizen cz bump --yes && git push --follow-tags
```

That reads the Conventional Commits since the last tag, decides patch / minor /
major, rewrites the version in all five places that mirror it, commits
`chore(release): X.Y.Z` and tags. Nothing is installed — it runs through `uvx`.

**Every release is tagged.** The increment is read from the commits since the
last tag, so a release that ships without one widens the range the next bump
reads and can turn a `feat!` from two releases ago into an unwanted major.
`git push --follow-tags` is part of the command above for that reason.

Then **write the CHANGELOG entry by hand**: `cz` deliberately does not, because
the entries here are prose that explains what changed and why, not a list of
commit subjects. `uvx --from commitizen cz changelog --dry-run` prints the
commits grouped by type, which is a useful checklist to write from.

## The rest, in one line each

- **Stdlib only** for anything under `scripts/` — it runs on the user's machine
  through `uv` with no dependencies. Dev-time tools invoked with `uvx` (like
  commitizen above) are not a dependency and are fine.
- **There is no test suite.** Each script carries its own asserts behind
  `--selftest`, and CI runs exactly that loop. A behaviour change needs an
  assert; if you cannot write one, say so and explain how you checked by hand.
- **Conventional Commits**, no exceptions — `feat` `fix` `docs` `style`
  `refactor` `perf` `test` `build` `ci` `chore`. The release tooling reads them
  to work out the version, so a sloppy type silently produces the wrong bump.
- **The rendered notes are the database.** `gallery.py` and `export.py` parse
  them back through `notes.py`, so the classes listed in CONTRIBUTING.md § 3
  are a contract, not styling.
- **Colour and type come from `scripts/themes.py`.** A template never hard-codes
  a hex or a font family.
- **Verify in a browser, not only in asserts.** The selftests prove the values
  reach the HTML; they cannot tell you the result is legible.
