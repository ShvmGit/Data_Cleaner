"""Encoding detection for uploaded files."""

import chardet
from core.logging import get_logger

logger = get_logger(__name__)

# Common encodings to try in order
ENCODING_FALLBACKS = ["utf-8-sig", "utf-8", "latin-1", "windows-1252", "iso-8859-1"]


def detect_encoding(file_bytes: bytes, sample_size: int = 100_000) -> str:
    """
    Detect file encoding using chardet with fallback chain.

    Args:
        file_bytes: Raw file bytes
        sample_size: Number of bytes to sample for detection

    Returns:
        Detected encoding string (e.g., 'utf-8', 'latin-1')
    """
    sample = file_bytes[:sample_size]

    # Try chardet first
    result = chardet.detect(sample)
    encoding = result.get("encoding")
    confidence = result.get("confidence", 0)

    if encoding and confidence > 0.7:
        logger.info(
            "encoding_detected",
            encoding=encoding,
            confidence=confidence,
            method="chardet",
        )
        return encoding.lower()

    # Low confidence — try fallbacks
    for enc in ENCODING_FALLBACKS:
        try:
            sample.decode(enc)
            logger.info(
                "encoding_detected",
                encoding=enc,
                confidence=1.0,
                method="fallback",
            )
            return enc
        except (UnicodeDecodeError, LookupError):
            continue

    # Last resort
    logger.warning("encoding_fallback", encoding="utf-8", reason="all_detection_failed")
    return "utf-8"
