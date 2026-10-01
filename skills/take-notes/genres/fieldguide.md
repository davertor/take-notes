---
layout: fieldguide
label-en: field guide
label-es: guía
when: several things of one kind described on shared axes — tools, models, products, options, the papers in a survey; four or more of them
---

# Genre — field guide (a comparative catalogue)

The body contract for a source that presents **several things of one kind on
shared axes** — tools, models, products, options, the papers in a survey. A
reader scans it to pick, not to follow an argument, so the note is a matrix, a
card per thing, and a recommendation. Everything in SKILL.md's `## Rules`
still applies; this file only replaces `## Sections`.

Pass `--genre fieldguide` in Step 5. The template numbers sections and entries
itself — never write the numbers.

## Sections

Mandatory, in this order:

1. `<h2>Executive summary</h2>` — 3–5 sentences: what is being compared, on
   what axes, and the verdict in one line. Opens with a `<p>`: the gallery card
   quotes it.
2. `<h2>The one takeaway</h2>` — 1–2 sentences wrapped in `<strong>`. The one
   rule for choosing between these things. If you can't name one, the notes
   aren't ready.
3. `<h2>Matrix</h2>` — one `<table>`, one row per thing, 3–4 columns for the
   axes the source actually uses (what it is, status or cost, what it is for,
   the hidden cost…). A `<span class="badge">` is allowed in a cell (see
   *Blocks*). Every thing in the matrix gets an entry below, and vice versa.
4. `<h2>Entries</h2>` — one `<section class="entry">` per thing, 5–15 of them,
   in the matrix's order:

   ```html
   <section class="entry">
     <h3>Name</h3>
     <p class="tagline">What it is, in one line.</p>
     <span class="badge is-free">Free · MIT</span>
     <dl>
       <dt>Features</dt><dd><ul><li>…</li><li>…</li></ul></dd>
       <dt>Alternatives</dt><dd><p>…</p></dd>
       <dt>Daily use</dt><dd><p>…</p></dd>
     </dl>
     <p class="verdict"><strong>When to pick it:</strong> … <a href="…">Official source ↗</a></p>
   </section>
   ```

   The `<dl>` carries 2–4 facets, **one `<dd>` per `<dt>`**, the same facets on
   every entry so the cards compare. Name the facets after what the source
   compares by; *Features / Alternatives / Daily use* is the usual set for
   tools. The verdict is the didactic part: when this one, when not, and what
   it really costs — with the official link.

   **`<section>`, never `<article>`.** The parser that feeds the gallery and
   the exporters ends the body at the first `</article>`; an article per entry
   would lose everything after the first one.
5. `<h2>Recommendation</h2>` — up to three picks, then one paragraph on the
   order to adopt them:

   ```html
   <div class="picks">
     <div class="pick"><span class="eyebrow">Minimal</span><p class="price">≈ 0 €</p><h3>Terminal first</h3><p>…</p><p><strong>Trade-off:</strong> …</p></div>
     <div class="pick">…</div>
     <div class="pick">…</div>
   </div>
   <p><strong>Recommended order:</strong> …</p>
   ```

   The middle pick is the highlighted one — put the recommendation for most
   readers there. `<div>`, never `<article>`, for the same reason as above.

Optional — include only when the source actually earns it, never as an empty heading:

- `<h2>Concepts</h2>` — jargon the source assumes, as
  `<li><strong>term</strong> — definition</li>`.
- `<h2>Going deeper</h2>` — what is verified and what is not: the date prices
  and licences were checked, what "free" does and does not cover, what the
  source leaves open, and a `<ul>` of the official sources consulted.

## Blocks

The genre's class vocabulary — the one exception to `## Rules`' "no classes":

- `<span class="badge">…</span>` — a status label in mono caps. `badge is-free`
  fills it with the theme's highlight (free / open source); `badge is-paid`
  with the pen (paid). Plain `badge` for anything in between (freemium,
  variable, community).
- `<ol class="flow">` — a pipeline: 3–6 `<li><strong>Step</strong> one-line
  gloss</li>`, rendered as a row of numbered boxes. At most one per note,
  usually in the summary, for the workflow the things plug into.
- `entry`, `tagline`, `verdict`, `picks`, `pick`, `eyebrow`, `price` — as in
  the skeletons above. Nothing else: no inline `style`, no other classes.

Length: 5–15 entries; a source with fewer than four things of one kind is not
a catalogue — write it as an offprint.
