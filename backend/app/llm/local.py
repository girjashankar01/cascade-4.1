"""Local Ollama LLM provider implementation behind the LLMProvider protocol."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import httpx

from app.llm.base import LLMProvider, LLMUnavailableError
from app.llm.online import DEFAULT_SYSTEM_PROMPT, extract_json_block

logger = logging.getLogger(__name__)

# Load root .env if not loaded yet
_root_env = Path(__file__).resolve().parents[3] / ".env"
if _root_env.exists():
    load_dotenv(dotenv_path=_root_env)
else:
    load_dotenv()


class LocalLLMProvider(LLMProvider):
    """Local Ollama-backed LLM provider calling Ollama's HTTP API."""

    def __init__(
        self,
        model: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ):
        self.model = (
            model
            or os.getenv("LLM_LOCAL_MODEL")
            or os.getenv("LLM_MODEL")
            or "gemma2:2b"
        )
        self.endpoint = (
            endpoint
            or os.getenv("LLM_LOCAL_ENDPOINT", "http://127.0.0.1:11434/v1/chat/completions")
        )
        self.timeout_s = float(
            timeout_s if timeout_s is not None else os.getenv("LLM_TIMEOUT_S", "60.0")
        )
        self.name = f"local-ollama-{self.model}"

    def extract_claims(self, prompt: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Call local Ollama model to extract structured claims."""
        sources_payload = []
        for src in sources:
            sources_payload.append(
                {
                    "source_id": src.get("id"),
                    "filename": src.get("filename"),
                    "pages": src.get("extracted_pages", {}),
                }
            )

        user_content = (
            f"SOURCES:\n{json.dumps(sources_payload, indent=2)}\n\n"
            f"INSTRUCTIONS:\n{prompt}\n\n"
            "IMPORTANT: Respond ONLY with a valid JSON array of objects as specified in the system instructions. "
            "Do not include introductory or conversational text."
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer ollama",
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
                response = client.post(self.endpoint, headers=headers, json=body)
                if response.status_code >= 400:
                    err_msg = ""
                    try:
                        err_json = response.json()
                        if isinstance(err_json, dict) and "error" in err_json:
                            err_info = err_json["error"]
                            if isinstance(err_info, dict):
                                err_msg = f": {err_info.get('message', '')}"
                            elif isinstance(err_info, str):
                                err_msg = f": {err_info}"
                    except Exception:
                        pass
                    raise LLMUnavailableError(
                        f"Local Ollama returned error (HTTP {response.status_code}){err_msg}"
                    )

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(extract_json_block(content))
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "claims" in parsed:
                    return parsed["claims"]
                raise ValueError("Ollama output did not contain a JSON list of claims")
        except httpx.TimeoutException as e:
            raise LLMUnavailableError(
                f"Local Ollama request timed out after {self.timeout_s:.1f}s"
            ) from e
        except (httpx.ConnectError, httpx.NetworkError) as e:
            raise LLMUnavailableError(
                f"Cannot connect to local Ollama service at {self.endpoint}. Make sure 'ollama serve' is running."
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from local Ollama: {e}") from e
        except Exception as e:
            if isinstance(e, LLMUnavailableError):
                raise
            raise LLMUnavailableError(f"Failed to communicate with local Ollama: {e}") from e

    def summarize(self, claims: List[Dict[str, Any]]) -> str:
        """Produce a short summary description from claims."""
        return f"Local Ollama analysis extracted {len(claims)} candidate claims."
