"""检查仓库 Python 代码的说明文档与类型标注。"""

from __future__ import annotations

# context-atlas-rules: [[rules/知识治理规则#RULE-CODE-001|RULE-CODE-001]] [[rules/知识治理规则#RULE-CODE-002|RULE-CODE-002]]

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Sequence


EXCLUDED_PARTS = frozenset(
    {".git", ".worktrees", "assets", "examples", "build", "__pycache__", ".test-probe", ".test-run", ".test-tmp"}
)
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
LOGIC_WORDS = (
    "流程", "逻辑", "先", "再", "根据", "逐", "依次", "校验", "验证", "构造",
    "扫描", "解析", "应用", "运行", "检查", "输出", "返回",
)


@dataclass(frozen=True)
class PythonDocumentationIssue:
    """表示一个可定位的 Python 说明或类型标注问题。"""

    code: str
    path: Path
    line: int
    message: str


def _python_files(root: Path) -> list[Path]:
    """返回根目录下需要检查的全部 Python 文件。"""

    return sorted(
        path
        for path in root.rglob("*.py")
        if path.is_file() and not EXCLUDED_PARTS.intersection(path.relative_to(root).parts)
    )


def _function_arguments(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterable[ast.arg]:
    """按声明顺序返回函数的普通参数、可变参数和关键字参数。"""

    yield from node.args.posonlyargs
    yield from node.args.args
    if node.args.vararg is not None:
        yield node.args.vararg
    yield from node.args.kwonlyargs
    if node.args.kwarg is not None:
        yield node.args.kwarg


def _check_function(
    path: Path,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[PythonDocumentationIssue]:
    """检查单个函数或方法的说明、参数类型与返回类型。"""

    issues: list[PythonDocumentationIssue] = []
    docstring = ast.get_docstring(node)
    if docstring is None:
        issues.append(PythonDocumentationIssue("PY_DOC_FUNCTION", path, node.lineno, node.name))
    elif not CHINESE_RE.search(docstring) or len(docstring.strip()) < 4:
        issues.append(PythonDocumentationIssue("PY_DOC_FUNCTION_DETAIL", path, node.lineno, node.name))
    branch_count = sum(
        isinstance(child, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Match))
        for child in ast.walk(node)
    )
    line_count = (node.end_lineno or node.lineno) - node.lineno + 1
    important_name = node.name == "main" or node.name.startswith(
        ("execute_", "initialize_", "apply_", "validate_", "build", "sync")
    )
    if docstring is not None and important_name and (branch_count >= 2 or line_count >= 20) and not any(
        word in docstring for word in LOGIC_WORDS
    ):
        issues.append(PythonDocumentationIssue("PY_DOC_IMPORTANT_LOGIC", path, node.lineno, node.name))
    for argument in _function_arguments(node):
        if argument.arg not in {"self", "cls"} and argument.annotation is None:
            issues.append(
                PythonDocumentationIssue(
                    "PY_TYPE_ARGUMENT",
                    path,
                    argument.lineno,
                    f"{node.name}.{argument.arg}",
                )
            )
    if node.returns is None:
        issues.append(PythonDocumentationIssue("PY_TYPE_RETURN", path, node.lineno, node.name))
    return issues


def _check_class(path: Path, node: ast.ClassDef) -> list[PythonDocumentationIssue]:
    """检查类说明以及类级属性的显式类型标注。"""

    issues: list[PythonDocumentationIssue] = []
    docstring = ast.get_docstring(node)
    if docstring is None:
        issues.append(PythonDocumentationIssue("PY_DOC_CLASS", path, node.lineno, node.name))
    elif not CHINESE_RE.search(docstring) or len(docstring.strip()) < 4:
        issues.append(PythonDocumentationIssue("PY_DOC_CLASS_DETAIL", path, node.lineno, node.name))
    for statement in node.body:
        if not isinstance(statement, ast.Assign):
            continue
        for target in statement.targets:
            if isinstance(target, ast.Name) and not target.id.startswith("__"):
                issues.append(
                    PythonDocumentationIssue(
                        "PY_TYPE_CLASS_ATTRIBUTE",
                        path,
                        target.lineno,
                        f"{node.name}.{target.id}",
                    )
                )
    return issues


def _check_file(path: Path) -> list[PythonDocumentationIssue]:
    """解析并检查一个 UTF-8 Python 文件。"""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError) as error:
        return [PythonDocumentationIssue("PY_PARSE", path, 1, str(error))]

    issues: list[PythonDocumentationIssue] = []
    module_docstring = ast.get_docstring(tree)
    if module_docstring is None:
        issues.append(PythonDocumentationIssue("PY_DOC_MODULE", path, 1, "模块缺少说明"))
    elif not CHINESE_RE.search(module_docstring) or len(module_docstring.strip()) < 4:
        issues.append(
            PythonDocumentationIssue(
                "PY_DOC_MODULE_DETAIL", path, 1, "模块说明必须用中文解释用途和适用场景"
            )
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            issues.extend(_check_class(path, node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            issues.extend(_check_function(path, node))
    return issues


def validate_python_documentation(
    root: Path,
    files: Sequence[Path] | None = None,
) -> list[PythonDocumentationIssue]:
    """验证指定文件或根目录下全部 Python 文件的代码说明规范。"""

    resolved_root = root.resolve()
    candidates = list(files) if files is not None else _python_files(resolved_root)
    issues: list[PythonDocumentationIssue] = []
    for path in candidates:
        issues.extend(_check_file(path.resolve()))
    return sorted(issues, key=lambda issue: (str(issue.path), issue.line, issue.code))


def _parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器。"""

    parser = argparse.ArgumentParser(description="检查 Python 注释与类型标注")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """运行仓库检查并返回适合持续集成使用的退出码。"""

    args = _parser().parse_args(list(argv) if argv is not None else None)
    issues = validate_python_documentation(args.root)
    for issue in issues:
        print(f"{issue.code}: {issue.path}:{issue.line}: {issue.message}")
    if issues:
        return 1
    print("Python documentation validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
