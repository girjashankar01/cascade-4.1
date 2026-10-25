"""LLM router orchestrating caching, retry policy, and audit trail persistence."""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.claims.schema import RawExtractedClaim
from app.db import get_db_connection
from app.llm.base import LLMProvider, LLMUnavailableError
from app.llm.cache import get_cached_response, set_cached_response
from app.llm.online import DEFAULT_SYSTEM_PROMPT, OnlineLLMProvider

logger = logging.getLogger(__name__)


def compute_hash(content: str) -> str:
    """Compute SHA-256 hex digest of string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_input_hash(sources: List[Dict[str, Any]]) -> str:
    """Compute deterministic SHA-256 hash of all input source IDs and page text."""
    normalized_sources = []
    for s in sorted(sources, key=lambda x: str(x.get("id", ""))):
        normalized_sources.append(
            {
                "id": s.get("id"),
                "sha256": s.get("sha256"),
                "pages": s.get("extracted_pages", {}),
            }
        )
    return compute_hash(json.dumps(normalized_sources, sort_keys=True))


class LLMRouter:
    """Orchestrates LLM calls, cache lookup, single retry on invalid JSON/schema, and audit logging."""

    def __init__(self, provider: Optional[LLMProvider] = None, db_path: Optional[Path | str] = None):
        if provider is not None:
            self.provider = provider
        else:
            import os
            mode = os.getenv("LLM_MODE", "online").lower()
            online_provider = os.getenv("LLM_ONLINE_PROVIDER", "").lower()
            if mode == "local" or online_provider == "ollama":
                from app.llm.local import LocalLLMProvider
                self.provider = LocalLLMProvider()
            else:
                self.provider = OnlineLLMProvider()
        self.db_path = db_path

    def analyze_sources(
        self,
        proposal_id: str,
        sources: List[Dict[str, Any]],
        prompt: str = "Extract factual payout claims with verbatim quotes.",
    ) -> Tuple[List[RawExtractedClaim], str]:
        """Extract candidate claims with cache check, retry on invalid output, and audit logging.

        Returns (raw_claims_list, cache_status).
        """
        start_time = time.perf_counter()
        effective_prompt = f"{DEFAULT_SYSTEM_PROMPT}\n{prompt}"
        prompt_hash = compute_hash(effective_prompt)
        input_hash = compute_input_hash(sources)
        model_name = getattr(self.provider, "model", "default")
        provider_name = self.provider.name

        source_ids = [str(s.get("id", "")) for s in sources]
        source_hashes = [str(s.get("sha256", "")) for s in sources]

        # 1. Check SQLite Cache
        cached_data = get_cached_response(
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            model=model_name,
            db_path=self.db_path,
        )

        if cached_data is not None:
            latency_ms = (time.perf_counter() - start_time) * 1000
            try:
                raw_claims = [RawExtractedClaim(**item) for item in cached_data]
                self._write_audit(
                    proposal_id=proposal_id,
                    status="SUCCESS",
                    source_ids=source_ids,
                    source_hashes=source_hashes,
                    provider=provider_name,
                    model=model_name,
                    prompt_hash=prompt_hash,
                    input_hash=input_hash,
                    latency_ms=latency_ms,
                    cache_status="cached",
                )
                return raw_claims, "cached"
            except (ValidationError, TypeError, KeyError) as e:
                logger.warning(f"Corrupt cache entry found: {e}. Re-executing provider.")

        # 2. Call Provider with Single Retry on Invalid JSON / Schema
        attempts = 0
        last_error: Optional[Exception] = None
        raw_claims_data: Optional[List[Dict[str, Any]]] = None

        while attempts < 2:
            attempts += 1
            try:
                raw_output = self.provider.extract_claims(prompt, sources)
                # Strict validation of each claim against RawExtractedClaim schema
                validated = [RawExtractedClaim(**item) for item in raw_output]
                raw_claims_data = [c.model_dump() for c in validated]
                break
            except (ValueError, ValidationError, json.JSONDecodeError) as parse_err:
                last_error = parse_err
                logger.warning(f"LLM extraction attempt {attempts} output invalid: {parse_err}")
                if attempts >= 2:
                    break
            except LLMUnavailableError as unavail_err:
                # Do not retry timeouts/429/5xx if provider already exhausted internal retries
                last_error = unavail_err
                break
            except Exception as other_err:
                last_error = other_err
                break

        latency_ms = (time.perf_counter() - start_time) * 1000

        # Handle failure
        if raw_claims_data is None:
            error_msg = str(last_error) if last_error else "Failed to extract claims after retries"
            error_code = getattr(last_error, "code", "LLM_UNAVAILABLE")
            self._write_audit(
                proposal_id=proposal_id,
                status="FAILED",
                source_ids=source_ids,
                source_hashes=source_hashes,
                provider=provider_name,
                model=model_name,
                prompt_hash=prompt_hash,
                input_hash=input_hash,
                latency_ms=latency_ms,
                cache_status="generated_now",
                error_code=error_code,
                error_message=error_msg,
            )
            raise LLMUnavailableError(error_msg)

        # 3. Store valid response in cache
        set_cached_response(
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            model=model_name,
            response_data=raw_claims_data,
            db_path=self.db_path,
        )

        # 4. Write audit record
        self._write_audit(
            proposal_id=proposal_id,
            status="SUCCESS",
            source_ids=source_ids,
            source_hashes=source_hashes,
            provider=provider_name,
            model=model_name,
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            latency_ms=latency_ms,
            cache_status="generated_now",
        )

        claims = [RawExtractedClaim(**item) for item in raw_claims_data]
        return claims, "generated_now"

    def _write_audit(
        self,
        proposal_id: str,
        status: str,
        source_ids: List[str],
        source_hashes: List[str],
        provider: str,
        model: str,
        prompt_hash: str,
        input_hash: str,
        latency_ms: float,
        cache_status: str,
        fallback_used: bool = False,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Persist analysis audit record to analyses table."""
        import uuid
        audit_id = f"anl_{proposal_id}_{time.time_ns()}_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        try:
            with get_db_connection(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO analyses (
                        id, proposal_id, status, source_ids, source_hashes,
                        provider, model, prompt_hash, input_hash, latency_ms,
                        cache_status, fallback_used, error_code, error_message,
                        rule_set_version, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        audit_id,
                        proposal_id,
                        status,
                        json.dumps(source_ids),
                        json.dumps(source_hashes),
                        provider,
                        model,
                        prompt_hash,
                        input_hash,
                        latency_ms,
                        cache_status,
                        int(fallback_used),
                        error_code,
                        error_message,
                        "1.0",
                        created_at,
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to record analysis audit: {e}")
