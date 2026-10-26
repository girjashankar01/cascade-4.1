"""SQLite database initialization, connection management, and schema for Stage 2+."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "dao_accountability.db"
_ORIGINAL_DEFAULT_DB_PATH = DEFAULT_DB_PATH


def get_db_path() -> Path:
    """Return database file path from environment or default project location.

    Relative paths in DATABASE_PATH are anchored to the repository root directory
    to ensure consistent database resolution regardless of the process working directory.
    """
    if DEFAULT_DB_PATH != _ORIGINAL_DEFAULT_DB_PATH:
        return DEFAULT_DB_PATH
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_absolute():
            return p
        return (REPO_ROOT / p).resolve()
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

            CREATE TABLE IF NOT EXISTS manifests (
                id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                canonical_json TEXT NOT NULL,
                manifest_dict TEXT NOT NULL,
                proposal_text_hash TEXT NOT NULL,
                evidence_root TEXT NOT NULL,
                prev_version_hash TEXT NOT NULL,
                version_hash TEXT NOT NULL,
                action_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'DRAFTED',
                proposer_address TEXT,
                proposer_signature TEXT,
                created_at TEXT NOT NULL,
                confirmed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_manifests_pid_ver ON manifests(proposal_id, version);

            CREATE TABLE IF NOT EXISTS versions (
                id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                version_hash TEXT NOT NULL,
                action_hash TEXT NOT NULL,
                evidence_root TEXT NOT NULL,
                prev_version_hash TEXT NOT NULL,
                commit_tx_hash TEXT,
                commit_block_number INTEGER,
                committed_at TEXT,
                approve_tx_hash TEXT,
                approve_block_number INTEGER,
                approved_at TEXT,
                onchain_verified BOOLEAN NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_versions_pid_ver ON versions(proposal_id, version);

            CREATE TABLE IF NOT EXISTS verifications (
                id TEXT PRIMARY KEY,
                proposal_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                target TEXT NOT NULL,
                value TEXT NOT NULL,
                calldata TEXT NOT NULL,
                action_hash TEXT NOT NULL,
                verdict TEXT NOT NULL,  -- VERIFIED, MISMATCH, UNSUPPORTED, UNCERTAIN
                rules_json TEXT NOT NULL,  -- array of rule outcomes
                diff_json TEXT NOT NULL,  -- field diffs
                simulation_json TEXT NOT NULL,  -- simulation summary & state deltas
                attestation_sig TEXT,
                deadline INTEGER,
                executed BOOLEAN NOT NULL DEFAULT 0,
                tx_hash TEXT,
                block_number INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_verifications_pid ON verifications(proposal_id);

            CREATE TABLE IF NOT EXISTS chain_txs (
                tx_hash TEXT PRIMARY KEY,
                run_id TEXT,
                step TEXT NOT NULL,
                role TEXT NOT NULL,
                "from" TEXT NOT NULL,
                "to" TEXT,
                status TEXT NOT NULL,  -- success, reverted, pending
                revert_reason TEXT,
                block_number INTEGER,
                gas_used INTEGER,
                effective_gas_price INTEGER,
                fee_eth REAL,
                timestamp TEXT NOT NULL,
                explorer_url TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_chain_txs_run_id ON chain_txs(run_id);
            CREATE INDEX IF NOT EXISTS idx_chain_txs_timestamp ON chain_txs(timestamp);
            CREATE INDEX IF NOT EXISTS idx_chain_txs_role ON chain_txs(role);
            """
        )


def record_chain_tx(
    tx_data: dict,
    db_path: Optional[Path | str] = None,
) -> None:
    """Insert or update a transaction record in the chain_txs table."""
    init_db(db_path)
    from_addr = tx_data.get("from") or tx_data.get("from_address") or ""
    to_addr = tx_data.get("to") or tx_data.get("to_address")
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO chain_txs (
                tx_hash, run_id, step, role, "from", "to", status,
                revert_reason, block_number, gas_used, effective_gas_price,
                fee_eth, timestamp, explorer_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx_data.get("tx_hash"),
                tx_data.get("run_id"),
                tx_data.get("step") or "unknown",
                tx_data.get("role") or "caller",
                from_addr,
                to_addr,
                tx_data.get("status") or "pending",
                tx_data.get("revert_reason"),
                tx_data.get("block_number"),
                tx_data.get("gas_used"),
                tx_data.get("effective_gas_price"),
                tx_data.get("fee_eth"),
                tx_data.get("timestamp"),
                tx_data.get("explorer_url"),
            ),
        )


def get_chain_txs(
    run_id: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[Path | str] = None,
) -> list[dict]:
    """Retrieve transaction history from chain_txs, newest first."""
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        if run_id:
            cursor.execute(
                """
                SELECT tx_hash, run_id, step, role, "from" as from_address, "to" as to_address,
                       status, revert_reason, block_number, gas_used, effective_gas_price,
                       fee_eth, timestamp, explorer_url
                FROM chain_txs
                WHERE run_id = ?
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?
                """,
                (run_id, limit),
            )
        else:
            cursor.execute(
                """
                SELECT tx_hash, run_id, step, role, "from" as from_address, "to" as to_address,
                       status, revert_reason, block_number, gas_used, effective_gas_price,
                       fee_eth, timestamp, explorer_url
                FROM chain_txs
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["from"] = d["from_address"]
            d["to"] = d["to_address"]
            result.append(d)
        return result


def get_chain_tx(
    tx_hash: str,
    db_path: Optional[Path | str] = None,
) -> Optional[dict]:
    """Retrieve single transaction record by tx_hash from chain_txs."""
    init_db(db_path)
    clean_hash = tx_hash.strip().lower()
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tx_hash, run_id, step, role, "from" as from_address, "to" as to_address,
                   status, revert_reason, block_number, gas_used, effective_gas_price,
                   fee_eth, timestamp, explorer_url
            FROM chain_txs
            WHERE LOWER(tx_hash) = ?
            LIMIT 1
            """,
            (clean_hash,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["from"] = d["from_address"]
        d["to"] = d["to_address"]
        return d
