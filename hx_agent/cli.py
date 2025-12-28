from __future__ import annotations

import sqlite3
from datetime import datetime
import typer

import time
import json
# 配置文件和日志的头文件
from hx_agent.app_context import get_ctx, ensure_default_config, settings, Path

from hx_agent.ingest.scanner import iter_docs, file_sha256

from hx_agent.index.meta_store import (
    start_run, finish_run, count_files, get_last_run,
    upsert_file_return_id,
    delete_chunks_for_file,
    insert_chunks_and_fts,
    get_chunk,
    stats,
    get_chunks_by_ids
)
from hx_agent.ask import stitch_chunks, summarize_rule
from hx_agent.ingest.chunker_md import chunk_markdown
from hx_agent.index.meta_store import search_fts
import re
from hx_agent.reformat import ReformatOptions, reformat_text


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
    ctx = get_ctx()

    files, chunks, fts = stats()
    ctx.logger.info(f"FILES: {files}")
    ctx.logger.info(f"CHUNKS: {chunks}")
    ctx.logger.info(f"FTS:   {fts}")
    last = get_last_run()
    
    _ensure_dirs()
    if last:
        rid, started, finished, ver, notes = last
        print(f"LAST_RUN: id={rid} started_at={started} finished_at={finished} policy={ver}")
    try:
        n = json.loads(notes) if notes else {}
        print(f"  notes: scanned={n.get('scanned')} rebuilt_files={n.get('rebuilt_files')} skipped={n.get('skipped')} inserted_chunks={n.get('inserted_chunks')} failed={len(n.get('failed') or [])} elapsed_sec={n.get('elapsed_sec')}")
    except Exception:
        print("  notes: (unparseable)")
    ctx.logger.debug("[bold green]OK[/bold green] hx-agent doctor")
    ctx.logger.debug(f"ROOT: {settings.ROOT}")
    ctx.logger.debug(f"KB_DB: {settings.KB_DB}")
    ctx.logger.debug(f"SCHEMA_SQL: {settings.SCHEMA_SQL}")
    ctx.logger.debug(f"OUT_DIR: {settings.OUT_DIR}")
    ctx.logger.debug(f"CACHE_DIR: {settings.CACHE_DIR}")
    ctx.logger.debug(f"CHUNK_POLICY_VERSION: {settings.CHUNK_POLICY_VERSION}")
    

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
def ingest(path: str =  typer.Argument("data")
           , rebuild: bool = typer.Option(False, "--rebuild", help="全量重建（忽略 sha 变化判断）")):
    """导入目录：files 增量 + chunks 重建 + fts 同步（v0.1-B）。"""
    
    ctx = get_ctx()
    data_root = Path(path).resolve()
    print(f"Ingest root={data_root}")
    # 如果不存在就创建
    if not data_root.exists():
        raise RuntimeError(f"path not found: {data_root}")
    
    t0 = time.time()
    run_id = start_run(settings.CHUNK_POLICY_VERSION)
    
    scanned = 0
    rebuilt_files = 0
    total_chunks = 0
    skipped = 0
    failed: list[dict] = []
    try:
        for p in iter_docs(data_root):
            scanned += 1
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
            
            if rebuild:
                changed = True

            
            scanned += 1

            if not changed:
                skipped += 1
                ctx.logger.debug("[cli::ingest] skipped same file: %s", db_path)
                continue
            
            # chunk + rewrite chunks/fts
            text = p.read_text(encoding="utf-8", errors="ignore")
            ck = chunk_markdown(text)
            text = p.read_text(encoding="utf-8", errors="ignore")
            ck = chunk_markdown(text)
            
            rebuilt_files += 1
            total_chunks += n

            delete_chunks_for_file(file_id)
            n = insert_chunks_and_fts(
                file_id=file_id,
                path=db_path,
                chunk_policy_version=settings.CHUNK_POLICY_VERSION,
                chunks=ck,
            )
            rebuilt += 1
            total_chunks += n

            failed.append({"path": str(p), "err": repr(e)})
            ctx.logger.exception("[cli::ingest] failed: %s", str(p))
            # 不中断整体 ingest
    finally:
        notes = {
            "scanned": scanned,
            "rebuilt_files": rebuilt_files,
            "skipped": skipped,
            "total_chunks": total_chunks,
            "failed": failed,
            "elapsed_sec": round(time.time() - t0, 3),
        }
        # 不管成功/失败（甚至中途 Ctrl+C），都写一条 run 结束记录
        finish_run(run_id, notes)

    print(
        f"OK run_id={run_id} scanned={scanned}, rebuilt_files={rebuilt_files}, "
        f"skipped={skipped}, total_chunks={total_chunks}, failed={len(failed)}"
    )

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


@app.command()
def ask(query: str, mode: str = "summary", topk: int = 8):
    """复习/问答：SQLite 版 RAG（v0.1 无 LLM）。"""
    hits = search_fts(query, topk=topk)
    if not hits:
        print("No hits.")
        return

    chunk_ids = [h["chunk_id"] for h in hits]
    raw_rows = get_chunks_by_ids(chunk_ids)

    rows = [
        {
            "chunk_id": int(r[0]),
            "path": r[1],
            "heading": r[2] or "",
            "start_line": int(r[3] or 0),
            "end_line": int(r[4] or 0),
            "chunk_index": int(r[5] or 0),
            "text": r[6] or "",
        }
        for r in raw_rows
    ]

    # 为了让 context 更贴 query：按 hits 顺序拼 context（FTS 相关度顺序）
    id2row = {x["chunk_id"]: x for x in rows}
    context_parts = []
    for h in hits:
        cid = h["chunk_id"]
        if cid in id2row:
            context_parts.append(id2row[cid]["text"])
    context = "\n\n".join(context_parts[:4])

    ans = summarize_rule(context, mode=mode)

    # citations 用 stitched（方便合并相邻），再去重
    stitched = stitch_chunks(rows, neighbor_gap=1)

    seen = set()
    citations = []
    for s in stitched:
        ref = f"{s['path']}#L{s['start_line']}-L{s['end_line']}"
        if ref in seen:
            continue
        seen.add(ref)
        citations.append(s)

    print(f"Q: {query}")
    print(f"mode={mode} topk={topk}")
    print("-" * 60)
    print(ans)
    print("\nCitations:")
    for i, s in enumerate(citations, start=1):
        ref = f"{s['path']}#L{s['start_line']}-L{s['end_line']}"
        ids = ",".join(map(str, s.get("chunk_ids", [s["chunk_id"]])))
        heading = s["heading"]
        if heading:
            print(f"[{i}] {ref} (chunks: {ids}) | {heading}")
        else:
            print(f"[{i}] {ref} (chunks: {ids})")



@app.command()
def reformat(
    file: str,
    template: str = "sop",
    out: str = "out",
):
    """把单份笔记整理成模板化文档（v0.1 规则版，默认不覆盖）。"""
    src = Path(file).resolve()
    if not src.exists():
        raise RuntimeError(f"file not found: {src}")

    out_dir = (settings.ROOT / out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    text = src.read_text(encoding="utf-8", errors="ignore")
    opt = ReformatOptions(template=template, keep_raw=True)

    title = src.stem
    formatted = reformat_text(text, opt, title=title)

    dst = out_dir / f"{src.stem}.reformatted.{template}.md"
    dst.write_text(formatted, encoding="utf-8")
    print(f"OK reformat -> {dst}")

if __name__ == "__main__":
    app()