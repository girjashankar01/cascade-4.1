"""SQLite database initialization, connection management, and schema for Stage 2+."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "dao_accountability.db"


def get_db_path() -> Path:
    """Return database file path from environment or default project location."""
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        return Path(env_path).resolve()
    return DEFAULT_DB_PATH


@contextmanager
def get_db_connection(db_path: Optional[Path | str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Yield an open SQLite connection with Row factory and foreign keys enabled."""
    target_path = Path(db_path).resolve() if db_path else get_db_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[Path | str] = None) -> None:
    """Initialize SQLite schema idempotently without destroying existing data."""
    with get_db_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                sha256 TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                page_count INTEGER NOT NULL DEFAULT 1,
                extracted_pages TEXT NOT NULL,  -- JSON mapping of page_num (int) to text
                ocr_used BOOLEAN NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                field TEXT NOT NULL,
                value TEXT NOT NULL,
                display_value TEXT NOT NULL,
                quote TEXT NOT NULL,
                source_id TEXT NOT NULL,
                page INTEGER NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,  -- GROUNDED, UNCERTAIN, REJECTED
                validation_details TEXT NOT NULL,  -- JSON list of details
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_claims_pid ON claims(proposal_id);
            CREATE INDEX IF NOT EXISTS idx_claims_field ON claims(field);

            CREATE TABLE IF NOT EXISTS conflicts (
                id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                field TEXT NOT NULL,
                value_a TEXT NOT NULL,
                display_value_a TEXT NOT NULL,
                source_id_a TEXT NOT NULL,
                quote_a TEXT NOT NULL,
                page_a INTEGER NOT NULL,
                value_b TEXT NOT NULL,
                display_value_b TEXT NOT NULL,
                source_id_b TEXT NOT NULL,
                quote_b TEXT NOT NULL,
                page_b INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'UNRESOLVED',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_conflicts_pid ON conflicts(proposal_id);

            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                status TEXT NOT NULL,  -- SUCCESS, FAILED, UNCERTAIN
                source_ids TEXT NOT NULL,  -- JSON array of source IDs
                source_hashes TEXT NOT NULL,  -- JSON array of sha256 hashes
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                cache_status TEXT NOT NULL,  -- cached, generated_now
                fallback_used BOOLEAN NOT NULL DEFAULT 0,
                error_code TEXT,
                error_message TEXT,
                rule_set_version TEXT NOT NULL DEFAULT '1.0',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_analyses_pid ON analyses(proposal_id);

            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key TEXT PRIMARY KEY,
                prompt_hash TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                model TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_cache_key ON llm_cache(cache_key);
            """
        )
