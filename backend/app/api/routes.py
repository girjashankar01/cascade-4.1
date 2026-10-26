"""FastAPI route implementations for Stage 2 evidence ingestion, analysis, and auditing."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
from app.manifest.builder import (
    EligibilityError,
    ManifestError,
    TamperError,
    build_manifest_draft,
    confirm_manifest_with_signature,
    verify_manifest_integrity,
)
from app.chain.client import (
    PK_GOVERNANCE,
    PK_PROPOSER,
    PK_VERIFIER,
    approve_version_onchain,
    commit_version_onchain,
    get_onchain_approved,
    get_onchain_version,
    get_web3,
    load_artifact,
    proposal_id_to_bytes32,
)
from app.chain.attest import compute_action_hash, recover_attestation_signer, VERIFIED
from app.chain.public import call_with_rpc_retry
from app.paths import (
    DEPLOYMENTS_LOCAL_PATH,
    DEPLOYMENTS_PROOF_PATH,
    DRYRUN_JSON_PATH,
    PROOF_JSON_PATH,
)
from app.verification.verify import verify_proposal_transaction, VERDICT_VERIFIED
from eth_account import Account
from web3 import Web3

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory short caches (5s TTL) for read RPC endpoints
_CHAIN_STATUS_CACHE: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}
_CHAIN_BALANCES_CACHE: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 5.0


def reset_chain_cache() -> None:
    """Clear in-memory chain status and balance caches (used for tests)."""
    _CHAIN_STATUS_CACHE.clear()
    _CHAIN_BALANCES_CACHE.clear()

# Global router instance, can be overridden in tests
_llm_router: Optional[LLMRouter] = None


def get_llm_router() -> LLMRouter:
    global _llm_router
    if _llm_router is not None:
        return _llm_router
    return LLMRouter()


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


class DraftManifestPayload(BaseModel):
    token_address: str
    token_decimals: Optional[int] = 6
    version: Optional[int] = 1
    proposal_text: Optional[str] = None
    source_id: Optional[str] = None
    prev_version_hash: Optional[str] = None


class ConfirmManifestPayload(BaseModel):
    token_address: str
    token_decimals: Optional[int] = 6
    version: Optional[int] = 1
    proposer_private_key: Optional[str] = None
    proposal_text: Optional[str] = None
    source_id: Optional[str] = None
    prev_version_hash: Optional[str] = None


class CommitVersionPayload(BaseModel):
    version: Optional[int] = None
    registry_address: Optional[str] = None
    proposer_private_key: Optional[str] = None
    rpc_url: Optional[str] = None


class ApproveVersionPayload(BaseModel):
    version: Optional[int] = None
    registry_address: Optional[str] = None
    governance_private_key: Optional[str] = None
    rpc_url: Optional[str] = None


class VerifyVersionPayload(BaseModel):
    version: Optional[int] = None
    manifest_dict: Optional[Dict[str, Any]] = None
    proposal_text: Optional[str] = None
    evidence_hashes: Optional[List[str]] = None
    registry_address: Optional[str] = None
    rpc_url: Optional[str] = None


class VerifyPayload(BaseModel):
    proposal_id: Optional[str] = None
    target: str
    value: Optional[int] = 0
    data: str
    registry_address: Optional[str] = None
    treasury_address: Optional[str] = None
    executor_address: Optional[str] = None
    verifier_private_key: Optional[str] = None
    ttl_seconds: Optional[int] = 3600
    rpc_url: Optional[str] = None


class ExecutePayload(BaseModel):
    proposal_id: Optional[str] = None
    target: str
    value: Optional[int] = 0
    data: str
    verdict: Optional[int] = 1
    deadline: Optional[int] = None
    signature: Optional[str] = None
    executor_address: Optional[str] = None
    registry_address: Optional[str] = None
    caller_private_key: Optional[str] = None
    rpc_url: Optional[str] = None


class ScenarioRunPayload(BaseModel):
    rpc_url: Optional[str] = None
    reset_first: Optional[bool] = False


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
                    "extracted_pages": json.loads(row["extracted_pages"]) if row["extracted_pages"] else {},
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

        cursor.execute(
            "SELECT cache_status FROM analyses WHERE proposal_id = ? ORDER BY created_at DESC LIMIT 1",
            (pid,),
        )
        latest_analysis = cursor.fetchone()
        cache_status = latest_analysis["cache_status"] if latest_analysis else "generated"

    return {
        "proposal_id": pid,
        "claims": claims,
        "conflicts": conflicts,
        "cache_status": cache_status,
    }


@router.get("/proposals/{pid}/coi", response_model=Dict[str, Any])
def get_proposal_coi_endpoint(pid: str) -> Dict[str, Any]:
    """Return Conflict-of-Interest (COI) wallet provenance and linkage graph analysis."""
    if not pid or not pid.strip():
        raise HTTPException(status_code=400, detail="Invalid proposal ID")
    from app.claims.coi import get_proposal_coi_analysis
    try:
        report = get_proposal_coi_analysis(proposal_id=pid)
        return report.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@router.post("/manifest/{pid}")
def draft_manifest(pid: str, payload: DraftManifestPayload) -> Dict[str, Any]:
    """Draft a canonical manifest from confirmed, conflict-free claims."""
    init_db()
    try:
        draft = build_manifest_draft(
            proposal_id=pid,
            token_address=payload.token_address,
            token_decimals=payload.token_decimals or 6,
            version=payload.version or 1,
            proposal_text=payload.proposal_text,
            source_id=payload.source_id,
            prev_version_hash=payload.prev_version_hash,
        )
        return draft
    except EligibilityError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "ELIGIBILITY_ERROR", "message": str(e)},
        ) from e
    except Exception as e:
        logger.error(f"Failed to draft manifest for '{pid}': {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/manifest/{pid}/confirm")
def confirm_manifest(pid: str, payload: ConfirmManifestPayload) -> Dict[str, Any]:
    """Confirm drafted manifest and sign versionHash with proposer key."""
    init_db()
    proposer_pk = payload.proposer_private_key or PK_PROPOSER
    try:
        confirmed = confirm_manifest_with_signature(
            proposal_id=pid,
            version=payload.version or 1,
            proposer_private_key=proposer_pk,
            token_address=payload.token_address,
            token_decimals=payload.token_decimals or 6,
            proposal_text=payload.proposal_text,
            source_id=payload.source_id,
            prev_version_hash=payload.prev_version_hash,
        )
        return confirmed
    except EligibilityError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "ELIGIBILITY_ERROR", "message": str(e)},
        ) from e
    except Exception as e:
        logger.error(f"Failed to confirm manifest for '{pid}': {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/manifest/{pid}")
def get_latest_manifest(pid: str, version: Optional[int] = None) -> Dict[str, Any]:
    """Fetch the latest confirmed manifest for a proposal."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if version is not None:
            cursor.execute(
                "SELECT * FROM manifests WHERE proposal_id = ? AND version = ?",
                (pid, version),
            )
        else:
            cursor.execute(
                "SELECT * FROM manifests WHERE proposal_id = ? ORDER BY version DESC LIMIT 1",
                (pid,),
            )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No manifest found for proposal '{pid}'",
        )

    return {
        "manifest_id": row["id"],
        "proposal_id": row["proposal_id"],
        "version": row["version"],
        "version_hash": row["version_hash"],
        "action_hash": row["action_hash"],
        "proposal_text_hash": row["proposal_text_hash"],
        "evidence_root": row["evidence_root"],
        "prev_version_hash": row["prev_version_hash"],
        "proposer_address": row["proposer_address"],
        "proposer_signature": row["proposer_signature"],
        "canonical_json": row["canonical_json"],
        "manifest": json.loads(row["manifest_dict"]),
        "status": row["status"],
        "confirmed_at": row["confirmed_at"],
    }


@router.post("/commit/{pid}")
def commit_version(pid: str, payload: Optional[CommitVersionPayload] = None) -> Dict[str, Any]:
    """Commit a manifest version to GovernanceRegistry on-chain and record in database."""
    init_db()
    target_version = payload.version if payload and payload.version else None
    registry_address = payload.registry_address if payload else None
    proposer_pk = (payload.proposer_private_key if payload and payload.proposer_private_key else None) or PK_PROPOSER
    rpc_url = payload.rpc_url if payload else None

    # 1. Fetch manifest record from database
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if target_version is not None:
            cursor.execute(
                "SELECT * FROM manifests WHERE proposal_id = ? AND version = ?",
                (pid, target_version),
            )
        else:
            cursor.execute(
                "SELECT * FROM manifests WHERE proposal_id = ? ORDER BY version DESC LIMIT 1",
                (pid,),
            )
        manifest_row = cursor.fetchone()

    if not manifest_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No confirmed manifest found for proposal '{pid}' to commit",
        )

    m = dict(manifest_row)
    ver = m["version"]
    vhash = m["version_hash"]
    ahash = m["action_hash"]
    eroot = m["evidence_root"]
    prev_vhash = m["prev_version_hash"]

    commit_tx_hash = None
    commit_block_number = None
    onchain_verified = False

    # 2. Call on-chain if registry address provided
    if registry_address:
        try:
            chain_res = commit_version_onchain(
                registry_address=registry_address,
                proposal_id=pid,
                version_hash=vhash,
                action_hash=ahash,
                evidence_root=eroot,
                proposer_key=proposer_pk,
                rpc_url=rpc_url,
            )
            commit_tx_hash = chain_res["tx_hash"]
            commit_block_number = chain_res["block_number"]
            onchain_verified = True
        except Exception as e:
            logger.error(f"On-chain commitVersion failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"On-chain commitVersion reverted: {e}",
            ) from e

    # 3. Record in versions table
    version_id = f"ver_{pid}_{ver}"
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO versions (
                id, proposal_id, version, version_hash, action_hash, evidence_root,
                prev_version_hash, commit_tx_hash, commit_block_number, committed_at,
                onchain_verified, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, datetime('now'))
            """,
            (
                version_id,
                pid,
                ver,
                vhash,
                ahash,
                eroot,
                prev_vhash,
                commit_tx_hash,
                commit_block_number,
                1 if onchain_verified else 0,
            ),
        )

    return {
        "version_id": version_id,
        "proposal_id": pid,
        "version": ver,
        "version_hash": vhash,
        "action_hash": ahash,
        "evidence_root": eroot,
        "prev_version_hash": prev_vhash,
        "commit_tx_hash": commit_tx_hash,
        "commit_block_number": commit_block_number,
        "onchain_verified": onchain_verified,
        "status": "COMMITTED",
    }


@router.post("/approve/{pid}")
def approve_version(pid: str, payload: Optional[ApproveVersionPayload] = None) -> Dict[str, Any]:
    """Governance approves the latest committed version for execution."""
    init_db()
    target_version = payload.version if payload and payload.version else None
    registry_address = payload.registry_address if payload else None
    governance_pk = (payload.governance_private_key if payload and payload.governance_private_key else None) or PK_GOVERNANCE
    rpc_url = payload.rpc_url if payload else None

    # Fetch committed version
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if target_version is not None:
            cursor.execute(
                "SELECT * FROM versions WHERE proposal_id = ? AND version = ?",
                (pid, target_version),
            )
        else:
            cursor.execute(
                "SELECT * FROM versions WHERE proposal_id = ? ORDER BY version DESC LIMIT 1",
                (pid,),
            )
        vrow = cursor.fetchone()

    if not vrow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No committed version found for proposal '{pid}' to approve",
        )

    ver = vrow["version"]
    vhash = vrow["version_hash"]
    approve_tx_hash = None
    approve_block_number = None

    if registry_address:
        try:
            chain_res = approve_version_onchain(
                registry_address=registry_address,
                proposal_id=pid,
                version_hash=vhash,
                governance_key=governance_pk,
                rpc_url=rpc_url,
            )
            approve_tx_hash = chain_res["tx_hash"]
            approve_block_number = chain_res["block_number"]
        except Exception as e:
            logger.error(f"On-chain approve failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"On-chain approve reverted: {e}",
            ) from e

    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE versions
            SET approve_tx_hash = ?, approve_block_number = ?, approved_at = datetime('now')
            WHERE proposal_id = ? AND version = ?
            """,
            (approve_tx_hash, approve_block_number, pid, ver),
        )

    return {
        "proposal_id": pid,
        "version": ver,
        "version_hash": vhash,
        "approve_tx_hash": approve_tx_hash,
        "approve_block_number": approve_block_number,
        "status": "APPROVED",
    }


@router.get("/versions/{pid}")
def get_version_chain(pid: str) -> List[Dict[str, Any]]:
    """Return complete version history and approval status for a proposal."""
    init_db()
    records: List[Dict[str, Any]] = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM versions WHERE proposal_id = ? ORDER BY version ASC",
            (pid,),
        )
        for row in cursor.fetchall():
            records.append(
                {
                    "id": row["id"],
                    "proposal_id": row["proposal_id"],
                    "version": row["version"],
                    "version_hash": row["version_hash"],
                    "action_hash": row["action_hash"],
                    "evidence_root": row["evidence_root"],
                    "prev_version_hash": row["prev_version_hash"],
                    "commit_tx_hash": row["commit_tx_hash"],
                    "commit_block_number": row["commit_block_number"],
                    "committed_at": row["committed_at"],
                    "approve_tx_hash": row["approve_tx_hash"],
                    "approve_block_number": row["approve_block_number"],
                    "approved_at": row["approved_at"],
                    "onchain_verified": bool(row["onchain_verified"]),
                    "is_approved": bool(row["approved_at"]),
                }
            )
    return records


@router.post("/verify-version/{pid}")
def verify_version(pid: str, payload: Optional[VerifyVersionPayload] = None) -> Dict[str, Any]:
    """Verify integrity of a committed manifest version against tampering."""
    init_db()
    ver = payload.version if payload and payload.version else 1
    m_dict = payload.manifest_dict if payload else None
    p_text = payload.proposal_text if payload else None
    e_hashes = payload.evidence_hashes if payload else None
    reg_addr = payload.registry_address if payload else None
    rpc_url = payload.rpc_url if payload else None

    try:
        report = verify_manifest_integrity(
            proposal_id=pid,
            version=ver,
            manifest_dict=m_dict,
            proposal_text=p_text,
            evidence_hashes=e_hashes,
            registry_address=reg_addr,
            rpc_url=rpc_url,
        )
        return report
    except TamperError as e:
        return {
            "verified": False,
            "tamper_detected": True,
            "proposal_id": pid,
            "version": ver,
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"Integrity check failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/verify")
@router.post("/verify/{pid}")
def verify_transaction_endpoint(
    payload: VerifyPayload,
    pid: Optional[str] = None,
) -> Dict[str, Any]:
    """Run full verification pipeline: decode, simulate, evaluate deterministic rules, and attest."""
    init_db()
    proposal_id = pid or payload.proposal_id
    if not proposal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="proposal_id is required either in URL path or JSON payload",
        )

    if not payload.registry_address or not payload.treasury_address or not payload.executor_address:
        # Require deployment addresses for live verification
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="registry_address, treasury_address, and executor_address are required for verification",
        )

    report = verify_proposal_transaction(
        proposal_id=proposal_id,
        target=payload.target,
        value=payload.value or 0,
        data=payload.data,
        registry_address=payload.registry_address,
        treasury_address=payload.treasury_address,
        executor_address=payload.executor_address,
        verifier_private_key=payload.verifier_private_key or PK_VERIFIER,
        ttl_seconds=payload.ttl_seconds or 3600,
        rpc_url=payload.rpc_url,
    )

    return report.to_dict()


@router.post("/execute")
@router.post("/execute/{pid}")
def execute_proposal_endpoint(
    payload: ExecutePayload,
    pid: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a verified proposal transaction through GuardedExecutor with strict TOCTOU checks."""
    init_db()
    proposal_id = pid or payload.proposal_id
    if not proposal_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="proposal_id is required either in URL path or JSON payload",
        )

    if not payload.executor_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="executor_address is required for guarded execution",
        )

    w3 = get_web3(payload.rpc_url)
    executor_cs = Web3.to_checksum_address(payload.executor_address)
    executor_artifact = load_artifact("GuardedExecutor")
    executor = w3.eth.contract(address=executor_cs, abi=executor_artifact["abi"])

    # Resolve registry address from executor if not provided
    registry_addr = payload.registry_address or executor.functions.registry().call()
    registry_cs = Web3.to_checksum_address(registry_addr)
    registry_artifact = load_artifact("GovernanceRegistry")
    registry = w3.eth.contract(address=registry_cs, abi=registry_artifact["abi"])

    pid_b32 = proposal_id_to_bytes32(proposal_id)

    # ---------------------------------------------------------
    # Mandatory TOCTOU Protection Immediately Before Broadcast
    # ---------------------------------------------------------

    # 1. Check replay state on GuardedExecutor
    if executor.functions.executed(pid_b32).call():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proposal '{proposal_id}' has already been executed on-chain (replay blocked)",
        )

    # 2. Check live governance approval tuple on GovernanceRegistry
    app_vhash, app_ahash, app_eroot = registry.functions.approved(pid_b32).call()
    if app_vhash == b"\x00" * 32 or app_vhash == "0x" + "00" * 32:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Proposal '{proposal_id}' has no live active approval on GovernanceRegistry",
        )

    # 3. Check submitted calldata matches approved actionHash
    raw_data = bytes.fromhex(payload.data[2:] if payload.data.startswith("0x") else payload.data)
    computed_ahash = compute_action_hash(payload.target, payload.value or 0, raw_data)
    if computed_ahash != app_ahash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submitted transaction does not match on-chain approved actionHash",
        )

    # 4. Resolve attestation signature and deadline
    signature = payload.signature
    deadline = payload.deadline

    if not signature or deadline is None:
        # Fetch latest VERIFIED record from database
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT attestation_sig, deadline FROM verifications
                WHERE proposal_id = ? AND verdict = 'VERIFIED' AND executed = 0
                ORDER BY created_at DESC LIMIT 1
                """,
                (proposal_id,),
            )
            v_row = cursor.fetchone()

        if not v_row or not v_row["attestation_sig"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No VERIFIED attestation found for this proposal; cannot execute non-verified transaction",
            )
        signature = v_row["attestation_sig"]
        deadline = v_row["deadline"]

    # 5. Check deadline against current chain block timestamp
    latest_block = w3.eth.get_block("latest")
    if latest_block["timestamp"] > deadline:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Attestation has expired: current chain timestamp {latest_block['timestamp']} > deadline {deadline}",
        )

    # 6. Verify verifier signature
    chain_id = w3.eth.chain_id
    expected_verifier = executor.functions.verifier().call()
    try:
        recovered = recover_attestation_signer(
            proposal_id=pid_b32,
            version_hash=app_vhash,
            action_hash=app_ahash,
            evidence_root=app_eroot,
            verdict=VERIFIED,
            deadline=deadline,
            chain_id=chain_id,
            verifying_contract=executor.address,
            signature=signature,
        )
        if recovered.lower() != expected_verifier.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Attestation signature recovered to {recovered}, expected verifier {expected_verifier}",
            )
    except Exception as sig_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid attestation signature: {sig_err}",
        ) from sig_err

    # ---------------------------------------------------------
    # Broadcast through GuardedExecutor.execute(...)
    # ---------------------------------------------------------
    caller_pk = payload.caller_private_key or PK_PROPOSER
    caller_account = Account.from_key(caller_pk)
    sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)

    chain_mode = os.environ.get("CHAIN_MODE", "").lower()
    is_local_chain = True
    try:
        is_local_chain = w3.eth.chain_id in {31337, 1337}
    except Exception:
        is_local_chain = True

    is_proof_mode = (chain_mode == "proof") or (not is_local_chain)

    try:
        from app.chain.public import send_tx_1559, explorer_tx_url, get_explorer_base
        from app.db import record_chain_tx
        from datetime import datetime, timezone

        exec_fn = executor.functions.execute(
            pid_b32,
            Web3.to_checksum_address(payload.target),
            int(payload.value or 0),
            raw_data,
            VERIFIED,
            int(deadline),
            sig_bytes,
        )

        if is_proof_mode:
            res = send_tx_1559(w3, caller_pk, exec_fn, gas=3_000_000, wait_timeout=120)
            receipt = res["receipt"]
            tx_hash_hex = res["tx_hash"]
        else:
            tx = exec_fn.build_transaction(
                {
                    "from": caller_account.address,
                    "nonce": w3.eth.get_transaction_count(caller_account.address),
                    "gas": 3_000_000,
                    "gasPrice": w3.eth.gas_price,
                }
            )
            signed_tx = w3.eth.account.sign_transaction(tx, caller_pk)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=10)
            tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)

        # Record to chain_txs table
        effective_gp = getattr(receipt, "effectiveGasPrice", 0)
        fee_eth = float(Web3.from_wei(receipt.gasUsed * effective_gp, "ether")) if effective_gp else 0.0
        record_chain_tx({
            "run_id": f"exec_{proposal_id}",
            "step": "execute",
            "role": "executor",
            "from": caller_account.address,
            "to": executor.address,
            "tx_hash": tx_hash_hex if tx_hash_hex.startswith("0x") else "0x" + tx_hash_hex,
            "status": "success" if receipt.status == 1 else "reverted",
            "revert_reason": None,
            "block_number": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "effective_gas_price": effective_gp,
            "fee_eth": fee_eth,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "explorer_url": explorer_tx_url(tx_hash_hex, get_explorer_base(w3.eth.chain_id)),
        })
    except Exception as e:
        logger.error(f"On-chain execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GuardedExecutor.execute reverted: {e}",
        ) from e

    if receipt.status != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction mined with failure status 0",
        )

    # 7. Update database record
    tx_hash_str = receipt.transactionHash.hex() if hasattr(receipt.transactionHash, "hex") else str(receipt.transactionHash)
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE verifications
            SET executed = 1, tx_hash = ?, block_number = ?
            WHERE proposal_id = ? AND verdict = 'VERIFIED'
            """,
            (tx_hash_str, receipt.blockNumber, proposal_id),
        )

    return {
        "success": True,
        "proposal_id": proposal_id,
        "tx_hash": receipt.transactionHash.hex(),
        "block_number": receipt.blockNumber,
        "status": "EXECUTED",
    }


@router.get("/sources", response_model=List[Dict[str, Any]])
def list_sources() -> List[Dict[str, Any]]:
    """List all ingested evidence sources."""
    init_db()
    sources: List[Dict[str, Any]] = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, sha256, filename, content_type, storage_path, page_count, ocr_used, created_at "
            "FROM sources ORDER BY created_at DESC"
        )
        for row in cursor.fetchall():
            sources.append(
                {
                    "id": row["id"],
                    "sha256": row["sha256"],
                    "filename": row["filename"],
                    "content_type": row["content_type"],
                    "storage_path": row["storage_path"],
                    "page_count": row["page_count"],
                    "ocr_used": bool(row["ocr_used"]),
                    "created_at": row["created_at"],
                }
            )
    return sources


@router.get("/sources/{source_id}", response_model=Dict[str, Any])
def get_source_detail(source_id: str) -> Dict[str, Any]:
    """Get single source metadata and extracted page texts."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with id '{source_id}' not found",
        )
    return {
        "id": row["id"],
        "sha256": row["sha256"],
        "filename": row["filename"],
        "content_type": row["content_type"],
        "storage_path": row["storage_path"],
        "page_count": row["page_count"],
        "extracted_pages": json.loads(row["extracted_pages"]) if row["extracted_pages"] else {},
        "ocr_used": bool(row["ocr_used"]),
        "created_at": row["created_at"],
    }


@router.get("/verifications/{pid}", response_model=List[Dict[str, Any]])
def get_verifications_for_proposal(pid: str) -> List[Dict[str, Any]]:
    """Return all persisted verification attempts and simulation outcomes for a proposal."""
    init_db()
    records: List[Dict[str, Any]] = []
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM verifications WHERE proposal_id = ? ORDER BY created_at DESC",
            (pid,),
        )
        for row in cursor.fetchall():
            calldata = row["calldata"] or ""
            target = row["target"] or ""
            value = int(row["value"] or 0)
            try:
                from app.verification.decode import decode_transaction
                decoded_tx = decode_transaction(target=target, value=value, data=calldata).to_dict()
            except Exception:
                decoded_tx = {
                    "target": target,
                    "value": value,
                    "selector": calldata[:10] if calldata else "",
                    "recipient": None,
                    "amount_raw": None,
                    "action_hash": row["action_hash"],
                    "calldata_hash": "",
                    "is_supported": False,
                }
            records.append(
                {
                    "id": row["id"],
                    "proposal_id": row["proposal_id"],
                    "version": row["version"],
                    "target": row["target"],
                    "value": row["value"],
                    "calldata": row["calldata"],
                    "action_hash": row["action_hash"],
                    "verdict": row["verdict"],
                    "rules": json.loads(row["rules_json"]) if row["rules_json"] else [],
                    "diff": json.loads(row["diff_json"]) if row["diff_json"] else {},
                    "simulation": json.loads(row["simulation_json"]) if row["simulation_json"] else {},
                    "decoded_tx": decoded_tx,
                    "attestation_sig": row["attestation_sig"],
                    "deadline": row["deadline"],
                    "executed": bool(row["executed"]),
                    "tx_hash": row["tx_hash"],
                    "block_number": row["block_number"],
                    "created_at": row["created_at"],
                }
            )
    return records


@router.get("/deployments", response_model=Dict[str, Any])
def get_deployments_endpoint() -> Dict[str, Any]:
    """Return active deployed contract addresses and roles."""
    from app.scenarios.runner import load_saved_deployments
    saved = load_saved_deployments()
    if saved:
        return saved
    from app.chain.client import PK_DEPLOYER, PK_GOVERNANCE, PK_PROPOSER, PK_VERIFIER, DEFAULT_RPC_URL
    return {
        "rpc_url": DEFAULT_RPC_URL,
        "token": None,
        "registry": None,
        "treasury": None,
        "executor": None,
        "deployer": Account.from_key(PK_DEPLOYER).address,
        "governance": Account.from_key(PK_GOVERNANCE).address,
        "verifier": Account.from_key(PK_VERIFIER).address,
        "proposer": Account.from_key(PK_PROPOSER).address,
    }


@router.get("/balances", response_model=Dict[str, Any])
def get_live_balances_endpoint(
    rpc_url: Optional[str] = None,
    recipient: Optional[str] = None,
) -> Dict[str, Any]:
    """Query live on-chain balances for Treasury, Recipient, and Attacker."""
    from app.scenarios.runner import load_saved_deployments, RECIPIENT_ADDR, ATTACKER_ADDR
    from app.chain.client import get_web3, load_artifact
    w3 = get_web3(rpc_url)
    deployments = load_saved_deployments() or {}
    token_addr = deployments.get("token")
    treasury_addr = deployments.get("treasury")
    recip_addr = recipient or RECIPIENT_ADDR
    attacker_addr = ATTACKER_ADDR

    result: Dict[str, Any] = {
        "connected": w3.is_connected(),
        "token_address": token_addr,
        "treasury": {"address": treasury_addr, "token_balance": 0, "token_balance_raw": "0"},
        "recipient": {"address": recip_addr, "token_balance": 0, "token_balance_raw": "0"},
        "attacker": {"address": attacker_addr, "token_balance": 0, "token_balance_raw": "0"},
    }

    if not w3.is_connected() or not token_addr:
        return result

    try:
        token_artifact = load_artifact("MockToken")
        token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=token_artifact["abi"])
        decimals = 6
        try:
            decimals = token_contract.functions.decimals().call()
        except Exception:
            pass

        if treasury_addr:
            t_raw = token_contract.functions.balanceOf(Web3.to_checksum_address(treasury_addr)).call()
            result["treasury"] = {
                "address": treasury_addr,
                "token_balance_raw": str(t_raw),
                "token_balance": t_raw / (10**decimals),
            }

        if recip_addr:
            r_raw = token_contract.functions.balanceOf(Web3.to_checksum_address(recip_addr)).call()
            result["recipient"] = {
                "address": recip_addr,
                "token_balance_raw": str(r_raw),
                "token_balance": r_raw / (10**decimals),
            }

        if attacker_addr:
            a_raw = token_contract.functions.balanceOf(Web3.to_checksum_address(attacker_addr)).call()
            result["attacker"] = {
                "address": attacker_addr,
                "token_balance_raw": str(a_raw),
                "token_balance": a_raw / (10**decimals),
            }
    except Exception as e:
        logger.warning(f"Failed to query live balances: {e}")

    return result


@router.post("/scenarios/{name}/run")
def run_scenario_endpoint(
    name: str,
    payload: Optional[ScenarioRunPayload] = None,
) -> Dict[str, Any]:
    """Execute scenario A, B1, or C deterministically."""
    from app.scenarios.runner import execute_scenario
    rpc_url = payload.rpc_url if payload else None
    try:
        result = execute_scenario(name=name, rpc_url=rpc_url)
        return result
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        ) from val_err
    except Exception as e:
        logger.error(f"Scenario execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scenario {name} failed: {e}",
        ) from e


@router.get("/proof", response_model=Dict[str, Any])
def get_proof_endpoint() -> Dict[str, Any]:
    """Read and return public testnet proof artifact from docs/proof.json.

    If proof.json is missing or empty, returns published=False with a clear message.
    If proof.json chain ID does not match the connected RPC chain ID, returns published=False.
    Always includes dryrun preview object if docs/dryrun.json exists.
    """
    chain_mode = os.environ.get("CHAIN_MODE", "").lower()
    rpc_url = (os.environ.get("AMOY_RPC") or os.environ.get("RPC_URL_PROOF")) if chain_mode == "proof" else os.environ.get("RPC_URL", "http://127.0.0.1:8545")
    w3 = get_web3(rpc_url)
    connected_chain_id: Optional[int] = None
    if w3.is_connected():
        try:
            connected_chain_id = call_with_rpc_retry(lambda: w3.eth.chain_id)
        except Exception:
            pass

    dryrun_data: Optional[Dict[str, Any]] = None
    if DRYRUN_JSON_PATH.exists():
        try:
            with open(DRYRUN_JSON_PATH, "r", encoding="utf-8") as f:
                dryrun_data = json.load(f)
        except Exception as e:
            logger.warning(f"Error reading docs/dryrun.json: {e}")

    if not PROOF_JSON_PATH.exists():
        return {
            "published": False,
            "chain_id": connected_chain_id,
            "run_id": None,
            "pid": None,
            "contracts": {},
            "transactions": [],
            "dryrun": dryrun_data,
            "message": "No proof published yet. Run scripts/publish_proof.py to broadcast and publish proof.",
        }

    try:
        with open(PROOF_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data or not isinstance(data, dict):
            return {
                "published": False,
                "chain_id": connected_chain_id,
                "run_id": None,
                "pid": None,
                "contracts": {},
                "transactions": [],
                "dryrun": dryrun_data,
                "message": "Proof file is empty or invalid.",
            }

        file_chain_id = data.get("chain_id")
        if connected_chain_id is not None and file_chain_id is not None:
            if int(connected_chain_id) != int(file_chain_id):
                return {
                    "published": False,
                    "chain_id": connected_chain_id,
                    "proof_chain_id": file_chain_id,
                    "run_id": data.get("run_id"),
                    "pid": data.get("pid"),
                    "contracts": {},
                    "transactions": [],
                    "dryrun": dryrun_data,
                    "message": f"Found proof for chain {file_chain_id}, but connected to {connected_chain_id}. Run scripts/publish_proof.py on this network.",
                }

        return {
            "published": True,
            "dryrun": dryrun_data,
            **data,
            "message": "Proof loaded successfully.",
        }
    except Exception as e:
        logger.warning(f"Error reading docs/proof.json: {e}")
        return {
            "published": False,
            "chain_id": connected_chain_id,
            "run_id": None,
            "pid": None,
            "contracts": {},
            "transactions": [],
            "dryrun": dryrun_data,
            "message": f"Error reading proof file: {e}",
        }


@router.get("/chain/status", response_model=Dict[str, Any])
def get_chain_status_endpoint() -> Dict[str, Any]:
    """Return live status of the connected blockchain and deployed contract addresses."""
    chain_mode = os.environ.get("CHAIN_MODE", "").lower()
    rpc_url = (os.environ.get("AMOY_RPC") or os.environ.get("RPC_URL_PROOF")) if chain_mode == "proof" else os.environ.get("RPC_URL", "http://127.0.0.1:8545")

    cache_key = (chain_mode, rpc_url)
    now = time.time()
    if cache_key in _CHAIN_STATUS_CACHE:
        cached_time, cached_val = _CHAIN_STATUS_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            return cached_val

    w3 = get_web3(rpc_url)
    connected = w3.is_connected()

    chain_id = None
    latest_block = None
    rpc_health = "disconnected"
    if connected:
        try:
            chain_id = call_with_rpc_retry(lambda: w3.eth.chain_id)
            latest_block = call_with_rpc_retry(lambda: w3.eth.block_number)
            rpc_health = "healthy"
        except Exception:
            rpc_health = "degraded"

    contracts: Dict[str, str] = {}
    if (chain_mode == "proof" or (chain_id and chain_id not in {31337, 1337})) and DEPLOYMENTS_PROOF_PATH.exists():
        try:
            with open(DEPLOYMENTS_PROOF_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                contracts = {
                    "token": d.get("token", ""),
                    "registry": d.get("registry", ""),
                    "treasury": d.get("treasury", ""),
                    "executor": d.get("executor", ""),
                }
        except Exception:
            pass
    elif DEPLOYMENTS_LOCAL_PATH.exists():
        try:
            with open(DEPLOYMENTS_LOCAL_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                contracts = {
                    "token": d.get("token", ""),
                    "registry": d.get("registry", ""),
                    "treasury": d.get("treasury", ""),
                    "executor": d.get("executor", ""),
                }
        except Exception:
            pass

    if not contracts.get("token"):
        if PROOF_JSON_PATH.exists():
            try:
                with open(PROOF_JSON_PATH, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    c_map = d.get("contracts", {})
                    contracts = {
                        k: (v.get("address") if isinstance(v, dict) else v)
                        for k, v in c_map.items()
                    }
            except Exception:
                pass

    from app.chain.public import get_explorer_base
    explorer_base = get_explorer_base(chain_id or 31337)

    contracts_deployed = bool(
        contracts.get("token")
        and contracts.get("registry")
        and contracts.get("treasury")
        and contracts.get("executor")
    )

    result = {
        "chain_id": chain_id,
        "latest_block": latest_block,
        "rpc_connected": connected,
        "rpc_health": rpc_health,
        "chain_mode": "proof" if (chain_mode == "proof" or (chain_id and chain_id not in {31337, 1337})) else "local",
        "contracts_deployed": contracts_deployed,
        "contract_addresses": contracts,
        "explorer_base": explorer_base,
    }
    _CHAIN_STATUS_CACHE[cache_key] = (now, result)
    return result


@router.get("/chain/balances", response_model=Dict[str, Any])
def get_chain_balances_endpoint() -> Dict[str, Any]:
    """Return live native ETH balances for core protocol roles and treasury token balance."""
    chain_mode = os.environ.get("CHAIN_MODE", "").lower()
    rpc_url = (os.environ.get("AMOY_RPC") or os.environ.get("RPC_URL_PROOF")) if chain_mode == "proof" else os.environ.get("RPC_URL", "http://127.0.0.1:8545")

    cache_key = (chain_mode, rpc_url)
    now = time.time()
    if cache_key in _CHAIN_BALANCES_CACHE:
        cached_time, cached_val = _CHAIN_BALANCES_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SECONDS:
            return cached_val

    w3 = get_web3(rpc_url)
    if not w3.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot connect to blockchain node",
        )

    try:
        chain_id = call_with_rpc_retry(lambda: w3.eth.chain_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RPC unavailable or rate-limited: {e}",
        ) from e

    is_proof = (chain_mode == "proof") or (chain_id not in {31337, 1337})

    role_addresses: Dict[str, str] = {}
    if is_proof:
        from app.chain.public import load_proof_env
        try:
            cfg = load_proof_env(".env.amoy", w3=w3)
            role_addresses = {
                "deployer": cfg.addresses.get("DEPLOYER_ADDR") or (Account.from_key(cfg.deployer_pk).address if cfg.deployer_pk else ""),
                "proposer": cfg.addresses.get("PROPOSER_ADDR") or (Account.from_key(cfg.proposer_pk).address if cfg.proposer_pk else ""),
                "governance": cfg.addresses.get("GOVERNANCE_ADDR") or (Account.from_key(cfg.governance_pk).address if cfg.governance_pk else ""),
                "verifier": cfg.addresses.get("VERIFIER_ADDR") or (Account.from_key(cfg.verifier_pk).address if cfg.verifier_pk else ""),
                "attacker": cfg.addresses.get("ATTACKER_ADDR") or "",
            }
        except Exception:
            pass

    if not role_addresses.get("proposer"):
        from app.chain.client import PK_DEPLOYER, PK_PROPOSER, PK_GOVERNANCE, PK_VERIFIER, PK_ATTACKER
        role_addresses = {
            "deployer": Account.from_key(PK_DEPLOYER).address,
            "proposer": Account.from_key(PK_PROPOSER).address,
            "governance": Account.from_key(PK_GOVERNANCE).address,
            "verifier": Account.from_key(PK_VERIFIER).address,
            "attacker": Account.from_key(PK_ATTACKER).address,
        }

    roles_balances = {}
    for role, addr in role_addresses.items():
        if addr:
            try:
                bal_wei = call_with_rpc_retry(lambda: w3.eth.get_balance(Web3.to_checksum_address(addr)))
                roles_balances[role] = {
                    "address": addr,
                    "balance_wei": bal_wei,
                    "balance_eth": float(Web3.from_wei(bal_wei, "ether")),
                }
            except Exception:
                roles_balances[role] = {"address": addr, "balance_wei": 0, "balance_eth": 0.0}
        else:
            roles_balances[role] = {"address": "", "balance_wei": 0, "balance_eth": 0.0}

    treasury_addr = ""
    token_addr = ""
    deploy_file = DEPLOYMENTS_PROOF_PATH if is_proof and DEPLOYMENTS_PROOF_PATH.exists() else DEPLOYMENTS_LOCAL_PATH

    if deploy_file.exists():
        try:
            with open(deploy_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                treasury_addr = d.get("treasury", "")
                token_addr = d.get("token", "")
        except Exception:
            pass

    if not treasury_addr:
        if PROOF_JSON_PATH.exists():
            try:
                with open(PROOF_JSON_PATH, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    c_map = d.get("contracts", {})
                    treasury_entry = c_map.get("treasury", {})
                    treasury_addr = treasury_entry.get("address") if isinstance(treasury_entry, dict) else treasury_entry
                    token_entry = c_map.get("token", {})
                    token_addr = token_entry.get("address") if isinstance(token_entry, dict) else token_entry
            except Exception:
                pass

    treasury_eth = 0.0
    treasury_token_bal = 0
    if treasury_addr:
        try:
            t_cs = Web3.to_checksum_address(treasury_addr)
            raw_t_eth = call_with_rpc_retry(lambda: w3.eth.get_balance(t_cs))
            treasury_eth = float(Web3.from_wei(raw_t_eth, "ether")) if isinstance(raw_t_eth, (int, float)) else 0.0
            if token_addr:
                mock_token_artifact = load_artifact("MockToken")
                token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_addr), abi=mock_token_artifact["abi"])
                raw_bal = call_with_rpc_retry(lambda: token_contract.functions.balanceOf(t_cs).call())
                treasury_token_bal = int(raw_bal) if isinstance(raw_bal, (int, float)) else 0
        except Exception as e:
            logger.warning(f"Error querying treasury balances: {e}")

    try:
        token_display = f"{treasury_token_bal / 10**6:,.2f} USDC"
    except Exception:
        token_display = "0.00 USDC"

    result = {
        "chain_id": chain_id,
        "chain_mode": "proof" if is_proof else "local",
        "roles": roles_balances,
        "treasury": {
            "address": treasury_addr,
            "balance_eth": treasury_eth,
            "token_balance": treasury_token_bal,
            "token_balance_display": token_display,
        },
    }
    _CHAIN_BALANCES_CACHE[cache_key] = (now, result)
    return result


@router.get("/chain/txs", response_model=List[Dict[str, Any]])
def get_chain_txs_endpoint(
    run_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Retrieve transaction history from chain_txs table, ordered newest first."""
    from app.db import get_chain_txs
    return get_chain_txs(run_id=run_id, limit=limit)


@router.get("/chain/tx/{hash}", response_model=Dict[str, Any])
def get_chain_tx_endpoint(
    hash: str,
) -> Dict[str, Any]:
    """Retrieve transaction details, receipt, decoded status, and revert reason for a transaction hash."""
    from app.db import get_chain_tx
    from app.chain.public import get_explorer_base, explorer_tx_url, revert_reason as fetch_revert_reason

    clean_hash = hash.strip()
    if not clean_hash.startswith("0x") and not clean_hash.startswith("0X"):
        clean_hash = "0x" + clean_hash

    db_tx = get_chain_tx(clean_hash)

    chain_mode = os.environ.get("CHAIN_MODE", "").lower()
    rpc_url = (os.environ.get("AMOY_RPC") or os.environ.get("RPC_URL_PROOF")) if chain_mode == "proof" else os.environ.get("RPC_URL", "http://127.0.0.1:8545")
    w3 = get_web3(rpc_url)

    receipt = None
    if w3.is_connected():
        try:
            receipt = w3.eth.get_transaction_receipt(clean_hash)
        except Exception:
            receipt = None

    if not db_tx and not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {clean_hash} not found in database or on chain",
        )

    chain_id = w3.eth.chain_id if w3.is_connected() else 11155111
    explorer_base = get_explorer_base(chain_id)

    status_val = "pending"
    revert_r = None
    block_num = None
    gas_used = None
    effective_gp = None
    fee_eth = None

    if receipt:
        status_val = "success" if receipt.status == 1 else "reverted"
        block_num = receipt.blockNumber
        gas_used = receipt.gasUsed
        effective_gp = getattr(receipt, "effectiveGasPrice", 0)
        fee_eth = float(Web3.from_wei(gas_used * effective_gp, "ether")) if effective_gp else 0.0
        if receipt.status == 0:
            revert_r = fetch_revert_reason(w3, clean_hash)

    if db_tx:
        return {
            "tx_hash": db_tx["tx_hash"],
            "run_id": db_tx.get("run_id"),
            "step": db_tx.get("step"),
            "role": db_tx.get("role"),
            "from": db_tx.get("from"),
            "to": db_tx.get("to"),
            "status": status_val if receipt else db_tx.get("status"),
            "revert_reason": revert_r or db_tx.get("revert_reason"),
            "block_number": block_num or db_tx.get("block_number"),
            "gas_used": gas_used or db_tx.get("gas_used"),
            "effective_gas_price": effective_gp or db_tx.get("effective_gas_price"),
            "fee_eth": fee_eth or db_tx.get("fee_eth"),
            "timestamp": db_tx.get("timestamp"),
            "explorer_url": explorer_tx_url(clean_hash, explorer_base),
        }

    return {
        "tx_hash": clean_hash,
        "run_id": None,
        "step": "onchain",
        "role": "unknown",
        "from": receipt["from"] if receipt else "",
        "to": receipt["to"] if receipt else "",
        "status": status_val,
        "revert_reason": revert_r,
        "block_number": block_num,
        "gas_used": gas_used,
        "effective_gas_price": effective_gp,
        "fee_eth": fee_eth,
        "timestamp": None,
        "explorer_url": explorer_tx_url(clean_hash, explorer_base),
    }

