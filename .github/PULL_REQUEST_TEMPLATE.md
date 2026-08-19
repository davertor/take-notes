<!-- Title in Conventional Commits form: feat(take-notes): … / fix(skills): … / docs: … -->

## What and why

<!-- The diff says what changed; use this for why. -->

## Checks

- [ ] `for s in render notes gallery export transcript; do uv run skills/take-notes/scripts/$s.py --selftest; done` passes
- [ ] No new third-party dependency (see CONTRIBUTING.md)
- [ ] English throughout — code, comments, commit messages

## If you touched…

- [ ] **a note template** — re-ran `notes.py --selftest`; the masthead classes and body structure it parses are unchanged
- [ ] **`SKILL.md` Sections** — the `<li><strong>term</strong> — definition</li>` shape still holds, so Anki export still finds cards
- [ ] **`disable-model-invocation`** — made the matching change in `agents/openai.yaml`
- [ ] **the version** — bumped it in `SKILL.md` *and* both plugin manifests, and added a `CHANGELOG.md` entry
- [ ] **anything user-facing** — updated `README.md` (and `README.es.md` if you can)
