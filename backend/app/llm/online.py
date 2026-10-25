"""Online hosted LLM provider implementation behind the LLMProvider protocol."""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

from app.llm.base import LLMProvider, LLMUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are a DAO Proposal Claim Extractor.
Extract structured factual claims from the provided proposal evidence.
Only extract claims that have direct, verbatim quote evidence in the text.

Required canonical fields to extract:
- amount: The proposed financial payout or budget amount (e.g., "$5.0M", "5,000,000 USDC")
- token: The token symbol (e.g., "USDC", "ETH")
- recipient: The beneficiary Ethereum address (e.g., "0x9965507D1a55BCC6475675304Ca994970De97744")
- purpose: Brief statement of the purpose of the grant or payout
- assumptions: Assumptions or milestones required for delivery

Return ONLY a valid JSON array of objects with the following schema:
[
  {
    "field": "amount",
    "value": "$5.0M",
    "quote": "requests a payout of $5.0M (5,000,000 USDC)",
    "source_id": "src_...",
    "page": 1,
    "confidence": 0.95
  }
]
"""


def extract_json_block(text: str) -> str:
    """Extract JSON string from raw model text, stripping markdown code fences if present."""
    clean = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
    if match:
        return match.group(1).strip()
    return clean


class OnlineLLMProvider(LLMProvider):
    """Online hosted LLM provider calling an external API via HTTP."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: float = 30.0,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.provider = (provider or os.getenv("LLM_ONLINE_PROVIDER", "openai")).lower()
        default_model = "gpt-4o-mini" if self.provider == "openai" else "gemini-2.5-flash"
        self.model = model or os.getenv("LLM_MODEL", default_model)
        self.timeout_s = float(os.getenv("LLM_TIMEOUT_S", str(timeout_s)))
        self.name = f"online-{self.provider}"

    def extract_claims(self, prompt: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Call external LLM or return structured claims from content."""
        if not self.api_key:
            raise LLMUnavailableError("LLM_API_KEY is not configured")

        # Prepare payload
        sources_payload = []
        for src in sources:
            sources_payload.append(
                {
                    "source_id": src.get("id"),
                    "filename": src.get("filename"),
                    "pages": src.get("extracted_pages", {}),
                }
            )

        user_content = f"SOURCES:\n{json.dumps(sources_payload, indent=2)}\n\nINSTRUCTIONS:\n{prompt}"

        # Standard OpenAI / OpenRouter / compatible endpoint call
        default_endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            if self.provider == "gemini"
            else "https://api.openai.com/v1/chat/completions"
        )
        endpoint = os.getenv("LLM_API_ENDPOINT", default_endpoint)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.0,
        }

        try:
            with httpx.Client(timeout=self.timeout_s) as client:
                response = client.post(endpoint, headers=headers, json=body)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After") or response.headers.get("retry-after")
                    detail = f", retry after {retry_after}s" if retry_after else ""
                    raise LLMUnavailableError(f"LLM rate limit exceeded (HTTP 429){detail}")
                elif response.status_code in (500, 502, 503, 504):
                    raise LLMUnavailableError(f"LLM provider service error (HTTP {response.status_code})")
                elif response.status_code >= 400:
                    raise LLMUnavailableError(f"LLM provider returned client error (HTTP {response.status_code})")

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(extract_json_block(content))
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "claims" in parsed:
                    return parsed["claims"]
                raise ValueError("Model output did not contain a JSON list of claims")
        except httpx.TimeoutException as e:
            raise LLMUnavailableError(f"LLM request timed out after {self.timeout_s:.1f}s") from e
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise LLMUnavailableError("LLM provider connection failed (network/DNS error)") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from LLM: {e}") from e
        except Exception as e:
            if isinstance(e, LLMUnavailableError):
                raise
            err_str = str(e)
            if self.api_key and self.api_key in err_str:
                err_str = err_str.replace(self.api_key, "[REDACTED]")
            raise LLMUnavailableError(f"Failed to communicate with LLM provider: {err_str}") from e

    def summarize(self, claims: List[Dict[str, Any]]) -> str:
        """Produce a short summary description from claims."""
        return f"Analysis extracted {len(claims)} candidate claims."
