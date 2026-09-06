---
name: learn
description: Start, continue, review or close a learning session that grows the Obsidian knowledge graph (vault "Second Brain", folder Learn/). Use when the user says /learn <topic>, "teach me", "let's continue X", "quiz me", "review", or wants to switch topics. Handles kickoff (domain, session note, live Obsidian mirror), review (spaced retrieval), status, and bookkeeping. The teaching itself follows the teach skill.
---

# /learn

One graph, many trees. Every session either deepens a tree (a domain) or reviews nodes that are due. The vault is `~/Documents/Second Brain`, the graph lives in `Learn/`, one note per concept, wikilinks as edges, sessions as hubs. Helper scripts (deterministic, never hand-edit frontmatter):

Always spell the commands out in full (each Bash call is a fresh zsh; shell variables and functions do not persist and `graph.py` style aliases do not word-split):

```bash
python3 ~/.claude/learn/graph.py <new|find|link|mark|touch|due|frontier|session|moc|stats|path> ...
python3 ~/.claude/learn/mdlog.py <link|unlink|status> ...
```

Load the `teach` skill for the principles and the probe, plan, teach loop. This skill is the mechanics around it.

## Modes

### `/learn <topic>` (default): start or continue a tree

1. **Domain.** Map the topic to a domain folder. Existing ones: `ls ~/Documents/Second\ Brain/Learn/`. Seeded: Mathematics, Stochastics, Quant, Markets and Economics, Optimization. Hobby domains (Hinduism, anything) are created on first use by `graph.py new --domain "<Name>"`. If the topic could sit in two domains, ask once (AskUserQuestion, not a quiz). Prefer fewer, broader domains; the graph links across them anyway.
2. **Orient in the vault before anything else.** Read the domain MOC's Frontier section, run `python3 ~/.claude/learn/graph.py frontier "<Domain>"` and `python3 ~/.claude/learn/graph.py find "<key terms>"`, and open any concept notes the topic touches. Also check `Learn/Artifacts.md` for an existing companion page on the topic. This is what makes "continue where I left off" work after weeks away.
3. **Session note + live mirror.**
   ```bash
   P=$(python3 ~/.claude/learn/graph.py session "<Topic as a short title>" --domain "<Domain>")   # creates Learn/Sessions/<date> <Topic>.md, prints path
   python3 ~/.claude/learn/mdlog.py link "$P"                                                     # from now on every prompt, lesson and quiz lands in that note
   ```
   Tell the learner in one line where the session is being written (they read it rendered in Obsidian). If `python3 ~/.claude/learn/mdlog.py link` reports no session id, the CLAUDE_CODE_SESSION_ID env var is missing: fall back to telling them to type `md-log <path>` as a prompt, which the hook understands.
4. **Teach** per the teach skill: probe (quizzes + goal), plan (present the mermaid map, wait for go-ahead), teach node by node with bookkeeping as you go (`python3 ~/.claude/learn/graph.py new/link/mark/touch`, fill the concept notes).
5. **Close** (also when the learner says they are bored or wants to switch): rewrite the domain MOC Frontier (solid / shaky / next node), `python3 ~/.claude/learn/graph.py moc "<Domain>"`, `python3 ~/.claude/learn/graph.py touch` any concepts not yet linked to the session, and give a six-line summary in chat (it lands in the note). Offer, in one line, a companion page (`/companion`) if the session was substantial.

### `/learn review [Domain]`: spaced retrieval across the whole graph

Retention is the reason the graph exists. Run:
```bash
python3 ~/.claude/learn/graph.py due --limit 12 [--domain "<Domain>"]
```
For each due concept, open its note, ask **The check** question as a quiz (teach skill quiz protocol). Then immediately `python3 ~/.claude/learn/graph.py mark "<Title>" pass|fail --note "..."`. On a fail, re-teach that node briefly from its parents (do not lecture the whole tree), re-quiz once, mark again. Never-checked seeded nodes count as due: for those, first ask whether the learner wants to be taught it or already knows it (a quiz answers that). Mix domains unless one was named; switching domains inside a review is fine and good. End with `python3 ~/.claude/learn/graph.py stats` and a line on what is next due.

### `/learn status`

`python3 ~/.claude/learn/graph.py stats`, `python3 ~/.claude/learn/graph.py due --limit 10`, and the Frontier section of each domain MOC. One screen, no prose beyond a line per domain.

### `/learn add <concept> [in <Domain>]`

Quick capture without a lesson: `python3 ~/.claude/learn/graph.py find` first (reuse), then `python3 ~/.claude/learn/graph.py new` with a real one-line claim and at least one `--depends` parent if one exists. Status stays unknown so review picks it up.

### `/learn off`

`python3 ~/.claude/learn/mdlog.py unlink`. Also happens implicitly at the end of the Claude Code session.

## Rules that keep the graph clean

- **One note per idea; the title is the idea's name** (noun phrase, capitalised like a heading, no trailing period). Before creating, always `python3 ~/.claude/learn/graph.py find`. Duplicate nodes are the main way graphs rot.
- **A title that exists in two domains is refused** by mark/link/touch/path (exit 3) until you pass `--domain "<D>"`; cmd `new` refuses a title that already exists in another domain. Prefer distinct titles ("Gamma (option greek)" vs "Gamma function").
- **Edges are dependencies, not associations.** `A --depends B` means A cannot be understood without B. Associations go in the note's "Connects to" section as plain wikilinks (they still draw in the graph, but the review scheduler and the frontier use only dependencies).
- **Cross-domain edges are encouraged**: a Quant node depending on a Mathematics node, a Hinduism node connecting to a Stochastics node if the learner finds the bridge. That is the whole point of one graph.
- **Provenance in every node's Sources**: book and section, artifact title and URL, paper. "Mine" derivations are marked as such.
- **Never delete notes.** Wrong ones get a "Correction" line at the top and stay, so the correction is visible. Renames only via Obsidian (it rewrites links).
- **Session notes are append-only** (the mirror writes them). Add the "Concepts touched" links via `python3 ~/.claude/learn/graph.py touch`.
- **Obsidian graph hygiene**: nodes carry `tags: [learn/<domain>]` so graph filters and colour groups per domain work (`tag:#learn/quant`). Suggest to the learner once: colour groups in Graph view, one per `learn/<domain>` tag, and filter `path:Learn` to see only the knowledge graph.

## Where things are

- `Learn/Learn MOC.md`: the entry point, with Dataview blocks (due today, shaky, per-domain counts). Dataview must be enabled once in Obsidian settings for those blocks to render; the `python3 ~/.claude/learn/graph.py due` and `python3 ~/.claude/learn/graph.py stats` commands give the same information without it.
- `Learn/<Domain>/<Domain> MOC.md`: the tree's frontier and managed concept list.
- `Learn/Sessions/`: one note per session, mirrored live.
- `Learn/viz/`: SVG figures made by the `svg-maker` agent, embedded with `![[viz-....svg|500]]`.
- `Learn/Artifacts.md`: index of companion pages (claude.ai artifacts), by domain and chapter.
- `Learn/How this works.md`: the learner-facing manual.
