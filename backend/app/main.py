"""DAO Accountability Engine FastAPI application entry point."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.paths import load_env_hierarchy

# Load environment hierarchy at import time
load_env_hierarchy()

from app.api.routes import router as api_router
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()

    chain_mode = os.environ.get("CHAIN_MODE", "").lower()
    if chain_mode == "proof":
        expected_chain_id = int(os.environ.get("CHAIN_ID", 11155111))
        rpc_url = os.environ.get("AMOY_RPC") or os.environ.get("RPC_URL_PROOF")
        if not rpc_url:
            raise RuntimeError("CHAIN_MODE=proof requires AMOY_RPC or RPC_URL_PROOF in environment")
        from app.chain.client import get_web3
        w3 = get_web3(rpc_url)
        if not w3.is_connected():
            raise RuntimeError(f"CHAIN_MODE=proof cannot connect to RPC endpoint: {rpc_url}")
        actual_chain_id = w3.eth.chain_id
        if actual_chain_id != expected_chain_id:
            raise RuntimeError(
                f"CHAIN_MODE=proof configuration error: Connected RPC chain ID {actual_chain_id} "
                f"does not match expected CHAIN_ID {expected_chain_id}."
            )
    yield


app = FastAPI(title="DAO Accountability Engine", version="0.2.0", lifespan=lifespan)

# Enable CORS for local development and UI integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, object]:
    from app.chain.client import get_web3, DEFAULT_RPC_URL
    chain_mode = os.environ.get("CHAIN_MODE", "").lower()
    target_rpc = (os.environ.get("AMOY_RPC") or os.environ.get("RPC_URL_PROOF")) if chain_mode == "proof" else DEFAULT_RPC_URL

    rpc_connected = False
    chain_id = None
    block_number = None
    try:
        w3 = get_web3(target_rpc)
        if w3.is_connected():
            rpc_connected = True
            chain_id = w3.eth.chain_id
            block_number = w3.eth.block_number
    except Exception:
        rpc_connected = False

    return {
        "status": "ok",
        "rpc_connected": rpc_connected,
        "chain_id": chain_id,
        "block_number": block_number,
        "rpc_url": target_rpc,
    }
