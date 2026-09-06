#!/usr/bin/env python3
"""graph.py — the knowledge graph in the Obsidian vault, as a deterministic CLI.

Every concept is ONE note under  <vault>/Learn/<Domain>/<Title>.md  with YAML
frontmatter. Wikilinks are the edges, so Obsidian's graph view IS the
dependency graph the teaching builds. Sessions are notes under Learn/Sessions/
that link to the concepts they touched, so a session shows up as a hub.

The teacher (Claude) never edits frontmatter by hand; it calls this script so
status, review dates and edges stay machine-consistent.

Commands
  new   "<Title>" --domain <D> [--one-line "..."] [--depends "A" "B"] [--source S ...]
                  [--alias X ...] [--status unknown|shaky|solid] [--check "Q: ... A: ..."]  create a node (never overwrites)
  find  "<term>"                                  search titles/aliases across the WHOLE vault
  link  "<Title>" --depends "<Other>" ...         add dependency edges (idempotent)
  (link/mark/touch/path accept --domain "<D>" to disambiguate a title that exists in several domains)
  mark  "<Title>" pass|fail [--note "..."]        record a retrieval check; schedules next review
  touch "<Title>" --session "<Session title>"     link a session note to a concept (both directions)
  due   [--domain D] [--limit N] [--all]          what is due for review today (never-checked last)
  frontier <Domain>                               where each strand ends: shaky, unknown, then leaves
  session "<Topic>" --domain <D> [--concepts A B] create Learn/Sessions/<date> <Topic>.md, print its path
  moc   <Domain>                                  regenerate the domain MOC's managed list
  moc-all                                         regenerate every domain MOC
  stats                                           counts per domain and status
  seed  <file.json>                               bulk-create nodes from a JSON list (see seed format below)
  path  "<Title>"                                 print the note's absolute path

Seed format: [{"title":..., "domain":..., "one_line":..., "depends_on":[...],
               "sources":[...], "aliases":[...], "status":"unknown"}, ...]

Domains are folder names (e.g. "Quant", "Markets and Economics", "Hinduism").
A new domain folder and MOC are created on first use.
"""
import datetime as dt
import glob
import json
import os
import re
import sys

VAULT = os.environ.get("LEARN_VAULT") or os.path.expanduser("~/Documents/Second Brain")
LEARN = os.path.join(VAULT, "Learn")
SESSIONS = os.path.join(LEARN, "Sessions")
TODAY = dt.date.today()

STATUSES = ("unknown", "shaky", "solid")
MOC_BEGIN = "<!-- graph:begin -->"
MOC_END = "<!-- graph:end -->"


# ------------------------------------------------------------ helpers ----

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def safe_title(s):
    s = s.strip()
    s = re.sub(r'[\\/:*?"<>|#^\[\]]+', " ", s)
    return re.sub(r"\s+", " ", s).strip()


def domain_dir(domain):
    return os.path.join(LEARN, safe_title(domain))


class AmbiguousTitle(Exception):
    def __init__(self, title, hits):
        super().__init__(title)
        self.title, self.hits = title, hits


def note_path(title, domain=None):
    """Find an existing concept note by title. With `domain`, only that folder is
    searched. Raises AmbiguousTitle if the same title exists in several domains
    and no domain was given. Returns None when the note does not exist."""
    t = safe_title(title).rstrip(".")
    hits = sorted(p for p in glob.glob(os.path.join(LEARN, "*", "*.md"))
                  if os.path.basename(p)[:-3].lower() == t.lower()
                  and os.path.basename(os.path.dirname(p)) != "Sessions")
    if domain:
        hits = [p for p in hits if os.path.basename(os.path.dirname(p)).lower() == safe_title(domain).lower()]
    if len(hits) > 1:
        raise AmbiguousTitle(t, hits)
    return hits[0] if hits else None


def _ambiguous(e):
    print(f"AMBIGUOUS: '{e.title}' exists in several domains; pass --domain to choose one:\n  "
          + "\n  ".join(e.hits), file=sys.stderr)
    return 3


def fm_parse(text):
    """YAML-subset parser: flat `key: value`, JSON flow lists, YAML block lists.
    Lines it cannot interpret are preserved verbatim under `_unparsed` and
    re-emitted by fm_dump, so a human edit is never silently dropped."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    block = text[4:end]
    body = text[end + 5:]
    fm = {}
    unparsed = []
    lines = block.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$", line)
        if not m:
            unparsed.append(line)
            continue
        k, v = m.group(1), m.group(2).strip()
        if v == "":
            # block list?
            items = []
            while i < len(lines) and re.match(r"^\s*-\s", lines[i]):
                items.append(re.sub(r"^\s*-\s+", "", lines[i]).strip().strip('"'))
                i += 1
            fm[k] = items if items else None
        elif v.startswith("["):
            try:
                fm[k] = json.loads(v)
            except Exception:
                fm[k] = [x.strip().strip('"') for x in v.strip("[]").split(",") if x.strip()]
        elif v.startswith('"'):
            try:
                fm[k] = json.loads(v)
            except Exception:
                fm[k] = v[1:-1] if v.endswith('"') else v
        elif re.fullmatch(r"-?\d+", v):
            fm[k] = int(v)
        else:
            fm[k] = v
    if unparsed:
        fm["_unparsed"] = unparsed
    return fm, body


def fm_dump(fm):
    lines = ["---"]
    for k, v in fm.items():
        if k == "_unparsed":
            continue
        if isinstance(v, list):
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        elif v is None:
            lines.append(f"{k}: ")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            s = str(v)
            if any(c in s for c in ':#[]{}"') or s != s.strip():
                s = json.dumps(s, ensure_ascii=False)
            lines.append(f"{k}: {s}")
    for raw in fm.get("_unparsed") or []:
        lines.append(raw)
    lines.append("---")
    return "\n".join(lines) + "\n"


def read_note(path):
    with open(path, "r", encoding="utf-8") as f:
        return fm_parse(f.read())


def write_note(path, fm, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(fm_dump(fm) + body)
    os.replace(tmp, path)


def canon(title, domain=None):
    """Resolve a title to the canonical on-disk note title if the note exists."""
    try:
        p = note_path(title, domain)
    except AmbiguousTitle as e:
        print(f"WARNING: dependency '{e.title}' is ambiguous across domains ({len(e.hits)} notes); "
              f"linking by plain title, disambiguate by hand", file=sys.stderr)
        p = None
    if p:
        return os.path.basename(p)[:-3]
    return safe_title(title).rstrip(".")


def wl(title):
    return f"[[{canon(title)}]]"


def unwl(s):
    m = re.match(r"^\[\[([^\]|#]+)", s.strip())
    return m.group(1).strip() if m else s.strip()


def all_concepts():
    out = []
    for p in sorted(glob.glob(os.path.join(LEARN, "*", "*.md"))):
        if os.path.basename(os.path.dirname(p)) == "Sessions":
            continue
        fm, body = read_note(p)
        if fm.get("type") != "concept":
            continue
        out.append((p, fm, body))
    return out


def ensure_section(body, heading, default_lines=()):
    if re.search(rf"^## {re.escape(heading)}\s*$", body, re.M):
        return body
    add = f"\n## {heading}\n" + "".join(f"{l}\n" for l in default_lines)
    return body.rstrip("\n") + "\n" + add


def append_under(body, heading, line):
    """Append a bullet under `## heading` (creating it) if the line is not already there."""
    body = ensure_section(body, heading)
    if line in body:
        return body
    parts = re.split(rf"(^## {re.escape(heading)}\s*$)", body, maxsplit=1, flags=re.M)
    if len(parts) < 3:
        return body.rstrip("\n") + f"\n{line}\n"
    head, h, rest = parts[0], parts[1], parts[2]
    nxt = re.search(r"^## ", rest, re.M)
    sec = rest if not nxt else rest[:nxt.start()]
    tail = "" if not nxt else rest[nxt.start():]
    sec = sec.rstrip("\n") + f"\n{line}\n\n"
    return head + h + sec + tail


# ----------------------------------------------------------- commands ----

def _check_lines(check):
    """Render a seed 'check' string ("Q: ... A: ...") as the Q/A block."""
    if not check:
        return "**Q:** (a retrieval question with a definite answer)\n**A:** \n"
    c = str(check).strip()
    m = re.match(r"^\s*Q:\s*(.*?)\s*(?:\n|\s)A:\s*(.*)$", c, re.S)
    if m:
        return f"**Q:** {m.group(1).strip()}\n**A:** {m.group(2).strip()}\n"
    return f"**Q:** {c}\n**A:** \n"


def concept_template(title, domain, one_line, depends, sources, check=None):
    dep_lines = [f"- {wl(d)}" for d in depends] or ["- (none yet: this is a root)"]
    src_lines = [f"- {s}" for s in sources] or ["- "]
    return (
        f"# {title}\n\n"
        f"**In one line.** {one_line or '(not yet stated)'}\n\n"
        f"## Rests on\n" + "\n".join(dep_lines) + "\n\n"
        f"## How you could have discovered it\n(taught in a session, not yet)\n\n"
        f"## Connects to\n- \n\n"
        f"## The check\n" + _check_lines(check) + "\n"
        f"## Sources\n" + "\n".join(src_lines) + "\n\n"
        f"## Sessions\n\n"
        f"## Review log\n"
    )


def cmd_new(title, domain, one_line="", depends=(), sources=(), aliases=(), status="unknown", quiet=False, check=None):
    raw = title.strip()
    title = safe_title(title).rstrip(".")
    try:
        existing = note_path(title)
    except AmbiguousTitle as e:
        return _ambiguous(e) and None
    if existing and os.path.basename(os.path.dirname(existing)).lower() != safe_title(domain).lower():
        print(f"EXISTS IN ANOTHER DOMAIN: '{raw}' is already {existing}; link to it or pick a distinct title",
              file=sys.stderr)
        return None
    if existing:
        efm, _ = read_note(existing)
        etitle = str(efm.get("title") or os.path.basename(existing)[:-3])
        if etitle.lower() != raw.lower() and etitle.lower() != title.lower():
            print(f"COLLISION: '{raw}' normalises to the same file as existing '{etitle}' ({existing}); "
                  f"choose a different title", file=sys.stderr)
            return None
        if not quiet:
            print(f"exists: {existing}")
        return existing
    if status not in STATUSES:
        status = "unknown"
    path = os.path.join(domain_dir(domain), title + ".md")
    fm = {
        "type": "concept",
        "title": raw,
        "domain": safe_title(domain),
        "tags": [f"learn/{slug(domain)}"],
        "status": status,
        "one_line": one_line or "",
        "depends_on": [wl(d) for d in depends],
        "sources": list(sources),
        "aliases": list(aliases),
        "created": TODAY.isoformat(),
        "last_checked": None,
        "next_review": None,
        "interval_days": 0,
        "reviews": 0,
        "lapses": 0,
    }
    write_note(path, fm, concept_template(title, domain, one_line, depends, sources, check))
    ensure_domain_moc(domain)
    if not quiet:
        print(f"created: {path}")
    return path


def cmd_find(term):
    t = term.lower()
    words = [w for w in re.split(r"\W+", t) if len(w) > 2]
    hits = []
    for p in glob.glob(os.path.join(VAULT, "**", "*.md"), recursive=True):
        if "/.obsidian/" in p or "/.trash/" in p:
            continue
        name = os.path.basename(p)[:-3]
        nl = name.lower()
        score = 0
        if nl == t:
            score = 100
        elif t in nl:
            score = 60
        else:
            score = sum(10 for w in words if w in nl)
        if score == 0 and p.startswith(LEARN):
            try:
                fm, _ = read_note(p)
                als = [a.lower() for a in (fm.get("aliases") or [])]
                if any(t == a or t in a for a in als):
                    score = 50
            except Exception:
                pass
        if score:
            rel = os.path.relpath(p, VAULT)
            hits.append((score, rel))
    hits.sort(key=lambda x: (-x[0], x[1]))
    for s, rel in hits[:25]:
        print(f"{s:3d}  {rel}")
    if not hits:
        print("(no matches)")


def cmd_link(title, depends, domain=None):
    try:
        path = note_path(title, domain)
    except AmbiguousTitle as e:
        return _ambiguous(e)
    if not path:
        print(f"no such concept: {title}", file=sys.stderr)
        return 1
    fm, body = read_note(path)
    deps = fm.get("depends_on") or []
    for d in depends:
        w = wl(d)
        if w not in deps:
            deps.append(w)
        body = append_under(body, "Rests on", f"- {w}")
        body = body.replace("- (none yet: this is a root)\n", "")
    fm["depends_on"] = deps
    write_note(path, fm, body)
    print(f"linked: {os.path.basename(path)[:-3]} -> {', '.join(depends)}")
    return 0


def schedule(fm, passed):
    interval = int(fm.get("interval_days") or 0)
    reviews = int(fm.get("reviews") or 0) + 1
    lapses = int(fm.get("lapses") or 0)
    if passed:
        interval = 1 if interval == 0 else max(interval + 1, round(interval * 2.3))
        status = "solid" if interval >= 5 else "shaky"
    else:
        interval = 1
        lapses += 1
        status = "shaky"
    fm["interval_days"] = interval
    fm["reviews"] = reviews
    fm["lapses"] = lapses
    fm["status"] = status
    fm["last_checked"] = TODAY.isoformat()
    fm["next_review"] = (TODAY + dt.timedelta(days=interval)).isoformat()
    return fm


def cmd_mark(title, result, note="", domain=None):
    try:
        path = note_path(title, domain)
    except AmbiguousTitle as e:
        return _ambiguous(e)
    if not path:
        print(f"no such concept: {title}", file=sys.stderr)
        return 1
    passed = result.lower() in ("pass", "p", "ok", "correct", "yes")
    fm, body = read_note(path)
    fm = schedule(fm, passed)
    body = append_under(body, "Review log",
                        f"- {TODAY.isoformat()} {'PASS' if passed else 'FAIL'}"
                        + (f": {note}" if note else "")
                        + f" (next {fm['next_review']}, interval {fm['interval_days']}d)")
    write_note(path, fm, body)
    print(f"{os.path.basename(path)[:-3]}: {'pass' if passed else 'fail'} -> status {fm['status']}, next review {fm['next_review']}")
    return 0


def cmd_touch(title, session_title, domain=None):
    try:
        path = note_path(title, domain)
    except AmbiguousTitle as e:
        return _ambiguous(e)
    if not path:
        print(f"no such concept: {title}", file=sys.stderr)
        return 1
    fm, body = read_note(path)
    body = append_under(body, "Sessions", f"- {wl(session_title)}")
    write_note(path, fm, body)
    # reverse edge on the session note
    sp = os.path.join(SESSIONS, safe_title(session_title) + ".md")
    if os.path.isfile(sp):
        sfm, sbody = read_note(sp)
        sbody = append_under(sbody, "Concepts touched", f"- {wl(os.path.basename(path)[:-3])}")
        cs = sfm.get("concepts") or []
        w = wl(os.path.basename(path)[:-3])
        if w not in cs:
            cs.append(w)
        sfm["concepts"] = cs
        write_note(sp, sfm, sbody)
    print(f"touched: {os.path.basename(path)[:-3]} <-> {session_title}")
    return 0


def cmd_due(domain=None, limit=20, show_all=False):
    rows = []
    for p, fm, _ in all_concepts():
        if domain and fm.get("domain", "").lower() != safe_title(domain).lower():
            continue
        nr = fm.get("next_review")
        checked = fm.get("last_checked")
        if nr:
            try:
                d = dt.date.fromisoformat(str(nr))
            except Exception:
                d = TODAY
            overdue = (TODAY - d).days
            if overdue >= 0 or show_all:
                rows.append((0, -overdue, fm["domain"], os.path.basename(p)[:-3], fm.get("status"), f"due {nr}" + (f" ({overdue}d overdue)" if overdue > 0 else "")))
        elif not checked:
            rows.append((1, 0, fm["domain"], os.path.basename(p)[:-3], fm.get("status"), "never checked"))
    rows.sort()
    for _, _, dom, name, st, when in rows[:limit]:
        print(f"{dom:24s} {name:48s} {st:8s} {when}")
    if not rows:
        print("(nothing due)")


def cmd_frontier(domain):
    nodes = [(p, fm, body) for p, fm, body in all_concepts()
             if fm.get("domain", "").lower() == safe_title(domain).lower()]
    if not nodes:
        print(f"(no concepts in {domain})")
        return
    names = {os.path.basename(p)[:-3] for p, _, _ in nodes}
    has_child = set()
    for _, fm, _ in nodes:
        for d in fm.get("depends_on") or []:
            has_child.add(unwl(d))
    def rows(status):
        return [os.path.basename(p)[:-3] for p, fm, _ in nodes if fm.get("status") == status]
    print(f"# {safe_title(domain)}: {len(nodes)} concepts")
    print("\n## Shaky (fix these first)")
    for n in rows("shaky"): print(f"- {n}")
    print("\n## Unknown (read or seeded, never checked)")
    for n in rows("unknown"): print(f"- {n}")
    print("\n## Solid leaves (nothing built on them yet: deepen here)")
    for n in rows("solid"):
        if n not in has_child:
            print(f"- {n}")


def ensure_domain_moc(domain):
    d = domain_dir(domain)
    os.makedirs(d, exist_ok=True)
    moc = os.path.join(d, f"{safe_title(domain)} MOC.md")
    if not os.path.isfile(moc):
        fm = {"type": "moc", "domain": safe_title(domain), "tags": [f"learn/{slug(domain)}", "MOC"]}
        body = (
            f"# {safe_title(domain)}\n\n"
            f"Part of [[Learn MOC]]. One note per concept; the links are the dependency graph.\n\n"
            f"## Frontier\n(where each strand currently ends; rewritten by the teacher at the end of a session)\n\n"
            f"## Concepts\n{MOC_BEGIN}\n{MOC_END}\n\n"
            f"## Sessions\n```dataview\nLIST FROM \"Learn/Sessions\" WHERE domain = \"{safe_title(domain)}\" SORT file.name DESC\n```\n"
        )
        write_note(moc, fm, body)
    return moc


def cmd_moc(domain):
    moc = ensure_domain_moc(domain)
    fm, body = read_note(moc)
    nodes = [(os.path.basename(p)[:-3], f) for p, f, _ in all_concepts()
             if f.get("domain", "").lower() == safe_title(domain).lower()]
    lines = []
    for st, label in (("shaky", "Shaky"), ("unknown", "Unknown"), ("solid", "Solid")):
        group = sorted(n for n, f in nodes if f.get("status") == st)
        if group:
            lines.append(f"**{label}** ({len(group)})")
            lines += [f"- [[{n}]]" for n in group]
            lines.append("")
    managed = MOC_BEGIN + "\n" + "\n".join(lines).rstrip("\n") + "\n" + MOC_END
    if MOC_BEGIN in body and MOC_END in body:
        body = re.sub(re.escape(MOC_BEGIN) + r"[\s\S]*?" + re.escape(MOC_END), lambda m: managed, body)
    else:
        body = body.rstrip("\n") + "\n\n## Concepts\n" + managed + "\n"
    write_note(moc, fm, body)
    print(f"moc: {moc} ({len(nodes)} concepts)")


def cmd_moc_all():
    doms = sorted({f.get("domain") for _, f, _ in all_concepts() if f.get("domain")})
    for d in doms:
        cmd_moc(d)


def cmd_session(topic, domain, concepts=()):
    os.makedirs(SESSIONS, exist_ok=True)
    title = safe_title(f"{TODAY.isoformat()} {topic}")
    path = os.path.join(SESSIONS, title + ".md")
    if os.path.isfile(path):
        print(path)
        return path
    ensure_domain_moc(domain)
    fm = {
        "type": "session",
        "domain": safe_title(domain),
        "tags": [f"learn/{slug(domain)}", "session"],
        "date": TODAY.isoformat(),
        "topic": topic,
        "concepts": [wl(c) for c in concepts],
    }
    body = (
        f"# {topic}\n\n"
        f"Domain: [[{safe_title(domain)} MOC]] · {TODAY.isoformat()}\n\n"
        f"## Concepts touched\n" + "".join(f"- {wl(c)}\n" for c in concepts) + "\n"
        f"## Transcript\n"
    )
    write_note(path, fm, body)
    print(path)
    return path


def cmd_stats():
    nodes = all_concepts()
    by = {}
    for _, fm, _ in nodes:
        by.setdefault(fm.get("domain"), {"unknown": 0, "shaky": 0, "solid": 0})
        by[fm.get("domain")][fm.get("status", "unknown")] += 1
    print(f"{'domain':26s} {'unknown':>8s} {'shaky':>6s} {'solid':>6s} {'total':>6s}")
    for d in sorted(by):
        c = by[d]
        print(f"{d:26s} {c['unknown']:8d} {c['shaky']:6d} {c['solid']:6d} {sum(c.values()):6d}")
    print(f"{'ALL':26s} {sum(c['unknown'] for c in by.values()):8d} {sum(c['shaky'] for c in by.values()):6d} {sum(c['solid'] for c in by.values()):6d} {len(nodes):6d}")
    sess = glob.glob(os.path.join(SESSIONS, "*.md"))
    print(f"sessions: {len(sess)}")


def cmd_seed(file):
    with open(file, "r", encoding="utf-8") as f:
        items = json.load(f)
    created = 0
    for it in items:
        p = cmd_new(it["title"], it["domain"], it.get("one_line", ""), [],
                    it.get("sources", []), it.get("aliases", []), it.get("status", "unknown"), quiet=True,
                    check=it.get("check"))
        if p and os.path.isfile(p):
            created += 1
    # second pass: edges to nodes that may have been created later in the list
    for it in items:
        if it.get("depends_on"):
            try:
                path = note_path(it["title"], it["domain"])
            except AmbiguousTitle as e:
                _ambiguous(e)
                continue
            if not path:
                continue
            fm, body = read_note(path)
            deps = fm.get("depends_on") or []
            for d in it["depends_on"]:
                if wl(d) not in deps:
                    deps.append(wl(d))
                    body = append_under(body, "Rests on", f"- {wl(d)}")
            fm["depends_on"] = deps
            body = body.replace("- (none yet: this is a root)\n", "") if deps else body
            write_note(path, fm, body)
    doms = sorted({it["domain"] for it in items})
    for d in doms:
        cmd_moc(d)
    print(f"seeded {created} notes across {len(doms)} domain(s): {', '.join(doms)}")


# ---------------------------------------------------------------- main ----

def parse_args(argv):
    pos, opts = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            vals = []
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                vals.append(argv[i])
                i += 1
            if key in ("depends", "source", "alias", "concepts"):
                opts.setdefault(key, []).extend(vals)
            elif key in ("all",):
                opts[key] = True
            else:
                opts[key] = " ".join(vals) if vals else True
        else:
            pos.append(a)
            i += 1
    return pos, opts


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    pos, o = parse_args(argv[2:])
    try:
        if cmd == "new":
            r = cmd_new(pos[0], o["domain"], o.get("one-line", ""), o.get("depends", []), o.get("source", []),
                        o.get("alias", []), o.get("status", "unknown"), check=o.get("check"))
            return 0 if r else 2
        elif cmd == "find":
            cmd_find(" ".join(pos))
        elif cmd == "link":
            return cmd_link(pos[0], o.get("depends", []), o.get("domain"))
        elif cmd == "mark":
            return cmd_mark(pos[0], pos[1], o.get("note", ""), o.get("domain"))
        elif cmd == "touch":
            return cmd_touch(pos[0], o["session"], o.get("domain"))
        elif cmd == "due":
            cmd_due(o.get("domain"), int(o.get("limit", 20)), bool(o.get("all")))
        elif cmd == "frontier":
            cmd_frontier(" ".join(pos))
        elif cmd == "session":
            cmd_session(pos[0], o["domain"], o.get("concepts", []))
        elif cmd == "moc":
            cmd_moc(" ".join(pos))
        elif cmd == "moc-all":
            cmd_moc_all()
        elif cmd == "stats":
            cmd_stats()
        elif cmd == "seed":
            cmd_seed(pos[0])
        elif cmd == "path":
            try:
                p = note_path(pos[0], o.get("domain"))
            except AmbiguousTitle as e:
                return _ambiguous(e)
            print(p or "")
            return 0 if p else 1
        else:
            print(f"unknown command: {cmd}", file=sys.stderr)
            return 1
    except (KeyError, IndexError) as e:
        print(f"graph.py {cmd}: missing argument {e}\n", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
