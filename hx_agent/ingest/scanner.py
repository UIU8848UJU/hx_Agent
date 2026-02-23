from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from hx_agent.app_context import get_ctx

CHUNK_SIZE = 1024 * 1024  # 1 MB


def iter_docs(root: Path, exts: Iterable[str] | None = None) -> Iterable[Path]:
    """遍历目录，按扩展名过滤文件，生成文件路径。"""
    if not root.is_dir():
        return []
    
    if exts is None:
        exts = get_ctx().cfg.ingest.include_exts

    exts_set = set(exts)
    for path in root.rglob('*'):
        if path.is_file() and path.suffix in exts_set:
            yield path


def file_sha256(p: Path) -> str:
    """计算文件的 SHA256 值(用于增量判断)"""
    hash_sha256 = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b''):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()
