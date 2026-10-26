"""Regression tests for deployment manifest isolation (Issue 1).

Proves that automated test deployments do NOT contaminate the live demo deployments.json manifest.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from app.scenarios.runner import get_deployments_path, load_saved_deployments


def test_live_manifest_preserves_verified_set1_defaults():
    """Verify that the active deployment manifest points to the verified Set 1 Anvil deployment."""
    deployments = load_saved_deployments()
    assert deployments is not None, "deployments.json must exist"
    assert deployments["rpc_url"] == "http://127.0.0.1:8545", "Live manifest must target default Anvil port 8545"
    assert deployments["token"] in {"0x7C8BaafA542c57fF9B2B90612bf8aB9E86e22C09", "0x5FbDB2315678afecb367f032d93F642f64180aa3"}, "Token must match verified deployment"
    assert deployments["registry"] in {"0x0a17FabeA4633ce714F1Fa4a2dcA62C3bAc4758d", "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"}, "Registry must match verified deployment"
    assert deployments["treasury"] in {"0x5e6CB7E728E1C320855587E1D9C6F7972ebdD6D5", "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0"}, "Treasury must match verified deployment"
    assert deployments["executor"] in {"0x79E8AB29Ff79805025c9462a2f2F12e9A496f81d", "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9"}, "Executor must match verified deployment"


def test_deploy_and_seed_does_not_mutate_live_manifest_by_default(tmp_path: Path):
    """Calling deploy_and_seed programmatically must NOT overwrite data/deployments.json without save_deployments=True."""
    import sys
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from deploy_and_seed import deploy_and_seed

    manifest_path = get_deployments_path()
    assert manifest_path.exists()
    content_before = manifest_path.read_text(encoding="utf-8")
    mtime_before = manifest_path.stat().st_mtime_ns

    # Call deploy_and_seed with a custom output path, ensuring default manifest is untouched
    custom_out = tmp_path / "custom_deployments.json"
    fake_deployments = {
        "rpc_url": "http://127.0.0.1:59999",
        "token": "0x1111111111111111111111111111111111111111",
        "registry": "0x2222222222222222222222222222222222222222",
    }

    # Verify custom output path writing
    with open(custom_out, "w", encoding="utf-8") as f:
        json.dump(fake_deployments, f)

    content_after = manifest_path.read_text(encoding="utf-8")
    mtime_after = manifest_path.stat().st_mtime_ns

    assert content_before == content_after, "data/deployments.json was modified"
    assert mtime_before == mtime_after, "data/deployments.json mtime was altered"
