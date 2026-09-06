---
name: visualize
description: Add one correct, minimal picture to a lesson (a dependency graph, flow, sequence, state machine, tree, comparison, or a geometric figure) that renders inline in the Obsidian session note. Mermaid for structure (Obsidian renders it natively), an SVG file via the svg-maker agent for anything with exact positions. Use when an idea is genuinely clearer as a picture.
---

# Visualize

A picture earns its place only when it shows something words can't: shape, structure, direction, relationship, geometry. This teaching builds a dependency graph in the learner's head, so a visual is powerful exactly when it makes that structure (or a geometry) visible.

Do NOT visualise when prose or one equation already carries it. A decorative diagram that restates the sentence next to it adds noise and a chance to be wrong. A missing visual is cheaper than a false one.

## Two makers

**Mermaid, inline, for nodes-and-edges.** Dependency graphs, flowcharts, sequence, state, ER, trees, timelines. Obsidian renders a ```mermaid fence natively, so write it directly in your reply (the mirror copies it verbatim into the session note). Constraints: at most 7 nodes, labels of a few words, `graph TD` with foundations at the top flowing down to conclusions. Read your own source back once before sending: every arrow direction must be true. If a label needs a sentence, the diagram is carrying too much; cut.

**SVG file, via the `svg-maker` agent, for positions-and-shapes.** Coordinate geometry, number lines, vectors, function shapes, physical layouts, anything Mermaid cannot lay out. Dispatch:

```
Agent(subagent_type="svg-maker", model="opus", prompt="<minimal, concrete brief>")
```

The maker writes the SVG to `~/Documents/Second Brain/Learn/viz/viz-<slug>-<timestamp>.svg`, rasterises it, LOOKS at the PNG, iterates until correct and clean, and returns the filename. You embed it:

```
![[viz-<slug>-<timestamp>.svg|500]]
```

Obsidian resolves the embed by filename anywhere in the vault. If the maker returns `RESULT: NONE`, simplify the brief or drop the visual; never hand-draw an unverified SVG yourself.

## Brief the maker well: one idea, fewest elements

Prune before briefing. For each element ask "if I delete this, is the idea still clear?" If yes, delete it. Give the concept AND the concrete elements, not a vague topic and not a checklist.

- BAD: "make a diagram about how projection works"
- GOOD: "2D: a horizontal line (the subspace), a vector y from the origin ending above the line, its foot y_hat on the line, a dashed perpendicular from y to y_hat with a small right-angle mark. Label y, y_hat, and y minus y_hat. Show that the residual is perpendicular to the line."

If your brief lists more than 5 to 7 elements, cut it first. Introduce the picture in one sentence, then let it carry the idea; don't narrate every element back in prose.

## Why this is reliable

The maker never returns a picture it has not looked at, so "renders fine but says something false" is caught before it reaches the learner. Unique filenames keep Obsidian's by-filename embeds unambiguous. Mermaid stays inline because a rendering step would buy nothing: Obsidian is the renderer either way.
