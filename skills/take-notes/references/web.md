# Acquisition — web article (blog post, docs page, news article)

Acquisition only. Return the fields listed in SKILL.md Step 1 and go back there
to write the notes.

No scripts here: `WebFetch` already converts a page to Markdown, and it is what
`/notion-summarize-blog` and `/didactic-blog` use in this repo. Don't add an
extraction dependency for this.

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

Keep the headings. They become the `## Section outline`, and their anchors are
what make it clickable. Keep the images too — verified live: `WebFetch` returns
real, absolute, hotlink-stable image URLs when asked, in document order, with
captions attached. It returns none of that unasked, so don't drop this line.

## Map the response to the Step 1 fields

| Step 1 field | From |
|---|---|
| title | the page title (not the browser tab's suffix) |
| byline | author, or the publication/site when no author is named |
| span | publication date, `unknown` when the page states none |
| canonical URL | the final URL after redirects |
| body | the returned article Markdown |

## Failure

Stop and say so — do not write notes from a stub — when the result is:

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
