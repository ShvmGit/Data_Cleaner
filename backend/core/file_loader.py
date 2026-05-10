"""File loader for CSV, TXT, XLS, and XLSX files."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd

from core.encoding import detect_encoding
from core.logging import get_logger

logger = get_logger(__name__)

# Supported file extensions and their MIME types
SUPPORTED_EXTENSIONS = {".csv", ".txt", ".xls", ".xlsx"}
SUPPORTED_MIMES = {
    "text/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",  # fallback
}

# Chunk threshold in bytes (50MB)
CHUNK_THRESHOLD = 50 * 1024 * 1024


def validate_file(filename: str, content_type: str | None, size_bytes: int, max_size_bytes: int) -> str | None:
    """
    Validate uploaded file. Returns error message or None if valid.
    """
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        return f"Unsupported file format: {ext}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"

    if size_bytes > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        actual_mb = size_bytes / (1024 * 1024)
        return f"File too large: {actual_mb:.1f}MB exceeds limit of {max_mb:.0f}MB"

    if content_type and content_type not in SUPPORTED_MIMES:
        logger.warning("unexpected_mime", mime=content_type, filename=filename)
        # Don't reject — some systems set wrong MIME types

    return None


def load_dataframe(file_path: str | Path, file_bytes: bytes | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Load a file into a pandas DataFrame with automatic encoding detection.

    Args:
        file_path: Path to the file
        file_bytes: Optional raw bytes (avoids re-reading file)

    Returns:
        Tuple of (DataFrame, metadata dict)
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if file_bytes is None:
        file_bytes = path.read_bytes()

    size_bytes = len(file_bytes)
    metadata: dict[str, Any] = {
        "filename": path.name,
        "extension": ext,
        "size_bytes": size_bytes,
    }

    logger.info("loading_file", filename=path.name, extension=ext, size_mb=round(size_bytes / 1024 / 1024, 2))

    try:
        if ext in (".csv", ".txt"):
            df = _load_csv(file_bytes, size_bytes)
        elif ext in (".xls", ".xlsx"):
            df = _load_excel(file_bytes, ext)
        else:
            raise ValueError(f"Unsupported extension: {ext}")
    except Exception as e:
        logger.error("file_load_failed", filename=path.name, error=str(e))
        raise

    # Optimize dtypes
    df = _optimize_dtypes(df)

    metadata.update({
        "row_count": len(df),
        "col_count": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "memory_mb": round(df.memory_usage(deep=False).sum() / 1024 / 1024, 2),
    })

    logger.info(
        "file_loaded",
        rows=metadata["row_count"],
        cols=metadata["col_count"],
        memory_mb=metadata["memory_mb"],
    )

    return df, metadata


def _load_csv(file_bytes: bytes, size_bytes: int) -> pd.DataFrame:
    """Load CSV/TXT with encoding detection and optional chunking."""
    encoding = detect_encoding(file_bytes)

    read_kwargs = {
        "encoding": encoding,
        "on_bad_lines": "warn",
        "low_memory": False,
    }

    # Try common separators
    sample = file_bytes[:5000].decode(encoding, errors="replace")
    if "\t" in sample and "," not in sample:
        read_kwargs["sep"] = "\t"

    if size_bytes > CHUNK_THRESHOLD:
        logger.info("chunked_read", threshold_mb=CHUNK_THRESHOLD / 1024 / 1024)
        chunks = []
        for chunk in pd.read_csv(io.BytesIO(file_bytes), chunksize=10_000, **read_kwargs):
            chunks.append(chunk)
        return pd.concat(chunks, ignore_index=True)

    return pd.read_csv(io.BytesIO(file_bytes), **read_kwargs)


def _load_excel(file_bytes: bytes, ext: str) -> pd.DataFrame:
    """Load Excel file (XLS or XLSX)."""
    engine = "openpyxl" if ext == ".xlsx" else "xlrd"

    try:
        return pd.read_excel(io.BytesIO(file_bytes), engine=engine)
    except ImportError:
        # xlrd might not be installed for .xls
        if ext == ".xls":
            logger.warning("xlrd_missing", fallback="openpyxl")
            return pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
        raise


def _optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Optimize DataFrame memory usage by converting to efficient dtypes."""
    for col in df.columns:
        col_data = df[col]

        # Convert low-cardinality string columns to category
        if col_data.dtype == "object":
            n_unique = col_data.nunique()
            n_total = len(col_data)
            if n_unique / max(n_total, 1) < 0.5:  # Less than 50% unique
                df[col] = col_data.astype("category")

    return df


def get_preview(df: pd.DataFrame, n_rows: int = 5) -> list[dict[str, Any]]:
    """Get first N rows as list of dicts for API preview."""
    preview_df = df.head(n_rows).copy()
    # Convert NaN to None for JSON serialization
    return preview_df.where(preview_df.notna(), None).to_dict(orient="records")
