#!/usr/bin/env bash
# install.sh: install (or update) the learn-claude system into ~/.claude.
# Idempotent. Re-run after `git pull` to update. Never touches your vault
# except to create Learn/ scaffolding when --seed is given.
#
#   ./install.sh            copy skills, agents, scripts; merge hooks; build the pdf venv
#   ./install.sh --seed     also create Learn/ in the vault (MOC, manual, the EQI seed) if absent
#
# Vault path: $LEARN_VAULT if set, else ~/Documents/Second Brain.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE="$HOME/.claude"
VAULT="${LEARN_VAULT:-$HOME/Documents/Second Brain}"

say() { printf '\033[1;32m>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*"; }

command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }
[ -d "$CLAUDE" ] || { echo "~/.claude not found: install Claude Code and run it once first"; exit 1; }

# 1. skills, agents, scripts
mkdir -p "$CLAUDE/skills" "$CLAUDE/agents" "$CLAUDE/learn/state"
for s in "$HERE"/skills/*/; do
  name="$(basename "$s")"
  rsync -a --delete --exclude '.venv' --exclude '__pycache__' "$s" "$CLAUDE/skills/$name/"
done
cp "$HERE"/agents/*.md "$CLAUDE/agents/"
cp "$HERE"/learn/*.py "$CLAUDE/learn/"
chmod +x "$CLAUDE"/learn/*.py
say "skills, agents and scripts installed"

# 2. hooks: merge into settings.json without disturbing anything else
python3 - "$CLAUDE/settings.json" <<'EOF'
import json, os, sys, shutil, time
p = sys.argv[1]
d = json.load(open(p)) if os.path.exists(p) else {}
if os.path.exists(p):
    shutil.copy(p, p + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
hooks = d.setdefault("hooks", {})
CMD = "/usr/bin/env python3 " + os.path.expanduser("~/.claude/learn/mdlog.py") + " hook"
def add(event, matcher=None):
    lst = hooks.setdefault(event, [])
    for e in lst:
        if e.get("matcher") == matcher and any(h.get("command", "").endswith("mdlog.py hook") for h in e.get("hooks", [])):
            for h in e["hooks"]:
                if h.get("command", "").endswith("mdlog.py hook"):
                    h["command"] = CMD
            return
    entry = {"hooks": [{"type": "command", "command": CMD}]}
    if matcher:
        entry["matcher"] = matcher
    lst.append(entry)
for ev, m in (("UserPromptSubmit", None), ("Stop", None), ("SessionStart", None),
              ("PreToolUse", "AskUserQuestion"), ("PostToolUse", "AskUserQuestion")):
    add(ev, m)
if os.environ.get("LEARN_VAULT"):
    d.setdefault("env", {})["LEARN_VAULT"] = os.environ["LEARN_VAULT"]
json.dump(d, open(p, "w"), indent=2)
print("hooks merged into", p)
EOF

# 3. pdf reader venv (best available python)
PY="$(command -v python3.12 || command -v python3.13 || command -v python3)"
if [ ! -x "$CLAUDE/skills/pdf-reader/.venv/bin/python" ]; then
  "$PY" -m venv "$CLAUDE/skills/pdf-reader/.venv"
  "$CLAUDE/skills/pdf-reader/.venv/bin/pip" install -q -r "$CLAUDE/skills/pdf-reader/requirements.txt" && say "pdf-reader venv built"
else
  say "pdf-reader venv present"
fi
command -v yt-dlp >/dev/null || warn "yt-dlp not found (optional): brew install yt-dlp"

# 4. vault scaffolding
if [ "${1:-}" = "--seed" ]; then
  if [ ! -d "$VAULT" ]; then warn "vault not found at $VAULT (set LEARN_VAULT); skipping seed"; else
    mkdir -p "$VAULT/Learn/Sessions" "$VAULT/Learn/viz"
    for f in "Learn MOC.md" "How this works.md"; do
      [ -f "$VAULT/Learn/$f" ] || cp "$HERE/vault/$f" "$VAULT/Learn/$f"
    done
    if [ -z "$(ls -d "$VAULT"/Learn/Quant 2>/dev/null)" ]; then
      LEARN_VAULT="$VAULT" python3 "$CLAUDE/learn/graph.py" seed "$HERE/vault/seed-eqi.json"
    else
      say "Learn/ already seeded; skipped"
    fi
  fi
fi

say "done. Open a NEW Claude Code session and type: /learn <topic>"
[ -d "$VAULT/Learn" ] || warn "no Learn/ in $VAULT yet: it is created by the first /learn, or run ./install.sh --seed"
