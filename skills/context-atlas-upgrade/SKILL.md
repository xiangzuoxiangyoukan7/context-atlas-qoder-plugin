---
name: context-atlas-upgrade
description: Upgrade one existing Context Atlas knowledge base to a supported representation and format. Use for compatibility migration only; never add, revise, retire, approve, or reinterpret project knowledge.
---

# Context Atlas Upgrade

Upgrade only the knowledge representation format and physical structure of an existing Context Atlas knowledge base. Never create, revise, approve, supersede, or archive business facts as part of this workflow.

Read `../../references/兼容与迁移.md`, `../../references/执行状态机.md`, `../../references/验证与结果报告.md`, and `../../references/宿主执行与运行时探测.md` before applying an upgrade. Read the target knowledge base's root `README.md`, `knowledge-base.yaml`, and `.project-kb/compatibility.json` when available.

Follow `upgrade-diagnose -> upgrade-propose -> await_confirmation -> upgrade-apply -> validate -> report`:

1. Run `upgrade-diagnose` without writing. Distinguish the installed plugin version, `format_version`, and business `project_version`.
2. If status is `compatible`, report that no upgrade is required and make zero writes.
3. If status is `conversion_available`, run `upgrade-propose` and show the source and target formats, every changed, moved, or removed path, unresolved items, and `proposal_revision`.
4. If status is `unsupported`, or any proposal item cannot be converted equivalently, stop without formal writes and report what requires human resolution.
5. Apply only after the user explicitly confirms the exact current `proposal_revision`. Recompute the proposal immediately before apply; reject stale confirmation.
6. Run the complete deterministic knowledge-base validator after apply. Report the resulting `format_version`, exact changed paths, validation result, and remaining unresolved items.

Installing or updating the Context Atlas plugin never upgrades a project knowledge base automatically. Upgrade may change only representation, layout, internal metadata, and `format_version`; preserve business meaning, approval state, source traceability, history, and `project_version`.

Use the structured executor under `../../assets/scripts/`. Prefer the canonical commands `upgrade-diagnose`, `upgrade-propose`, and `upgrade-apply`; legacy migration command names are compatibility aliases only. Do not ask the user to construct low-level file or content parameters.

Before apply, follow the runtime detection contract. Use the bundled Python executor when Python 3 is available. If deterministic execution or validation is unavailable, stop with zero formal writes; format upgrade must not use a best-effort host fallback.
