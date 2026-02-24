from __future__ import annotations

from pathlib import Path
from typing import Any

from hx_agent.ask import stitch_chunks, summarize_rule
from hx_agent.app_context import settings
from hx_agent.index.meta_store import (
    add_study_message,
    add_study_note,
    create_study_session,
    end_study_session,
    get_chunks_by_path_prefix,
    get_active_study_session,
    get_chunks_by_ids,
    get_study_session,
    list_study_notes,
    search_fts,
    stats,
)
from hx_agent.llm.client import LLMClient


def start_session(name: str, source_path: str) -> int:
    return create_study_session(name=name, source_path=source_path)


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


def _citations_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stitched = stitch_chunks(rows, neighbor_gap=1)
    seen = set()
    out: list[dict[str, Any]] = []
    for s in stitched:
        ref = f'{s["path"]}#L{s["start_line"]}-L{s["end_line"]}'
        if ref in seen:
            continue
        seen.add(ref)
        out.append(
            {
                'path': s['path'],
                'start_line': s['start_line'],
                'end_line': s['end_line'],
                'heading': s.get('heading', ''),
                'chunk_ids': s.get('chunk_ids', [s['chunk_id']]),
            }
        )
    return out


def study_ask(
    query: str,
    mode: str = 'summary',
    topk: int = 8,
    session_id: int | None = None,
) -> dict[str, Any]:
    _, total_chunks, _ = stats()
    if total_chunks <= 0:
        msg = 'Knowledge base is empty. Run `hx-agent ingest data` first.'
        return {'session_id': None, 'answer': msg, 'citations': [], 'note_id': None}

    if session_id is None:
        session = get_active_study_session()
        if not session:
            raise RuntimeError('No active session. Run `hx-agent study start` first.')
        session_id = int(session['id'])
    else:
        session = get_study_session(session_id)
        if not session:
            raise RuntimeError(f'Session not found: {session_id}')

    source_path = str(session['source_path'] or '')
    source_candidates = _source_candidates(source_path)

    hits = []
    for cand in source_candidates:
        hits = search_fts(query, topk=topk, path_prefix=cand)
        if hits:
            break
    if not hits:
        # If semantic-like question ("这里讲了什么") has no keyword hits, still summarize scoped source.
        raw_rows = []
        for cand in source_candidates:
            raw_rows = get_chunks_by_path_prefix(cand, topk=topk)
            if raw_rows:
                break
        if not raw_rows:
            add_study_message(session_id, 'user', query, [])
            add_study_message(session_id, 'assistant', 'No hits in current source scope.', [])
            return {
                'session_id': session_id,
                'answer': 'No hits in current source scope. Recheck source path or ingest data.',
                'citations': [],
                'note_id': None,
            }
        rows = _to_rows(raw_rows)
        context = '\n\n'.join([r['text'] for r in rows[:4]])
        answer = summarize_rule(context, mode=mode)
        citations = _citations_from_rows(rows)
        add_study_message(session_id, 'user', query, [])
        add_study_message(session_id, 'assistant', answer, citations)
        note_id = add_study_note(
            session_id=session_id,
            title=query[:80] if query.strip() else 'Untitled question',
            body=answer,
            citations=citations,
        )
        return {'session_id': session_id, 'answer': answer, 'citations': citations, 'note_id': note_id}

    chunk_ids = [h['chunk_id'] for h in hits]
    rows = _to_rows(get_chunks_by_ids(chunk_ids))
    id2row = {x['chunk_id']: x for x in rows}
    context_parts = [id2row[h['chunk_id']]['text'] for h in hits if h['chunk_id'] in id2row]
    context = '\n\n'.join(context_parts[:4])

    llm = LLMClient()
    llm_resp = llm.answer(query=query, context=context)
    answer = llm_resp.text.strip() if llm_resp.text.strip() else summarize_rule(context, mode=mode)

    citations = _citations_from_rows(rows)
    add_study_message(session_id, 'user', query, [])
    add_study_message(session_id, 'assistant', answer, citations)
    note_id = add_study_note(
        session_id=session_id,
        title=query[:80] if query.strip() else 'Untitled question',
        body=answer,
        citations=citations,
    )
    return {'session_id': session_id, 'answer': answer, 'citations': citations, 'note_id': note_id}


def end_session(session_id: int | None = None) -> int:
    if session_id is None:
        session = get_active_study_session()
        if not session:
            raise RuntimeError('No active session.')
        session_id = int(session['id'])
    end_study_session(session_id)
    return int(session_id)


def list_notes(session_id: int | None = None):
    if session_id is None:
        session = get_active_study_session()
        if not session:
            raise RuntimeError('No active session.')
        session_id = int(session['id'])
    return list_study_notes(int(session_id))


def _source_candidates(source_path: str) -> list[str]:
    if not source_path:
        return ['data']

    p = source_path.replace('\\', '/')
    out = [p]
    try:
        rel = str(Path(source_path).resolve().relative_to(settings.ROOT.resolve())).replace('\\', '/')
        if rel not in out:
            out.append(rel)
    except Exception:
        pass

    if p.endswith('/'):
        out.append(p.rstrip('/'))
    elif '.' in Path(p).name:
        parent = str(Path(p).parent).replace('\\', '/')
        if parent and parent not in out:
            out.append(parent)

    # Normalize common default
    if 'data' not in out:
        out.append('data')

    expanded: list[str] = []
    for item in out:
        if item not in expanded:
            expanded.append(item)
        backslash = item.replace('/', '\\')
        if backslash not in expanded:
            expanded.append(backslash)
    return expanded
