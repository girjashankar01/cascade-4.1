"""Read the local chain only. Run: cd backend; uv run python ../scripts/check_chain.py."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from web3 import Web3

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
rpc_url = os.getenv("RPC_URL", "http://127.0.0.1:8545")
if urlsplit(rpc_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
    raise SystemExit("Stage 0 connectivity check requires a loopback RPC_URL.")

chain = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 5}))
if not chain.is_connected():
    raise SystemExit("Local RPC unavailable. Start Anvil, then retry this command.")
print(f"block_number={chain.eth.block_number}")
