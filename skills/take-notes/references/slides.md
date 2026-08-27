# Acquisition — Google Slides presentation

Acquisition only. Return the fields listed in SKILL.md Step 1 and go back there
to write the notes.

`SKILL_DIR` is already resolved in SKILL.md — reuse it.

## Read the deck

```bash
uv run "${SKILL_DIR}/scripts/slides.py" "<presentation URL>"
```

Prints the deck title, the slide count, and one `### Slide N` block per slide
carrying its text, its **speaker notes**, its **page id**, and a count of what
is drawn on it. No API key and no dependency: Google exports any link-visible
deck as `.pptx`, and a pptx is a zip of XML.

## Read the speaker notes — they are half the source

A slide is a prompt for a person who is about to talk over it. The bullets are
what the audience *sees*; the notes are what the presenter was going to *say* —
the mechanism behind the diagram, the caveat behind the number, the reason this
slide follows the last one. Notes taken from the bullets alone reproduce a deck's
shorthand, which is the exact failure SKILL.md's "didactic means explaining, not
compressing" rule is about.

So treat the notes as body text, equal in standing to the slide's own words, and
prefer them wherever the two disagree in depth. In practice they are where most
of *How it works*, *Concepts*, and *Going deeper* come from — a bullet says
"clean the traces", the note says why deterministic redaction runs before the
LLM review.

The header line says how many slides carry them:

- `on 12 of 16 slides` — read every one before writing anything.
- `none written on any slide` — a fact about the deck, not a parsing failure;
  the script checked. Say so in *Going deeper* when the slides are thin enough
  that the missing narration is why the notes are shorter than the topic
  deserves.

## The figures are the point of this source

A deck's diagrams are frequently the entire argument, and most of them exist in
no image file: a pipeline drawn as boxes and arrows is native Slides shapes, so
extracting embedded media would return the screenshots and miss the diagrams.
Rendering the whole slide catches both.

Every slide has a stable image URL, and the script prints the page id for each:

```
https://docs.google.com/presentation/d/<DECK_ID>/export/png?pageid=<PAGE_ID>
```

960×540 PNG, no auth, straight into `<img src>`.

The per-slide counts are the shortlist. `connectors` is the strongest signal —
boxes alone are a layout, boxes joined by arrows are an explanation. A high
`shapes` count is a built-up diagram or a table; `images` is a pasted
screenshot or chart. `text only` is a bullet slide, and never a figure.

Verify before embedding, the same check `web.md` uses:

```bash
curl -sIL -o /dev/null -w "%{http_code} %{content_type}" "<png URL>"
```

`-L` is not optional here: the export answers `307 application/binary` and
redirects to the rendered image, so without it every figure looks like a failure.

Anything but `200 image/png` means the deck is not link-readable — drop the
figure rather than shipping a broken image, and fold the caption into the prose.

Two things to be honest about in the note when it matters: the URL renders the
deck's **current** slide, so a figure drifts if the deck is later edited, and it
breaks entirely if the deck's sharing is tightened.

Cap and placement follow SKILL.md's **Source figures** rule — at most 3, inline
in the section each one supports, never a gallery.

## Map the output to the Step 1 fields

| Step 1 field | From |
|---|---|
| title | `**Title:**` — the deck's own name |
| byline | the presenter or team named on the title slide; the script cannot report one, so read it off slide 1, and fall back to `Google Slides` when the deck names nobody |
| span | `**Slides:**`, written out in the note's own language — `16 slides` or `16 diapositivas` |
| canonical URL | `**Deck URL:**` — the bare `/edit` form, without the `#slide=` fragment the user's link carried |
| body | the `## Slides` blocks, text and speaker notes together |

A deck has no video ID, so Step 5 renders the article layout. Its `Section
outline` is the deck's own arc: group the slides into the 6–15 moves the talk
actually makes, and link each to its slide with the deep link the script printed
(`.../edit#slide=id.<PAGE_ID>`). One line per slide is a table of contents, not
an outline.

A **focus** narrows which slides matter, not which are fetched — the whole deck
arrives in one download either way.

## Failure

The script exits non-zero and says which of these it hit:

- **not link-readable**: the export answers with a sign-in page. Say so and stop.
  The fix is the user's: set sharing to *Anyone with the link → Viewer*, or paste
  the content. Do not write notes from the title.
- **not a Slides URL**: a Docs or Sheets link is a different product, and a
  `/presentation/` link that is really a published `/pub` page is a web page —
  use `references/web.md`.

A deck that is mostly screenshots with three words per slide has no body to take
notes from. Say that rather than padding one out; the speaker notes are the last
place to check before giving up.
