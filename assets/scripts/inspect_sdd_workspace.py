"""输出外部 SDD 工作区到 Context Atlas 的只读映射。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.project_kb.sdd_adapters import inspect_sdd_workspace


def main(argv: Sequence[str] | None = None) -> int:
    """解析来源类型和路径，运行只读检查并输出 JSON。"""

    parser = argparse.ArgumentParser(description="Inspect an external SDD workspace without writing")
    parser.add_argument("source_system", choices=("openspec", "spec-kit"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    inspection = inspect_sdd_workspace(args.root, args.source_system)
    print(json.dumps(inspection.to_dict(), ensure_ascii=False, indent=2))
    return 0 if not inspection.warnings else 1


if __name__ == "__main__":
    raise SystemExit(main())
