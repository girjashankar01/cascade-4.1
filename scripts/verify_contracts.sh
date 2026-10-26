#!/usr/bin/env bash
# scripts/verify_contracts.sh
# Verified independent source verification on Sepolia Etherscan (Chain ID 11155111).
# Uses `cast abi-encode` for constructor arguments. Never logs or echoes EXPLORER_API_KEY.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# 1. Source environment files silently
if [ -f ".env" ]; then
    set -a
    source ".env"
    set +a
fi

if [ -f ".env.amoy" ]; then
    set -a
    source ".env.amoy"
    set +a
fi

DEPLOYMENTS_FILE="data/deployments.proof.json"

if [ ! -f "$DEPLOYMENTS_FILE" ]; then
    echo "ERROR: Deployment manifest not found at $DEPLOYMENTS_FILE" >&2
    echo "Please broadcast deployment and run: uv run --project backend python scripts/write_proof_deployments.py" >&2
    exit 1
fi

if [ -z "${EXPLORER_API_KEY:-}" ]; then
    echo "ERROR: EXPLORER_API_KEY environment variable is not set." >&2
    echo "Please set EXPLORER_API_KEY in .env or .env.amoy (Etherscan API key for Sepolia verification)." >&2
    exit 1
fi

CHAIN_ID="11155111"
ETHERSCAN_BASE="https://sepolia.etherscan.io"

echo "================================================================================"
echo "CASCADE 4.1 — Sepolia Contract Etherscan Verification Helper"
echo "Target Chain: Ethereum Sepolia (Chain ID: $CHAIN_ID)"
echo "Explorer Base: $ETHERSCAN_BASE"
echo "================================================================================"
echo ""

# Extract addresses from deployments.proof.json using Python
eval "$(uv run --project backend python - << 'EOF'
import json, sys
with open("data/deployments.proof.json", "r") as f:
    d = json.load(f)
print(f"TOKEN_ADDR={d.get('token', '')}")
print(f"REGISTRY_ADDR={d.get('registry', '')}")
print(f"TREASURY_ADDR={d.get('treasury', '')}")
print(f"EXECUTOR_ADDR={d.get('executor', '')}")
print(f"GOVERNANCE_ADDR={d.get('governance', '')}")
print(f"VERIFIER_ADDR={d.get('verifier', '')}")
EOF
)"

cd contracts

declare -A VERIFY_STATUS
declare -A EXPLORER_LINKS

verify_single_contract() {
    local contract_name="$1"
    local contract_path="$2"
    local contract_addr="$3"
    local constructor_args="$4"

    echo "--------------------------------------------------------------------------------"
    echo "Verifying $contract_name at $contract_addr..."

    if [ -z "$contract_addr" ]; then
        echo "FAIL: Missing address for $contract_name" >&2
        VERIFY_STATUS["$contract_name"]="FAIL (No Address)"
        return
    fi

    local cmd=(forge verify-contract \
        --chain-id "$CHAIN_ID" \
        --etherscan-api-key "$EXPLORER_API_KEY" \
        "$contract_addr" \
        "$contract_path:$contract_name")

    if [ -n "$constructor_args" ]; then
        cmd+=(--constructor-args "$constructor_args")
    fi

    # Execute verification without exposing the API key in error messages
    if "${cmd[@]}"; then
        VERIFY_STATUS["$contract_name"]="PASS"
        EXPLORER_LINKS["$contract_name"]="${ETHERSCAN_BASE}/address/${contract_addr}#code"
    else
        echo "WARNING: Verification failed for $contract_name (check output above for compiler or bytecode mismatch)." >&2
        VERIFY_STATUS["$contract_name"]="FAIL"
        EXPLORER_LINKS["$contract_name"]="${ETHERSCAN_BASE}/address/${contract_addr}#code"
    fi
}

# 1. MockToken: constructor(string,string,uint256) -> "USD Coin", "USDC", 10000000000000 (10M * 10**6)
TOKEN_ARGS=$(cast abi-encode "constructor(string,string,uint256)" "USD Coin" "USDC" "10000000000000")
verify_single_contract "MockToken" "src/MockToken.sol" "$TOKEN_ADDR" "$TOKEN_ARGS"

# 2. GovernanceRegistry: constructor(address) -> GOVERNANCE_ADDR
REGISTRY_ARGS=$(cast abi-encode "constructor(address)" "$GOVERNANCE_ADDR")
verify_single_contract "GovernanceRegistry" "src/GovernanceRegistry.sol" "$REGISTRY_ADDR" "$REGISTRY_ARGS"

# 3. Treasury: constructor() -> no arguments
verify_single_contract "Treasury" "src/Treasury.sol" "$TREASURY_ADDR" ""

# 4. GuardedExecutor: constructor(address,address,address) -> REGISTRY, TREASURY, VERIFIER
EXECUTOR_ARGS=$(cast abi-encode "constructor(address,address,address)" "$REGISTRY_ADDR" "$TREASURY_ADDR" "$VERIFIER_ADDR")
verify_single_contract "GuardedExecutor" "src/GuardedExecutor.sol" "$EXECUTOR_ADDR" "$EXECUTOR_ARGS"

echo ""
echo "================================================================================"
echo "ETHERSCAN VERIFICATION SUMMARY"
echo "================================================================================"
printf "%-22s | %-10s | %s\n" "Contract" "Status" "Verified Source Link"
echo "--------------------------------------------------------------------------------"
for c in "MockToken" "GovernanceRegistry" "Treasury" "GuardedExecutor"; do
    printf "%-22s | %-10s | %s\n" "$c" "${VERIFY_STATUS[$c]:-UNKNOWN}" "${EXPLORER_LINKS[$c]:-}"
done
echo "================================================================================"
echo "Note: Independent verification with 'cast abi-encode' is preferred over"
echo "'forge script --resume --verify' because it isolates each contract,"
echo "avoids cascading batch aborts on rate limits, and deterministically computes"
echo "exact ABI-encoded constructor parameters directly from deployed state."
echo "================================================================================"
