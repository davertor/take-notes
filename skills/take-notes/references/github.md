# Acquisition — GitHub repository

Acquisition only. Return the fields listed in SKILL.md Step 1 and go back there
to write the notes.

The output is an **orientation note**: what this project is, what problem it
solves, how it is put together, and what to read first. Not a README reprint —
the README is already on the page the user just sent you.

## Fetch

Prefer the `gh` CLI when it is on PATH, because it returns structured metadata
that the rendered page does not:

```bash
gh api repos/<owner>/<repo> --jq '{description, homepage, language, stars: .stargazers_count, pushed: .pushed_at, topics, license: .license.spdx_id}'
gh api repos/<owner>/<repo>/readme --jq '.content' | base64 -d
gh api repos/<owner>/<repo>/contents --jq '.[].name'
gh release view --repo <owner>/<repo> --json tagName,publishedAt 2>/dev/null   # may not exist
```

If `gh` is missing or unauthenticated, fall back to `WebFetch` on
`https://github.com/<owner>/<repo>`, which renders the README inline:

> Return the complete README as Markdown, preserving heading structure, code
> blocks, and tables verbatim. Do not summarise. Also report: the repository
> description, its primary language, its topics, and the date of the last commit.

## Go one level past the README

A README says what the authors want you to know. The orientation note needs the
shape of the thing, so also list the top-level tree (`gh api …/contents`, or the
file list on the page) and read whichever of these exist — they are where a
project's real structure is written down:

- `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `docs/`
- the entry point named in the README's install or usage block

Do not clone the repo and do not read the whole source tree. Two or three files
past the README is the point where you can explain the layout; beyond that you
are reading code to summarise it, which this skill is not for.

## Map the response to the Step 1 fields

| Step 1 field | From |
|---|---|
| title | `<owner>/<repo>` followed by the repo description, when it has one |
| byline | the owner — the org or user, as GitHub displays it |
| span | the latest release tag and date, else the last-commit date |
| canonical URL | `https://github.com/<owner>/<repo>` |
| body | the README, plus the tree listing and any structure files you read |

## Failure

Stop and say so when:

- **the repo is empty or private**: no README, or `gh` returns 404
- **the README is a stub**: a title and a badge row with no prose. Say there is
  not enough to teach from, rather than padding notes with the file listing.

## Note on scope

A link to a **file**, a **pull request**, an **issue**, or a **gist** is not a
repository — those are pages, so use `references/web.md`. A repo whose README is
mostly a video embed is a *video* source; use `references/youtube.md` on the
embedded URL.
