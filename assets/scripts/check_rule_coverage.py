"""检查权威规则引用、执行覆盖与规则变化影响。"""

from __future__ import annotations

# context-atlas-rules: [[rules/知识治理规则#RULE-GOV-002|RULE-GOV-002]]

import argparse
from pathlib import Path
from typing import Sequence

from project_kb.rule_catalog import (
    build_reverse_index,
    build_rule_change_impact,
    validate_rule_coverage,
)


def main(argv: Sequence[str] | None = None) -> int:
    """运行规则覆盖检查并按需打印反向索引或变化影响。"""

    parser = argparse.ArgumentParser(description="检查 Context Atlas 规则覆盖")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--print-index", action="store_true")
    parser.add_argument("--changed-rule", action="append", default=[])
    args = parser.parse_args(list(argv) if argv is not None else None)

    issues = validate_rule_coverage(args.root)
    for issue in issues:
        print(f"{issue.code}: {issue.path}: {issue.message}")
    if args.print_index:
        for rule_id, consumers in build_reverse_index(args.root).items():
            print(f"{rule_id}:")
            for consumer in consumers:
                print(f"  - {consumer.kind}: {consumer.path.relative_to(args.root.resolve())}")
    if args.changed_rule:
        for impact in build_rule_change_impact(args.root, set(args.changed_rule)):
            relative = impact.consumer.path.relative_to(args.root.resolve())
            print(f"impact: {impact.rule_id}: {impact.action}: {impact.consumer.kind}: {relative}")
    if issues:
        return 1
    print("Rule coverage validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
