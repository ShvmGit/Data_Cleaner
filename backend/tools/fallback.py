"""Fallback pipeline — deterministic rule-based cleaning when LLM is unavailable."""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.logging import get_logger
from tools.cleaning import (
    handle_missing_values,
    remove_duplicates,
    handle_outliers,
    standardize_formats,
    drop_columns,
)
from tools.eda import (
    generate_correlation_heatmap,
    generate_distribution_plots,
    generate_box_plots,
    generate_summary_table,
)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.schemas import CleaningCriteria, CleaningLogEntry, DataProfile, Insight, InsightSeverity

logger = get_logger(__name__)


def run_fallback_pipeline(
    df: pd.DataFrame,
    profile: DataProfile,
    criteria: CleaningCriteria,
) -> tuple[pd.DataFrame, list[CleaningLogEntry], list[dict[str, Any]], list[Insight]]:
    """
    Run deterministic cleaning pipeline without LLM.

    Steps:
        1. Drop columns with >50% missing
        2. Impute remaining missing values (median for numeric, mode for categorical)
        3. Remove exact duplicates
        4. Cap outliers using IQR
        5. Standardize string formats
        6. Generate EDA charts

    Returns:
        (cleaned_df, cleaning_log, plots, insights)
    """
    logger.info("fallback_pipeline_started", rows=len(df), cols=len(df.columns))

    cleaning_log: list[CleaningLogEntry] = []
    insights: list[Insight] = []

    # 1. Drop columns with >50% missing
    high_missing_cols = [
        cp.name for cp in profile.columns
        if cp.missing_pct > 50.0
    ]
    if high_missing_cols:
        df, log = drop_columns(df, columns=high_missing_cols)
        cleaning_log.append(log)
        insights.append(Insight(
            title="High Missing Columns Dropped",
            description=f"Dropped {len(high_missing_cols)} columns with >50% missing values: {', '.join(high_missing_cols)}",
            severity=InsightSeverity.WARNING,
            affected_columns=high_missing_cols,
            category="missing_data",
        ))

    # 2. Handle remaining missing values
    missing_cols = [col for col in df.columns if df[col].isna().any()]
    if missing_cols:
        strategy = criteria.missing_strategy.value
        df, log = handle_missing_values(df, strategy=strategy, columns=missing_cols)
        cleaning_log.append(log)

    # 3. Remove duplicates
    if criteria.remove_duplicates and profile.duplicate_count > 0:
        df, log = remove_duplicates(df)
        cleaning_log.append(log)
        if profile.duplicate_pct > 5:
            insights.append(Insight(
                title="Significant Duplicates Found",
                description=f"{profile.duplicate_count} duplicate rows ({profile.duplicate_pct:.1f}%) were removed",
                severity=InsightSeverity.WARNING,
                category="duplicates",
            ))

    # 4. Handle outliers
    if criteria.outlier_method.value != "none":
        df, log = handle_outliers(df, method=criteria.outlier_method.value)
        cleaning_log.append(log)

    # 5. Standardize string formats
    df, log = standardize_formats(df, operations=["strip"])
    cleaning_log.append(log)

    # 6. Generate EDA
    plots: list[dict[str, Any]] = []
    plot_types = [p.value for p in criteria.eda_plots]

    if "correlation" in plot_types:
        plots.append(generate_correlation_heatmap(df))
    if "distribution" in plot_types:
        plots.extend(generate_distribution_plots(df))
    if "boxplot" in plot_types:
        plots.append(generate_box_plots(df))
    if "summary" in plot_types:
        plots.append(generate_summary_table(df))

    # Generate basic insights
    insights.extend(_generate_basic_insights(df, profile))

    logger.info("fallback_pipeline_completed", rows=len(df), cols=len(df.columns), steps=len(cleaning_log))
    return df, cleaning_log, plots, insights


def _generate_basic_insights(df: pd.DataFrame, profile: DataProfile) -> list[Insight]:
    """Generate deterministic insights without LLM."""
    insights = []

    # Data shape
    insights.append(Insight(
        title="Dataset Overview",
        description=f"Dataset contains {len(df)} rows and {len(df.columns)} columns after cleaning",
        severity=InsightSeverity.INFO,
        category="overview",
    ))

    # Skewness detection
    for cp in profile.columns:
        if cp.skewness is not None and abs(cp.skewness) > 2:
            direction = "right" if cp.skewness > 0 else "left"
            insights.append(Insight(
                title=f"Highly Skewed: {cp.name}",
                description=f"Column '{cp.name}' has skewness of {cp.skewness:.2f} ({direction}-skewed). Consider log transformation.",
                severity=InsightSeverity.WARNING,
                affected_columns=[cp.name],
                category="distribution",
            ))

    # High correlation detection
    if profile.correlation_matrix:
        seen = set()
        for col_a, corrs in profile.correlation_matrix.items():
            for col_b, val in corrs.items():
                if col_a != col_b and abs(val) > 0.9 and (col_b, col_a) not in seen:
                    seen.add((col_a, col_b))
                    insights.append(Insight(
                        title=f"High Correlation: {col_a} ↔ {col_b}",
                        description=f"Correlation of {val:.3f} detected. Consider removing one to reduce multicollinearity.",
                        severity=InsightSeverity.WARNING,
                        affected_columns=[col_a, col_b],
                        category="correlation",
                    ))

    return insights
