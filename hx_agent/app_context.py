from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from hx_agent.config import settings                      
from hx_agent.core.config import load_config, AppConfig, save_default_config
from hx_agent.core.logging import setup_logging, LoggerOptions

CONFIG_PATH = settings.ROOT / "hx_agent.json"

@dataclass(frozen=True)
class AppContext:
    repo_root: Path
    config_path: Path
    cfg: AppConfig

_ctx: Optional[AppContext] = None

def get_ctx() -> AppContext:
    """全局单例：第一次调用时初始化。"""
    global _ctx
    if _ctx is not None:
        return _ctx
    ensure_default_config()

    cfg = load_config(CONFIG_PATH)

    # 把 cfg.log 映射到 LoggerOptions，然后只配置一次 logging
    opt = LoggerOptions(
        level=cfg.log.level,
        to_console=cfg.log.to_console,
        to_file=cfg.log.to_file,
        file=Path(cfg.log.file),
        rotate_mb=cfg.log.rotate_mb,
        backups=cfg.log.backups,
    )
    
    setup_logging(opt, repo_root=settings.ROOT)

    _ctx = AppContext(
        repo_root=settings.ROOT,
        config_path=CONFIG_PATH,
        cfg=cfg,
    )
    return _ctx

def ensure_default_config() -> Path:
    """如果配置不存在就生成默认配置。"""
    if not CONFIG_PATH.exists():
        save_default_config(CONFIG_PATH)
    return CONFIG_PATH
