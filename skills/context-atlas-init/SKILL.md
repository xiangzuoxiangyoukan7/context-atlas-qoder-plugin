---
name: context-atlas-init
description: Initialize a new self-contained Context Atlas project knowledge base. Use when the user explicitly invokes context-atlas-init for a project that does not yet contain its doc-* knowledge-base directory.
---

# Context Atlas Init

<!-- context-atlas-rules: [[rules/知识治理规则#RULE-AGENT-001|RULE-AGENT-001]] [[rules/知识治理规则#RULE-IMPACT-001|RULE-IMPACT-001]] [[rules/知识治理规则#RULE-IMPACT-002|RULE-IMPACT-002]] [[rules/知识治理规则#RULE-REL-002|RULE-REL-002]] -->

Initialize a new project knowledge base. Formal writes require explicit invocation of this Skill; natural-language requests may inspect and propose but must not initialize.

Read `../../references/执行状态机.md`, `../../references/初始化协议.md`, `../../references/知识采集与确认.md`, and `../../references/宿主执行与运行时探测.md` before writing.

Follow `inspect -> propose -> await_confirmation -> apply -> validate -> report`. Obtain the user's 显式确认 for the exact Proposal revision before applying it. Derive the default target as `doc-<项目目录名>`. If the 目标已存在, stop and direct the user to `$context-atlas-add`, `$context-atlas-revise`, or `$context-atlas-retire` according to intent; never overwrite or reinitialize it.

Inspect the project root README and existing product documents, dependency/build manifests, source modules, API or message entry points, database models and migrations, tests, CI/release configuration, and existing ADRs. Route observations into the Proposal groups `goals`, `boundaries_in`, `boundaries_out`, `technology_stacks`, `terms`, `capabilities`, `features`, `modules`, `interfaces`, `databases`, `external_dependencies`, `tests`, and `adrs`. An existing-code project must include every supported observation that can be precisely sourced; an empty project must use empty arrays and must not invent placeholder facts.

Before building an initialization Proposal, ensure the user has selected a workspace profile. If the invocation does not already make the choice explicit, pause the initialization workflow and proactively offer exactly these two user-facing choices: `standard` (plain Markdown knowledge base, no `.obsidian/`) and `obsidian` (minimal local settings and predefined graph color groups). Do not silently choose `standard`, infer a preference from installed software or repository files, or generate the Proposal until the user selects one. This profile selection is separate from confirmation of the later Proposal.

Build an initialization Proposal that conforms to `../../assets/schemas/initialization-proposal.schema.json`. Always include the selected `project.workspace_profile` as `standard` or `obsidian`; the executor's omitted-value `standard` behavior is compatibility-only and must not be used by the interactive Skill. Obsidian mode creates minimal local presentation settings and predefined graph color groups, while standard mode creates no `.obsidian/` directory. Compute `proposal_revision` from canonical JSON excluding that field, display the same revision with the human-readable Proposal, and require confirmation of that exact revision. Do not ask the user to write JSON or provide low-level file parameters. Repository observations prove implementation facts only: keep product meaning, design reasons, approval, and anything not discoverable as `proposed` or in `unknowns`.

Display every target, fact, source, status, inference, unknown, conflict, relation, impact, and validation step that contributes to the revision. Pagination is allowed; a count-only summary or an Agent-local temporary JSON path is not a reviewable Proposal. Preserve unknowns and conflicts when the user postpones them, marking the owner action as deferred for this round; do not empty them unless the user explicitly resolves each item. Keep repository sources `observed` and never invent `confirmed_at` before an actual source confirmation.

Before reading configuration files, detect likely secret-bearing names and fields. Inspect only keys, redacted summaries, or explicitly safe fields; never print or load a complete credential-bearing configuration into the conversation.

Use `../../assets/templates/core/doc-project/` as the only template source. During inspect, identify the current host (`codex`, `claude`, `qoder`, or `trae`) and include `agent_entry` in the Proposal when it is known: Codex/Qoder/Trae map to `AGENTS.md`, Claude Code maps to `CLAUDE.md`. After approval, follow the runtime detection contract. When Python 3 is available, pass the Proposal through standard input to `../../assets/scripts/agent_kb_operation.py initialize --proposal - --confirmed-revision <revision>`. The executor must initialize both the structure and the corresponding document contents; copying an empty skeleton for an existing-code Proposal is failure. When Python 3 is unavailable but the Agent host passes the required capability preflight, use the isolated staging, scope checks, host validation, and atomic rename procedure in `../../references/宿主执行与运行时探测.md`; never write directly to the final target. Treat only a report conforming to `../../assets/schemas/initialization-report.schema.json` with `operation: initialized` and `validation.result: passed` as success.

Before apply, resolve and verify Python 3 exactly as defined by the runtime detection contract. A failing Windows Store `python` alias (including exit code 9009) does not prove Python is unavailable until all platform candidates have been checked. If no Python 3 interpreter works, select `agent_host` only when its capability preflight passes; otherwise stop with zero formal writes and report every checked capability and interpreter command.

Copy the bundled schemas and validation scripts into the target `.project-kb/` bundle, validate the result, and report exact paths and unresolved items.

After initialization, invoke the copied `.project-kb/scripts/agent_kb_operation.py` directly for `children`, `neighbors`, and a bounded `graph`. Treat these as required usability smoke checks and distinguish them from structural validation in the report.

Keep repository evidence, AI inference, user approval, stored knowledge, and validator results distinct. Never store secrets or unredacted personal data. For a confirmed `agent_entry`, preserve existing project instructions and maintain only the marked Context Atlas block; do not create a file when the host is unknown.
