---
type: moc
tags: [MOC, learn]
---
# Learn

One graph, many trees. Every concept is one note; every wikilink is an edge; every session is a hub. Read [[How this works]] once. Companion pages live in [[Artifacts]].

## Domains
- [[Mathematics MOC]]
- [[Stochastics MOC]]
- [[Quant MOC]]
- [[Markets and Economics MOC]]
- [[Optimization MOC]]
- (new domains appear here on first `/learn`; add a line)

## Due for review
```dataview
TABLE WITHOUT ID file.link AS concept, domain, status, next_review AS due
FROM "Learn"
WHERE type = "concept" AND next_review AND next_review <= date(today)
SORT next_review ASC
LIMIT 25
```

## Shaky (fix these first)
```dataview
LIST domain
FROM "Learn"
WHERE type = "concept" AND status = "shaky"
SORT file.name ASC
```

## Never checked (seeded or read, not yet quizzed)
```dataview
TABLE WITHOUT ID file.link AS concept, domain
FROM "Learn"
WHERE type = "concept" AND !last_checked
SORT domain ASC, file.name ASC
LIMIT 40
```

## Recent sessions
```dataview
TABLE WITHOUT ID file.link AS session, domain, date
FROM "Learn/Sessions"
SORT date DESC
LIMIT 15
```

## Counts
```dataview
TABLE WITHOUT ID domain, length(rows) AS concepts, length(filter(rows, (r) => r.status = "solid")) AS solid, length(filter(rows, (r) => r.status = "shaky")) AS shaky
FROM "Learn"
WHERE type = "concept"
GROUP BY domain
```

> [!note] Dataview
> The tables above need the Dataview community plugin enabled (it is installed, not enabled). Without it, the same information comes from `python3 ~/.claude/learn/graph.py due` and `graph.py stats`.
