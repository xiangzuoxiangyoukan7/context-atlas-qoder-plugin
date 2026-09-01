"""从源码构建平台专属 Context Atlas 插件；用于本地验收和正式发布场景。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

try:
    from .project_kb.plugin_contract import validate_plugin_contract
    from .project_kb.plugin_assets import materialize_plugin_assets
except ImportError:  # 兼容直接执行 scripts/build_plugin.py
    from project_kb.plugin_contract import validate_plugin_contract
    from project_kb.plugin_assets import materialize_plugin_assets


ROOT = Path(__file__).resolve().parents[1]
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _copy_tree(source: Path, target: Path) -> None:
    """复制目录树，并拒绝发布源根目录使用符号链接。"""

    if source.is_symlink():
        raise ValueError(f"发布源不得包含符号链接：{source}")
    shutil.copytree(source, target, dirs_exist_ok=True, symlinks=False)


def _copy_common(target: Path, platform: str) -> None:
    """复制指定平台共享的最小运行时文件。"""

    if platform == "trae":
        runtime_root = target / ".agents"
        runtime_root.mkdir(parents=True, exist_ok=True)
        _copy_tree(ROOT / "skills", runtime_root / "skills")
        materialize_plugin_assets(ROOT, runtime_root / "assets")
        _copy_tree(ROOT / "references", runtime_root / "references")
    else:
        manifest_dir = {
            "codex": ".codex-plugin",
            "claude": ".claude-plugin",
            "qoder": ".qoder-plugin",
        }[platform]
        (target / manifest_dir).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / manifest_dir / "plugin.json", target / manifest_dir / "plugin.json")
        if platform == "qoder":
            shutil.copy2(
                ROOT / ".qoder-plugin" / "marketplace.json",
                target / "marketplace.json",
            )
        _copy_tree(ROOT / "skills", target / "skills")
        materialize_plugin_assets(ROOT, target / "assets")
        _copy_tree(ROOT / "references", target / "references")
    if platform == "claude":
        shutil.copy2(
            ROOT / ".claude-plugin" / "marketplace.json",
            target / ".claude-plugin" / "marketplace.json",
        )
    for name in ("README.md", "LICENSE"):
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, target / name)
    platform_readme = ROOT / "packaging" / platform / "README.md"
    if platform_readme.is_file():
        shutil.copy2(platform_readme, target / "PLATFORM-README.md")
    if platform == "trae":
        shutil.copy2(ROOT / "packaging" / "trae" / "install.ps1", target / "install.ps1")


def build(output: Path, platform: str, archive: bool = False) -> Path:
    """构建干净的平台发布物。

    输入平台、输出路径和归档开关；先验证插件契约并清理指定产物，再复制白名单内容，
    需要归档时按稳定顺序生成 ZIP 和摘要，最后返回实际产物路径。
    """

    if platform not in {"codex", "claude", "qoder", "trae"}:
        raise ValueError("platform must be codex, claude, qoder or trae")
    contract_errors = validate_plugin_contract(ROOT)
    if contract_errors:
        raise ValueError("插件契约检查失败：\n- " + "\n- ".join(contract_errors))
    output = output.resolve()
    if output.exists():
        shutil.rmtree(output) if output.is_dir() else output.unlink()
    stage = output if not archive else output.with_suffix("")
    if stage.exists():
        shutil.rmtree(stage) if stage.is_dir() else stage.unlink()
    stage.mkdir(parents=True, exist_ok=True)
    _copy_common(stage, platform)
    if not archive:
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(path.relative_to(stage).as_posix(), ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, path.read_bytes())
    shutil.rmtree(stage, ignore_errors=True)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name(output.name + ".sha256").write_text(
        f"{digest}  {output.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return output


def main() -> int:
    """解析构建参数、生成产物并输出机器可读结果。"""

    parser = argparse.ArgumentParser(description="Build Context Atlas plugin payload")
    parser.add_argument("platform", choices=("codex", "claude", "qoder", "trae"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", action="store_true")
    args = parser.parse_args()
    result = build(args.output, args.platform, args.archive)
    print(json.dumps({"ok": True, "platform": args.platform, "output": str(result)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
