from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from hx_agent.ask import stitch_chunks, summarize_rule
from hx_agent.app_context import get_ctx, settings
from hx_agent.core.logging import get_logger
from hx_agent.index.meta_store import (
    add_study_message,
    add_study_note,
    create_study_session,
    end_study_session,
    get_active_study_session,
    get_study_session,
    list_study_notes,
    stats,
)
from hx_agent.llm.client import LLMClient
from hx_agent.rag.retriever import retrieve_context

log = get_logger(__name__)


@dataclass
class AnswerResult:
    answer: str
    citations: list[dict[str, Any]]
    provider: str
    model: str
    fallback_used: bool
    request_id: str
    latency_ms: int
    retry_count: int
    token_usage: dict[str, int]


def start_session(name: str, source_path: str) -> int:
    return create_study_session(name=name, source_path=source_path)


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
    request_id = str(uuid4())
    _, total_chunks, _ = stats()
    if total_chunks <= 0:
        msg = 'Knowledge base is empty. Run `hx-agent ingest data` first.'
        return {
            'session_id': None,
            'answer': msg,
            'citations': [],
            'note_id': None,
            'request_id': request_id,
            'fallback_used': True,
        }

    if session_id is None:
        session = get_active_study_session()
        if not session:
            raise RuntimeError('No active session. Run `hx-agent study start` first.')
        session_id = int(session['id'])
    else:
        session = get_study_session(session_id)
        if not session:
            raise RuntimeError(f'Session not found: {session_id}')

    source_candidates = _source_candidates(str(session['source_path'] or ''))
    retrieval = retrieve_context(
        question=query,
        topk=topk,
        retrieval_query='',
        path_prefixes=source_candidates,
    )
    if not retrieval.rows:
        add_study_message(session_id, 'user', query, [])
        add_study_message(
            session_id,
            'assistant',
            'No hits in current source scope.',
            [{'request_id': request_id, 'fallback_used': True, 'error_code': 'no_hits'}],
        )
        return {
            'session_id': session_id,
            'answer': 'No hits in current source scope. Recheck source path or ingest data.',
            'citations': [],
            'note_id': None,
            'request_id': request_id,
            'fallback_used': True,
            'retrieval_query': retrieval.retrieval_query,
            'retrieval_strategy': retrieval.strategy,
        }

    rows = retrieval.rows
    context = retrieval.context

    if retrieval.strategy == 'scope_fallback':
        answer = summarize_rule(context, mode=mode)
        citations = _citations_from_rows(rows)
        add_study_message(session_id, 'user', query, [])
        add_study_message(
            session_id,
            'assistant',
            answer,
            citations
            + [
                {
                    'request_id': request_id,
                    'provider': 'rule',
                    'model': 'rule',
                    'fallback_used': True,
                    'latency_ms': 0,
                    'retry_count': 0,
                    'token_usage': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0},
                }
            ],
        )
        note_id = add_study_note(
            session_id=session_id,
            title=query[:80] if query.strip() else 'Untitled question',
            body=answer,
            citations=citations,
        )
        return {
            'session_id': session_id,
            'answer': answer,
            'citations': citations,
            'note_id': note_id,
            'request_id': request_id,
            'fallback_used': True,
            'retrieval_query': retrieval.retrieval_query,
            'retrieval_strategy': retrieval.strategy,
        }

    llm = LLMClient()
    llm_resp = llm.answer(query=query, context=context, request_id=request_id, session_id=session_id)
    fallback_answer = summarize_rule(context, mode=mode)
    fallback_enabled = bool(get_ctx().cfg.llm.fallback_enabled)
    if llm_resp.text.strip():
        answer = llm_resp.text.strip()
    elif fallback_enabled:
        answer = fallback_answer
    else:
        answer = 'LLM failed and fallback is disabled. Please retry or check llm settings.'

    result = AnswerResult(
        answer=answer,
        citations=_citations_from_rows(rows),
        provider=llm_resp.provider,
        model=llm_resp.model,
        fallback_used=not bool(llm_resp.text.strip()),
        request_id=request_id,
        latency_ms=llm_resp.latency_ms,
        retry_count=llm_resp.retry_count,
        token_usage={
            'input_tokens': llm_resp.input_tokens,
            'output_tokens': llm_resp.output_tokens,
            'total_tokens': llm_resp.total_tokens,
        },
    )
    add_study_message(session_id, 'user', query, [])
    add_study_message(
        session_id,
        'assistant',
        result.answer,
        result.citations
        + [
            {
                'request_id': result.request_id,
                'provider': result.provider,
                'model': result.model,
                'fallback_used': result.fallback_used,
                'latency_ms': result.latency_ms,
                'retry_count': result.retry_count,
                'token_usage': result.token_usage,
                'error_code': llm_resp.error_code,
            }
        ],
    )
    note_id = add_study_note(
        session_id=session_id,
        title=query[:80] if query.strip() else 'Untitled question',
        body=result.answer,
        citations=result.citations,
    )
    log.info(
        '[study.ask] request_id=%s session_id=%s provider=%s model=%s fallback_used=%s latency_ms=%s retry_count=%s total_tokens=%s',
        result.request_id,
        session_id,
        result.provider,
        result.model,
        result.fallback_used,
        result.latency_ms,
        result.retry_count,
        result.token_usage.get('total_tokens', 0),
    )
    return {
        'session_id': session_id,
        'answer': result.answer,
        'citations': result.citations,
        'note_id': note_id,
        'request_id': result.request_id,
        'provider': result.provider,
        'model': result.model,
        'fallback_used': result.fallback_used,
        'latency_ms': result.latency_ms,
        'retry_count': result.retry_count,
        'token_usage': result.token_usage,
        'retrieval_query': retrieval.retrieval_query,
        'retrieval_strategy': retrieval.strategy,
    }


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
