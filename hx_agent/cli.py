from __future__ import annotations

import sqlite3
from datetime import datetime
import typer
from rich import print

from hx_agent.config import settings
from hx_agent.core.logger import ILogger
from hx_agent.core.config import load_config, save_default_config

from pathlib import Path
from hx_agent.ingest.scanner import iter_docs, file_sha256
from hx_agent.index.meta_store import upsert_file, count_files


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


@app.command()
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

@app.command()
def ingest(path: str = "docs"):
    """扫描目录，扫描 md/txt 文件并入files表中。"""

    root = Path(path).resolve()
    
    if(not root.exists()):
        raise RuntimeError(f"Path not exists: {root}")
    
    before_count = count_files()
    n =0 
    for p in iter_docs(root):
        stat = p.stat()
        sha = file_sha256(p)
        upsert_file(
            path=str(p.relative_to(root)),
            mtime=int(stat.st_mtime),
            sha256=sha,
            size=int(stat.st_size),
            ftype=p.suffix.lower().lstrip("."),
        )
        n += 1
        after = count_files()
        print(f"[green]Ingested[/green]: scanned={n}, total files={after}, after files={after}")


def init_config():
    """生成一配置文件在hx_agent.json默认配置"""
    if(CONFIG_PATH.exists()):
        logger.warning(f"[red]Config file already exists:[/red] {CONFIG_PATH}")
        return
    save_default_config(CONFIG_PATH)
    logger.info(f"Default config file created at: {CONFIG_PATH}")


if __name__ == "__main__":
    app()