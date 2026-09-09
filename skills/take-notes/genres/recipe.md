---
layout: recipe
label-en: recipe
label-es: receta
when: a dish — ingredients with quantities and a method with times
---

# Genre — recipe

The body contract for a source that is **a dish**: ingredients with quantities
and a method with times. The note is a card you can cook from, and a study note
too — the *why* of the key steps, the technique named, the mistakes the source
warns about. Everything in SKILL.md's `## Rules` still applies; this file only
replaces `## Sections`.

Pass `--genre recipe` in Step 5. The template lifts the card and the
ingredients out of the body on its own, numbers the steps, and puts a video's
timestamps in the margin — never write step numbers.

## Sections

In the spine (SKILL.md Step 4): the summary is the dish — where it comes from
and what this version does differently; the takeaway is the one thing that
makes or breaks it. Then, mandatory, in this order:

1. `<h2>Card</h2>` — the facts, as a `<dl class="facts">`, one `<dd>` per
   `<dt>`, 4–7 pairs: servings, prep time, cook time, total, difficulty, and
   every **setting** the method depends on (oven °C and mode, hob power, pan
   size). Short values — the template sets them as a ticket.

   ```html
   <dl class="facts">
     <dt>Serves</dt><dd>4</dd>
     <dt>Prep</dt><dd>20 min</dd>
     <dt>Cook</dt><dd>45 min</dd>
     <dt>Oven</dt><dd>180 °C, fan</dd>
     <dt>Difficulty</dt><dd>Easy</dd>
   </dl>
   ```
2. `<h2>Ingredients</h2>` — a `<ul class="ingredients">`, quantity in
   `<strong>`, then the ingredient and its prep:
   `<li><strong>200 g</strong> flour, sifted</li>`. Use the source's units and
   add the metric ones in parentheses when it gives cups or ounces. When the
   dish has components (the dough, the filling), an `<h3>` per component, each
   with its own `<ul class="ingredients">`.
3. `<h2>Method</h2>` — an `<ol class="steps">`, one `<li>` per step, 6–15 steps:

   ```html
   <li><a href="https://youtu.be/<ID>?t=754s">12:34</a> — <strong>Brown the onion</strong> — Medium heat, stirring every minute, until the edges catch: that is where the sweetness comes from, so do not rush it. <span class="time">12 min</span> <span class="setting">medium heat</span></li>
   ```

   The timestamp link opens the step only when the source is a video (absolute
   `?t=<seconds>s`, as in the offprint outline); leave it out for a page. The
   `<strong>` title names the action; the sentence says how *and why* on the
   steps where the why matters — that is what makes this a study note and not
   a copy of the recipe. Close with the `<span class="time">` the step takes
   and the `<span class="setting">` it needs, when the source gives them.
4. `<h2>Tips</h2>` — a `<ul>` of `<li><strong>tip</strong> — why it works</li>`:
   the source's warnings, substitutions, make-ahead and storage. 3–6 items.

Optional, beyond the spine's — include only when the source actually earns it,
never as an empty heading:

- `<h2>Gallery</h2>` — up to 6 `<figure><img src="…" alt="…"><figcaption>…</figcaption></figure>`
  with the source's own photos of the stages or the finished dish (`web.md`
  returns them; verify each URL serves an image). For a video, skip it: the
  poster is in the masthead and every step already links to its minute.

In this genre the spine's *Concepts* are the techniques the recipe assumes
(emulsify, temper, deglaze…), as `<li><strong>technique</strong> — what it is
and what it does</li>`; *Going deeper* is the variations the source mentions,
what it leaves out, and the next dish that uses the same technique.

## Blocks

The genre's class vocabulary — the one exception to `## Rules`' "no classes":

- `facts` on the card's `<dl>`, `ingredients` on each ingredient `<ul>`,
  `steps` on the method `<ol>` — the template finds the sections by these, not
  by their headings, so they must be present exactly once each.
- `<span class="time">` and `<span class="setting">` inside a step. Nothing
  else: no inline `style`, no other classes.

Language: headings in the note's language (*Ficha, Ingredientes, Técnica,
Trucos*), structure unchanged.
