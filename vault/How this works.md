---
type: reference
tags: [learn]
---
# How this works

The learning system is a port of Amos Blomqvist's `learn` (a pi configuration) to Claude Code, with the knowledge graph made literal in this vault. Read this once.

## The idea

Understanding is a dependency graph: a few unconditional truths at the roots, every other fact derivable from them, connected. The teaching builds that graph in your head (two principles: unconditional truths first, and "how could I have discovered this?"). This vault holds the same graph on disk, so it survives topic switches and months away, and Obsidian's graph view draws it.

- **One note per concept**, under `Learn/<Domain>/`. Its `depends_on` links are the edges. Its `status` is what the last quiz showed: `unknown`, `shaky`, `solid`.
- **One note per session**, under `Learn/Sessions/`, written live while you learn (prompts, lessons, quizzes and answers as callouts). It links to every concept it touched, so a session is a hub in the graph.
- **One MOC per domain** with a Frontier section: where each strand currently ends. That is how "continue where I left off" works.
- **Review is scheduled.** Each quiz pass lengthens a concept's review interval (1, 2, 5, 12, 27 days...); a fail resets it to tomorrow and marks it shaky. `/learn review` walks what is due, across all domains.

## Commands (in Claude Code)

| you type | what happens |
|---|---|
| `/learn <topic>` | picks the domain, reads the frontier, creates today's session note and mirrors the conversation into it live, then probes, plans (mermaid map, waits for your go-ahead) and teaches node by node with quizzes |
| `/learn review [Domain]` | spaced retrieval: quizzes whatever is due, re-teaches misses |
| `/learn status` | counts, what is due, each domain's frontier |
| `/learn add <concept> in <Domain>` | capture a node without a lesson |
| `/learn off` | stop mirroring |
| `/companion` | a long-form page in the EQI house style (computed figures, provenance labels), published as an artifact and indexed in [[Artifacts]] |
| `md-log Learn/Sessions/<note>.md` | manual mirror link (the hook understands it as a plain prompt) |

Quizzes are AskUserQuestion prompts with a "Quiz" header; the last option is always "I don't know" and Claude grades in its next message. "Other" is your free-text note.

## Obsidian setup (one-time)

1. Settings, Community plugins, enable **Dataview** (already installed) so [[Learn MOC]] tables render.
2. Graph view: filter `path:Learn`, then add colour groups: `tag:#learn/quant`, `tag:#learn/stochastics`, `tag:#learn/mathematics`, `tag:#learn/markets-and-economics`, `tag:#learn/optimization`, and one per hobby domain as they appear. Sessions are tagged `#session`.
3. Optional: in Graph view, "Orphans" off, and "Existing files only" on, so half-written links do not clutter.

## Rules the system follows (so you can catch it)

- Never a fact taught without motivation; never a foundation left unconfirmed by a quiz.
- Unsure about a fact: a researcher agent verifies before it is said.
- Provenance on every node: book section, page, or "mine".
- Corrections are shown, not silently fixed. Wrong notes are corrected in place, never deleted.
- No em dashes in prose. LaTeX for math. Mermaid for maps. Figures go to `Learn/viz/`.

## Files

`~/.claude/skills/{learn,teach,visualize,companion,pdf-reader,youtube-transcript}`, `~/.claude/agents/{researcher,svg-maker}.md`, `~/.claude/learn/{graph.py,mdlog.py}`, hooks in `~/.claude/settings.json`.
