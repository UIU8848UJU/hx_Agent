from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import json

@dataclass
class LogConfig:
    level: str = "INFO"          # DEBUG/INFO/WARNING/ERROR
    to_console: bool = True
    to_file: bool = True
    file: str = "cache/logs/hx_agent.log"
    rotate_mb: int = 5
    backups: int = 3

@dataclass
class IngestConfig:
    include_exts: list[str] = field(default_factory=lambda: [".md", ".txt"])
    # 后面可以加 exclude_globs / ignore_dirs 等

@dataclass
class ChunkConfig:
    policy_version: str = "md_v1"
    target_chars: int = 800       # 先预留（后面 chunk 用）
    overlap_chars: int = 120

@dataclass
class AppConfig:
    # 路径尽量用相对路径（相对 repo root）
    db_path: str = "kb.sqlite"
    out_dir: str = "out"
    cache_dir: str = "cache"
    vectors_dir: str = "vectors"

    log: LogConfig = field(default_factory=LogConfig)
    ingest: IngestConfig = field(default_factory=IngestConfig)
    chunk: ChunkConfig = field(default_factory=ChunkConfig)

def default_config() -> AppConfig:
    return AppConfig()

def load_config(config_path: Path) -> AppConfig:
    """
    读取 JSON 配置。不存在则返回默认配置。
    这里先用“浅合并”方式：只覆盖提供的字段。
    """
    cfg = default_config()
    if not config_path.exists():
        return cfg

    data = json.loads(config_path.read_text(encoding="utf-8"))

    # 顶层字段
    for k in ["db_path", "out_dir", "cache_dir", "vectors_dir"]:
        if k in data:
            setattr(cfg, k, data[k])

    # 子配置：log
    log = data.get("log", {})
    for k in ["level", "to_console", "to_file", "file", "rotate_mb", "backups"]:
        if k in log:
            setattr(cfg.log, k, log[k])

    # ingest
    ingest = data.get("ingest", {})
    if "include_exts" in ingest:
        cfg.ingest.include_exts = list(ingest["include_exts"])

    # chunk
    chunk = data.get("chunk", {})
    for k in ["policy_version", "target_chars", "overlap_chars"]:
        if k in chunk:
            setattr(cfg.chunk, k, chunk[k])

    return cfg

def save_default_config(config_path: Path) -> None:
    """生成一个默认配置文件"""
    cfg = default_config()
    data = {
        "db_path": cfg.db_path,
        "out_dir": cfg.out_dir,
        "cache_dir": cfg.cache_dir,
        "vectors_dir": cfg.vectors_dir,
        "log": {
            "level": cfg.log.level,
            "to_console": cfg.log.to_console,
            "to_file": cfg.log.to_file,
            "file": cfg.log.file,
            "rotate_mb": cfg.log.rotate_mb,
            "backups": cfg.log.backups,
        },
        "ingest": {
            "include_exts": cfg.ingest.include_exts,
        },
        "chunk": {
            "policy_version": cfg.chunk.policy_version,
            "target_chars": cfg.chunk.target_chars,
            "overlap_chars": cfg.chunk.overlap_chars,
        },
    }
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")