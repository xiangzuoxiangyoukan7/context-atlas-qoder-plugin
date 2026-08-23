"""从仓库唯一源码确定性物化插件运行资产。"""

from __future__ import annotations

import json
from pathlib import Path
import shutil


def _safe_child(root: Path, relative_text: str) -> Path:
    """解析清单路径并拒绝绝对路径、父级跳转和根目录逃逸。"""

    relative = Path(relative_text)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"不安全的资产路径：{relative_text}")
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError(f"资产路径越界：{relative_text}")
    return candidate


def load_asset_manifest(manifest_path: Path) -> tuple[str, ...]:
    """读取有序、唯一的发布资产清单。"""

    payload = json.loads(manifest_path.resolve().read_text(encoding="utf-8"))
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        raise ValueError("资产清单 files 必须是字符串数组")
    if files != sorted(set(files)):
        raise ValueError("资产清单 files 必须有序且唯一")
    return tuple(files)


def materialize_plugin_assets(source_root: Path, target_assets: Path) -> tuple[str, ...]:
    """从唯一源码生成完整 assets，并返回生成的相对文件列表。"""

    source_root = source_root.resolve()
    target_assets = target_assets.resolve()
    manifest_source = source_root / "assets" / "manifest.json"
    files = load_asset_manifest(manifest_source)
    if target_assets.exists():
        raise FileExistsError(f"资产目标已存在：{target_assets}")
    target_assets.mkdir(parents=True)
    shutil.copy2(manifest_source, target_assets / "manifest.json")
    generated: list[str] = []
    try:
        for relative_text in files:
            source = _safe_child(source_root, relative_text)
            if not source.is_file():
                raise FileNotFoundError(f"清单源码不存在：{relative_text}")
            target = _safe_child(target_assets, relative_text)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            generated.append(relative_text)
    except Exception:
        shutil.rmtree(target_assets, ignore_errors=True)
        raise
    return tuple(generated)
