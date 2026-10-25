"""Protocol and exceptions for LLM providers."""

from typing import Any, Dict, List, Protocol, runtime_checkable


class LLMError(Exception):
    """Base exception for LLM-related failures."""

    def __init__(self, message: str, code: str = "LLM_ERROR"):
        super().__init__(message)
        self.code = code
        self.message = message


class LLMUnavailableError(LLMError):
    """Raised when LLM calls fail, time out, rate limit, or fail validation after retries."""

    def __init__(self, message: str = "LLM service unavailable"):
        super().__init__(message, code="LLM_UNAVAILABLE")


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol implemented by online (and future local) LLM providers."""

    name: str

    def extract_claims(self, prompt: str, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract candidate claims matching RawExtractedClaim schema from provided sources."""
        ...

    def summarize(self, claims: List[Dict[str, Any]]) -> str:
        """Produce an explainable summary of extracted claims."""
        ...
