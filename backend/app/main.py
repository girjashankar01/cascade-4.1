"""DAO Accountability Engine FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.routes import router as api_router
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


app = FastAPI(title="DAO Accountability Engine", version="0.2.0", lifespan=lifespan)

# Register API routes
app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, object]:
    from app.chain.client import get_web3, DEFAULT_RPC_URL
    rpc_connected = False
    chain_id = None
    block_number = None
    try:
        w3 = get_web3()
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
        "rpc_url": DEFAULT_RPC_URL,
    }
