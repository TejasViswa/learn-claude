#!/usr/bin/env python3
"""mdlog.py — mirror a Claude Code session into an Obsidian note.

Port of the `md-log` extension from github.com/amosblomqvist/learn (a pi
extension) to Claude Code hooks. The linked .md file is meant to be read
RENDERED in Obsidian, so assistant prose with $...$ math, ```mermaid fences,
code blocks and wikilink embeds renders natively. Nothing is transformed.

What gets captured (reading-relevant content only):
  - user prompts (system-injected tags stripped)
  - assistant text (lesson prose)
  - AskUserQuestion question + answer blocks (the quiz / ask surface)
Every other tool call (Bash, Read, Write, ...) is omitted.

Commands (run from a Claude Code session; the session id comes from the
CLAUDE_CODE_SESSION_ID env var that the Bash tool exports):
  mdlog.py link <path> [--create]   link a note (backfills the session so far)
  mdlog.py unlink                   stop mirroring
  mdlog.py status                   show the linked file
  mdlog.py hook                     hook entry point (stdin = hook JSON)

Hook wiring (settings.json): UserPromptSubmit, Stop, SessionStart, and
PreToolUse/PostToolUse with matcher AskUserQuestion all call `mdlog.py hook`.
The UserPromptSubmit hook also understands two typed commands, so the learner
can link from the prompt line without a skill:
  md-log <path>      (or /md-log <path>)
  md-unlog           (or /md-unlog)

Design rules:
  - fail OPEN: any internal error exits 0 with nothing written, so a bug here
    can never block a prompt, a tool, or a stop.
  - append-only, deduplicated by transcript uuid / tool_use id so the live
    hooks and the Stop-time replay never double-write.
  - a relative path resolves against the cwd first, then the Obsidian vault.
"""
import fcntl
import glob
import hashlib
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
LEARN_DIR = os.path.join(HOME, ".claude", "learn")
STATE_DIR = os.path.join(LEARN_DIR, "state")
VAULT = os.environ.get("LEARN_VAULT") or os.path.join(HOME, "Documents", "Second Brain")
PROJECTS = os.path.join(HOME, ".claude", "projects")

ASSISTANT_LABEL = "CLAUDE"
USER_LABEL = "YOU"


# ---------------------------------------------------------------- state ----

_SID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def valid_sid(sid):
    return bool(sid) and bool(_SID_RE.match(str(sid))) and ".." not in str(sid)


def _state_path(sid):
    if not valid_sid(sid):
        raise ValueError("invalid session id")
    return os.path.join(STATE_DIR, f"{sid}.json")


def load_state(sid):
    try:
        with open(_state_path(sid), "r", encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        st = {}
    st.setdefault("file", None)
    st.setdefault("logged", [])
    st.setdefault("pending_prompts", [])   # hashes of prompts written live, awaiting their transcript record
    return st


def save_state(sid, st):
    os.makedirs(STATE_DIR, exist_ok=True)
    # keep the dedupe sets bounded; a session rarely has >5000 records
    st["logged"] = st["logged"][-20000:]
    st["pending_prompts"] = st["pending_prompts"][-200:]
    tmp = _state_path(sid) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(tmp, _state_path(sid))


def find_transcript(sid, hint=None):
    if hint and os.path.isfile(hint):
        return hint
    cands = glob.glob(os.path.join(PROJECTS, "*", f"{sid}.jsonl"))
    if not cands:
        return None
    cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return cands[0]


# ------------------------------------------------------------- writing ----

def append_block(path, text):
    """Append one block. Returns True only if the bytes were written and flushed."""
    if not path or not text:
        return False
    written = False
    try:
        with open(path, "a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                current = f.read()
                prefix = "\n\n" if current.strip() else ""
                f.write(prefix + text.rstrip("\n") + "\n")
                f.flush()
                written = True
                # durability is best-effort: some mounts (iCloud Drive, FUSE) reject fsync
                # after accepting the bytes, and "did the write land" must not depend on it
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        return written
    except Exception:
        return written


def callout(kind, title, body_lines):
    lines = [f"> [!{kind}] {title}"]
    for line in body_lines:
        lines.append(">" if not line else f"> {line}")
    return "\n".join(lines)


def user_block(text):
    return f"> [!quote] {USER_LABEL}\n\n{text}"


def assistant_block(text):
    return f"> [!abstract] {ASSISTANT_LABEL}\n\n{text}"


def _h(s):
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()[:16]


# --------------------------------------------------------- text cleanup ----

_STRIP_TAGS = [
    r"<system-reminder>[\s\S]*?</system-reminder>",
    r"<local-command-caveat>[\s\S]*?</local-command-caveat>",
    r"<local-command-stdout>[\s\S]*?</local-command-stdout>",
    r"<command-name>[\s\S]*?</command-name>",
    r"<command-message>[\s\S]*?</command-message>",
    r"<command-args>[\s\S]*?</command-args>",
    r"<task-notification>[\s\S]*?</task-notification>",
    r"<invoke[\s\S]*?</invoke>",
]


def clean_user_text(text):
    for pat in _STRIP_TAGS:
        text = re.sub(pat, "", text)
    # skill bodies injected as <skill name="..."> ... </skill>
    text = re.sub(
        r"<skill\b([^>]*)>[\s\S]*?</skill>",
        lambda m: "> [!note] SKILL loaded: "
        + (re.search(r'name="([^"]+)"', m.group(1) or "") or [None, "(unknown)"])[1]
        if re.search(r'name="([^"]+)"', m.group(1) or "")
        else "> [!note] SKILL loaded",
        text,
    )
    return text.strip()


def is_mdlog_command(text):
    m = re.match(r"^\s*/?md-(log|unlog)\b\s*(.*)$", text.strip(), re.S)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


# ------------------------------------------------ AskUserQuestion render ----

def question_blocks(tool_input):
    """Render the question(s) of one AskUserQuestion call as callouts."""
    out = []
    for q in (tool_input or {}).get("questions", []) or []:
        header = q.get("header") or "Question"
        body = [ln for ln in (q.get("question") or "").split("\n")]
        opts = q.get("options") or []
        if opts:
            body.append("")
            for i, o in enumerate(opts, 1):
                label = o.get("label", "")
                desc = (o.get("description") or "").strip()
                body.append(f"{i}. **{label}**" + (f": {desc}" if desc else ""))
        kind = "question"
        title = f"Quiz" if header.lower().startswith("quiz") else f"Question · {header}"
        out.append(callout(kind, title, body))
    return "\n\n".join(out)


def _answers_from_response(resp):
    """Best-effort extraction of {question: answer} from a tool response."""
    if resp is None:
        return {}
    if isinstance(resp, dict):
        for key in ("answers", "answer", "result"):
            v = resp.get(key)
            if isinstance(v, dict):
                return {str(k): (", ".join(x) if isinstance(x, list) else str(x)) for k, x in v.items()}
        return {}
    return {}


def answer_block(tool_input, tool_response):
    answers = _answers_from_response(tool_response)
    body = []
    if answers:
        qs = (tool_input or {}).get("questions", []) or []
        for q in qs:
            qt = q.get("question", "")
            a = answers.get(qt)
            if a is None and len(answers) == 1:
                a = next(iter(answers.values()))
            if a is not None:
                body.append(f"**{q.get('header') or 'Answer'}:** {a}")
        if not body:
            for k, v in answers.items():
                body.append(f"{v}")
    else:
        # fall back to whatever text the tool returned
        txt = tool_response if isinstance(tool_response, str) else json.dumps(tool_response, ensure_ascii=False)
        txt = (txt or "").strip()
        if txt:
            body = txt.split("\n")[:12]
    if not body:
        body = ["(no answer)"]
    return callout("example", "Answer", body)


def _tool_result_text(block):
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
    return ""


# ------------------------------------------------------------- replay ----

def replay(sid, st, transcript):
    """Append every not-yet-logged reading-relevant record from the transcript."""
    if not transcript or not os.path.isfile(transcript):
        return 0
    logged = set(st["logged"])
    pending = list(st["pending_prompts"])
    path = st["file"]

    def consume_pending(hh):
        """True if this prompt was already written live (and drop it from the queue)."""
        if hh in pending:
            pending.remove(hh)
            return True
        return False
    written = 0
    pending_questions = {}  # tool_use_id -> tool_input (awaiting their result)
    asst_buf = {"id": None, "parts": [], "uuids": []}

    def flush_asst():
        nonlocal written
        if asst_buf["parts"]:
            append_block(path, assistant_block("\n\n".join(asst_buf["parts"])))
            written += 1
        for u in asst_buf["uuids"]:
            logged.add(u)
        asst_buf["id"] = None
        asst_buf["parts"] = []
        asst_buf["uuids"] = []

    with open(transcript, "r", encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            t = r.get("type")
            if t not in ("user", "assistant"):
                continue
            if r.get("isSidechain"):
                continue
            uuid = r.get("uuid")
            msg = r.get("message") or {}
            content = msg.get("content")

            if t == "assistant":
                mid = msg.get("id") or uuid
                if asst_buf["id"] not in (None, mid):
                    flush_asst()
                asst_buf["id"] = mid
                if not isinstance(content, list):
                    continue
                for b in content:
                    bt = b.get("type")
                    if bt == "text":
                        if uuid in logged:
                            continue
                        txt = (b.get("text") or "").strip()
                        if txt:
                            asst_buf["parts"].append(txt)
                        asst_buf["uuids"].append(uuid)
                    elif bt == "tool_use" and b.get("name") == "AskUserQuestion":
                        flush_asst()
                        tid = b.get("id")
                        key = f"q:{tid}"
                        pending_questions[tid] = b.get("input") or {}
                        if key not in logged and f"q:{_h(json.dumps(b.get('input'), sort_keys=True))}" not in logged:
                            append_block(path, question_blocks(b.get("input") or {}))
                            written += 1
                        logged.add(key)
                continue

            # user record
            if r.get("isMeta"):
                logged.add(uuid)
                continue
            if isinstance(content, str):
                flush_asst()
                if uuid in logged:
                    continue
                txt = clean_user_text(content)
                logged.add(uuid)
                if not txt or is_mdlog_command(txt):
                    continue
                if consume_pending(_h(txt)):
                    continue
                append_block(path, user_block(txt))
                written += 1
            elif isinstance(content, list):
                texts = []
                for b in content:
                    bt = b.get("type")
                    if bt == "text":
                        texts.append(b.get("text") or "")
                    elif bt == "tool_result":
                        tid = b.get("tool_use_id")
                        if tid in pending_questions:
                            flush_asst()
                            key = f"a:{tid}"
                            if key not in logged:
                                resp = r.get("toolUseResult")
                                if resp is None:
                                    resp = _tool_result_text(b)
                                append_block(path, answer_block(pending_questions[tid], resp))
                                written += 1
                                logged.add(key)
                            pending_questions.pop(tid, None)
                if texts:
                    flush_asst()
                    if uuid not in logged:
                        txt = clean_user_text("\n".join(texts))
                        logged.add(uuid)
                        if txt and not is_mdlog_command(txt):
                            if not consume_pending(_h(txt)):
                                append_block(path, user_block(txt))
                                written += 1
                else:
                    logged.add(uuid)
    flush_asst()
    st["logged"] = sorted(logged)
    st["pending_prompts"] = pending
    return written


# ------------------------------------------------------------ commands ----

def resolve_note(arg, cwd, create=False):
    p = os.path.expanduser(arg)
    if not os.path.isabs(p):
        c1 = os.path.abspath(os.path.join(cwd or os.getcwd(), p))
        c2 = os.path.abspath(os.path.join(VAULT, p))
        p = c1 if os.path.isfile(c1) else c2
    if not p.endswith(".md"):
        p += ".md"
    p = os.path.realpath(p)
    vault_root = os.path.realpath(VAULT)
    if not p.startswith(vault_root + os.sep):
        raise PermissionError(f"the mirror may only write inside the vault: {VAULT}")
    if not os.path.isfile(p):
        if not create:
            raise FileNotFoundError(p)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write("")
    return p


def cmd_link(sid, arg, cwd, create, transcript_hint=None):
    note = resolve_note(arg, cwd, create=create)
    st = load_state(sid)
    if st["file"] != note:
        # a fresh link (or a re-link to a different note) backfills from scratch
        st["logged"] = []
        st["pending_prompts"] = []
    st["file"] = note
    n = replay(sid, st, find_transcript(sid, transcript_hint))
    save_state(sid, st)
    return note, n


def cmd_unlink(sid):
    st = load_state(sid)
    old = st["file"]
    st["file"] = None
    save_state(sid, st)
    return old


def session_id_from_env():
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")


# --------------------------------------------------------------- hooks ----

def _emit(obj=None):
    if obj:
        sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def hook_main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    sid = payload.get("session_id")
    if not valid_sid(sid):
        return
    event = payload.get("hook_event_name") or ""
    cwd = payload.get("cwd")
    transcript = payload.get("transcript_path")
    st = load_state(sid)

    if event == "UserPromptSubmit":
        prompt = payload.get("prompt") or ""
        cmd = is_mdlog_command(prompt)
        if cmd:
            kind, arg = cmd
            if kind == "unlog":
                old = cmd_unlink(sid)
                msg = f"md-log: unlinked {old}" if old else "md-log: no file was linked"
            else:
                if not arg:
                    msg = "md-log: usage: md-log <path-to-note.md> (relative paths resolve against cwd, then the Obsidian vault)"
                else:
                    try:
                        note, n = cmd_link(sid, arg, cwd, create=True, transcript_hint=transcript)
                        msg = f"md-log: session now mirrored to {note} ({n} blocks backfilled). Tell the user in one line; then continue."
                    except Exception as e:  # noqa: BLE001
                        msg = f"md-log: could not link ({e})"
            _emit({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": msg}})
            return
        if st["file"]:
            txt = clean_user_text(prompt)
            if txt:
                # only suppress the later transcript replay if the live write really landed;
                # a failed write leaves the prompt for the Stop replay to recover
                if append_block(st["file"], user_block(txt)):
                    st["pending_prompts"].append(_h(txt))
                    save_state(sid, st)
        return

    if not st["file"]:
        return

    if event == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion":
        tin = payload.get("tool_input") or {}
        tid = payload.get("tool_use_id")
        key = f"q:{tid}" if tid else f"q:{_h(json.dumps(tin, sort_keys=True))}"
        if key not in set(st["logged"]):
            append_block(st["file"], question_blocks(tin))
            st["logged"].append(key)
            if tid:
                st["logged"].append(f"q:{_h(json.dumps(tin, sort_keys=True))}")
            save_state(sid, st)
        return

    if event == "PostToolUse" and payload.get("tool_name") == "AskUserQuestion":
        tin = payload.get("tool_input") or {}
        tid = payload.get("tool_use_id")
        key = f"a:{tid}" if tid else f"a:{_h(json.dumps(tin, sort_keys=True))}"
        if key not in set(st["logged"]):
            append_block(st["file"], answer_block(tin, payload.get("tool_response")))
            st["logged"].append(key)
            save_state(sid, st)
        return

    if event == "Stop":
        replay(sid, st, find_transcript(sid, transcript))
        save_state(sid, st)
        return

    if event == "SessionStart":
        _emit({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                      "additionalContext": f"md-log: this session is mirrored to {st['file']} (Obsidian). Keep teaching prose in Markdown with LaTeX math; it renders there."}})
        return


# ---------------------------------------------------------------- main ----

def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "hook":
        try:
            hook_main()
        except Exception:
            pass
        return 0

    sid = None
    args = []
    create = False
    i = 2
    while i < len(argv):
        if argv[i] == "--session" and i + 1 < len(argv):
            sid = argv[i + 1]
            i += 2
            continue
        if argv[i] == "--create":
            create = True
            i += 1
            continue
        args.append(argv[i])
        i += 1
    sid = sid or session_id_from_env()
    if not valid_sid(sid):
        print("mdlog: no valid session id (set CLAUDE_CODE_SESSION_ID or pass --session)", file=sys.stderr)
        return 1

    if cmd == "link":
        if not args:
            print("usage: mdlog.py link <path> [--create]", file=sys.stderr)
            return 1
        try:
            note, n = cmd_link(sid, args[0], os.getcwd(), create)
        except FileNotFoundError as e:
            print(f"mdlog: file does not exist: {e} (pass --create to create it inside the vault)", file=sys.stderr)
            return 1
        except PermissionError as e:
            print(f"mdlog: {e}", file=sys.stderr)
            return 1
        print(f"linked: {note} ({n} blocks backfilled)")
        return 0
    if cmd == "unlink":
        old = cmd_unlink(sid)
        print(f"unlinked: {old}" if old else "nothing was linked")
        return 0
    if cmd == "status":
        st = load_state(sid)
        print(f"session {sid}\nfile: {st['file'] or '(none)'}\nlogged records: {len(st['logged'])}")
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
