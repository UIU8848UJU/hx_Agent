from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

@dataclass(frozen=True)
class LoggerOptions:
    level: str = "INFO"
    to_console: bool = True
    to_file: bool = True
    file: Path = Path("cache/logs/hx_agent.log")
    rotate_mb: int = 5
    backups: int = 3

_configured = False

def setup_logging(repo_root: Path, opt: LoggerOptions) -> None:
    """全局只配置一次 hx_agent logger 的 handler/format。"""
    global _configured
    if _configured:
        return

    lvl = getattr(logging, opt.level.upper(), logging.INFO)

    root = logging.getLogger("hx_agent")
    root.setLevel(lvl)
    root.propagate = False  # 避免重复打印到 root logger

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(module)s.%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if opt.to_console:
        sh = logging.StreamHandler()
        sh.setLevel(lvl)
        sh.setFormatter(fmt)
        root.addHandler(sh)

    if opt.to_file:
        log_path = (repo_root / opt.file).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_path,
            maxBytes=opt.rotate_mb * 1024 * 1024,
            backupCount=opt.backups,
            encoding="utf-8",
        )
        fh.setLevel(lvl)
        fh.setFormatter(fmt)
        root.addHandler(fh)

    _configured = True

def get_logger(name: str) -> logging.Logger:
    """
    各模块用 get_logger(__name__) 获取 logger。
    统一挂到 hx_agent 命名空间下，确保能继承 handlers。
    """
    if name == "hx_agent" or name.startswith("hx_agent."):
        return logging.getLogger(name)
    return logging.getLogger(f"hx_agent.{name}")
