from __future__ import annotations

import sqlite3
from datetime import datetime
import typer

# 配置文件和日志的头文件
from hx_agent.app_context import get_ctx, ensure_default_config, settings, Path

from hx_agent.ingest.scanner import iter_docs, file_sha256

from hx_agent.index.meta_store import (
    count_files,
    upsert_file_return_id,
    delete_chunks_for_file,
    insert_chunks_and_fts,
    get_chunk,
    stats
)
from hx_agent.ingest.chunker_md import chunk_markdown
from hx_agent.index.meta_store import search_fts
import re

_HTML_RE = re.compile(r"<[^>]+>")

# 用于测试
app = typer.Typer(add_completion=False)


def _ensure_dirs():
    settings.OUT_DIR.mkdir(parents=True, exist_ok=True)
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
def strip_html(s: str) -> str:
    return _HTML_RE.sub("", s).strip()
    

# 初始化配置文件的调试
@app.command("init-config")
def init_config():
    path = ensure_default_config()
    print(f"config ready: {path}")
    

# 查找数据库的位置
@app.command()
def doctor():
    """健康检查：路径/目录/DB位置。"""
    
    files, chunks, fts = stats()
    print(f"FILES: {files}")
    print(f"CHUNKS: {chunks}")
    print(f"FTS:   {fts}")

    _ensure_dirs()
    ctx = get_ctx()
    ctx.logger.info("[bold green]OK[/bold green] hx-agent doctor")
    ctx.logger.info(f"ROOT: {settings.ROOT}")
    ctx.logger.info(f"KB_DB: {settings.KB_DB}")
    ctx.logger.info(f"SCHEMA_SQL: {settings.SCHEMA_SQL}")
    ctx.logger.info(f"OUT_DIR: {settings.OUT_DIR}")
    ctx.logger.info(f"CACHE_DIR: {settings.CACHE_DIR}")
    ctx.logger.info(f"CHUNK_POLICY_VERSION: {settings.CHUNK_POLICY_VERSION}")
    

# 初始化数据库
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

# # 扫描md和txt并插入files的表中
# @app.command()
# def ingest(path: str = "docs"):
#     """扫描目录，扫描 md/txt 文件并入files表中。"""

#     root = Path(path).resolve()
    
#     if(not root.exists()):
#         raise RuntimeError(f"Path not exists: {root}")
    
#     before_count = count_files()
#     n =0 
#     for p in iter_docs(root):
#         stat = p.stat()
#         sha = file_sha256(p)
#         upsert_file(
#             path=str(p.relative_to(root)),
#             mtime=int(stat.st_mtime),
#             sha256=sha,
#             size=int(stat.st_size),
#             ftype=p.suffix.lower().lstrip("."),
#         )
#         n += 1
#         after = count_files()
#         print(f"[green]Ingested[/green]: scanned={n}, total files={after}, after files={after}")



@app.command()
def ingest(path: str =  typer.Argument("data")):
    """导入目录：files 增量 + chunks 重建 + fts 同步（v0.1-B）。"""
    
    ctx = get_ctx()
    root = Path(path).resolve()
    print(f"Ingest root={root}")
    if not root.exists():
        raise RuntimeError(f"path not found: {root}")

    scanned = 0
    rebuilt = 0
    total_chunks = 0

    for p in iter_docs(root):
        st = p.stat()
        sha = file_sha256(p)

        # 拿相对路径
        repo_root = settings.ROOT.resolve()
        p_abs = p.resolve()
        try:
            db_path = str(p_abs.relative_to(repo_root))  # 后续应当增加为绝对路径
            ctx.logger.info("[cli::ingest]the path is %s", db_path)
        except ValueError:
            db_path = str(p_abs)  # 不在仓库内就保留绝对路径
            ctx.logger.info("[cli::ingest]the path is %s", db_path)

        file_id, changed = upsert_file_return_id(
            path=db_path,
            mtime=int(st.st_mtime),
            sha256=sha,
            size=int(st.st_size),
            ftype=p.suffix.lower().lstrip("."),
        )
        scanned += 1

        if not changed:
            continue

        text = p.read_text(encoding="utf-8", errors="ignore")
        ck = chunk_markdown(text)

        delete_chunks_for_file(file_id)
        n = insert_chunks_and_fts(
            file_id=file_id,
            path=db_path,
            chunk_policy_version=settings.CHUNK_POLICY_VERSION,
            chunks=ck,
        )
        rebuilt += 1
        total_chunks += n

    print(f"OK scanned={scanned}, rebuilt_files={rebuilt}, inserted_chunks={total_chunks}")


@app.command()
def search(query: str, topk: int = 10):
    """全文检索（FTS5）。"""
    rows = search_fts(query, topk=topk)
    if not rows:
        print("No hits.")
        return
    
    
    for i, r in enumerate(rows, start=1):
        print(f"[{i}] score={r['score']:.4f}  id={r['chunk_id']}")
        print(f"    ref: {r['path']}#L{r['start']}-L{r['end']}")
        if r["heading"]:
            print(f"    heading: {r['heading']}")
        print(f"    {r['snippet']}")
        print()



# 回看的能力
@app.command()
def show(chunk_id: int):
    row = get_chunk(chunk_id)
    if not row:
        print("Not found.")
        return
    _id, path, heading, start, end, text = row
    print(f"chunk_id: {_id}")
    print(f"path: {path}")
    if heading:
        print(f"heading: {heading}")
    print(f"range: L{start}-L{end}")
    print("-" * 60)
    print(text)



if __name__ == "__main__":
    app()