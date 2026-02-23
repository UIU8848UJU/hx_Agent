from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from hx_agent.config import settings
from hx_agent.core.config import AppConfig, load_config, save_default_config
from hx_agent.core.logging import LoggerOptions, get_logger, setup_logging

CONFIG_PATH = settings.ROOT


@dataclass(frozen=True)
class AppContext:
    repo_root: Path
    config_path: Path
    cfg: AppConfig
    logger: object  # 实际是 logging.Logger


_ctx: Optional[AppContext] = None


def _repo_root() -> Path:
    # hx_agent/app_context.py -> hx_agent/ -> repo root
    return Path(__file__).resolve().parents[1]


def ensure_default_config(config_path: Path) -> None:
    """如果配置不存在就生成默认配置。"""
    if not config_path.exists():
        save_default_config(config_path)


def get_ctx() -> AppContext:
    """全局单例：第一次调用时初始化。"""
    global _ctx
    if _ctx:
        return _ctx

    repo_root = _repo_root()
    config_path = repo_root / 'hx_agent.json'
    cfg = load_config(repo_root / 'hx_agent.json')

    # 把 cfg.log 映射到 LoggerOptions，然后只配置一次 logging
    cfg.db_path = str((repo_root / cfg.db_path).resolve())
    cfg.out_dir = str((repo_root / cfg.out_dir).resolve())
    cfg.cache_dir = str((repo_root / cfg.cache_dir).resolve())
    cfg.vectors_dir = str((repo_root / cfg.vectors_dir).resolve())

    setup_logging(
        repo_root,
        LoggerOptions(
            level=cfg.log.level,
            to_console=cfg.log.to_console,
            to_file=cfg.log.to_file,
            file=Path(cfg.log.file),
            rotate_mb=cfg.log.rotate_mb,
            backups=cfg.log.backups,
        ),
    )

    logger = get_logger('hx_agent')
    _ctx = AppContext(
        repo_root=repo_root,
        config_path=config_path,
        cfg=cfg,
        logger=logger,
    )
    return _ctx
