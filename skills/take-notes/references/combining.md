# Combining several sources into one note

Read from Step 1 of SKILL.md when the invocation carries more than one URL.
Several URLs are **one note about one subject from several sources** — a talk
and the deck it was given from, a paper and the repo that implements it — not
one note each. Fetching is the only part that repeats: from Step 2 on there is
one language, one tag, one body, one note.

## Acquire

The **first URL is the primary source**. Everything the note's chrome shows
comes from it — title, byline, span, canonical URL — and it picks the masthead:
a video first gets the poster (and, in the offprint, timestamps), a deck, paper
or article first gets the byline kicker. The note's *shape* — its genre — is
Step 3's call, made from the whole set. The rest are
**companions**: they contribute body, and Step 5 links them in the rail. Order
is the user's control over that, so take it literally rather than promoting the
richest source.

A **companion** that yields no body is not fatal: name it, say the notes are
poorer for it, and write from what did arrive. A **primary** that yields no body
stops the run — the note would be filed under a source it was not written from.

A focus narrows every source at once, which is where it earns the most: two
full-length sources is the largest input this skill ever takes.

## Read

With several sources, read them **against each other** before writing — that
comparison is the whole reason they were combined:

- **Overlap** — write it once, from whichever source explains it better. A deck
  bullet and the sentence spoken over it are one point, not two.
- **Gaps** — a figure that is on a slide and in no transcript, a number said out
  loud that is on no slide. These are what the second source bought.
- **Contradictions** — say so and attribute both. A talk that updates its own
  deck is worth a line in *Going deeper*.

Never organise the notes by source. One set of sections, ordered by what has to
be understood first; a reader should not be able to tell where the seam was.

## Render

The masthead flags describe the **primary** source. When the run combined
several, add one `--source "<label>" "<url>"` per companion, in the order they
were given:

```bash
--source "Slides" "https://docs.google.com/presentation/d/<DECK_ID>/edit"
```

They render as a short muted list under the source link. The label names the
**kind** of source — `Slides`, `Paper`, `Repo`, `Video`, `Article` — in the
note's own language; the title is already the `<h1>`, and repeating it there
tells the reader nothing. A companion the run failed to fetch gets no `--source`
entry: the rail lists what the notes were written from.
