"""将唯一源码白名单同步到独立的 Context Atlas Codex 发布仓库。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from typing import Sequence

try:
    from .project_kb.plugin_assets import materialize_plugin_assets
except ImportError:  # 兼容直接执行 scripts/sync_to_codex_plugin.py
    from project_kb.plugin_assets import materialize_plugin_assets


ROOT = Path(__file__).resolve().parents[1]
LOCAL_IGNORED_ROOTS = frozenset({".idea"})
MANAGED_PATHS = (
    Path(".agents"),
    Path(".codex-plugin"),
    Path("skills"),
    Path("assets"),
    Path("references"),
    Path("README.md"),
    Path("LICENSE"),
    Path("release-manifest.json"),
)
FORBIDDEN_ROOTS = frozenset(
    {
        ".claude-plugin",
        ".codex",
        ".superpowers",
        "doc-atlas",
        "docs",
        "examples",
        "operations",
        "rules",
        "schemas",
        "scripts",
        "templates",
        "tests",
        "AGENTS.md",
        "CLAUDE.md",
    }
)
ALLOWED_ROOTS = frozenset(
    {".git", ".gitignore", ".agents", ".codex-plugin", "skills", "assets", "references", "README.md", "LICENSE", "release-manifest.json"}
)


def _remove_managed(path: Path, destination: Path) -> None:
    """只删除已验证发布仓库中的受管路径。"""

    resolved = path.resolve()
    resolved.relative_to(destination)
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _copy_tree(source: Path, target: Path) -> None:
    """复制不包含符号链接的发布目录树。"""

    linked = [path for path in source.rglob("*") if path.is_symlink()]
    if source.is_symlink() or linked:
        raise ValueError(f"发布源不得包含符号链接：{linked[0] if linked else source}")
    shutil.copytree(source, target)


def _marketplace() -> dict[str, object]:
    """返回生产 Codex Marketplace 清单。"""

    return {
        "name": "context-atlas",
        "interface": {"displayName": "Context Atlas"},
        "plugins": [
            {
                "name": "context-atlas",
                "source": {"source": "url", "url": "./"},
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
        ],
    }


def _file_hash(path: Path) -> str:
    """计算单个发布文件的 SHA-256。"""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_release_manifest(destination: Path, version: str) -> None:
    """写入确定性的发布版本与文件摘要清单。"""

    files = {
        path.relative_to(destination).as_posix(): _file_hash(path)
        for path in sorted(destination.rglob("*"))
        if path.is_file()
        and ".git" not in path.relative_to(destination).parts
        and not (LOCAL_IGNORED_ROOTS & set(path.relative_to(destination).parts))
        and path.name != "release-manifest.json"
    }
    payload = {"plugin": "context-atlas", "version": version, "files": files}
    (destination / "release-manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sync(destination: Path) -> list[str]:
    """同步发布白名单，验证发布边界并返回相对文件列表。"""

    destination = destination.resolve()
    if destination == ROOT or not (destination / ".git").is_dir():
        raise ValueError("destination 必须是独立 Git 仓库根目录")
    if destination.is_symlink():
        raise ValueError("destination 不得是符号链接")

    for relative in MANAGED_PATHS:
        _remove_managed(destination / relative, destination)

    (destination / ".codex-plugin").mkdir(parents=True)
    shutil.copy2(
        ROOT / ".codex-plugin" / "plugin.json",
        destination / ".codex-plugin" / "plugin.json",
    )
    _copy_tree(ROOT / "skills", destination / "skills")
    materialize_plugin_assets(ROOT, destination / "assets")
    _copy_tree(ROOT / "references", destination / "references")
    (destination / ".agents" / "plugins").mkdir(parents=True)
    (destination / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps(_marketplace(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    shutil.copy2(ROOT / "packaging" / "codex" / "README.md", destination / "README.md")
    if (ROOT / "LICENSE").is_file():
        shutil.copy2(ROOT / "LICENSE", destination / "LICENSE")

    manifest = json.loads(
        (destination / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    _write_release_manifest(destination, str(manifest["version"]))

    forbidden = sorted(name for name in FORBIDDEN_ROOTS if (destination / name).exists())
    if forbidden:
        raise ValueError(f"发布仓库包含禁止路径：{forbidden}")
    unexpected = sorted(
        path.name
        for path in destination.iterdir()
        if path.name not in ALLOWED_ROOTS and path.name not in LOCAL_IGNORED_ROOTS
    )
    if unexpected:
        raise ValueError(f"发布仓库包含非白名单根路径：{unexpected}")
    expected_skills = {
        destination / "skills" / "context-atlas-work" / "SKILL.md",
        destination / "skills" / "context-atlas-init" / "SKILL.md",
        destination / "skills" / "context-atlas-navigate" / "SKILL.md",
        destination / "skills" / "context-atlas-review" / "SKILL.md",
        destination / "skills" / "context-atlas-ingest" / "SKILL.md",
        destination / "skills" / "context-atlas-add" / "SKILL.md",
        destination / "skills" / "context-atlas-revise" / "SKILL.md",
        destination / "skills" / "context-atlas-retire" / "SKILL.md",
        destination / "skills" / "context-atlas-upgrade" / "SKILL.md",
    }
    actual_skills = set(destination.rglob("SKILL.md"))
    if actual_skills != expected_skills:
        raise ValueError("Codex 发布仓库必须且只能包含 context-atlas-work、context-atlas-init、context-atlas-navigate、context-atlas-review、context-atlas-ingest、context-atlas-add、context-atlas-revise、context-atlas-retire 和 context-atlas-upgrade 九个 Skills")
    return [
        path.relative_to(destination).as_posix()
        for path in sorted(destination.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(destination).parts
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """解析目标仓库，执行同步并输出机器可读报告。"""

    parser = argparse.ArgumentParser(description="同步 Context Atlas Codex 发布仓库")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    files = sync(args.destination)
    print(json.dumps({"ok": True, "files": files}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
