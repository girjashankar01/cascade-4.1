#!/usr/bin/env bash
set -euo pipefail

# Directory paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DATA_DIR="$REPO_ROOT/data"
STATE_FILE="$DATA_DIR/anvil_state.json"

mkdir -p "$DATA_DIR"

ANVIL_ARGS=(
  --host 127.0.0.1
  --port 8545
  --chain-id 31337
  --dump-state "$STATE_FILE"
)

if [ -f "$STATE_FILE" ]; then
  echo "[start_anvil] State file found at $STATE_FILE. Loading persisted state..."
  ANVIL_ARGS+=(--load-state "$STATE_FILE")
else
  echo "[start_anvil] No previous state file found at $STATE_FILE. Starting clean state..."
fi

echo "[start_anvil] Launching Anvil on 127.0.0.1:8545 (Chain ID: 31337)..."
exec anvil "${ANVIL_ARGS[@]}"
