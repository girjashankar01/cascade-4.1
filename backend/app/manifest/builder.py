"""Manifest builder, confirmation engine, and integrity verification for DAO proposals."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from eth_account import Account
from eth_account.messages import encode_defunct

from app.claims.schema import Claim, ClaimStatus
from app.db import get_db_connection
from app.manifest.canon import canonical_json, canonicalize_manifest
from app.manifest.hashes import (
    INITIAL_PREV_VERSION_HASH,
    compute_evidence_root,
    compute_manifest_action_hash,
    compute_proposal_text_hash,
    compute_version_hash,
    normalize_hex_32,
)

logger = logging.getLogger(__name__)


class ManifestError(Exception):
    """Base exception for manifest construction errors."""


class EligibilityError(ManifestError):
    """Raised when claims are ineligible (conflicted, uncertain, or rejected)."""


class TamperError(ManifestError):
    """Raised when recomputed commitments do not match stored or on-chain values."""


def check_claims_eligibility(
    proposal_id: str,
    db_path: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Verify that claims are grounded, conflict-free, and sufficient for manifest drafting.

    Returns (claims_list, sources_map).
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Check for unresolved conflicts
        cursor.execute(
            "SELECT * FROM conflicts WHERE proposal_id = ? AND status IN ('UNRESOLVED', 'CONFLICT')",
            (proposal_id,),
        )
        conflicts = cursor.fetchall()
        if conflicts:
            conf_details = [f"{c['field']}: {c['display_value_a']} vs {c['display_value_b']}" for c in conflicts]
            raise EligibilityError(
                f"Proposal '{proposal_id}' has unresolved conflicts and cannot be confirmed: {', '.join(conf_details)}"
            )

        # 2. Fetch claims
        cursor.execute("SELECT * FROM claims WHERE proposal_id = ?", (proposal_id,))
        claim_rows = cursor.fetchall()
        if not claim_rows:
            raise EligibilityError(f"No claims found for proposal '{proposal_id}'. Run analysis first.")

        claims = [dict(r) for r in claim_rows]

        # 3. Check for uncertain or rejected mandatory claims
        mandatory_fields = {"amount", "recipient"}
        fields_found = set()
        for c in claims:
            field = c["field"]
            status = c["status"]
            if field in mandatory_fields:
                if status == ClaimStatus.UNCERTAIN.value:
                    raise EligibilityError(
                        f"Mandatory claim '{field}' is UNCERTAIN (display: '{c['display_value']}') and cannot be confirmed"
                    )
                if status == ClaimStatus.REJECTED.value:
                    raise EligibilityError(
                        f"Mandatory claim '{field}' is REJECTED and cannot be confirmed"
                    )
                fields_found.add(field)

        missing = mandatory_fields - fields_found
        if missing:
            raise EligibilityError(f"Missing mandatory claims for manifest: {sorted(missing)}")

        # 4. Fetch source metadata referenced by the proposal claims
        source_ids = {c["source_id"] for c in claims if c.get("source_id")}
        if source_ids:
            placeholders = ",".join(["?"] * len(source_ids))
            cursor.execute(f"SELECT * FROM sources WHERE id IN ({placeholders})", list(source_ids))
            sources = {r["id"]: dict(r) for r in cursor.fetchall()}
        else:
            cursor.execute("SELECT * FROM sources ORDER BY created_at ASC")
            sources = {r["id"]: dict(r) for r in cursor.fetchall()}

    return claims, sources


def build_manifest_draft(
    proposal_id: str,
    token_address: str,
    token_decimals: int = 6,
    version: int = 1,
    proposal_text: Optional[str] = None,
    source_id: Optional[str] = None,
    prev_version_hash: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Draft a single-action canonical manifest from grounded, conflict-free claims."""
    claims, sources = check_claims_eligibility(proposal_id, db_path=db_path)

    # Resolve amount and recipient
    amount_claim = next((c for c in claims if c["field"] == "amount" and c["status"] == ClaimStatus.GROUNDED.value), None)
    if not amount_claim:
        raise EligibilityError(f"No grounded amount claim found for proposal '{proposal_id}'")

    recipient_claim = next((c for c in claims if c["field"] == "recipient" and c["status"] == ClaimStatus.GROUNDED.value), None)
    if not recipient_claim:
        raise EligibilityError(f"No grounded recipient claim found for proposal '{proposal_id}'")

    token_normalized = token_address.lower()
    recipient_normalized = recipient_claim["value"].lower()

    # Exact integer arithmetic: amountRaw = amount * 10^decimals
    amount_tokens = int(amount_claim["value"])
    amount_raw = str(amount_tokens * (10**token_decimals))

    # Resolve proposal text hash
    if proposal_text is not None:
        proposal_full_text = proposal_text
    else:
        primary_source = None
        if source_id and source_id in sources:
            primary_source = sources[source_id]
        else:
            for src in sources.values():
                if "proposal" in src["filename"].lower() or src["content_type"] == "application/pdf":
                    primary_source = src
                    break
            if not primary_source and sources:
                primary_source = next(iter(sources.values()))

        if not primary_source:
            raise EligibilityError(f"No proposal source found for proposal '{proposal_id}'")

        extracted_pages = json.loads(primary_source["extracted_pages"])
        proposal_full_text = "\n\n".join(extracted_pages[str(p)] for p in sorted(map(int, extracted_pages.keys())))

    proposal_text_hash = compute_proposal_text_hash(proposal_full_text)

    # Compute evidenceRoot from all distinct source hashes
    all_sha256 = list({src["sha256"] for src in sources.values()})
    evidence_root = compute_evidence_root(all_sha256)

    # Determine prevVersionHash
    if prev_version_hash is not None:
        resolved_prev_vhash = normalize_hex_32(prev_version_hash)
    elif version == 1:
        resolved_prev_vhash = INITIAL_PREV_VERSION_HASH
    else:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT version_hash FROM versions WHERE proposal_id = ? AND version = ?",
                (proposal_id, version - 1),
            )
            row = cursor.fetchone()
            if not row:
                cursor.execute(
                    "SELECT version_hash FROM manifests WHERE proposal_id = ? AND version = ?",
                    (proposal_id, version - 1),
                )
                row = cursor.fetchone()

            if not row:
                raise EligibilityError(
                    f"Previous version {version - 1} not found for proposal '{proposal_id}' to link version chain"
                )
            resolved_prev_vhash = row["version_hash"]

    # Assemble manifest structure matching Section 5.1
    manifest_dict = {
        "proposalId": proposal_id,
        "version": version,
        "action": {
            "kind": "erc20_payout",
            "token": token_normalized,
            "decimals": token_decimals,
            "recipient": recipient_normalized,
            "amountRaw": amount_raw,
        },
        "envelope": {
            "maxTokenOutflow": {
                token_normalized: amount_raw,
            },
            "allowApprovals": False,
            "allowRoleChanges": False,
            "allowImplChange": False,
            "allowNewContracts": False,
        },
        "proposalTextHash": proposal_text_hash,
        "evidenceRoot": evidence_root,
        "prevVersionHash": resolved_prev_vhash,
    }

    # Compute canonical bytes, versionHash, and actionHash
    canon_bytes = canonicalize_manifest(manifest_dict)
    vhash = compute_version_hash(canon_bytes, resolved_prev_vhash)
    ahash = compute_manifest_action_hash(manifest_dict["action"])

    return {
        "manifest": manifest_dict,
        "canonical_json": canon_bytes.decode("utf-8"),
        "version_hash": vhash,
        "action_hash": ahash,
        "proposal_text_hash": proposal_text_hash,
        "evidence_root": evidence_root,
        "prev_version_hash": resolved_prev_vhash,
    }


def confirm_manifest_with_signature(
    proposal_id: str,
    version: int,
    proposer_private_key: str,
    token_address: str,
    token_decimals: int = 6,
    proposal_text: Optional[str] = None,
    source_id: Optional[str] = None,
    prev_version_hash: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Draft, confirm, and sign manifest with the proposer's development private key."""
    draft = build_manifest_draft(
        proposal_id=proposal_id,
        token_address=token_address,
        token_decimals=token_decimals,
        version=version,
        proposal_text=proposal_text,
        source_id=source_id,
        prev_version_hash=prev_version_hash,
        db_path=db_path,
    )

    account = Account.from_key(proposer_private_key)
    proposer_address = account.address

    # Proposer signs the versionHash
    vhash_str = draft["version_hash"]
    msg = encode_defunct(hexstr=vhash_str)
    signed = account.sign_message(msg)
    sig_hex = signed.signature.hex()

    manifest_id = f"man_{proposal_id}_{version}"

    # Persist in manifests table
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO manifests (
                id, proposal_id, version, canonical_json, manifest_dict,
                proposal_text_hash, evidence_root, prev_version_hash,
                version_hash, action_hash, status, proposer_address,
                proposer_signature, created_at, confirmed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?, datetime('now'), datetime('now'))
            """,
            (
                manifest_id,
                proposal_id,
                version,
                draft["canonical_json"],
                json.dumps(draft["manifest"]),
                draft["proposal_text_hash"],
                draft["evidence_root"],
                draft["prev_version_hash"],
                draft["version_hash"],
                draft["action_hash"],
                proposer_address,
                sig_hex,
            ),
        )

    return {
        "manifest_id": manifest_id,
        "proposal_id": proposal_id,
        "version": version,
        "version_hash": draft["version_hash"],
        "action_hash": draft["action_hash"],
        "proposal_text_hash": draft["proposal_text_hash"],
        "evidence_root": draft["evidence_root"],
        "prev_version_hash": draft["prev_version_hash"],
        "proposer_address": proposer_address,
        "proposer_signature": sig_hex,
        "canonical_json": draft["canonical_json"],
        "manifest": draft["manifest"],
        "status": "CONFIRMED",
    }


def verify_manifest_integrity(
    proposal_id: str,
    version: int,
    manifest_dict: Optional[Dict[str, Any]] = None,
    proposal_text: Optional[str] = None,
    evidence_hashes: Optional[List[str]] = None,
    registry_address: Optional[str] = None,
    rpc_url: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify integrity of a manifest, recomputing all commitments and verifying against stored and on-chain records.

    Raises TamperError if tampering or commitment mismatch is detected.
    """
    # 1. Fetch stored manifest record from database if available
    stored_record = None
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM manifests WHERE proposal_id = ? AND version = ?",
            (proposal_id, version),
        )
        row = cursor.fetchone()
        if row:
            stored_record = dict(row)

    if manifest_dict is None:
        if not stored_record:
            raise ManifestError(f"No manifest found for proposal '{proposal_id}' version {version}")
        manifest_dict = json.loads(stored_record["manifest_dict"])

    # 2. Check canonical serialization
    canon_bytes = canonicalize_manifest(manifest_dict)
    canon_json = canon_bytes.decode("utf-8")

    # 3. Check proposalTextHash if text is available
    if proposal_text is not None:
        recomputed_text_hash = compute_proposal_text_hash(proposal_text)
        if recomputed_text_hash != manifest_dict.get("proposalTextHash"):
            raise TamperError(
                f"Tamper detected in proposalTextHash: expected {manifest_dict.get('proposalTextHash')}, "
                f"recomputed {recomputed_text_hash}"
            )

    # 4. Check evidenceRoot if evidence hashes are available
    if evidence_hashes is not None:
        recomputed_evidence_root = compute_evidence_root(evidence_hashes)
        if recomputed_evidence_root != manifest_dict.get("evidenceRoot"):
            raise TamperError(
                f"Tamper detected in evidenceRoot: expected {manifest_dict.get('evidenceRoot')}, "
                f"recomputed {recomputed_evidence_root}"
            )

    # 5. Check actionHash
    action = manifest_dict.get("action", {})
    recomputed_action_hash = compute_manifest_action_hash(action)

    # 6. Check versionHash
    prev_vhash = manifest_dict.get("prevVersionHash", INITIAL_PREV_VERSION_HASH)
    recomputed_version_hash = compute_version_hash(canon_bytes, prev_vhash)

    if stored_record is not None:
        if stored_record["version_hash"] != recomputed_version_hash:
            raise TamperError(
                f"Tamper detected in versionHash: stored {stored_record['version_hash']}, "
                f"recomputed {recomputed_version_hash}"
            )
        if stored_record["action_hash"] != recomputed_action_hash:
            raise TamperError(
                f"Tamper detected in actionHash: stored {stored_record['action_hash']}, "
                f"recomputed {recomputed_action_hash}"
            )

    # 7. Check on-chain record if registry is provided
    onchain_match = False
    if registry_address is not None:
        from app.chain.client import get_onchain_version
        try:
            on_vhash, on_ahash, on_eroot = get_onchain_version(
                registry_address=registry_address,
                proposal_id=proposal_id,
                version_number=version,
                rpc_url=rpc_url,
            )
            if on_vhash != recomputed_version_hash:
                raise TamperError(
                    f"Tamper detected on-chain versionHash mismatch: on-chain {on_vhash}, "
                    f"recomputed {recomputed_version_hash}"
                )
            if on_ahash != recomputed_action_hash:
                raise TamperError(
                    f"Tamper detected on-chain actionHash mismatch: on-chain {on_ahash}, "
                    f"recomputed {recomputed_action_hash}"
                )
            if on_eroot != manifest_dict.get("evidenceRoot"):
                raise TamperError(
                    f"Tamper detected on-chain evidenceRoot mismatch: on-chain {on_eroot}, "
                    f"manifest {manifest_dict.get('evidenceRoot')}"
                )
            onchain_match = True
        except Exception as e:
            if isinstance(e, TamperError):
                raise
            logger.warning(f"Could not verify on-chain: {e}")

    return {
        "verified": True,
        "proposal_id": proposal_id,
        "version": version,
        "version_hash": recomputed_version_hash,
        "action_hash": recomputed_action_hash,
        "proposal_text_hash": manifest_dict.get("proposalTextHash"),
        "evidence_root": manifest_dict.get("evidenceRoot"),
        "prev_version_hash": prev_vhash,
        "onchain_verified": onchain_match,
    }
