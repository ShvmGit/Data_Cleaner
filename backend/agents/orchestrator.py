"""ADK Pipeline Orchestrator — chains profiler, cleaner, EDA, and reporter agents."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from core.config import get_settings
from core.llm_client import groq_client
from core.logging import get_logger
from tools.profiler import compute_profile
from tools.cleaning import (
    handle_missing_values,
    remove_duplicates,
    handle_outliers,
    standardize_formats,
    convert_dtypes,
    rename_columns,
    drop_columns,
)
from tools.eda import (
    generate_correlation_heatmap,
    generate_distribution_plots,
    generate_scatter_matrix,
    generate_box_plots,
    generate_summary_table,
)
from tools.fallback import run_fallback_pipeline

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.schemas import (
    CleaningCriteria, CleaningLogEntry, DataProfile,
    Insight, InsightSeverity, PlotType,
)

logger = get_logger(__name__)

# Map tool names to functions
CLEANING_TOOLS = {
    "handle_missing_values": handle_missing_values,
    "remove_duplicates": remove_duplicates,
    "handle_outliers": handle_outliers,
    "standardize_formats": standardize_formats,
    "convert_dtypes": convert_dtypes,
    "rename_columns": rename_columns,
    "drop_columns": drop_columns,
}

# Tool schemas for LLM function calling
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "handle_missing_values",
            "description": "Handle missing/null values in specified columns using a fill strategy",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {
                        "type": "string",
                        "enum": ["drop", "mean", "median", "mode", "ffill"],
                        "description": "Strategy to handle missing values"
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to process. Omit for all columns."
                    }
                },
                "required": ["strategy"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_duplicates",
            "description": "Remove duplicate rows from the dataset",
            "parameters": {
                "type": "object",
                "properties": {
                    "subset": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columns to consider for duplicate detection. Omit for all."
                    },
                    "keep": {
                        "type": "string",
                        "enum": ["first", "last"],
                        "description": "Which duplicate to keep"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "handle_outliers",
            "description": "Detect and handle outliers in numeric columns",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["iqr_cap", "iqr_remove", "zscore"],
                        "description": "Method to handle outliers"
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific numeric columns. Omit for all numeric."
                    },
                    "threshold": {
                        "type": "number",
                        "description": "IQR multiplier or z-score threshold (default: 1.5)"
                    }
                },
                "required": ["method"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "standardize_formats",
            "description": "Standardize string formats (strip whitespace, change case)",
            "parameters": {
                "type": "object",
                "properties": {
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns. Omit for all string columns."
                    },
                    "operations": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["strip", "lower", "upper", "title"]},
                        "description": "Operations to apply"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "drop_columns",
            "description": "Drop columns by name or by missing value threshold",
            "parameters": {
                "type": "object",
                "properties": {
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to drop"
                    },
                    "missing_threshold": {
                        "type": "number",
                        "description": "Drop columns with missing % above this value (0-100)"
                    }
                }
            }
        }
    },
]

MAX_TOOL_CALLS = 10


async def run_ai_pipeline(
    df: pd.DataFrame,
    profile: DataProfile,
    criteria: CleaningCriteria,
    on_log: Callable[[str, str], Any] | None = None,
) -> tuple[pd.DataFrame, list[CleaningLogEntry], list[dict[str, Any]], list[Insight], bool]:
    """
    Run the full AI-driven cleaning + EDA pipeline.

    Args:
        df: Input DataFrame
        profile: Pre-computed data profile
        criteria: User cleaning preferences
        on_log: Callback for streaming log messages (stage, message)

    Returns:
        (cleaned_df, cleaning_log, plots, insights, used_fallback)
    """
    try:
        return await _run_with_llm(df, profile, criteria, on_log)
    except (ConnectionError, Exception) as e:
        logger.warning("llm_pipeline_failed", error=str(e), fallback="rule_based")
        if on_log:
            await on_log("clean", f"⚠️ AI unavailable ({str(e)[:50]}), switching to rule-based fallback")

        cleaned_df, logs, plots, insights = run_fallback_pipeline(df, profile, criteria)
        return cleaned_df, logs, plots, insights, True


async def _run_with_llm(
    df: pd.DataFrame,
    profile: DataProfile,
    criteria: CleaningCriteria,
    on_log: Callable | None,
) -> tuple[pd.DataFrame, list[CleaningLogEntry], list[dict[str, Any]], list[Insight], bool]:
    """Run the LLM-driven pipeline."""
    cleaning_log: list[CleaningLogEntry] = []

    # ── Step 1: Profiler Agent — Analyze and recommend strategy ──
    if on_log:
        await on_log("clean", "🤖 AI analyzing data profile...")

    strategy = await _run_profiler_agent(profile, criteria)

    if on_log:
        await on_log("clean", f"📋 Strategy: {strategy.get('reasoning', 'Analyzing...')[:100]}")

    # ── Step 2: Cleaner Agent — Select and execute tools ──
    if on_log:
        await on_log("clean", "🧹 AI selecting cleaning tools...")

    df, logs = await _run_cleaner_agent(df, profile, criteria, on_log)
    cleaning_log.extend(logs)

    # ── Step 3: EDA Agent — Select visualizations and generate insights ──
    if on_log:
        await on_log("analyze", "📊 AI selecting visualizations...")

    plots, insights = await _run_eda_agent(df, profile, criteria, on_log)

    return df, cleaning_log, plots, insights, False


async def _run_profiler_agent(profile: DataProfile, criteria: CleaningCriteria) -> dict[str, Any]:
    """LLM analyzes the data profile and recommends a cleaning strategy."""
    profile_summary = _summarize_profile(profile)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a data quality analyst. Given a dataset profile, identify the most critical "
                "data quality issues and recommend a cleaning strategy. Be concise and specific. "
                "Respond with JSON: {\"priority_issues\": [...], \"recommended_tools\": [...], \"reasoning\": \"...\"}"
            ),
        },
        {
            "role": "user",
            "content": f"Dataset profile:\n{json.dumps(profile_summary, indent=2)}\n\n"
                       f"User preferences:\n- Missing strategy: {criteria.missing_strategy.value}\n"
                       f"- Outlier method: {criteria.outlier_method.value}\n"
                       f"- Remove duplicates: {criteria.remove_duplicates}\n\n"
                       f"Analyze the data quality and recommend a cleaning strategy.",
        },
    ]

    response = await groq_client.chat(messages, temperature=0.1, max_tokens=1024)

    try:
        return json.loads(response["content"])
    except (json.JSONDecodeError, TypeError):
        return {"priority_issues": [], "recommended_tools": [], "reasoning": response.get("content", "")}


async def _run_cleaner_agent(
    df: pd.DataFrame,
    profile: DataProfile,
    criteria: CleaningCriteria,
    on_log: Callable | None,
) -> tuple[pd.DataFrame, list[CleaningLogEntry]]:
    """LLM selects and executes cleaning tools via function calling."""
    logs: list[CleaningLogEntry] = []
    profile_summary = _summarize_profile(profile)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a data engineer. Clean the dataset by calling the provided tools in the optimal order. "
                "Consider the user's preferences. Only call tools that are needed based on the profile. "
                "Do NOT call tools for issues that don't exist in the data. Be efficient."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Dataset profile:\n{json.dumps(profile_summary, indent=2)}\n\n"
                f"User preferences:\n- Missing strategy: {criteria.missing_strategy.value}\n"
                f"- Outlier method: {criteria.outlier_method.value}\n"
                f"- Remove duplicates: {criteria.remove_duplicates}\n\n"
                f"Clean this dataset by calling the appropriate tools."
            ),
        },
    ]

    # Iterative tool calling loop
    for i in range(MAX_TOOL_CALLS):
        response = await groq_client.chat(messages, tools=TOOL_SCHEMAS, tool_choice="auto")

        if not response["tool_calls"]:
            break  # LLM decided no more tools needed

        for tc in response["tool_calls"]:
            tool_name = tc["name"]
            tool_args = tc["arguments"]

            if tool_name not in CLEANING_TOOLS:
                logger.warning("unknown_tool", tool=tool_name)
                continue

            if on_log:
                await on_log("clean", f"🔧 Executing: {tool_name}({json.dumps(tool_args)[:80]})")

            try:
                tool_fn = CLEANING_TOOLS[tool_name]
                df, log_entry = tool_fn(df, **tool_args)
                logs.append(log_entry)

                # Add tool result to conversation
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": tc["id"], "type": "function", "function": {"name": tool_name, "arguments": json.dumps(tool_args)}}],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps({"success": True, "message": log_entry.message, "rows_after": log_entry.rows_after}),
                })

                if on_log:
                    await on_log("clean", f"✅ {log_entry.message}")

            except Exception as e:
                logger.error("tool_execution_failed", tool=tool_name, error=str(e))
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": tc["id"], "type": "function", "function": {"name": tool_name, "arguments": json.dumps(tool_args)}}],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps({"success": False, "error": str(e)}),
                })

    return df, logs


async def _run_eda_agent(
    df: pd.DataFrame,
    profile: DataProfile,
    criteria: CleaningCriteria,
    on_log: Callable | None,
) -> tuple[list[dict[str, Any]], list[Insight]]:
    """LLM selects visualizations and generates insights."""
    plots: list[dict[str, Any]] = []
    plot_types = [p.value for p in criteria.eda_plots]

    # Generate requested charts
    if "correlation" in plot_types:
        plots.append(generate_correlation_heatmap(df))
        if on_log:
            await on_log("analyze", "📈 Generated correlation heatmap")

    if "distribution" in plot_types:
        dist_plots = generate_distribution_plots(df)
        plots.extend(dist_plots)
        if on_log:
            await on_log("analyze", f"📊 Generated {len(dist_plots)} distribution plots")

    if "scatter" in plot_types:
        plots.append(generate_scatter_matrix(df))
        if on_log:
            await on_log("analyze", "🔵 Generated scatter matrix")

    if "boxplot" in plot_types:
        plots.append(generate_box_plots(df))
        if on_log:
            await on_log("analyze", "📦 Generated box plots")

    if "summary" in plot_types:
        plots.append(generate_summary_table(df))
        if on_log:
            await on_log("analyze", "📋 Generated summary statistics")

    # Generate AI insights
    insights = await _generate_ai_insights(df, profile, on_log)

    return plots, insights


async def _generate_ai_insights(
    df: pd.DataFrame,
    profile: DataProfile,
    on_log: Callable | None,
) -> list[Insight]:
    """LLM generates natural language insights about the data."""
    profile_summary = _summarize_profile(profile)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a data scientist. Analyze the dataset profile and provide 3-5 actionable insights. "
                "Focus on anomalies, trends, and data quality observations. "
                "Respond with JSON array: [{\"title\": \"...\", \"description\": \"...\", "
                "\"severity\": \"info|warning|critical\", \"affected_columns\": [...], \"category\": \"...\"}]"
            ),
        },
        {
            "role": "user",
            "content": f"Generate insights for this cleaned dataset:\n{json.dumps(profile_summary, indent=2)}",
        },
    ]

    try:
        response = await groq_client.chat(messages, temperature=0.3, max_tokens=1024)
        insights_data = json.loads(response["content"])

        if isinstance(insights_data, list):
            insights = []
            for item in insights_data[:5]:
                insights.append(Insight(
                    title=item.get("title", "Insight"),
                    description=item.get("description", ""),
                    severity=InsightSeverity(item.get("severity", "info")),
                    affected_columns=item.get("affected_columns", []),
                    category=item.get("category", "general"),
                ))
            if on_log:
                await on_log("analyze", f"💡 Generated {len(insights)} AI insights")
            return insights

    except Exception as e:
        logger.warning("insight_generation_failed", error=str(e))

    # Fallback to basic insights
    from tools.fallback import _generate_basic_insights
    return _generate_basic_insights(df, profile)


def _summarize_profile(profile: DataProfile) -> dict[str, Any]:
    """Create a concise profile summary for LLM consumption (no raw data)."""
    return {
        "row_count": profile.row_count,
        "col_count": profile.col_count,
        "memory_mb": profile.memory_mb,
        "duplicate_count": profile.duplicate_count,
        "duplicate_pct": profile.duplicate_pct,
        "columns": [
            {
                "name": cp.name,
                "dtype": cp.dtype,
                "missing_pct": cp.missing_pct,
                "unique_count": cp.unique_count,
                "is_numeric": cp.is_numeric,
                "skewness": cp.skewness,
            }
            for cp in profile.columns
        ],
        "outlier_counts": profile.outlier_counts,
        "high_correlations": _get_high_correlations(profile),
    }


def _get_high_correlations(profile: DataProfile) -> list[dict[str, Any]]:
    """Extract notable correlations for LLM context."""
    if not profile.correlation_matrix:
        return []

    high_corr = []
    seen = set()

    for col_a, corrs in profile.correlation_matrix.items():
        for col_b, val in corrs.items():
            pair = tuple(sorted([col_a, col_b]))
            if col_a != col_b and abs(val) > 0.7 and pair not in seen:
                seen.add(pair)
                high_corr.append({"columns": list(pair), "correlation": val})

    return sorted(high_corr, key=lambda x: abs(x["correlation"]), reverse=True)[:10]
