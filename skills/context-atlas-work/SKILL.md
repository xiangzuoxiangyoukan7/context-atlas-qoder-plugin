---
name: context-atlas-work
description: Orchestrate Context Atlas for concrete project work such as implementing or changing features, fixing bugs, refactoring, and modifying interfaces or databases. Use when a user describes a development goal and should not need to choose individual knowledge-governance Skills. Do not use for unrelated general questions or when the user explicitly opts out of Context Atlas guidance.
---

# Context Atlas Work

Turn a natural-language project task into the smallest useful Context Atlas workflow while preserving the user's authority to start development. This is the user-facing orchestration entry; `navigate`, `review`, `ingest`, `add`, `revise`, `retire`, `init`, and `upgrade` remain specialized operators.

Read `../../references/执行状态机.md`, `../../references/知识采集与确认.md`, `../../references/规格审查与SDD适配.md`, and `../../references/验证与结果报告.md`. Read other references only when the selected route needs them.

## Intake and routing

1. Preserve the user's concrete delivery goal. Do not turn the task into knowledge administration or require the user to name another Skill.
2. Detect the project root and its single `doc-*` knowledge base. If no knowledge base exists, explain that initialization is available; do not initialize implicitly. If the format is unsupported, route to upgrade and keep zero formal writes.
3. Start read-only. Use the bundled executor to discover the smallest relevant knowledge area, then query direct neighbors or a bounded graph only when needed. Read the located requirements, features, modules, interfaces, databases, ADRs, changes, and acceptance contracts that materially constrain the task.
4. Classify the request as one or more of: new capability, change to existing behavior, defect investigation, refactor, retirement, or implementation-completion reconciliation. This classification selects knowledge operations; it never decides whether development may execute.
5. Review readiness. Ask only questions whose answers materially change scope, public behavior, failure behavior, compatibility, security, data, operations, or acceptance. Present concrete choices when the repository cannot answer them.

## Development path choice

After the useful read-only findings, offer these paths when durable knowledge would change:

- **Establish the knowledge baseline, then develop (recommended):** prepare one atomic Proposal containing every required add, revise, or retire operation.
- **Proceed without formal knowledge updates:** continue the user's development task using the read-only findings; make zero formal knowledge writes and offer reconciliation after implementation.

Do not ask for this choice when the task is purely read-only or no durable knowledge changes are needed. Do not block an explicitly authorized development task merely because the user postpones knowledge maintenance.

## Baseline path

Route new stable identities to add, changes that preserve an existing identity to revise, and withdrawal of current authority to retire. Combine dependent operations into one Proposal. Display every target, fact, source, inference, unknown, conflict, relation, impact, validation step, and immutable `proposal_revision`.

The initial task request is not confirmation. Apply formal knowledge changes only after the user explicitly confirms the exact current revision. Recompute the Proposal immediately before apply, reject stale confirmation, use the deterministic executor, validate the complete knowledge base, and report knowledge validation separately from implementation validation and business confirmation.

After a validated development baseline, continue the originally authorized implementation when the host supports it. Context Atlas provides constraints and evidence; it does not grant new permission for external writes, deployment, or other side effects.

## Defects and implementation completion

For defect investigation, keep logs, transient symptoms, and hypotheses in task context. Propose formal maintenance only for verified, reusable conclusions with durable value.

After implementation, compare actual modules, interfaces, data structures, dependencies, tests, and runtime evidence with the baseline. If they differ, prepare a new Proposal rather than silently rewriting knowledge. Record acceptance as passed only with locatable evidence for the corresponding version and keep business confirmation distinct.

## Response contract

Keep the conversation task-oriented. Report:

- the delivery goal and located knowledge;
- material gaps or conflicts requiring a decision;
- affected modules, interfaces, databases, dependencies, and acceptance items;
- the selected development path and knowledge-write state;
- the next concrete development action.

Never expose secrets, treat archived knowledge as current authority, invent missing product decisions, or present a validator result as proof that the implementation or business outcome is correct.
