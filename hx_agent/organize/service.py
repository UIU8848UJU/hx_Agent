from __future__ import annotations

from pathlib import Path

from hx_agent.app_context import get_ctx, settings
from hx_agent.ask import summarize_rule
from hx_agent.index.meta_store import record_organize_run
from hx_agent.reformat import ReformatOptions, reformat_text


def _collect_text(target: Path) -> str:
    cfg = get_ctx().cfg
    if target.is_file():
        return target.read_text(encoding='utf-8', errors='ignore')

    if not target.is_dir():
        raise RuntimeError(f'path not found: {target}')

    exts = set(cfg.ingest.include_exts)
    parts: list[str] = []
    for p in target.rglob('*'):
        if p.is_file() and p.suffix in exts:
            parts.append(f'\n\n# File: {p}\n')
            parts.append(p.read_text(encoding='utf-8', errors='ignore'))
    return '\n'.join(parts).strip()


def organize_target(target_path: str, template: str = 'sop', out_dir: str = 'out/organized') -> dict:
    target = Path(target_path).resolve()
    text = _collect_text(target)
    if not text:
        raise RuntimeError(f'no supported content in target: {target}')

    summary = summarize_rule(text, mode='summary')
    source = summary if summary.strip() else text
    formatted = reformat_text(
        source,
        ReformatOptions(template=template, keep_raw=True),
        title=target.stem or target.name,
    )

    dst_dir = (settings.ROOT / out_dir).resolve()
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f'{target.stem or target.name}.organized.{template}.md'
    dst.write_text(formatted, encoding='utf-8')

    run_id = record_organize_run(
        target_path=str(target),
        mode=template,
        output_path=str(dst),
        status='ok',
        notes={'chars': len(text)},
    )
    return {'run_id': run_id, 'output_path': str(dst)}
