---
layout: recipe
label-en: recipe
label-es: receta
when: a dish — ingredients with quantities and a method with times
---

# Genre — recipe

The body contract for a source that is **a dish**: ingredients with quantities
and a method with times. The note is a page in the user's own cookbook — kept
to cook from, and found again months later by what kind of dish it is and how
long it takes. It is not a study note about cooking: no takeaway, no glossary.
Everything in SKILL.md's `## Rules` still applies.

Pass `--genre recipe` in Step 5. The template lifts the card and the
ingredients out of the body on its own, numbers the steps, and puts a video's
timestamps in the margin — never write step numbers.

**Never invent a fact the source did not state.** A time, a quantity, a pan
size or a temperature the author left out is written as missing, never
estimated — and listed under *Gaps*. The one field you assign yourself is the
category, from the closed list below, the same way you pick a tag.

## Sections

Mandatory, in this order:

1. `<h2>Description</h2>` — 2–4 sentences: the dish, where it comes from, what
   this version does differently, and why it is worth keeping. Opens with a
   `<p>`: the gallery card quotes it.
2. `<h2>Card</h2>` — the facts, as one `<dl class="facts">`, one `<dd>` per
   `<dt>`. Short values — the template sets them as a ticket. Three parts, in
   this order:

   **The core — every recipe, always these five labels**, so the cards compare
   across the archive. When the source does not give one, write *Not stated*
   (*No indicado*) rather than drop the row:

   | Field | What goes in it |
   |---|---|
   | *Category* | one of the list below — the only field you choose |
   | *Yield* | in the source's own words: *4 servings*, *1 loaf*, *24 cookies*, *2 jars* |
   | *Active time* | hands-on time — what decides whether you cook it on a weekday |
   | *Total time* | wall-clock start to plate, rests and proofs included; stated by the source, or the sum of times it states — never an estimate |
   | *Setup* | what success depends on beyond the ingredients: oven °C and mode, pan or tin size, appliance. Just the equipment that changes the result |

   **Then the category's own fields**, from this table — only those the
   source actually gives:

   | Category | Extra fields |
   |---|---|
   | *Breakfast* · *Starter* · *Main* · *Side* · *Snack* | — |
   | *Dessert* | *Bake*, or *Chill* when it sets cold |
   | *Bread & dough* | *Proof*, *Rest* |
   | *Sauce & preserve* | *Storage* — mandatory here, write *Not stated* if absent; yield in ml or jars |
   | *Drink* | — ; *Setup* only when it needs an appliance |

   **Then, optional, only when the source states them:** *Cuisine*, *Diet*
   (vegetarian, gluten-free… — only a claim the source makes, never one read
   off the ingredient list), *Storage*, *Nutrition*, *Difficulty*.

   ```html
   <dl class="facts">
     <dt>Category</dt><dd>Bread &amp; dough</dd>
     <dt>Yield</dt><dd>1 loaf</dd>
     <dt>Active time</dt><dd>20 min</dd>
     <dt>Total time</dt><dd>3 h 15 min</dd>
     <dt>Setup</dt><dd>220 °C, 1 kg loaf tin</dd>
     <dt>Proof</dt><dd>2 h</dd>
   </dl>
   ```
3. `<h2>Ingredients</h2>` — a `<ul class="ingredients">`, quantity in
   `<strong>`, then the ingredient and its state:
   `<li><strong>200 g</strong> flour, sifted</li>`. The state matters as much
   as the amount — *very ripe*, *room temperature*, *melted*. **Keep the
   source's units and never convert them**: a cup of flour and a cup of sugar
   weigh different things, and a guessed gram is an invented fact. When the
   dish has components (the dough, the filling), an `<h3>` per component, each
   with its own `<ul class="ingredients">`.
4. `<h2>Steps</h2>` — an `<ol class="steps">`, one `<li>` per step, 6–15 steps:

   ```html
   <li><a href="https://youtu.be/<ID>?t=754s">12:34</a> — <strong>Brown the onion</strong> — Medium heat, stirring every minute, until the edges turn deep gold; pale onion makes a flat sauce. <span class="time">12 min</span> <span class="setting">medium heat</span></li>
   ```

   The timestamp link opens the step only when the source is a video (absolute
   `?t=<seconds>s`); leave it out for a page. The `<strong>` names the action;
   the sentence says **how, the cue that it is done, and the warning** where
   the source gives one — what you need with your hands full, not the theory.
   Close with the `<span class="time">` the step takes and the
   `<span class="setting">` it needs, when the source gives them.
5. `<h2>Tips</h2>` — a `<ul>` of `<li><strong>tip</strong> — why it works</li>`:
   the source's substitutions, doneness cues, make-ahead and storage. 3–6
   items, each one the source said.

Optional — include only when the source actually earns it, never as an empty
heading:

- `<h2>Gallery</h2>` — up to 6 `<figure><img src="…" alt="…"><figcaption>…</figcaption></figure>`
  with the source's own photos of the stages or the finished dish (`web.md`
  returns them; verify each URL serves an image). For a video, skip it: the
  poster is in the masthead and every step already links to its minute.
- `<h2>Gaps</h2>` — what you would trip over cooking from the source: amounts
  never measured (*a glass*, *a splash*), a missing tin size, no doneness
  test, times that contradict each other, a step skipped on screen. One
  `<li>` each, saying what is missing and what it decides. Name the gap; never
  fill it with a number of your own.

## Blocks

The genre's class vocabulary — the one exception to `## Rules`' "no classes":

- `facts` on the card's `<dl>`, `ingredients` on each ingredient `<ul>`,
  `steps` on the method `<ol>`. The template lifts **the section** that holds
  each one, so each belongs to exactly one section — *Ingredients* may hold
  several `ul.ingredients`, one per component.
- `<span class="time">` and `<span class="setting">` inside a step. Nothing
  else: no inline `style`, no other classes.

Language: headings and card labels in the note's language — *Descripción,
Ficha, Ingredientes, Pasos, Trucos, Galería, Errores detectados*; *Categoría,
Rinde, Tiempo activo, Tiempo total, Montaje*, and *Desayuno, Entrante,
Principal, Guarnición, Picoteo, Postre, Pan y masas, Salsa y conserva, Bebida*.
Structure unchanged.
