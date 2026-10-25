"""Unit tests for LocalLLMProvider and local Ollama routing."""

import json
from unittest.mock import MagicMock
import httpx
import pytest

from app.llm.base import LLMUnavailableError
from app.llm.local import LocalLLMProvider
from app.llm.router import LLMRouter


def test_local_llm_provider_init():
    provider = LocalLLMProvider(model="gemma2:2b", endpoint="http://127.0.0.1:11434/v1/chat/completions")
    assert provider.model == "gemma2:2b"
    assert provider.endpoint == "http://127.0.0.1:11434/v1/chat/completions"
    assert "local-ollama-gemma2:2b" in provider.name


def test_local_llm_connection_error_raises_llm_unavailable(monkeypatch):
    provider = LocalLLMProvider(endpoint="http://127.0.0.1:9999/v1/chat/completions")

    def mock_post(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.Client, "post", mock_post)

    sources = [{"id": "s1", "filename": "doc.txt", "extracted_pages": {1: "test text"}}]
    with pytest.raises(LLMUnavailableError) as exc_info:
        provider.extract_claims("Extract claims", sources)

    assert "Cannot connect to local Ollama service" in str(exc_info.value)


def test_local_llm_extract_claims_success(monkeypatch):
    provider = LocalLLMProvider(model="gemma2:2b")

    mock_resp_data = {
        "choices": [
            {
                "message": {
                    "content": json.dumps([
                        {
                            "field": "amount",
                            "value": "5000000",
                            "quote": "grant of 5,000,000 USDC",
                            "source_id": "s1",
                            "page": 1,
                            "confidence": 0.95,
                        }
                    ])
                }
            }
        ]
    }

    class MockResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return mock_resp_data

    monkeypatch.setattr(httpx.Client, "post", lambda *args, **kwargs: MockResponse())

    sources = [{"id": "s1", "filename": "doc.txt", "extracted_pages": {1: "grant of 5,000,000 USDC"}}]
    claims = provider.extract_claims("Extract claims", sources)
    assert len(claims) == 1
    assert claims[0]["field"] == "amount"
    assert claims[0]["value"] == "5000000"


def test_llm_router_selects_local_provider_when_configured(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "local")
    monkeypatch.setenv("LLM_LOCAL_MODEL", "gemma2:2b")

    router = LLMRouter()
    assert isinstance(router.provider, LocalLLMProvider)
    assert router.provider.model == "gemma2:2b"
