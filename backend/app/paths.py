"""Centralized canonical path resolution and environment loading across API and scripts.

Ensures that DATABASE_PATH, docs/proof.json, docs/dryrun.json, and data/*.json
are always anchored to the repository root regardless of current working directory.
"""

import os
from pathlib import Path
from typing import Dict, Optional

# Repo root is two levels above backend/app/
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DOCS_DIR = REPO_ROOT / "docs"

PROOF_JSON_PATH = DOCS_DIR / "proof.json"
DRYRUN_JSON_PATH = DOCS_DIR / "dryrun.json"
REHEARSAL_PROOF_PATH = DOCS_DIR / "proof.rehearsal-anvil.json"

DEPLOYMENTS_PROOF_PATH = DATA_DIR / "deployments.proof.json"
DEPLOYMENTS_LOCAL_PATH = DATA_DIR / "deployments.json"

DEFAULT_DB_PATH = DATA_DIR / "dao_accountability.db"


def get_repo_root() -> Path:
    """Return absolute path to repository root."""
    return REPO_ROOT


def resolve_db_path(custom_path: Optional[str | Path] = None) -> Path:
    """Resolve database path anchored to the repository root if relative."""
    raw = custom_path or os.environ.get("DATABASE_PATH")
    if raw:
        p = Path(raw)
        if p.is_absolute():
            return p
        return (REPO_ROOT / p).resolve()
    return DEFAULT_DB_PATH


def load_env_hierarchy() -> Dict[str, str]:
    """Auto-load .env then .env.amoy if CHAIN_MODE=proof.

    Never prints or logs private keys or API keys.
    Returns dictionary of loaded configuration.
    """
    loaded: Dict[str, str] = {}

    def _read_env_file(path: Path) -> None:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    # Do not overwrite if already set in process os.environ unless loading hierarchy
                    if k not in os.environ:
                        os.environ[k] = v
                    loaded[k] = v

    # 1. Base .env
    _read_env_file(REPO_ROOT / ".env")

    # 2. If CHAIN_MODE is proof (or configured in .env / process env), load .env.amoy with precedence
    chain_mode = os.environ.get("CHAIN_MODE", loaded.get("CHAIN_MODE", "")).lower()
    if chain_mode == "proof":
        proof_env = REPO_ROOT / ".env.amoy"
        if proof_env.exists():
            with open(proof_env, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    os.environ[k] = v
                    loaded[k] = v

    return loaded
