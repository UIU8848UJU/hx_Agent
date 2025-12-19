from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional, Protocol

class ILogger(Protocol):
    def debug(self, msg: str, *args, **kwargs) -> None: ...
    def info(self, msg: str, *args, **kwargs) -> None: ...
    def warning(self, msg: str, *args, **kwargs) -> None: ...
    def error(self, msg: str, *args, **kwargs) -> None: ...
    def exception(self, msg: str, *args, **kwargs) -> None: ...

@dataclass(frozen=True)
class LoggerOptions:
    name: str = "hx_agent"
    level: str = "INFO"
    to_console: bool = True
    to_file: bool = True
    file: Path = Path("cache/logs/hx_agent.log")
    rotate_mb: int = 5
    backups: int = 3

class StdLogger(ILogger):
    """标准库 logging 的封装实现。未来要换实现，只要换 create_logger 返回的类即可。"""
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def debug(self, msg: str, *args, **kwargs) -> None: self._logger.debug(msg, *args, **kwargs)
    def info(self, msg: str, *args, **kwargs) -> None: self._logger.info(msg, *args, **kwargs)
    def warning(self, msg: str, *args, **kwargs) -> None: self._logger.warning(msg, *args, **kwargs)
    def error(self, msg: str, *args, **kwargs) -> None: self._logger.error(msg, *args, **kwargs)
    def exception(self, msg: str, *args, **kwargs) -> None: self._logger.exception(msg, *args, **kwargs)

def create_logger(opt: LoggerOptions, repo_root: Path) -> ILogger:
    logger = logging.getLogger(opt.name)

    # 关键：避免重复添加 handler
    if getattr(logger, "_hx_configured", False):
        return StdLogger(logger)

    level = getattr(logging, opt.level.upper(), logging.INFO)
    logger.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if opt.to_console:
        sh = logging.StreamHandler()
        sh.setLevel(level)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    if opt.to_file:
        log_path = (repo_root / opt.file).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_path,
            maxBytes=opt.rotate_mb * 1024 * 1024,
            backupCount=opt.backups,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    logger._hx_configured = True  # 标记，防止重复配置
    return StdLogger(logger)