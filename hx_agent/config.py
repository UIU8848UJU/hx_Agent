from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    # 仓库根目录：hx_agent/config.py 往上两级
    ROOT: Path = Path(__file__).resolve().parents[1]

    KB_DB: Path = ROOT / "kb.sqlite"
    SCHEMA_SQL: Path = Path(__file__).resolve().parent / "index" / "sql" / "schema.sql"

    OUT_DIR: Path = ROOT / "out"
    CACHE_DIR: Path = ROOT / "cache"

    # 切块策略版本（进库，用于回归）
    CHUNK_POLICY_VERSION: str = "md_v1"

    # 读取文件类型配置
    DEFAULT_FILE_TAIL: tuple[str, ...] = (".md", ".txt")
    
    # data存放资源文件的位置，后续可以写入特定的目录
    DEFAULT_DATA: Path = ROOT/ "data"

# 导出 settings
settings = Settings()
