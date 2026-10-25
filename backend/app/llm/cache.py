"""Deterministic SQLite cache for LLM extraction and summaries."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.db import get_db_connection


def compute_cache_key(prompt_hash: str, input_hash: str, model: str) -> str:
    """Compute deterministic SHA-256 cache key over (prompt_hash, input_hash, model)."""
    raw = f"{prompt_hash}:{input_hash}:{model}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_response(
    prompt_hash: str,
    input_hash: str,
    model: str,
    db_path: Optional[Path | str] = None,
) -> Optional[Any]:
    """Retrieve cached response if present in llm_cache."""
    cache_key = compute_cache_key(prompt_hash, input_hash, model)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT response_json FROM llm_cache WHERE cache_key = ?", (cache_key,))
        row = cursor.fetchone()
        if row:
            try:
                return json.loads(row["response_json"])
            except Exception:
                return None
    return None


def set_cached_response(
    prompt_hash: str,
    input_hash: str,
    model: str,
    response_data: Any,
    db_path: Optional[Path | str] = None,
) -> None:
    """Persist validated LLM response into llm_cache."""
    cache_key = compute_cache_key(prompt_hash, input_hash, model)
    response_json = json.dumps(response_data)
    created_at = datetime.now(timezone.utc).isoformat()

    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO llm_cache (cache_key, prompt_hash, input_hash, model, response_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (cache_key, prompt_hash, input_hash, model, response_json, created_at),
        )
