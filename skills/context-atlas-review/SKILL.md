---
name: context-atlas-review
description: Assess existing Context Atlas specifications, readiness, or knowledge health without changing them. Use for quality judgments after relevant knowledge has been located; use navigate instead for discovery-only questions.
---

# Context Atlas Review

Review project specifications without changing formal knowledge. Read `../../references/规格审查与SDD适配.md`, `../../references/关系与影响分析.md`, and `../../references/验证与结果报告.md`. Read the target knowledge-base `README.md`, `knowledge-base.yaml`, collaboration rules, and only directly relevant knowledge.

Resolve the project root and exactly one current `doc-*` knowledge base first. If none exists, route to `$context-atlas-init`; if multiple candidates exist, ask the user to identify the current authority; if its format is unsupported, route to `$context-atlas-upgrade`. Keep zero writes.

Select one or more modes: `requirement`, `feature`, `design`, `change`, `implementation_readiness`, `acceptance_readiness`, or `knowledge_health`. Separate confirmed facts, repository observations, external artifacts, unresolved questions, and AI inferences. Do not fill gaps with plausible behavior.

When deterministic assets are available, run the checker with `--level spec` or `--level readiness`. For OpenSpec or Spec Kit sources, use the bundled read-only SDD inspector and retain source paths and versions. External approval, task completion, archive, branch, or test state never becomes Context Atlas approval.

For `knowledge_health`, run the packaged `agent_kb_operation.py health <knowledge-base-root>` operation. Report duplicate identities, orphan items, dangling relations, stale items, unresolved conflicts, unverified sources, and authority gaps. Time-based findings are warnings, not automatic errors. Never use `.context-atlas/ingest-history/` as formal knowledge or repair findings automatically.

Return reviewed IDs and paths, mode, deterministic issues, human-review findings, blocking questions, traceability gaps, and the next smallest action. Use `clear | findings | blocked` for requirement, feature, design, and change review; `ready | blocked` for implementation or acceptance readiness; and `healthy | findings | blocked` for knowledge health. Never create, edit, archive, approve, or migrate knowledge. To preserve findings, route a single maintenance kind to `$context-atlas-add`, `$context-atlas-revise`, or `$context-atlas-retire`; route mixed maintenance to `$context-atlas-work`. Every formal write remains behind exact Proposal confirmation.
