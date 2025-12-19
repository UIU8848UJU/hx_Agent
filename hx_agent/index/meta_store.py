from __future__ import annotations
import sqlite3
from pathlib import Path
from hx_agent.config import settings

def connect() -> sqlite3.Connection:
    """连接到知识库 SQLite 数据库。"""
    db_path = Path(settings.KB_DB)
    if(not db_path.exists()):
        raise RuntimeError(f"知识库数据库不存在: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def upsert_file(path: str, mtime: int, sha256: str, size: int, ftype: str) -> None:
    """插入或更新 files 表中的记录。"""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO files(path, mtime, sha256, size, type, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(path) DO UPDATE SET
                mtime=excluded.mtime,
                sha256=excluded.sha256,
                size=excluded.size,
                type=excluded.type,
                updated_at=datetime('now')
            """,
            (path, mtime, sha256, size, ftype),
        )
        conn.commit()


def count_files()-> int:
    """统计 files 表中的记录数"""
    with connect() as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM files;").fetchone()
        return int(n)

