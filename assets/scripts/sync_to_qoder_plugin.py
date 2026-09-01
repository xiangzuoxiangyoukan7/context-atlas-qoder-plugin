"""将唯一源码白名单同步到独立的 Context Atlas Qoder 发布仓库。"""

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
MANAGED = (Path(".qoder-plugin"), Path("skills"), Path("assets"), Path("references"), Path("README.md"), Path("LICENSE"), Path("marketplace.json"), Path("release-manifest.json"))
ALLOWED = {".git", ".qoder-plugin", "skills", "assets", "references", "README.md", "LICENSE", "marketplace.json", "release-manifest.json", ".idea"}


def _remove(path: Path, root: Path) -> None:
    """只移除发布仓库内的受管路径。"""

    path.resolve().relative_to(root)
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def sync(destination: Path) -> list[str]:
    """同步 Qoder 插件发布边界并返回文件列表。"""

    destination = destination.resolve()
    if destination == ROOT or not (destination / ".git").is_dir():
        raise ValueError("destination 必须是独立 Git 仓库根目录")
    for relative in MANAGED:
        _remove(destination / relative, destination)
    shutil.copytree(ROOT / ".qoder-plugin", destination / ".qoder-plugin")
    shutil.copytree(ROOT / "skills", destination / "skills")
    materialize_plugin_assets(ROOT, destination / "assets")
    shutil.copytree(ROOT / "references", destination / "references")
    shutil.copy2(ROOT / "packaging/qoder/README.md", destination / "README.md")
    if (ROOT / "LICENSE").is_file():
        shutil.copy2(ROOT / "LICENSE", destination / "LICENSE")
    marketplace = json.loads((destination / ".qoder-plugin/marketplace.json").read_text(encoding="utf-8"))
    (destination / "marketplace.json").write_text(json.dumps(marketplace, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    manifest = json.loads((destination / ".qoder-plugin/plugin.json").read_text(encoding="utf-8"))
    files = {
        path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(destination.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(destination).parts and path.name != "release-manifest.json"
    }
    (destination / "release-manifest.json").write_text(
        json.dumps({"plugin": "context-atlas", "platform": "qoder", "version": manifest["version"], "files": files}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    unexpected = sorted(path.name for path in destination.iterdir() if path.name not in ALLOWED)
    if unexpected:
        raise ValueError(f"Qoder 发布仓库包含非白名单根路径：{unexpected}")
    return [path.relative_to(destination).as_posix() for path in sorted(destination.rglob("*")) if path.is_file() and ".git" not in path.relative_to(destination).parts]


def main(argv: Sequence[str] | None = None) -> int:
    """解析目标仓库并输出同步报告。"""

    parser = argparse.ArgumentParser(description="同步 Context Atlas Qoder 发布仓库")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(json.dumps({"ok": True, "files": sync(args.destination)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
