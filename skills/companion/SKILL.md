---
name: companion
description: Build a long-form companion page (a claude.ai artifact) in the learner's established house style, the one used for the Paleologo EQI chapter pages (The Second Moment, Statistical Factor Models, Which Bell Is Which). Use after a substantial /learn session, when the user asks for "the page", "a companion", "write it up like the EQI ones", or wants a chapter or topic worked in full with computed figures.
---

# Companion page

The learner's preferred deep-reading medium. A companion is not a summary of a session: it is the topic worked in full, in order, with every number computed and every figure drawn from those numbers. Fourteen of these exist for EQI chapters 2 to 7; match them.

Before writing, load `artifact-design` (required by the Artifact tool) and `dataviz` (for the figures). Then read `house.css.html` next to this file: it is the exact CSS of the existing pages. Reuse it verbatim so the new page reads as one of the series.

## The contract with the reader (every page has it, verbatim in spirit)

Hero block, in this order: eyebrow (series, book, chapter or "companion note"), `h1` with one italic word, a dek paragraph that states the argument of the page in four or five sentences, then the mono `.src` block with these lines:

- **COVERS**: exactly which sections, equations, figures, exercises of the source.
- **ASSUMES**: what is taken as known, and where each is recalled.
- **CHECKED**: "Every number here was computed and printed before it was written down." Name any place the source's own arithmetic did not check out, and any place an earlier version of this material was wrong: those are shown in a red `.corr` box and corrected in context, never silently fixed.
- **LABELS**: every section carries a provenance chip: `in the book` (`.prov.book`), `expanded` (`.prov.exp`), `mine` (`.prov.mine`). This exists because an earlier page built a large apparatus around half a page of source and presented it as the book's. Do not repeat that.

## Structure

- Tabs (`.tabbar` + `.tabpanel`) for Acts when the page has more than three acts; a single scroll otherwise. Act dividers (`.act`) carry a Roman numeral, a title, a one-line `.actw` subject and a paragraph `.actl` saying why this act exists.
- Sections (`section.part`) numbered like the source (`7.4`, `2.1.3`), each with an `h2`, an italic `.sub` line, and the provenance chip.
- The first section of a book chapter is always **"Read the label on every section"** with the `.provkey` legend and any notation conventions (estimates written `x^est` because accents do not compose on Greek letters in a browser).
- The last act is **the ledger**: what is his, what is expanded, what is mine; what was checked and what did not reproduce; and **"The whole page in N lines"** in a `.box.key`.

## Prose rules (the learner's register)

- Derive, never state. Every symbol is motivated by a picture or a problem before it appears. "Why would anyone reach for this?" is answered before the formula.
- Quote the source in `.box.quote` when the claim is the author's. Paraphrase is attribution theft.
- Corrections to the source or to earlier pages are shown, with the derivation, in a `.corr` box. Places where the author explicitly declines to go further are stated ("where he stops", `.box.beyond`).
- Traps get a `.box.trap`. Key results get a `.box.key`. Comparisons go in tables (`.tw table` or `.scrollx .tbl2`).
- A running concrete example carried through the page beats a new example per section.
- No em or en dashes, no " - " separators. Commas, colons, full stops.

## Figures (the load-bearing part)

1. **Compute first.** Write a Python script in the scratchpad that produces every number on the page (exact formulas, root-finding, or simulation with a stated seed). Print the numbers. Only then write captions. The `CHECKED` line is a promise; keep it.
2. **Draw from those numbers as inline SVG** using the house chart idiom: `<figure><div class="figin"><div class="fightl"><span class="eyebrow">Figure N · exact | simulated, seed S, n draws</span><h4>claim the figure makes</h4></div><div class="chartbox"><div class="cw"><svg viewBox="0 0 740 ...">...</svg></div></div><div class="legend">...</div><figcaption>...</figcaption></div></figure>`. Colours only from the CSS variables (`--s1` teal, `--s2` amber, `--s3` rose, `--s4` indigo, `--mut`, `--grid`, `--axis`). Axis text uses class `ax` at 11px. Width 740 for a full panel; `.pair` for two, `.trio` for three, `.quad` for four.
3. **The caption carries the numbers.** State the values the reader should take away, bold, and the check that ties the figure to the formula (agreement to 2.3e-13, ratio 1.015, and so on).
4. Every figure has a legend. A figure that restates the paragraph is deleted.
5. Nothing on the page is presented as market data unless it is, and then the source and date are named.

## After publishing

- Publish with the Artifact tool (favicon: one emoji; title: the noun phrase; description: one sentence). Keep the `<title>` stable across redeploys.
- Add the page to `~/Documents/Second Brain/Learn/Artifacts.md` under its domain, with the URL, and link it from the session note and from every concept note it establishes (`graph.py new/link` for any node the page adds; the page URL goes in `--source`).
- Tell the learner the URL and the two or three places on the page where the argument is theirs to check.
