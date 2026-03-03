from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LogConfig:
    level: str = 'INFO'  # DEBUG/INFO/WARNING/ERROR
    to_console: bool = True
    to_file: bool = True
    file: str = 'cache/logs/hx_agent.log'
    rotate_mb: int = 5
    backups: int = 3


@dataclass
class IngestConfig:
    include_exts: list[str] = field(default_factory=lambda: ['.md', '.txt'])
    # 后面可以加 exclude_globs / ignore_dirs 等


@dataclass
class ChunkConfig:
    policy_version: str = 'md_v1'
    target_chars: int = 800  # 先预留（后面 chunk 用）
    overlap_chars: int = 120


@dataclass
class LLMConfig:
    enabled: bool = False
    provider: str = 'openai_compatible'
    base_url: str = 'https://api.openai.com/v1'
    api_key_env: str = 'HX_AGENT_LLM_API_KEY'
    model: str = 'gpt-4o-mini'
    timeout_sec: int = 30
    max_retries: int = 2
    retry_backoff_ms: int = 400
    temperature: float = 0.2
    max_tokens: int = 1200
    fallback_enabled: bool = True
    circuit_breaker_fail_threshold: int = 3
    circuit_breaker_reset_sec: int = 30


@dataclass
class AppConfig:
    # 路径尽量用相对路径（相对 repo root）
    db_path: str = 'kb.sqlite'
    out_dir: str = 'out'
    cache_dir: str = 'cache'
    vectors_dir: str = 'vectors'

    log: LogConfig = field(default_factory=LogConfig)
    ingest: IngestConfig = field(default_factory=IngestConfig)
    chunk: ChunkConfig = field(default_factory=ChunkConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


def default_config() -> AppConfig:
    return AppConfig()


def load_config(config_path: Path) -> AppConfig:
    """
    读取 JSON 配置。不存在则返回默认配置。
    这里先用“浅合并”方式：只覆盖提供的字段。
    """
    cfg = default_config()
    if not config_path.exists():
        return cfg

    data = json.loads(config_path.read_text(encoding='utf-8'))

    # 顶层字段
    for k in ['db_path', 'out_dir', 'cache_dir', 'vectors_dir']:
        if k in data:
            setattr(cfg, k, data[k])

    # 子配置：log
    log = data.get('log', {})
    for k in ['level', 'to_console', 'to_file', 'file', 'rotate_mb', 'backups']:
        if k in log:
            setattr(cfg.log, k, log[k])

    # ingest
    ingest = data.get('ingest', {})
    if 'include_exts' in ingest:
        cfg.ingest.include_exts = list(ingest['include_exts'])

    # chunk
    chunk = data.get('chunk', {})
    for k in ['policy_version', 'target_chars', 'overlap_chars']:
        if k in chunk:
            setattr(cfg.chunk, k, chunk[k])

    llm = data.get('llm', {})
    for k in [
        'enabled',
        'provider',
        'base_url',
        'api_key_env',
        'model',
        'timeout_sec',
        'max_retries',
        'retry_backoff_ms',
        'temperature',
        'max_tokens',
        'fallback_enabled',
        'circuit_breaker_fail_threshold',
        'circuit_breaker_reset_sec',
    ]:
        if k in llm:
            setattr(cfg.llm, k, llm[k])

    return cfg


def save_default_config(config_path: Path) -> None:
    """生成一个默认配置文件"""
    cfg = default_config()
    data = {
        'db_path': cfg.db_path,
        'out_dir': cfg.out_dir,
        'cache_dir': cfg.cache_dir,
        'vectors_dir': cfg.vectors_dir,
        'log': {
            'level': cfg.log.level,
            'to_console': cfg.log.to_console,
            'to_file': cfg.log.to_file,
            'file': cfg.log.file,
            'rotate_mb': cfg.log.rotate_mb,
            'backups': cfg.log.backups,
        },
        'ingest': {
            'include_exts': cfg.ingest.include_exts,
        },
        'chunk': {
            'policy_version': cfg.chunk.policy_version,
            'target_chars': cfg.chunk.target_chars,
            'overlap_chars': cfg.chunk.overlap_chars,
        },
        'llm': {
            'enabled': cfg.llm.enabled,
            'provider': cfg.llm.provider,
            'base_url': cfg.llm.base_url,
            'api_key_env': cfg.llm.api_key_env,
            'model': cfg.llm.model,
            'timeout_sec': cfg.llm.timeout_sec,
            'max_retries': cfg.llm.max_retries,
            'retry_backoff_ms': cfg.llm.retry_backoff_ms,
            'temperature': cfg.llm.temperature,
            'max_tokens': cfg.llm.max_tokens,
            'fallback_enabled': cfg.llm.fallback_enabled,
            'circuit_breaker_fail_threshold': cfg.llm.circuit_breaker_fail_threshold,
            'circuit_breaker_reset_sec': cfg.llm.circuit_breaker_reset_sec,
        },
    }
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
