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

Resolve the current installed Skill root first, then use only its `../../assets/scripts/agent_kb_operation.py` executor together with its `../../assets/compatibility.json` as the upgrade-version authority. Pass that compatibility path explicitly to `upgrade-diagnose`, `upgrade-propose`, and `upgrade-apply`. Never use the target knowledge base's `.project-kb/scripts/agent_kb_operation.py` or `.project-kb/compatibility.json` to decide whether a newer installed plugin offers a conversion: those files describe the target's embedded format generation and can only prove compatibility with themselves. The command report must identify the current installed `runtime_assets_root` and `compatibility_path`; if either points inside the target knowledge base, reject the result and rerun with the installed assets.

Prefer the canonical commands `upgrade-diagnose`, `upgrade-propose`, and `upgrade-apply`; legacy migration command names are compatibility aliases only. Do not ask the user to construct low-level file or content parameters.

Before apply, follow the runtime detection contract. Use the bundled Python executor when Python 3 is available. If deterministic execution or validation is unavailable, stop with zero formal writes; format upgrade must not use a best-effort host fallback.
