"""OCR fallback engine using RapidOCR when native text extraction is insufficient."""

import logging
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)

# Global mock hook for testing without ONNX model downloads
_OCR_MOCK_HANDLER: Optional[Callable[[bytes], Tuple[str, float]]] = None


def set_ocr_mock_handler(handler: Optional[Callable[[bytes], Tuple[str, float]]]) -> None:
    """Set or clear a mock OCR handler for testing."""
    global _OCR_MOCK_HANDLER
    _OCR_MOCK_HANDLER = handler


def ocr_page_bytes(image_bytes: bytes) -> Tuple[str, float]:
    """Run OCR on image bytes, returning (extracted_text, average_confidence).

    Confidence is bounded strictly to 0.0–1.0.
    """
    if _OCR_MOCK_HANDLER is not None:
        return _OCR_MOCK_HANDLER(image_bytes)

    try:
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
        result, _ = engine(image_bytes)
        if not result:
            return "", 0.0

        # RapidOCR returns list of [[box], text, confidence]
        texts = []
        confidences = []
        for item in result:
            if len(item) >= 3:
                texts.append(str(item[1]))
                confidences.append(float(item[2]))

        full_text = "\n".join(texts).strip()
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        # Ensure confidence is strictly 0.0 to 1.0
        avg_conf = max(0.0, min(1.0, avg_conf))
        return full_text, avg_conf
    except ImportError:
        logger.warning("RapidOCR not installed. OCR fallback skipped.")
        return "", 0.0
    except Exception as e:
        logger.error(f"OCR execution failed: {e}")
        return "", 0.0
