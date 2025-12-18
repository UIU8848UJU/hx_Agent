from __future__ import annotations

import sqlite3
from datetime import datetime
import typer
from rich import print

from hx_agent.config import settings

app = typer.Typer(add_completion=False)


def _ensure_dirs():
    settings.OUT_DIR.mkdir(parents=True, exist_ok=True)
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    

@app.command()
def doctor():
    """健康检查：路径/目录/DB位置。"""
    _ensure_dirs()
    print("[bold green]OK[/bold green] hx-agent doctor")
    print(f"ROOT: {settings.ROOT}")
    print(f"KB_DB: {settings.KB_DB}")
    print(f"SCHEMA_SQL: {settings.SCHEMA_SQL}")
    print(f"OUT_DIR: {settings.OUT_DIR}")
    print(f"CACHE_DIR: {settings.CACHE_DIR}")
    print(f"CHUNK_POLICY_VERSION: {settings.CHUNK_POLICY_VERSION}")

@app.command("init-db")
def init_db():
    """初始化 SQLite（创建表 + FTS）。"""
    _ensure_dirs()

    
    print("[bold]Init DB[/bold]")
    print(f"schema: {settings.SCHEMA_SQL}")
    print(f"db:     {settings.KB_DB}")
    
    if not settings.SCHEMA_SQL.exists():
        raise RuntimeError(f"schema.sql not found: {settings.SCHEMA_SQL}")

    sql = settings.SCHEMA_SQL.read_text(encoding="utf-8")
    with sqlite3.connect(settings.KB_DB) as conn:
        conn.executescript(sql)
        conn.commit()

    print(f"[bold green]DB initialized[/bold green]: {settings.KB_DB}")
    print(f"at {datetime.now().isoformat(timespec='seconds')}")

if __name__ == "__main__":
    app()