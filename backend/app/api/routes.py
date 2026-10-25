"""FastAPI route implementations for Stage 2 evidence ingestion, analysis, and auditing."""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel

from app.claims.conflicts import detect_conflicts
from app.claims.ground import validate_and_ground_claim
from app.claims.schema import AnalysisResponse, Claim, ClaimStatus, Conflict
from app.db import get_db_connection, init_db
from app.ingestion.pdf import (
    EmptyDocumentError,
    IngestionError,
    MalformedDocumentError,
    UnsupportedFormatError,
    ingest_source,
)
from app.llm.base import LLMUnavailableError
from app.llm.router import LLMRouter

logger = logging.getLogger(__name__)

router = APIRouter()

# Global router instance, can be overridden in tests
_llm_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _llm_router
    if _llm_router is None:
        _llm_router = LLMRouter()
    return _llm_router


def set_llm_router(custom_router: Optional[LLMRouter]) -> None:
    global _llm_router
    _llm_router = custom_router


class PasteSourcePayload(BaseModel):
    content: str
    filename: Optional[str] = "pasted_source.txt"
    content_type: Optional[str] = "text/plain"


class AnalyzePayload(BaseModel):
    source_ids: Optional[List[str]] = None
    prompt: Optional[str] = "Extract factual payout claims with verbatim quotes."


@router.post("/sources", status_code=status.HTTP_201_CREATED)
async def upload_or_paste_source(
    request: Request,
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = Form(None),
    filename: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Ingest a proposal PDF file upload or plain-text content."""
    # Ensure database initialized
    init_db()

    raw_bytes: bytes = b""
    fname: str = "uploaded_source"
    ctype: Optional[str] = None

    if file is not None:
        raw_bytes = await file.read()
        fname = file.filename or "uploaded_source"
        ctype = file.content_type
    elif content is not None:
        raw_bytes = content.encode("utf-8")
        fname = filename or "pasted_source.txt"
        ctype = "text/plain"
    else:
        # Check if request has JSON body
        try:
            body = await request.json()
            if isinstance(body, dict) and "content" in body:
                raw_bytes = str(body["content"]).encode("utf-8")
                fname = body.get("filename", "pasted_source.txt")
                ctype = body.get("content_type", "text/plain")
        except Exception:
            pass

    if not raw_bytes or not raw_bytes.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source content or uploaded file cannot be empty",
        )

    try:
        source_meta = ingest_source(raw_bytes=raw_bytes, filename=fname, content_type=ctype)
        return {
            "source_id": source_meta["id"],
            "sha256": source_meta["sha256"],
            "filename": source_meta["filename"],
            "content_type": source_meta["content_type"],
            "page_count": source_meta["page_count"],
            "ocr_used": source_meta["ocr_used"],
            "created_at": source_meta["created_at"],
        }
    except EmptyDocumentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except MalformedDocumentError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/analyze/{pid}", response_model=AnalysisResponse)
def analyze_proposal(pid: str, payload: Optional[AnalyzePayload] = None) -> AnalysisResponse:
    """Run LLM extraction, deterministic text grounding, and cross-source conflict detection."""
    init_db()
    llm_router = get_llm_router()
    requested_ids = payload.source_ids if payload and payload.source_ids else None
    prompt = payload.prompt if payload and payload.prompt else "Extract factual payout claims with verbatim quotes."

    # 1. Fetch sources from database
    sources: List[Dict[str, Any]] = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if requested_ids:
            placeholders = ",".join(["?"] * len(requested_ids))
            cursor.execute(f"SELECT * FROM sources WHERE id IN ({placeholders})", requested_ids)
        else:
            cursor.execute("SELECT * FROM sources ORDER BY created_at ASC")

        for row in cursor.fetchall():
            sources.append(
                {
                    "id": row["id"],
                    "sha256": row["sha256"],
                    "filename": row["filename"],
                    "content_type": row["content_type"],
                    "page_count": row["page_count"],
                    "extracted_pages": json.loads(row["extracted_pages"]),
                    "ocr_used": bool(row["ocr_used"]),
                }
            )

    if not sources:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No matching sources found for analysis of proposal '{pid}'",
        )

    # 2. Extract candidate claims via LLM Router
    try:
        raw_claims, cache_status = llm_router.analyze_sources(proposal_id=pid, sources=sources, prompt=prompt)
    except LLMUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "LLM_UNAVAILABLE", "message": str(e)},
        ) from e

    # 3. Ground and validate each claim
    sources_map = {s["id"]: s for s in sources}
    grounded_claims: List[Claim] = []
    for idx, raw in enumerate(raw_claims, start=1):
        claim = validate_and_ground_claim(
            raw=raw,
            proposal_id=pid,
            sources_map=sources_map,
            claim_index=idx,
        )
        grounded_claims.append(claim)

    # 4. Deterministic conflict detection
    conflicts, final_claims = detect_conflicts(grounded_claims, proposal_id=pid)

    # Overall proposal analysis status:
    # If any conflicts or uncertain claims exist -> UNCERTAIN, else SUCCESS
    analysis_status = "SUCCESS"
    if conflicts or any(c.status == ClaimStatus.UNCERTAIN for c in final_claims):
        analysis_status = "UNCERTAIN"

    # 5. Persist claims and conflicts to SQLite
    with get_db_connection() as conn:
        # Clear existing claims and conflicts for this proposal to keep fresh
        conn.execute("DELETE FROM claims WHERE proposal_id = ?", (pid,))
        conn.execute("DELETE FROM conflicts WHERE proposal_id = ?", (pid,))

        for c in final_claims:
            conn.execute(
                """
                INSERT INTO claims (id, proposal_id, field, value, display_value, quote, source_id, page, confidence, status, validation_details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    c.id,
                    c.proposal_id,
                    c.field,
                    c.value,
                    c.display_value,
                    c.quote,
                    c.source_id,
                    c.page,
                    c.confidence,
                    c.status.value,
                    json.dumps(c.validation_details),
                ),
            )

        for conf in conflicts:
            conn.execute(
                """
                INSERT INTO conflicts (id, proposal_id, field, value_a, display_value_a, source_id_a, quote_a, page_a, value_b, display_value_b, source_id_b, quote_b, page_b, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    conf.id,
                    conf.proposal_id,
                    conf.field,
                    conf.value_a,
                    conf.display_value_a,
                    conf.source_id_a,
                    conf.quote_a,
                    conf.page_a,
                    conf.value_b,
                    conf.display_value_b,
                    conf.source_id_b,
                    conf.quote_b,
                    conf.page_b,
                    conf.status,
                ),
            )

    model_name = getattr(llm_router.provider, "model", "default")
    return AnalysisResponse(
        proposal_id=pid,
        status=analysis_status,
        claims=final_claims,
        conflicts=conflicts,
        provider=llm_router.provider.name,
        model=model_name,
        cache_status=cache_status,
        summary=f"Extracted {len(final_claims)} claims with {len(conflicts)} conflict(s).",
    )


@router.get("/claims/{pid}", response_model=Dict[str, Any])
def get_claims_for_proposal(pid: str) -> Dict[str, Any]:
    """Return all persisted claims and unresolved conflicts for a proposal."""
    init_db()
    claims: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM claims WHERE proposal_id = ? ORDER BY id ASC", (pid,))
        for row in cursor.fetchall():
            claims.append(
                {
                    "id": row["id"],
                    "proposal_id": row["proposal_id"],
                    "field": row["field"],
                    "value": row["value"],
                    "display_value": row["display_value"],
                    "quote": row["quote"],
                    "source_id": row["source_id"],
                    "page": row["page"],
                    "confidence": row["confidence"],
                    "status": row["status"],
                    "validation_details": json.loads(row["validation_details"]),
                }
            )

        cursor.execute("SELECT * FROM conflicts WHERE proposal_id = ? ORDER BY id ASC", (pid,))
        for row in cursor.fetchall():
            conflicts.append(
                {
                    "id": row["id"],
                    "proposal_id": row["proposal_id"],
                    "field": row["field"],
                    "value_a": row["value_a"],
                    "display_value_a": row["display_value_a"],
                    "source_id_a": row["source_id_a"],
                    "quote_a": row["quote_a"],
                    "page_a": row["page_a"],
                    "value_b": row["value_b"],
                    "display_value_b": row["display_value_b"],
                    "source_id_b": row["source_id_b"],
                    "quote_b": row["quote_b"],
                    "page_b": row["page_b"],
                    "status": row["status"],
                }
            )

    return {
        "proposal_id": pid,
        "claims": claims,
        "conflicts": conflicts,
    }


@router.get("/audit/{pid}", response_model=List[Dict[str, Any]])
def get_audit_trail(pid: str) -> List[Dict[str, Any]]:
    """Return all analysis audit records for a proposal."""
    init_db()
    records: List[Dict[str, Any]] = []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analyses WHERE proposal_id = ? ORDER BY created_at DESC", (pid,))
        for row in cursor.fetchall():
            records.append(
                {
                    "id": row["id"],
                    "proposal_id": row["proposal_id"],
                    "status": row["status"],
                    "source_ids": json.loads(row["source_ids"]),
                    "source_hashes": json.loads(row["source_hashes"]),
                    "provider": row["provider"],
                    "model": row["model"],
                    "prompt_hash": row["prompt_hash"],
                    "input_hash": row["input_hash"],
                    "latency_ms": row["latency_ms"],
                    "cache_status": row["cache_status"],
                    "fallback_used": bool(row["fallback_used"]),
                    "error_code": row["error_code"],
                    "error_message": row["error_message"],
                    "rule_set_version": row["rule_set_version"],
                    "created_at": row["created_at"],
                }
            )

    return records
