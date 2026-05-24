# Wikipedia / WikiAlive adapter

Turns Wikipedia articles into structured, reusable API Anything capabilities.

## What this adapter does

Read-only capabilities:

- `extract_article` — fetch a Wikipedia article through the official Wikipedia API and return clean structured data.
- `wikialive` — return the same experience model used by WikiAlive: summary, story chapters, timeline, quiz, cards, keywords, and a WikiAlive URL.
- `build_timeline` — extract dated events from the article.
- `generate_quiz` — create simple quiz questions from article keywords.

## Example commands

```bash
api-anything inspect wikipedia
api-anything run wikipedia extract_article --params '{"url":"https://he.wikipedia.org/wiki/משה_שרת"}'
api-anything run wikipedia wikialive --params '{"url":"https://he.wikipedia.org/wiki/משה_שרת"}'
api-anything run wikipedia wikialive --params '{"url":"https://wiki-alive.vercel.app/wiki/משה_שרת"}'
api-anything run wikipedia wikialive --params '{"title":"Napoleon","lang":"en"}'
```

## URL compatibility

Supported inputs:

- `https://he.wikipedia.org/wiki/משה_שרת`
- `https://wiki-alive.vercel.app/wiki/משה_שרת`
- `https://wiki-alive.vercel.app/en/wiki/Napoleon`
- plain title + `lang`

Hebrew WikiAlive routes use `/wiki/<title>` by default. Non-Hebrew routes use `/<lang>/wiki/<title>`.

## Safety

This adapter is read-only. It does not need credentials and does not write to Wikipedia or WikiAlive.

## Attribution

Content comes from Wikipedia and must keep attribution/link-back under CC BY-SA.
