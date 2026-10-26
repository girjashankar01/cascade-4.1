#!/usr/bin/env bash
set -eo pipefail

# Preflight validation for deploying DAO Accountability Engine to Ethereum Sepolia (11155111)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Auto-load .env and .env.amoy if present
if [ -f "$REPO_ROOT/.env" ]; then
    set -a; source "$REPO_ROOT/.env"; set +a
fi
if [ -f "$REPO_ROOT/.env.amoy" ]; then
    set -a; source "$REPO_ROOT/.env.amoy"; set +a
fi

RPC_URL="${AMOY_RPC:-${RPC_URL_PROOF}}"
EXPECTED_CHAIN_ID="${CHAIN_ID:-11155111}"
REQUIRED_BALANCE_ETH="0.01"

echo "================================================================================"
echo "          DAO ACCOUNTABILITY ENGINE — PREFLIGHT DEPLOYMENT AUDIT"
echo "================================================================================"
echo "Target Network:      Ethereum Sepolia (Expected Chain ID: $EXPECTED_CHAIN_ID)"

ERRORS=0

# 1. Check RPC configuration
if [ -z "$RPC_URL" ]; then
    echo "[-] ERROR: AMOY_RPC (or RPC_URL_PROOF) is not set."
    ERRORS=$((ERRORS + 1))
else
    # Query chain ID using cast or python
    ACTUAL_CHAIN_ID=""
    if command -v cast &>/dev/null; then
        ACTUAL_CHAIN_ID=$(cast chain-id --rpc-url "$RPC_URL" 2>/dev/null || true)
    fi
    if [ -z "$ACTUAL_CHAIN_ID" ]; then
        ACTUAL_CHAIN_ID=$(uv run --project "$REPO_ROOT/backend" python -c "
import sys
from web3 import Web3
try:
    w3 = Web3(Web3.HTTPProvider('$RPC_URL'))
    if w3.is_connected():
        print(w3.eth.chain_id)
except Exception:
    pass
" 2>/dev/null || true)
    fi

    if [ "$ACTUAL_CHAIN_ID" = "$EXPECTED_CHAIN_ID" ]; then
        echo "[+] RPC Connected:     Chain ID $ACTUAL_CHAIN_ID matches expected $EXPECTED_CHAIN_ID"
    else
        echo "[-] ERROR: Connected chain ID '$ACTUAL_CHAIN_ID' does not match expected '$EXPECTED_CHAIN_ID'."
        ERRORS=$((ERRORS + 1))
    fi
fi

# 2. Check Participant Addresses
if [ -z "$GOVERNANCE_ADDR" ]; then
    echo "[-] ERROR: GOVERNANCE_ADDR is not set."
    ERRORS=$((ERRORS + 1))
else
    echo "[+] Governance Addr:   $GOVERNANCE_ADDR"
fi

if [ -z "$VERIFIER_ADDR" ]; then
    echo "[-] ERROR: VERIFIER_ADDR is not set."
    ERRORS=$((ERRORS + 1))
else
    echo "[+] Verifier Addr:     $VERIFIER_ADDR"
fi

# 3. Check Deployer Keystore / Account & Address Match
if [ -z "$DEPLOYER_ADDR" ]; then
    echo "[-] ERROR: DEPLOYER_ADDR is not set."
    ERRORS=$((ERRORS + 1))
fi

if [ -n "$DEPLOYER_ACCOUNT" ]; then
    echo "[+] Deployer Account:  $DEPLOYER_ACCOUNT (Foundry keystore)"
    KEYSTORE_PATH="$HOME/.foundry/keystores/$DEPLOYER_ACCOUNT"
    if [ -f "$KEYSTORE_PATH" ]; then
        echo "[+] Keystore File:     Found at $KEYSTORE_PATH"
    fi

    RESOLVED_ADDR=""
    if [ -n "$ETH_KEYSTORE_PASSWORD" ] && command -v cast &>/dev/null; then
        RESOLVED_ADDR=$(cast wallet address --account "$DEPLOYER_ACCOUNT" --password "$ETH_KEYSTORE_PASSWORD" 2>/dev/null || true)
    elif [ "$1" = "--interactive" ] && command -v cast &>/dev/null; then
        RESOLVED_ADDR=$(cast wallet address --account "$DEPLOYER_ACCOUNT" 2>/dev/null || true)
    fi

    if [ -n "$RESOLVED_ADDR" ]; then
        if [ "${RESOLVED_ADDR,,}" = "${DEPLOYER_ADDR,,}" ]; then
            echo "[+] Keystore Address:  $RESOLVED_ADDR matches DEPLOYER_ADDR"
        else
            echo "[-] ERROR: Keystore account '$DEPLOYER_ACCOUNT' resolved to $RESOLVED_ADDR, does not match DEPLOYER_ADDR $DEPLOYER_ADDR"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "[+] Keystore Account:  $DEPLOYER_ACCOUNT configured for deployer $DEPLOYER_ADDR"
    fi
else
    echo "[!] INFO: DEPLOYER_ACCOUNT not set in env; using DEPLOYER_ADDR: $DEPLOYER_ADDR"
fi

# 4. Check Deployer Balance
if [ -n "$DEPLOYER_ADDR" ] && [ -n "$RPC_URL" ]; then
    DEPLOYER_BAL_ETH=""
    if command -v cast &>/dev/null; then
        DEPLOYER_BAL_ETH=$(cast balance --ether "$DEPLOYER_ADDR" --rpc-url "$RPC_URL" 2>/dev/null || true)
    fi
    if [ -z "$DEPLOYER_BAL_ETH" ]; then
        DEPLOYER_BAL_ETH=$(uv run --project "$REPO_ROOT/backend" python -c "
from web3 import Web3
try:
    w3 = Web3(Web3.HTTPProvider('$RPC_URL'))
    bal = w3.eth.get_balance(Web3.to_checksum_address('$DEPLOYER_ADDR'))
    print(float(Web3.from_wei(bal, 'ether')))
except Exception:
    pass
" 2>/dev/null || true)
    fi

    if [ -n "$DEPLOYER_BAL_ETH" ]; then
        echo "[+] Deployer Balance:  $DEPLOYER_BAL_ETH ETH (Required: >= $REQUIRED_BALANCE_ETH ETH)"
        IS_SUFFICIENT=$(uv run --project "$REPO_ROOT/backend" python -c "print(1 if float('$DEPLOYER_BAL_ETH') >= float('$REQUIRED_BALANCE_ETH') else 0)" 2>/dev/null || echo "0")
        if [ "$IS_SUFFICIENT" -eq 1 ]; then
            echo "[+] Balance Check:     PASSED"
        else
            echo "[-] ERROR: Deployer balance ($DEPLOYER_BAL_ETH ETH) is below required $REQUIRED_BALANCE_ETH ETH for deployment gas."
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "[!] WARNING: Could not query deployer balance from RPC."
    fi
fi

echo "================================================================================"
if [ "$ERRORS" -eq 0 ]; then
    echo "STATUS: PREFLIGHT PASSED. Ready to run DeployProof.s.sol broadcast."
    echo ""
    echo "EXACT BROADCAST COMMAND TO RUN (Manual Broadcast Step):"
    echo "  cd contracts && forge script script/DeployProof.s.sol \\"
    echo "    --rpc-url \"$RPC_URL\" \\"
    echo "    --account \"${DEPLOYER_ACCOUNT:-amoy-deployer}\" \\"
    echo "    --broadcast"
    echo "================================================================================"
    exit 0
else
    echo "STATUS: PREFLIGHT FAILED with $ERRORS error(s). Please resolve blockers above."
    echo "================================================================================"
    exit 1
fi
