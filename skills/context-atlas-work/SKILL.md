---
name: context-atlas-work
description: Orchestrate Context Atlas for a concrete development goal or a change that requires more than one knowledge-maintenance operation. Use as the single user-facing coordinator for mixed add, revise, retire, and delete work; do not use for unrelated questions or when the user opts out.
---

# Context Atlas Work

Turn a natural-language project task into the smallest useful Context Atlas workflow while preserving the user's authority to start development. This is the user-facing orchestration entry and the only owner of a Proposal that mixes add, revise, retire, and delete operations. The specialized Skills remain direct entry points for one operation kind.

An explicit `$context-atlas-work` invocation, or the user's explicit selection of the baseline path after this Skill is automatically chosen, authorizes it to coordinate delegated maintenance; the user does not need to invoke each maintenance Skill again. Neither automatic discovery nor the initial task description is confirmation. Apply only after the user separately confirms the exact Proposal revision.

Read `../../references/执行状态机.md`, `../../references/知识采集与确认.md`, `../../references/规格审查与SDD适配.md`, and `../../references/验证与结果报告.md`. Read other references only when the selected route needs them.

## Intake and routing

1. Preserve the user's concrete delivery goal. Do not turn the task into knowledge administration or require the user to name another Skill.
2. Detect the project root and exactly one current `doc-*` knowledge base. If none exists, explain that initialization is available; do not initialize implicitly. If more than one candidate exists, stop and ask the user to identify the current authority. If the format is unsupported, route to upgrade and keep zero formal writes.
3. Start read-only. Use the bundled executor to discover the smallest relevant knowledge area, then query direct neighbors or a bounded graph only when needed. Read the located requirements, features and their embedded decisions and acceptance scenarios, modules, concrete interfaces, databases, changes, legacy ADRs or acceptance contracts, and evidence that materially constrain the task.
4. Classify the request as one or more of: new capability, change to existing behavior, defect investigation, refactor, retirement, or implementation-completion reconciliation. This classification selects knowledge operations; it never decides whether development may execute.
5. Review readiness. When the user has supplied a usage scenario and the repository contains enough constraints, synthesize the smallest usable recommended solution before asking questions. Mark derived details as `ai_inference` and `proposed`, cite the constraints behind them, and never treat the prohibition on inventing approved facts as a reason to return only missing fields. Ask only questions whose answers materially change scope, public behavior, failure behavior, compatibility, security, data precision or capacity, operations, lifecycle, or acceptance. When the repository cannot determine one safe choice, present two or three concrete choices, their impacts, and a recommended option.

## Development path choice

After the useful read-only findings, offer these paths when durable knowledge would change:

- **Establish the knowledge baseline, then develop (recommended):** prepare one atomic Proposal containing every required add, revise, retire, or delete operation.
- **Proceed without formal knowledge updates:** continue the user's development task using the read-only findings; make zero formal knowledge writes and offer reconciliation after implementation.

Do not ask for this choice when the task is purely read-only or no durable knowledge changes are needed. Do not block an explicitly authorized development task merely because the user postpones knowledge maintenance.

## Baseline path

Route new stable identities to add, changes to an existing identity or replacement by a successor to revise, withdrawal without creating a successor to retire, and permanent removal of knowledge confirmed to have no audit value to delete. Combine dependent operations into one Proposal owned by this Skill. Display every target, fact, source, inference, unknown, conflict, relation, impact, validation step, and immutable `proposal_revision`.

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

For an incomplete design request, include the recommended candidate solution, its evidence and inference boundary, alternatives with impacts when needed, and only the material decisions that still require the user. For example, a table-creation scenario with known usage must receive proposed columns, SQL data types, nullability, defaults, value domains, indexes, and relations where relevant; do not merely report that a type is missing.

Never expose secrets, treat archived knowledge as current authority, invent missing product decisions, or present a validator result as proof that the implementation or business outcome is correct.
