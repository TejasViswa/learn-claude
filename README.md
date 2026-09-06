# learn-claude

An AI learning system for Claude Code with a persistent knowledge graph in Obsidian. A port of [amosblomqvist/learn](https://github.com/amosblomqvist/learn) (built for the `pi` agent) with the dependency graph made literal: one note per concept, wikilinks as edges, sessions as hubs, spaced retrieval on top.

## Install (any Mac with Claude Code and Obsidian)

```bash
git clone git@github.com:TejasViswa/learn-claude.git ~/code/learn-claude && ~/code/learn-claude/install.sh
```

Add `--seed` to also create the `Learn/` folder in the vault with the 259-node quant seed (first machine only; on other machines the vault syncs). If the vault is not at `~/Documents/Second Brain`, prefix with `LEARN_VAULT="/path/to/vault"`.

Update later: `cd ~/code/learn-claude && git pull && ./install.sh`.

Then open a **new** Claude Code session and type `/learn <topic>`.

## What it installs

| where | what |
|---|---|
| `~/.claude/skills/learn` | `/learn <topic>`, `/learn review`, `/learn status`, `/learn add`, `/learn off` |
| `~/.claude/skills/teach` | the teaching principles, the quiz protocol, the learner profile |
| `~/.claude/skills/visualize` | mermaid inline, SVG figures via the `svg-maker` agent |
| `~/.claude/skills/companion` | long-form companion pages in the house style |
| `~/.claude/skills/pdf-reader`, `youtube-transcript` | from amosblomqvist/pi-config |
| `~/.claude/agents/researcher.md`, `svg-maker.md` | subagents |
| `~/.claude/learn/graph.py` | the graph CLI (new, find, link, mark, due, frontier, session, moc, stats, seed) |
| `~/.claude/learn/mdlog.py` | the session mirror; five hooks merged into `~/.claude/settings.json` |

## How it works

Read `vault/How this works.md` (also installed into the vault as `Learn/How this works.md`).

## Attribution

Teaching philosophy, quiz design and the md-log idea are Amos Blomqvist's, from `learn` and `pi-config`, adapted to Claude Code. The graph, review scheduling and vault layout are additions.
