# Acquisition — arXiv paper

Acquisition only. Return the fields listed in SKILL.md Step 1 and go back there
to write the notes.

No scripts here, same as `web.md`: arXiv serves the full text as HTML, so
`WebFetch` is the whole pipeline. Do not add a PDF dependency for this.

## Normalise the URL first

Every arXiv link carries the same paper ID (`2604.26962`, sometimes with a
version suffix like `v2`, older ones like `math/0211159`). Pull the ID out of
whatever form the user gave you — `/abs/`, `/pdf/`, `/html/`, a `doi.org`
redirect, or a bare ID — then work from these:

| Want | URL |
|---|---|
| full text | `https://arxiv.org/html/<ID>` — native HTML, most papers since Dec 2023 |
| full text, fallback | `https://ar5iv.labs.arxiv.org/html/<ID>` — LaTeX-to-HTML for older papers |
| metadata + abstract | `https://arxiv.org/abs/<ID>` |

## Fetch

Try `https://arxiv.org/html/<ID>` first, then the ar5iv mirror. Ask for the
paper rather than a summary:

> Return the complete paper body as Markdown, preserving the section heading
> structure, lists, tables and equations. Do not summarise or paraphrase.
> Render display equations as fenced blocks and inline maths as `$…$`.
> Preserve every figure as `![alt text](absolute image URL)` in its original
> position, with the caption immediately after it. Also report: the full title,
> every author, the submission date, and the version.

Then fetch `https://arxiv.org/abs/<ID>` **as well** when the HTML version gave
you no clean author list or date — the abs page always has both, and they are
the two fields the HTML render is most likely to mangle.

## Map the response to the Step 1 fields

| Step 1 field | From |
|---|---|
| title | the paper title, not the `[2604.26962] …` browser-tab form |
| byline | the authors — all of them up to three, otherwise `First Author et al.` |
| span | the submission date, plus the version when it is not `v1` (`Apr 2026 · v2`) |
| canonical URL | `https://arxiv.org/abs/<ID>` — the abs page, never `/pdf/` |
| body | the returned paper Markdown |

A paper's own sections are its outline, so SKILL.md's `Section outline` applies
unchanged — use the paper's numbered headings and link them to the HTML
version's anchors when it has them.

## Failure

Stop and say so — do not write notes from an abstract alone — when:

- **only a scanned PDF exists**: both HTML routes 404 and the abs page offers
  nothing but a PDF link. Say the paper has no machine-readable full text and
  offer to work from a PDF the user extracts themselves.
- **the ID does not resolve**: arXiv returns its "not found" page.
- **it is a withdrawn paper**: the abs page says withdrawn. Report that rather
  than taking notes on a retracted claim.

Writing notes from the abstract only is the failure mode to avoid here. An
abstract is already a summary; notes made from it teach nothing the abstract
did not, and they will read as if the paper had been consumed when it had not.

## Note on scope

A link to a paper hosted somewhere other than arXiv (a journal page, a lab's
own PDF, OpenReview) is **not** this guide — use `references/web.md`, and stop
if the page is a paywall stub.
