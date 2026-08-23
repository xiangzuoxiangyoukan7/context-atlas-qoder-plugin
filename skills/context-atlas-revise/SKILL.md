---
name: context-atlas-revise
description: Revise, synchronize, or supersede existing formal business knowledge in a self-contained Context Atlas project knowledge base. Use only when the user explicitly invokes context-atlas-revise. Do not use it to add unrelated knowledge, retire authority, or upgrade the format.
---

# Context Atlas Revise

Revise existing formal knowledge without silently overwriting approved history. Formal writes require explicit invocation of this Skill; natural-language requests may inspect and propose but must not write.

Read `../../references/执行状态机.md`, `../../references/知识采集与确认.md`, `../../references/更新冲突与归档.md`, `../../references/关系与影响分析.md`, `../../references/验证与结果报告.md`, and `../../references/宿主执行与运行时探测.md`. Read the target root `README.md` and `knowledge-base.yaml` before proposing.

Follow `inspect -> propose -> await_confirmation -> apply -> validate -> report`. Diagnose compatibility first; use `$context-atlas-upgrade` for format conversion and `$context-atlas-init` when no knowledge base exists. Obtain 显式确认 of the exact Proposal revision before writing.

Choose `patch` only when stable identity and meaning remain the same. Choose `supersede` when authority or semantics change: create the successor, establish `supersedes` and `superseded_by`, migrate current references, then validate. Preserve competing evidence as `conflicted`; never pick a winner without the required resolver. Requests that only add unrelated identity belong to `$context-atlas-add`; removal of current authority belongs to `$context-atlas-retire`.

Apply a request spanning multiple maintenance kinds as one atomic Proposal through the shared executor under `../../assets/scripts/`. Follow runtime detection; use `agent_host` only under its isolated staging contract and otherwise keep zero formal writes. Report exact paths, confirmation, impact, validation, unknowns, and conflicts.
