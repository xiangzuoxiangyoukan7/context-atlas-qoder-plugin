"""提供项目知识库确定性检查的命令行入口。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.project_kb.frontmatter import FrontMatterError as MetadataError
from scripts.project_kb.frontmatter import parse_document
from scripts.project_kb.model import Issue
from scripts.project_kb.reporting import render_json, render_text
from scripts.project_kb.validator import ValidationConfig
from scripts.project_kb.validator import validate as validate_with_config


def parse_front_matter(path: Path) -> dict[str, object]:
    """兼容旧调用方并返回文档头部元数据。"""

    return parse_document(path).metadata


def default_schema_root() -> Path:
    """返回与检查脚本一起发布的默认 Schema 目录。"""

    return Path(__file__).resolve().parents[1] / "schemas"


def validate(root: Path) -> list[Issue]:
    """使用默认 Schema 验证指定知识库。"""

    return validate_with_config(root, ValidationConfig(schema_root=default_schema_root()))


def _parser() -> argparse.ArgumentParser:
    """创建知识库检查命令的参数解析器。"""

    parser = argparse.ArgumentParser(description="Validate a project knowledge base")
    parser.add_argument("root", type=Path)
    parser.add_argument("--schema-root", type=Path, default=default_schema_root())
    parser.add_argument(
        "--relation-catalog",
        type=Path,
        help="可选的关系目录路径；默认使用 Schema 目录中的 relation-catalog.json",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--level",
        choices=("all", "structure", "spec", "readiness"),
        default="all",
        help="选择全部、基础结构、规格或就绪度检查",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行检查并按成功、问题或配置错误返回退出码。"""

    parser = _parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
        issues = validate_with_config(
            args.root,
            ValidationConfig(
                schema_root=args.schema_root,
                relation_catalog_path=args.relation_catalog,
                level=args.level,
            ),
        )
    except (OSError, ValueError) as error:
        parser.exit(2, f"configuration error: {error}\n")
    print(render_json(issues) if args.format == "json" else render_text(issues))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
