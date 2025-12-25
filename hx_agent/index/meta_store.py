from __future__ import annotations
import sqlite3
from pathlib import Path
import hashlib
from typing import Iterable, Optional, Tuple, List, Dict, Any

from hx_agent.app_context import settings, get_ctx

meta_log =  get_ctx()

def connect() -> sqlite3.Connection:
    """连接到知识库 SQLite 数据库。"""
    db_path = Path(settings.KB_DB)
    if(not db_path.exists()):
        meta_log.logger.error("detalib is Not exist!")
        raise RuntimeError(f"知识库数据库不存在: {db_path}")
    conn = sqlite3.connect(settings.KB_DB)
    conn.row_factory = sqlite3.Row 
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_file_by_path(path: str) -> Optional[Tuple[int, str]]:
    """返回 (file_id, sha256) 或 None"""
    with connect() as conn:
        row = conn.execute("SELECT id, sha256 FROM files WHERE path=?", (path,)).fetchone()
        if not row:
            meta_log.logger.debug("[get_file_by_path]: files is same")
            return None
        return int(row[0]), str(row[1])
    

def upsert_file_return_id(path: str
                , mtime: int
                , sha256: str
                , size: int
                , ftype: str
                ) -> Tuple[int, bool]:
    """
    Upsert files，并返回 (file_id, changed)
    changed: 该 path 之前不存在，或 sha256 与之前不同
    """
    prev = get_file_by_path(path)
    changed = (prev is None) or (prev[1] != sha256)
    
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
        # 拿 file_id
        (file_id,) = conn.execute("SELECT id FROM files WHERE path=?", (path,)).fetchone()
        conn.commit()
    return int(file_id), changed


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


# 这里是不是可以直接用SELECT id...存到列表当中去再删
def delete_chunks_for_file(file_id: int) -> None:
    """先删 FTS，再删 chunks（避免失去 rowid 对应）"""
    with connect() as conn:
        conn.execute("DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE file_id=?)", (file_id,))
        conn.execute("DELETE FROM chunks WHERE file_id=?", (file_id,))
        conn.commit()



def insert_chunks_and_fts(
    file_id: int,   # 文件id号
    path: str,      #路径名
    chunk_policy_version: str, # 切块的版本
    chunks: List[Dict[str, Any]], # 总共切了多少块
    ) -> int:
    """
    chunks: [{'heading': str, 'start_line': int, 'end_line': int, 'text': str}, ...]
    返回插入 chunk 数量
    """
    with connect() as conn:
        inserted = 0
        for idx, c in enumerate(chunks):
            text = c["text"]
            heading = c.get("heading") or ""
            start_line = int(c.get("start_line", 0))
            end_line = int(c.get("end_line", 0))
            text_hash = _hash_text(text)

            cur = conn.execute(
                """
                INSERT INTO chunks(file_id, chunk_index, heading, start_offset, end_offset, text, text_hash, chunk_policy_version)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, idx, heading, start_line, end_line, text, text_hash, chunk_policy_version),
            )
            chunk_id = int(cur.lastrowid)

            # FTS rowid = chunk_id
            conn.execute(
                "INSERT OR REPLACE INTO chunks_fts(rowid, text, path, heading) VALUES(?, ?, ?, ?)",
                (chunk_id, text, path, heading),
            )
            inserted += 1

        conn.commit()
    return inserted


def search_fts(query: str, topk: int = 10):
    """
    返回: [{'chunk_id', 'path', 'heading', 'snippet', 'score'}...]
    bm25 越小越相关（FTS5）
    """
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
              chunks_fts.rowid AS chunk_id,
              f.path    AS path,
              c.heading AS heading,
              c.start_offset AS start_line,
              c.end_offset   AS end_line,
              substr(c.text, 1, 220) AS snip,
              bm25(chunks_fts) AS score
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            JOIN files  f ON f.id = c.file_id
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (query, int(topk)),
        ).fetchall()

    out = []
    for r in rows:
        out.append(
            {
                "chunk_id": int(r["chunk_id"]),
                "path": str(r["path"]),
                "heading": str(r["heading"] or ""),
                "start": int(r["start_line"] or 0),
                "end": int(r["end_line"] or 0),
                "snippet": (r["snip"] or "").replace("\n"," "),
                "score": float(r["score"]),
            }
        )
    return out

def count_files()-> int:
    """统计 files 表中的记录数"""
    with connect() as conn:
        (n,) = conn.execute("SELECT COUNT(*) FROM files;").fetchone()
        conn.row_factory = sqlite3.Row
        return int(n)
    
# 查询某个笔记
def get_chunk(chunk_id: int):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT c.id, f.path, c.heading, c.start_offset, c.end_offset, c.text
            FROM chunks c JOIN files f ON f.id=c.file_id
            WHERE c.id=?
            """,
            (int(chunk_id),),
        ).fetchone()
    return row


def stats():
    with connect() as conn:
        files = conn.execute("select count(*) from files").fetchone()[0]
        chunks = conn.execute("select count(*) from chunks").fetchone()[0]
        fts = conn.execute("select count(*) from chunks_fts").fetchone()[0]
    return files, chunks, fts