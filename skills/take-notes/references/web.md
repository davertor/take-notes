# Acquisition — web article (blog post, docs page, news article)

Acquisition only. Return the fields listed in SKILL.md Step 1 and go back there
to write the notes.

No scripts here: `WebFetch` already converts a page to Markdown, and it is what
`/notion-summarize-blog` and `/didactic-blog` use in this repo. Don't add an
extraction dependency for this.

## Try the page's own Markdown export first

Many docs frameworks (GitBook, Mintlify, Docusaurus with the docs-as-markdown
plugin) publish a clean Markdown copy of every page, usually at `<url>.md`, and
sometimes point at a whole-site `llms.txt` index. Try `WebFetch` on `<url>.md`
before the rendered page. When it resolves to real Markdown, use it — it's
already just the content, so there's no nav/sidebar/footer chrome for the
extraction pass to filter out, which is less to go wrong. When it 404s,
redirects to non-Markdown, or the site plainly doesn't use the convention,
drop it and fetch the normal URL below without a second thought — most sites
don't support this, and confirming that isn't worth a round trip.

## Fetch

Call `WebFetch` on the URL, asking it to return the article rather than a
summary — the note-writing happens back in SKILL.md and needs the real text:

> Return the complete article body as Markdown, preserving heading structure,
> lists, code blocks and tables verbatim. Do not summarise or paraphrase. Also
> preserve every figure, diagram, chart, or screenshot as a standard Markdown
> image tag ![alt text](absolute image URL), keeping it in its original
> position in the text, with any caption text immediately after it. Also
> report: the title, the author or publishing site, the publication date, and
> the heading anchors if the page has them.

When the invocation gave a **focus**, narrow this same prompt: ask for the
complete, verbatim body only of the sections covering it, but still ask for
every heading on the page — in and out of focus — so the section outline stays
accurate. On a short, single-topic page this narrows nothing and isn't worth
the extra prompt clause; it earns its keep on long or multi-topic pages, where
it can cut what comes back by half or more.

Keep the headings. They become the `## Section outline`, and their anchors are
what make it clickable. Keep the images too — `WebFetch` returns real, absolute
image URLs when asked, in document order, with captions attached. It returns
none of that unasked, so don't drop this line.

**Before embedding one as a `<figure>`, confirm it actually serves an image:**
`curl -sI -o /dev/null -w "%{http_code} %{content_type}"` on the URL. A page
behind bot protection (Cloudflare and similar) returns an HTML challenge page
instead of image bytes for any out-of-browser request — and critically, no
header fixes this, because it also blocks the `<img>` tag in the finished
note for every future reader: an `<img>` is a subresource fetch, not a page
navigation, so it can never run the challenge's JS, in any browser. When the
check doesn't come back as an image, drop the `<img>`/`<figure>` and fold
whatever the caption said into the surrounding prose instead — a broken-image
icon teaches nothing the sentence next to it didn't already say.

## Map the response to the Step 1 fields

| Step 1 field | From |
|---|---|
| title | the page title (not the browser tab's suffix) |
| byline | author, or the publication/site when no author is named |
| span | publication date, `unknown` when the page states none |
| canonical URL | the final URL after redirects |
| body | the returned article Markdown |

## Check you got the article, not a summary of it

`WebFetch` answers a prompt against the page, so it will sometimes **paraphrase
in the third person** however firmly you ask for verbatim text — short, terse
posts are the usual trigger. The tell is prose about the author rather than by
them: "Evans recommends…", "The author notes…", a tidy bulleted digest where
the page had paragraphs, or a body far shorter than the page's own length (or,
when a focus narrowed the ask, far shorter than the focused sections' own
length — not the whole page's).

Retry **once**, explicitly forbidding the third person and asking for her actual
sentences. If the second attempt is still a summary, **stop** — this is a
failure, not a partial success. Notes written from a summary are a summary of a
summary: they teach nothing the digest didn't, and nothing in the finished note
will reveal that the source was never actually read.

## Failure

Stop and say so — do not write notes from a stub — when the result is:

- a **summary instead of the body**, after one retry (above)
- a **paywall or consent wall**: a few hundred words ending in a subscribe prompt
- a **JS shell**: nav and footer chrome with no article body
- **visibly truncated**: cuts mid-sentence, or ends far earlier than the page's
  own outline implies
- a **login redirect**: the final URL is an auth page

Offer the alternatives rather than guessing: the user can paste the text
directly, or point at an archive or reader-mode URL.

## Note on scope

A page that is mostly a video embed is a *video* source — go back and use
`references/youtube.md` on the embedded URL instead.
