"""Regression tests for stable SQLite database path resolution (Issue 2).

Proves that relative DATABASE_PATH resolves identically regardless of process working directory.
"""

import os
from pathlib import Path
import pytest

from app.db import REPO_ROOT, get_db_path


def test_relative_database_path_resolves_to_repo_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Relative DATABASE_PATH must resolve against REPO_ROOT regardless of current working directory."""
    monkeypatch.setenv("DATABASE_PATH", "data/dao_accountability.db")

    orig_cwd = os.getcwd()
    try:
        # 1. From repository root
        os.chdir(REPO_ROOT)
        path_from_root = get_db_path()
        assert path_from_root == (REPO_ROOT / "data" / "dao_accountability.db").resolve()

        # 2. From backend directory
        os.chdir(REPO_ROOT / "backend")
        path_from_backend = get_db_path()
        assert path_from_backend == path_from_root, "Must resolve identically when CWD is backend/"

        # 3. From an arbitrary temporary directory
        os.chdir(tmp_path)
        path_from_tmp = get_db_path()
        assert path_from_tmp == path_from_root, "Must resolve identically when CWD is an arbitrary tmp directory"

    finally:
        os.chdir(orig_cwd)


def test_absolute_database_path_is_preserved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Explicit absolute DATABASE_PATH must be preserved as-is."""
    abs_db = (tmp_path / "custom_test.db").resolve()
    monkeypatch.setenv("DATABASE_PATH", str(abs_db))
    resolved = get_db_path()
    assert resolved == abs_db
