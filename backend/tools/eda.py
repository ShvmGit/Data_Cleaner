"""EDA tools — generate Plotly visualizations from cleaned DataFrames."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff

from core.logging import get_logger

logger = get_logger(__name__)

# Dark theme template for all charts
PLOTLY_TEMPLATE = "plotly_dark"
CHART_HEIGHT = 500
COLOR_SEQUENCE = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"]


def generate_correlation_heatmap(df: pd.DataFrame) -> dict[str, Any]:
    """Generate an annotated correlation heatmap for numeric columns."""
    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) < 2:
        return _empty_chart("Correlation Heatmap", "Need ≥2 numeric columns")

    corr = numeric_df.corr()

    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.columns.tolist(),
        colorscale="RdBu_r",
        zmid=0,
        text=np.round(corr.values, 2),
        texttemplate="%{text}",
        textfont={"size": 10},
        hovertemplate="<b>%{x}</b> vs <b>%{y}</b><br>Correlation: %{z:.3f}<extra></extra>",
    ))

    fig.update_layout(
        title="Correlation Heatmap",
        template=PLOTLY_TEMPLATE,
        height=CHART_HEIGHT,
        xaxis_title="",
        yaxis_title="",
    )

    logger.info("chart_generated", type="correlation_heatmap", cols=len(numeric_df.columns))
    return {"type": "correlation", "title": "Correlation Heatmap", "figure": fig.to_dict()}


def generate_distribution_plots(df: pd.DataFrame, columns: list[str] | None = None) -> list[dict[str, Any]]:
    """Generate histogram + KDE distribution plots for numeric columns."""
    numeric_cols = columns or list(df.select_dtypes(include=[np.number]).columns)
    plots = []

    for col in numeric_cols[:10]:  # Limit to 10 columns
        if col not in df.columns:
            continue

        data = df[col].dropna()
        if len(data) == 0:
            continue

        fig = go.Figure()

        fig.add_trace(go.Histogram(
            x=data,
            name="Distribution",
            nbinsx=min(50, len(data.unique())),
            marker_color="#3b82f6",
            opacity=0.7,
            histnorm="probability density",
        ))

        fig.update_layout(
            title=f"Distribution: {col}",
            template=PLOTLY_TEMPLATE,
            height=400,
            xaxis_title=col,
            yaxis_title="Density",
            showlegend=False,
        )

        plots.append({"type": "distribution", "title": f"Distribution: {col}", "column": col, "figure": fig.to_dict()})

    logger.info("chart_generated", type="distribution", count=len(plots))
    return plots


def generate_scatter_matrix(df: pd.DataFrame, columns: list[str] | None = None) -> dict[str, Any]:
    """Generate a scatter plot matrix for top correlated numeric columns."""
    numeric_df = df.select_dtypes(include=[np.number])
    if len(numeric_df.columns) < 2:
        return _empty_chart("Scatter Matrix", "Need ≥2 numeric columns")

    # Pick top 5 columns by variance
    cols = columns or list(numeric_df.var().nlargest(5).index)
    cols = [c for c in cols if c in numeric_df.columns][:5]

    fig = px.scatter_matrix(
        numeric_df[cols],
        dimensions=cols,
        color_discrete_sequence=COLOR_SEQUENCE,
        template=PLOTLY_TEMPLATE,
        height=max(CHART_HEIGHT, len(cols) * 150),
        title="Scatter Matrix",
    )

    fig.update_traces(diagonal_visible=False, marker=dict(size=3, opacity=0.5))

    logger.info("chart_generated", type="scatter_matrix", cols=len(cols))
    return {"type": "scatter", "title": "Scatter Matrix", "figure": fig.to_dict()}


def generate_box_plots(df: pd.DataFrame, columns: list[str] | None = None) -> dict[str, Any]:
    """Generate box plots for numeric columns with outlier markers."""
    numeric_cols = columns or list(df.select_dtypes(include=[np.number]).columns)
    numeric_cols = [c for c in numeric_cols if c in df.columns][:15]

    if not numeric_cols:
        return _empty_chart("Box Plots", "No numeric columns found")

    fig = go.Figure()
    for i, col in enumerate(numeric_cols):
        fig.add_trace(go.Box(
            y=df[col].dropna(),
            name=col,
            marker_color=COLOR_SEQUENCE[i % len(COLOR_SEQUENCE)],
            boxpoints="outliers",
        ))

    fig.update_layout(
        title="Box Plots — Numeric Columns",
        template=PLOTLY_TEMPLATE,
        height=CHART_HEIGHT,
        yaxis_title="Value",
        showlegend=True,
    )

    logger.info("chart_generated", type="box_plots", cols=len(numeric_cols))
    return {"type": "boxplot", "title": "Box Plots", "figure": fig.to_dict()}


def generate_summary_table(df: pd.DataFrame) -> dict[str, Any]:
    """Generate a styled summary statistics table."""
    desc = df.describe(include="all").round(2)

    # Convert to list of dicts for frontend rendering
    summary_data = []
    for col in desc.columns:
        row = {"column": col}
        for stat in desc.index:
            val = desc.loc[stat, col]
            row[stat] = None if pd.isna(val) else val
        summary_data.append(row)

    logger.info("chart_generated", type="summary_table", cols=len(desc.columns))
    return {
        "type": "summary",
        "title": "Summary Statistics",
        "data": summary_data,
        "stats": list(desc.index),
    }


def _empty_chart(title: str, message: str) -> dict[str, Any]:
    """Create an empty chart placeholder with a message."""
    fig = go.Figure()
    fig.add_annotation(text=message, xref="paper", yref="paper", x=0.5, y=0.5,
                       showarrow=False, font=dict(size=16, color="#94a3b8"))
    fig.update_layout(title=title, template=PLOTLY_TEMPLATE, height=300)
    return {"type": "empty", "title": title, "figure": fig.to_dict(), "message": message}
