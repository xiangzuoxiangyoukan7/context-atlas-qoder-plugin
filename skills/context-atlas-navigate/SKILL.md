---
name: context-atlas-navigate
description: Read an existing Context Atlas knowledge base progressively through directory, neighbor, or bounded graph queries. Use to locate relevant project knowledge, not to assess readiness, health, or correctness.
---

# Context Atlas Navigate

Perform read-only, progressive knowledge navigation. Do not create a Proposal or modify the knowledge base.

Resolve the project root and exactly one current `doc-*` knowledge base first. If none exists, route to `$context-atlas-init`; if multiple candidates exist, ask the user to identify the current authority; if its format is unsupported, route to `$context-atlas-upgrade`. Make zero writes in every case.

Choose the smallest operation that answers the question:

- Discover what knowledge exists: query one directory level with `children`.
- Relate a located stable node: query one hop with `neighbors`.
- Analyze a wider relation area: query a bounded subgraph with `graph --start`.
- Analyze the whole knowledge base only when explicitly needed: query `graph --all`.

Start directory discovery at the knowledge-base root and descend only into relevant children:

```text
python <knowledge-base>/.project-kb/scripts/agent_kb_operation.py children <knowledge-base> --path .
```

`children` returns directory and Markdown summaries. Directory descriptions come from their `README.md`; the filesystem remains the authoritative tree. Do not recursively enumerate the tree unless the user's question requires it.

After locating a formal node, identify it by stable Front Matter `id` or knowledge-base-relative file path and query direct relations:

```text
python <knowledge-base>/.project-kb/scripts/agent_kb_operation.py neighbors <knowledge-base> --id <ID>
```

Use `--path <relative-markdown-path>` instead of `--id` when the current file is known. Resolve Python 3 using the same platform-aware runtime checks as the other Context Atlas Skills; `py -3` is valid on Windows. Never pass an absolute path to `--path`.

The default query is `--direction both` and returns only one-hop node summaries, relation directions, and paths. Optionally filter with `--direction outgoing|incoming` or `--relation rel_reads`. Do not recursively load every returned file.

For deliberate multi-hop analysis, run:

```text
python <knowledge-base>/.project-kb/scripts/agent_kb_operation.py graph <knowledge-base> --start <ID> --depth 2 --max-nodes 200
```

Use `--all` instead of `--start` only for an explicit whole-graph question. Optionally filter with `--relation`, `--type`, or `--status`. Treat `truncated: true` as an incomplete result and narrow the query or explicitly raise `--max-nodes`; never infer omitted nodes.

Inspect the result and choose only neighbors relevant to the user's task. Read those files normally; if another hop is needed, query the selected neighbor as a new starting node. Treat a relation as navigation evidence, not as proof that the neighbor must change.

If an operation reports invalid tree metadata, invalid relationships, missing stable identity, ambiguity, or an absent node, report the issue without guessing content or links. This Skill is read-only and does not require confirmation, but any later formal knowledge write must use `$context-atlas-add`, `$context-atlas-revise`, or `$context-atlas-retire` according to intent.

Route specification clarity, coverage, or readiness assessment to `$context-atlas-review`; navigation itself does not judge or change readiness.
