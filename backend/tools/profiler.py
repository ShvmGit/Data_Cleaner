"""Data profiler — computes comprehensive statistical profiles of DataFrames."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

from core.logging import get_logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.schemas import DataProfile, ColumnProfile

logger = get_logger(__name__)


def compute_profile(df: pd.DataFrame) -> DataProfile:
    """
    Compute a comprehensive statistical profile of the DataFrame.

    Returns:
        DataProfile with per-column stats, correlation matrix, outlier counts
    """
    start = time.time()

    columns = []
    outlier_counts = {}

    for col_name in df.columns:
        col = df[col_name]
        col_profile = _profile_column(col, col_name)
        columns.append(col_profile)

        # Count outliers for numeric columns
        if col_profile.is_numeric:
            n_outliers = _count_outliers_iqr(col.dropna())
            if n_outliers > 0:
                outlier_counts[col_name] = n_outliers

    # Correlation matrix (numeric columns only)
    numeric_df = df.select_dtypes(include=[np.number])
    correlation_matrix = None
    if len(numeric_df.columns) >= 2:
        corr = numeric_df.corr()
        correlation_matrix = {
            col: {row: round(float(val), 4) for row, val in corr[col].items()}
            for col in corr.columns
        }

    # Duplicate detection
    dup_count = int(df.duplicated().sum())

    profile = DataProfile(
        row_count=len(df),
        col_count=len(df.columns),
        memory_mb=round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
        columns=columns,
        correlation_matrix=correlation_matrix,
        outlier_counts=outlier_counts,
        duplicate_count=dup_count,
        duplicate_pct=round(dup_count / max(len(df), 1) * 100, 2),
    )

    duration = round((time.time() - start) * 1000)
    logger.info("profile_computed", rows=profile.row_count, cols=profile.col_count, duration_ms=duration)

    return profile


def _profile_column(col: pd.Series, col_name: str) -> ColumnProfile:
    """Compute statistics for a single column."""
    dtype_str = str(col.dtype)
    missing_count = int(col.isna().sum())
    total = len(col)

    profile = ColumnProfile(
        name=col_name,
        dtype=dtype_str,
        missing_count=missing_count,
        missing_pct=round(missing_count / max(total, 1) * 100, 2),
        unique_count=int(col.nunique()),
        is_numeric=pd.api.types.is_numeric_dtype(col),
        is_datetime=pd.api.types.is_datetime64_any_dtype(col),
    )

    non_null = col.dropna()

    if profile.is_numeric and len(non_null) > 0:
        profile.mean = round(float(non_null.mean()), 4)
        profile.median = round(float(non_null.median()), 4)
        profile.std = round(float(non_null.std()), 4)
        profile.min_val = round(float(non_null.min()), 4)
        profile.max_val = round(float(non_null.max()), 4)
        try:
            profile.skewness = round(float(non_null.skew()), 4)
        except Exception:
            profile.skewness = None

    # Top values (works for all dtypes)
    if len(non_null) > 0:
        top = non_null.value_counts().head(5)
        profile.top_values = [
            {"value": _serialize_value(val), "count": int(count)}
            for val, count in top.items()
        ]

    return profile


def _count_outliers_iqr(series: pd.Series) -> int:
    """Count outliers using IQR method."""
    if len(series) < 4:
        return 0

    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1

    if iqr == 0:
        return 0

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    return int(((series < lower) | (series > upper)).sum())


def _serialize_value(val: Any) -> Any:
    """Convert numpy/pandas types to JSON-serializable Python types."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return round(float(val), 4)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if pd.isna(val):
        return None
    return str(val)
