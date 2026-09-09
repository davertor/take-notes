---
layout: offprint
label-en: offprint
label-es: separata
when: anything else — a talk, an article, a paper, a docs page, a repo, a lesson
---

# Genre — offprint (a linear argument)

The body contract for a source that **makes an argument**: a talk, an article,
a paper, a docs page, a repo, a lesson. The reader follows it from the top, so
the note is a summary, the one thing to keep, the claims that support it, and
the source's own spine as an outline. This is the default genre and the
catch-all in the router: when no other genre clearly fits, it is this one.
Everything in SKILL.md's `## Rules` still applies.

Leave `--genre` off in Step 5, or pass `--genre offprint`; the offprint is what
the renderer writes when told nothing.

## Sections

Mandatory, in this order. The title and metadata line are **not** in the body —
they come from the renderer flags.

1. `<h2>Executive summary</h2>` — 3–5 sentences: what the source covers and what
   it argues.
2. `<h2>The one takeaway</h2>` — 1–2 sentences wrapped in `<strong>`. The single
   most important insight. If you can't name one, the notes aren't ready.
3. `<h2>Key points</h2>` — a `<ul>` of 5–10 items, each
   `<li><strong>Claim</strong> — the detail that supports it</li>`.
   Cap at 10; more than that is a transcript with bullets in front of it.
4. The outline, rendered to match the source:
   - video → `<h2>Timestamped outline</h2>`, one `<li>` per topic:
     `<li><a href="https://youtu.be/<ID>?t=754s">12:34</a> — <strong>Topic</strong> — one-line summary</li>`
     Use absolute `?t=<seconds>s` URLs so the links jump to the right moment.
   - article → `<h2>Section outline</h2>`, one `<li>` per section:
     `<li><strong>Section heading</strong> — one-line summary</li>`, wrapping the
     heading in `<a href="<URL>#anchor">` when the page has stable anchors.

   Aim for 6–15 entries either way; group adjacent material covering one idea.

   The outline follows the **primary** source only — it is one source's spine,
   and interleaving two makes it navigate neither. A companion stays traceable
   through inline deep links wherever a point comes from it: a slide's
   `<a href="<deck URL>#slide=id.<PAGE_ID>">`, a video's `?t=<seconds>s`.

Optional — include only when the source actually earns it, never as an empty heading:

- `<h2>Concepts</h2>` — jargon the source assumes or introduces, as
  `<li><strong>term</strong> — definition</li>`. Include a term only if not
  knowing it blocks understanding the notes.
- `<h2>How it works</h2>` — an `<ol>` for a mechanism, pipeline, or worked example
  the source demonstrates. Code goes in `<pre><code>`.
- `<h2>Going deeper</h2>` — what the source leaves open: unanswered questions,
  claims made without evidence, and the concrete next thing to read or try.

**Source figures** — `web.md` and `arxiv.md` return the diagrams, charts, and
screenshots the page carried; `slides.md` returns an image URL for every slide.
Include one only when it is load-bearing — the diagram *is* the explanation, the
chart *is* the evidence — never a decorative photo, a header banner, an author
headshot, or (for a deck) a slide that is just bullets you already wrote out.
Cap at 3, the same "more than that is a dump" discipline as Key Points. Not a
section of its own: place
`<figure><img src="<url>" alt="<alt text>"><figcaption>caption</figcaption></figure>`
inline, in whichever section it supports — most often *How it works*, *Key
points*, or *Concepts*. Each guide says how to confirm the URL really serves an
image before you embed it; a broken-image icon teaches nothing.
