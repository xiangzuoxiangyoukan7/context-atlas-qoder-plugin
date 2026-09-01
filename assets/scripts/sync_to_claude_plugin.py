"""将唯一源码白名单同步到独立的 Context Atlas Claude 发布仓库。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from typing import Sequence

try:
    from .project_kb.plugin_assets import materialize_plugin_assets
except ImportError:
    from project_kb.plugin_assets import materialize_plugin_assets


ROOT = Path(__file__).resolve().parents[1]
LOCAL_IGNORED_ROOTS = frozenset({".idea"})
MANAGED_PATHS = (
    Path(".claude-plugin"), Path("skills"), Path("assets"), Path("references"),
    Path("README.md"), Path("LICENSE"), Path("release-manifest.json"),
)
ALLOWED_ROOTS = frozenset({".git", ".claude-plugin", "skills", "assets", "references",
                           "README.md", "LICENSE", "release-manifest.json"})


def _remove_managed(path: Path, destination: Path) -> None:
    """只删除已验证发布仓库中的受管路径。"""

    path.resolve().relative_to(destination)
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _copy_tree(source: Path, target: Path) -> None:
    """复制目录并拒绝符号链接。"""

    linked = [path for path in source.rglob("*") if path.is_symlink()]
    if source.is_symlink() or linked:
        raise ValueError(f"发布源不得包含符号链接：{linked[0] if linked else source}")
    shutil.copytree(source, target)


def _marketplace(version: str) -> dict[str, object]:
    """生成生产 Claude Marketplace 清单。"""

    return {
        "name": "context-atlas",
        "description": "Context Atlas Claude Code Marketplace",
        "owner": {"name": "Context Atlas Maintainers"},
        "plugins": [{
            "name": "context-atlas",
            "description": "通过统一协议维护项目知识库",
            "version": version,
            "source": "./",
            "author": {"name": "Context Atlas Maintainers"},
        }],
    }


def _write_release_manifest(destination: Path, version: str) -> None:
    """写入确定性的版本与文件摘要清单。"""

    files = {
        path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(destination.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(destination).parts
        and not (LOCAL_IGNORED_ROOTS & set(path.relative_to(destination).parts))
        and path.name != "release-manifest.json"
    }
    (destination / "release-manifest.json").write_text(
        json.dumps({"plugin": "context-atlas", "platform": "claude", "version": version, "files": files},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def sync(destination: Path) -> list[str]:
    """同步 Claude 发布白名单并验证发布边界。"""

    destination = destination.resolve()
    if destination == ROOT or not (destination / ".git").is_dir():
        raise ValueError("destination 必须是独立 Git 仓库根目录")
    if destination.is_symlink():
        raise ValueError("destination 不得是符号链接")
    for relative in MANAGED_PATHS:
        _remove_managed(destination / relative, destination)

    (destination / ".claude-plugin").mkdir(parents=True)
    shutil.copy2(ROOT / ".claude-plugin" / "plugin.json", destination / ".claude-plugin" / "plugin.json")
    manifest = json.loads((destination / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    (destination / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(_marketplace(str(manifest["version"])), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n"
    )
    _copy_tree(ROOT / "skills", destination / "skills")
    materialize_plugin_assets(ROOT, destination / "assets")
    _copy_tree(ROOT / "references", destination / "references")
    shutil.copy2(ROOT / "packaging" / "claude" / "README.md", destination / "README.md")
    if (ROOT / "LICENSE").is_file():
        shutil.copy2(ROOT / "LICENSE", destination / "LICENSE")
    _write_release_manifest(destination, str(manifest["version"]))

    unexpected = sorted(path.name for path in destination.iterdir()
                        if path.name not in ALLOWED_ROOTS and path.name not in LOCAL_IGNORED_ROOTS)
    if unexpected:
        raise ValueError(f"发布仓库包含非白名单根路径：{unexpected}")
    expected = {destination / "skills" / name / "SKILL.md" for name in (
        "context-atlas-work", "context-atlas-init", "context-atlas-navigate", "context-atlas-review", "context-atlas-ingest",
        "context-atlas-add", "context-atlas-revise", "context-atlas-retire", "context-atlas-upgrade")}
    if set(destination.rglob("SKILL.md")) != expected:
        raise ValueError("Claude 发布仓库必须且只能包含九个 Context Atlas Skills")
    return [path.relative_to(destination).as_posix() for path in sorted(destination.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(destination).parts]


def main(argv: Sequence[str] | None = None) -> int:
    """解析发布目标并同步经过白名单约束的 Claude 插件文件。"""

    parser = argparse.ArgumentParser(description="同步 Context Atlas Claude 发布仓库")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(json.dumps({"ok": True, "files": sync(args.destination)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
