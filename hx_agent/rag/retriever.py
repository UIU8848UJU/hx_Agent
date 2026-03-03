from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from hx_agent.index.meta_store import get_chunks_by_ids, get_chunks_by_path_prefix, search_fts

_WORD_RE = re.compile(r'[\u4e00-\u9fff]+|[A-Za-z_][A-Za-z0-9_]*')
_STOP = {
    '这里',
    '这个',
    '什么',
    '讲了',
    '讲',
    '一下',
    '一下子',
    '如何',
    '怎么',
    '以及',
    '一个',
    '一些',
    '关于',
    '的',
    '了',
    '吗',
    '呢',
}


@dataclass
class RetrievalResult:
    rows: list[dict[str, Any]]
    context: str
    retrieval_query: str
    strategy: str


def retrieve_context(
    *,
    question: str,
    topk: int = 8,
    retrieval_query: str = '',
    path_prefixes: list[str] | None = None,
) -> RetrievalResult:
    queries = build_retrieval_queries(question=question, retrieval_query=retrieval_query)
    for i, q in enumerate(queries):
        hits = _search(q, topk=topk, path_prefixes=path_prefixes)
        if hits:
            rows = _rows_from_hits(hits)
            return RetrievalResult(
                rows=rows,
                context=_context_from_rows(rows, limit=4),
                retrieval_query=q,
                strategy='fts_and' if i == 0 else 'fts_or',
            )

    if path_prefixes:
        for p in path_prefixes:
            raw = get_chunks_by_path_prefix(p, topk=topk)
            if raw:
                rows = _to_rows(raw)
                return RetrievalResult(
                    rows=rows,
                    context=_context_from_rows(rows, limit=4),
                    retrieval_query='',
                    strategy='scope_fallback',
                )

    return RetrievalResult(rows=[], context='', retrieval_query=queries[0] if queries else '', strategy='no_hits')


def build_retrieval_queries(*, question: str, retrieval_query: str = '') -> list[str]:
    explicit = (retrieval_query or '').strip()
    if explicit:
        return [explicit]

    kws = extract_keywords(question)
    if not kws:
        q = (question or '').strip()
        return [q] if q else []

    and_q = ' '.join(kws)
    or_q = ' OR '.join(kws)
    if and_q == or_q:
        return [and_q]
    return [and_q, or_q]


def extract_keywords(text: str) -> list[str]:
    out: list[str] = []
    for w in _WORD_RE.findall(text or ''):
        tok = w.strip()
        if not tok:
            continue
        if tok.lower() in _STOP or tok in _STOP:
            continue
        if len(tok) == 1 and not tok.isascii():
            continue
        if tok not in out:
            out.append(tok)
    return out[:8]


def _search(query: str, topk: int, path_prefixes: list[str] | None):
    if not path_prefixes:
        return search_fts(query, topk=topk)
    for p in path_prefixes:
        rows = search_fts(query, topk=topk, path_prefix=p)
        if rows:
            return rows
    return []


def _rows_from_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunk_ids = [h['chunk_id'] for h in hits]
    raw_rows = get_chunks_by_ids(chunk_ids)
    rows = _to_rows(raw_rows)
    id2row = {r['chunk_id']: r for r in rows}
    ordered = [id2row[h['chunk_id']] for h in hits if h['chunk_id'] in id2row]
    return ordered


def _to_rows(raw_rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            'chunk_id': int(r[0]),
            'path': r[1],
            'heading': r[2] or '',
            'start_line': int(r[3] or 0),
            'end_line': int(r[4] or 0),
            'chunk_index': int(r[5] or 0),
            'text': r[6] or '',
        }
        for r in raw_rows
    ]


def _context_from_rows(rows: list[dict[str, Any]], limit: int = 4) -> str:
    return '\n\n'.join([r['text'] for r in rows[:limit]])
