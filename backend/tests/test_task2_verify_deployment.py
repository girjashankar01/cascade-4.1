"""Tests for scripts/verify_deployment.py post-deployment verification."""

import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKEND_DIR = REPO_ROOT / "backend"
for p in (SCRIPTS_DIR, BACKEND_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from verify_deployment import verify_deployment


def test_verify_deployment_all_pass(tmp_path):
    dep_file = tmp_path / "deployments.proof.json"
    env_file = tmp_path / ".env.test"

    token_addr = "0x1111111111111111111111111111111111111111"
    reg_addr = "0x2222222222222222222222222222222222222222"
    tre_addr = "0x3333333333333333333333333333333333333333"
    exec_addr = "0x4444444444444444444444444444444444444444"
    gov_addr = "0x5555555555555555555555555555555555555555"
    ver_addr = "0x6666666666666666666666666666666666666666"
    dep_addr = "0x7777777777777777777777777777777777777777"

    dep_file.write_text(json.dumps({
        "token": token_addr,
        "registry": reg_addr,
        "treasury": tre_addr,
        "executor": exec_addr,
        "governance": gov_addr,
        "verifier": ver_addr,
        "deployer": dep_addr,
        "chain_id": 11155111,
    }))

    env_file.write_text(
        f"CHAIN_ID=11155111\n"
        f"AMOY_RPC=https://rpc.sepolia.org\n"
        f"GOVERNANCE_ADDR={gov_addr}\n"
        f"VERIFIER_ADDR={ver_addr}\n"
        f"DEPLOYER_ADDR={dep_addr}\n"
    )

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.get_code.return_value = b"\x60\x80\x60\x40"

    # Mock contract calls
    def mock_contract(address, abi):
        c = MagicMock()
        addr_str = str(address).lower()
        if addr_str == reg_addr.lower():
            c.functions.governance.return_value.call.return_value = gov_addr
        elif addr_str == tre_addr.lower():
            c.functions.executor.return_value.call.return_value = exec_addr
            c.functions.deployer.return_value.call.return_value = dep_addr
        elif addr_str == exec_addr.lower():
            c.functions.verifier.return_value.call.return_value = ver_addr
            c.functions.registry.return_value.call.return_value = reg_addr
            c.functions.treasury.return_value.call.return_value = tre_addr
        elif addr_str == token_addr.lower():
            c.functions.balanceOf.return_value.call.return_value = 1_000_000 * 10**6
        return c

    mock_w3.eth.contract.side_effect = mock_contract

    res = verify_deployment(deployments_path=dep_file, env_path=env_file, w3_override=mock_w3)
    assert res is True


def test_verify_deployment_fails_on_wrong_wiring(tmp_path):
    dep_file = tmp_path / "deployments.proof.json"
    env_file = tmp_path / ".env.test"

    token_addr = "0x1111111111111111111111111111111111111111"
    reg_addr = "0x2222222222222222222222222222222222222222"
    tre_addr = "0x3333333333333333333333333333333333333333"
    exec_addr = "0x4444444444444444444444444444444444444444"
    gov_addr = "0x5555555555555555555555555555555555555555"
    ver_addr = "0x6666666666666666666666666666666666666666"

    dep_file.write_text(json.dumps({
        "token": token_addr,
        "registry": reg_addr,
        "treasury": tre_addr,
        "executor": exec_addr,
        "governance": gov_addr,
        "verifier": ver_addr,
        "chain_id": 11155111,
    }))

    env_file.write_text(
        f"CHAIN_ID=11155111\n"
        f"AMOY_RPC=https://rpc.sepolia.org\n"
        f"GOVERNANCE_ADDR={gov_addr}\n"
        f"VERIFIER_ADDR={ver_addr}\n"
    )

    mock_w3 = MagicMock()
    mock_w3.eth.chain_id = 11155111
    mock_w3.eth.get_code.return_value = b"\x60\x80\x60\x40"

    def mock_contract(address, abi):
        c = MagicMock()
        addr_str = str(address).lower()
        if addr_str == reg_addr.lower():
            c.functions.governance.return_value.call.return_value = gov_addr
        elif addr_str == tre_addr.lower():
            # Executor not set!
            c.functions.executor.return_value.call.return_value = "0x0000000000000000000000000000000000000000"
            c.functions.deployer.return_value.call.return_value = "0x7777777777777777777777777777777777777777"
        elif addr_str == exec_addr.lower():
            c.functions.verifier.return_value.call.return_value = ver_addr
            c.functions.registry.return_value.call.return_value = reg_addr
            c.functions.treasury.return_value.call.return_value = tre_addr
        elif addr_str == token_addr.lower():
            c.functions.balanceOf.return_value.call.return_value = 1_000_000 * 10**6
        return c

    mock_w3.eth.contract.side_effect = mock_contract

    res = verify_deployment(deployments_path=dep_file, env_path=env_file, w3_override=mock_w3)
    assert res is False
