"""Cleaning tools — pure Python functions for data transformations.

Each function takes a DataFrame and parameters, returns (new_df, CleaningLogEntry).
These are registered as ADK tools for LLM function calling.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Literal

import numpy as np
import pandas as pd

from core.logging import get_logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.schemas import CleaningLogEntry

logger = get_logger(__name__)


def _make_log(tool: str, params: dict, rows_before: int, rows_after: int,
              cols: list[str], message: str, start_time: float) -> CleaningLogEntry:
    """Helper to create a CleaningLogEntry."""
    return CleaningLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        tool=tool,
        params=params,
        rows_before=rows_before,
        rows_after=rows_after,
        cols_affected=cols,
        message=message,
        duration_ms=int((time.time() - start_time) * 1000),
    )


def handle_missing_values(
    df: pd.DataFrame,
    strategy: str = "median",
    columns: list[str] | None = None,
) -> tuple[pd.DataFrame, CleaningLogEntry]:
    """
    Handle missing values using the specified strategy.

    Args:
        df: Input DataFrame
        strategy: One of 'drop', 'mean', 'median', 'mode', 'ffill'
        columns: Specific columns to process (None = all)
    """
    start = time.time()
    rows_before = len(df)
    target_cols = columns or list(df.columns)
    result = df.copy()
    affected = []

    for col in target_cols:
        if col not in result.columns:
            continue
        missing = result[col].isna().sum()
        if missing == 0:
            continue

        affected.append(col)

        if strategy == "drop":
            result = result.dropna(subset=[col])
        elif strategy == "mean" and pd.api.types.is_numeric_dtype(result[col]):
            result[col] = result[col].fillna(result[col].mean())
        elif strategy == "median" and pd.api.types.is_numeric_dtype(result[col]):
            result[col] = result[col].fillna(result[col].median())
        elif strategy == "mode":
            mode_val = result[col].mode()
            if len(mode_val) > 0:
                result[col] = result[col].fillna(mode_val.iloc[0])
        elif strategy == "ffill":
            result[col] = result[col].ffill()
        else:
            # Numeric fallback for non-numeric columns with mean/median
            if strategy in ("mean", "median"):
                mode_val = result[col].mode()
                if len(mode_val) > 0:
                    result[col] = result[col].fillna(mode_val.iloc[0])

    total_imputed = rows_before * len(affected) - result[affected].isna().sum().sum() if affected else 0
    msg = f"Handled missing values in {len(affected)} columns using '{strategy}' strategy"

    log = _make_log("handle_missing_values", {"strategy": strategy, "columns": columns},
                     rows_before, len(result), affected, msg, start)

    logger.info("tool_executed", tool="handle_missing_values", affected=len(affected), strategy=strategy)
    return result, log


def remove_duplicates(
    df: pd.DataFrame,
    subset: list[str] | None = None,
    keep: str = "first",
) -> tuple[pd.DataFrame, CleaningLogEntry]:
    """
    Remove duplicate rows.

    Args:
        df: Input DataFrame
        subset: Columns to consider for duplicates (None = all)
        keep: 'first', 'last', or False (remove all)
    """
    start = time.time()
    rows_before = len(df)
    keep_val = keep if keep != "false" else False

    result = df.drop_duplicates(subset=subset, keep=keep_val).reset_index(drop=True)
    removed = rows_before - len(result)
    cols = subset or list(df.columns)

    msg = f"Removed {removed} duplicate rows (keep='{keep}')"
    log = _make_log("remove_duplicates", {"subset": subset, "keep": keep},
                     rows_before, len(result), cols, msg, start)

    logger.info("tool_executed", tool="remove_duplicates", removed=removed)
    return result, log


def handle_outliers(
    df: pd.DataFrame,
    method: str = "iqr_cap",
    columns: list[str] | None = None,
    threshold: float = 1.5,
) -> tuple[pd.DataFrame, CleaningLogEntry]:
    """
    Handle outliers in numeric columns.

    Args:
        df: Input DataFrame
        method: 'iqr_cap', 'iqr_remove', or 'zscore'
        columns: Specific columns (None = all numeric)
        threshold: IQR multiplier or z-score threshold
    """
    start = time.time()
    rows_before = len(df)
    result = df.copy()

    numeric_cols = columns or list(result.select_dtypes(include=[np.number]).columns)
    affected = []
    total_outliers = 0

    for col in numeric_cols:
        if col not in result.columns or not pd.api.types.is_numeric_dtype(result[col]):
            continue

        series = result[col].dropna()
        if len(series) < 4:
            continue

        if method in ("iqr_cap", "iqr_remove"):
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr

            outliers = (result[col] < lower) | (result[col] > upper)
            n_outliers = outliers.sum()

            if n_outliers > 0:
                affected.append(col)
                total_outliers += int(n_outliers)

                if method == "iqr_cap":
                    # Convert to float to avoid TypeError when assigning float caps to int columns
                    if not pd.api.types.is_float_dtype(result[col]):
                        result[col] = result[col].astype(float)
                    result.loc[result[col] < lower, col] = lower
                    result.loc[result[col] > upper, col] = upper
                else:
                    result = result[~outliers]

        elif method == "zscore":
            z = np.abs((result[col] - result[col].mean()) / result[col].std())
            outliers = z > threshold
            n_outliers = outliers.sum()

            if n_outliers > 0:
                affected.append(col)
                total_outliers += int(n_outliers)
                result = result[~outliers]

    result = result.reset_index(drop=True)

    msg = f"Handled {total_outliers} outliers in {len(affected)} columns using '{method}'"
    log = _make_log("handle_outliers", {"method": method, "threshold": threshold},
                     rows_before, len(result), affected, msg, start)

    logger.info("tool_executed", tool="handle_outliers", outliers=total_outliers, method=method)
    return result, log


def standardize_formats(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    operations: list[str] | None = None,
) -> tuple[pd.DataFrame, CleaningLogEntry]:
    """
    Standardize string formats (strip whitespace, lowercase, title case).

    Args:
        df: Input DataFrame
        columns: Specific columns (None = all object columns)
        operations: List of operations: 'strip', 'lower', 'upper', 'title'
    """
    start = time.time()
    rows_before = len(df)
    result = df.copy()
    ops = operations or ["strip"]

    target_cols = columns or list(result.select_dtypes(include=["object", "category"]).columns)
    affected = []

    for col in target_cols:
        if col not in result.columns:
            continue

        original = result[col].copy()

        if result[col].dtype.name == "category":
            result[col] = result[col].astype(str)

        for op in ops:
            if op == "strip":
                result[col] = result[col].astype(str).str.strip()
            elif op == "lower":
                result[col] = result[col].astype(str).str.lower()
            elif op == "upper":
                result[col] = result[col].astype(str).str.upper()
            elif op == "title":
                result[col] = result[col].astype(str).str.title()

        if not result[col].equals(original):
            affected.append(col)

    msg = f"Standardized formats in {len(affected)} columns (ops: {', '.join(ops)})"
    log = _make_log("standardize_formats", {"operations": ops},
                     rows_before, len(result), affected, msg, start)

    logger.info("tool_executed", tool="standardize_formats", affected=len(affected))
    return result, log


def convert_dtypes(
    df: pd.DataFrame,
    column_types: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, CleaningLogEntry]:
    """
    Convert column data types.

    Args:
        df: Input DataFrame
        column_types: Dict of {column_name: target_type}. Types: 'numeric', 'datetime', 'category', 'string'
    """
    start = time.time()
    rows_before = len(df)
    result = df.copy()
    affected = []

    if not column_types:
        # Auto-detect: try converting object columns to numeric or datetime
        for col in result.select_dtypes(include=["object"]).columns:
            try:
                converted = pd.to_numeric(result[col], errors="coerce")
                if converted.notna().sum() > len(converted) * 0.5:
                    result[col] = converted
                    affected.append(col)
                    continue
            except Exception:
                pass

            try:
                converted = pd.to_datetime(result[col], errors="coerce", infer_datetime_format=True)
                if converted.notna().sum() > len(converted) * 0.5:
                    result[col] = converted
                    affected.append(col)
            except Exception:
                pass
    else:
        for col, target_type in column_types.items():
            if col not in result.columns:
                continue
            try:
                if target_type == "numeric":
                    result[col] = pd.to_numeric(result[col], errors="coerce")
                elif target_type == "datetime":
                    result[col] = pd.to_datetime(result[col], errors="coerce")
                elif target_type == "category":
                    result[col] = result[col].astype("category")
                elif target_type == "string":
                    result[col] = result[col].astype(str)
                affected.append(col)
            except Exception as e:
                logger.warning("dtype_conversion_failed", col=col, target=target_type, error=str(e))

    msg = f"Converted data types for {len(affected)} columns"
    log = _make_log("convert_dtypes", {"column_types": column_types or "auto"},
                     rows_before, len(result), affected, msg, start)

    logger.info("tool_executed", tool="convert_dtypes", affected=len(affected))
    return result, log


def rename_columns(
    df: pd.DataFrame,
    mapping: dict[str, str] | None = None,
    style: str = "snake_case",
) -> tuple[pd.DataFrame, CleaningLogEntry]:
    """
    Rename columns using a mapping or automatic style conversion.

    Args:
        df: Input DataFrame
        mapping: Dict of {old_name: new_name}
        style: 'snake_case', 'lower', 'strip' (used if mapping is None)
    """
    import re
    start = time.time()
    rows_before = len(df)
    result = df.copy()

    if mapping:
        result = result.rename(columns=mapping)
        affected = list(mapping.keys())
    else:
        old_cols = list(result.columns)
        if style == "snake_case":
            new_cols = []
            for col in old_cols:
                s = re.sub(r'[^\w\s]', '', str(col))
                s = re.sub(r'\s+', '_', s.strip())
                s = re.sub(r'([a-z])([A-Z])', r'\1_\2', s)
                new_cols.append(s.lower())
            result.columns = new_cols
        elif style == "lower":
            result.columns = [str(c).lower() for c in result.columns]
        elif style == "strip":
            result.columns = [str(c).strip() for c in result.columns]

        affected = [old for old, new in zip(old_cols, result.columns) if old != new]

    msg = f"Renamed {len(affected)} columns (style: {style})"
    log = _make_log("rename_columns", {"style": style, "mapping": mapping},
                     rows_before, len(result), affected, msg, start)

    logger.info("tool_executed", tool="rename_columns", affected=len(affected))
    return result, log


def drop_columns(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    missing_threshold: float | None = None,
) -> tuple[pd.DataFrame, CleaningLogEntry]:
    """
    Drop specified columns or columns exceeding a missing value threshold.

    Args:
        df: Input DataFrame
        columns: Specific columns to drop
        missing_threshold: Drop columns with missing % above this (0-100)
    """
    start = time.time()
    rows_before = len(df)
    result = df.copy()
    affected = []

    if columns:
        existing = [c for c in columns if c in result.columns]
        result = result.drop(columns=existing)
        affected = existing

    if missing_threshold is not None:
        for col in list(result.columns):
            pct = result[col].isna().sum() / max(len(result), 1) * 100
            if pct > missing_threshold:
                result = result.drop(columns=[col])
                affected.append(col)

    msg = f"Dropped {len(affected)} columns"
    log = _make_log("drop_columns", {"columns": columns, "missing_threshold": missing_threshold},
                     rows_before, len(result), affected, msg, start)

    logger.info("tool_executed", tool="drop_columns", dropped=len(affected))
    return result, log
