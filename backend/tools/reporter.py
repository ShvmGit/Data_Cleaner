"""Report generator — HTML report via Jinja2 + CSV/Excel export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from core.logging import get_logger

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.schemas import PipelineState

logger = get_logger(__name__)


def generate_report(state: PipelineState, df: pd.DataFrame, output_dir: Path) -> dict[str, str]:
    """
    Generate all output files: cleaned CSV, Excel, HTML report.

    Returns:
        Dict of {file_type: relative_path}
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}

    # Cleaned CSV
    csv_path = output_dir / "cleaned.csv"
    df.to_csv(csv_path, index=False)
    outputs["csv"] = str(csv_path)
    logger.info("output_generated", type="csv", path=str(csv_path))

    # Cleaned Excel
    try:
        xlsx_path = output_dir / "cleaned.xlsx"
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        outputs["xlsx"] = str(xlsx_path)
        logger.info("output_generated", type="xlsx", path=str(xlsx_path))
    except Exception as e:
        logger.warning("excel_export_failed", error=str(e))

    # Plotly JSON
    if state.plots:
        plots_path = output_dir / "charts.json"
        plots_path.write_text(json.dumps(state.plots, default=str))
        outputs["charts"] = str(plots_path)

    # HTML Report
    try:
        html_path = output_dir / "report.html"
        html_content = _render_html_report(state, df)
        html_path.write_text(html_content, encoding="utf-8")
        outputs["report"] = str(html_path)
        logger.info("output_generated", type="html_report", path=str(html_path))
    except Exception as e:
        logger.warning("html_report_failed", error=str(e))

    return outputs


def _render_html_report(state: PipelineState, df: pd.DataFrame) -> str:
    """Render HTML report using inline template (no external file dependency)."""
    profile = state.profile
    cleaning_log = state.cleaning_log
    insights = state.insights

    # Build summary stats
    summary_html = df.describe(include="all").round(2).to_html(
        classes="stats-table", border=0
    ) if len(df) > 0 else "<p>No data</p>"

    # Build cleaning log table
    log_rows = ""
    for entry in cleaning_log:
        log_rows += f"""
        <tr>
            <td>{entry.timestamp[:19]}</td>
            <td><span class="badge">{entry.tool}</span></td>
            <td>{entry.message}</td>
            <td>{entry.rows_before} → {entry.rows_after}</td>
            <td>{entry.duration_ms}ms</td>
        </tr>"""

    # Build insights
    insight_cards = ""
    for ins in insights:
        severity_class = {"info": "info", "warning": "warning", "critical": "critical"}.get(ins.severity.value, "info")
        insight_cards += f"""
        <div class="insight-card {severity_class}">
            <div class="insight-header">
                <span class="severity-badge {severity_class}">{ins.severity.value.upper()}</span>
                <strong>{ins.title}</strong>
            </div>
            <p>{ins.description}</p>
            {f'<small>Columns: {", ".join(ins.affected_columns)}</small>' if ins.affected_columns else ''}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataCleaner AI Report — {state.filename}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; padding: 2rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 2rem; background: linear-gradient(135deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem; }}
        h2 {{ color: #94a3b8; font-size: 1.3rem; margin: 2rem 0 1rem; border-bottom: 1px solid #1e293b; padding-bottom: 0.5rem; }}
        .meta {{ color: #64748b; margin-bottom: 2rem; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
        .stat-card {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }}
        .stat-value {{ font-size: 2rem; font-weight: 700; color: #3b82f6; }}
        .stat-label {{ color: #94a3b8; font-size: 0.875rem; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #1e293b; }}
        th {{ background: #1e293b; color: #94a3b8; font-weight: 600; }}
        tr:hover {{ background: #1e293b40; }}
        .badge {{ background: #3b82f620; color: #3b82f6; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
        .insight-card {{ background: #1e293b; border-radius: 12px; padding: 1.25rem; margin-bottom: 1rem; border-left: 4px solid #3b82f6; }}
        .insight-card.warning {{ border-left-color: #f59e0b; }}
        .insight-card.critical {{ border-left-color: #ef4444; }}
        .insight-header {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }}
        .severity-badge {{ padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.625rem; font-weight: 700; }}
        .severity-badge.info {{ background: #3b82f620; color: #3b82f6; }}
        .severity-badge.warning {{ background: #f59e0b20; color: #f59e0b; }}
        .severity-badge.critical {{ background: #ef444420; color: #ef4444; }}
        .stats-table {{ font-size: 0.875rem; }}
        .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #1e293b; color: #475569; font-size: 0.75rem; text-align: center; }}
        small {{ color: #64748b; }}
        @media print {{ body {{ background: #fff; color: #000; }} .stat-card, .insight-card {{ border: 1px solid #ddd; }} }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 DataCleaner AI Report</h1>
        <p class="meta">File: <strong>{state.filename}</strong> | Generated: {state.completed_at or 'N/A'} | {'⚠️ Fallback Mode' if state.fallback_mode else '🤖 AI-Powered'}</p>

        <div class="grid">
            <div class="stat-card"><div class="stat-value">{profile.row_count if profile else 'N/A'}</div><div class="stat-label">Total Rows</div></div>
            <div class="stat-card"><div class="stat-value">{profile.col_count if profile else 'N/A'}</div><div class="stat-label">Columns</div></div>
            <div class="stat-card"><div class="stat-value">{profile.duplicate_count if profile else 0}</div><div class="stat-label">Duplicates Found</div></div>
            <div class="stat-card"><div class="stat-value">{len(cleaning_log)}</div><div class="stat-label">Transformations</div></div>
            <div class="stat-card"><div class="stat-value">{profile.memory_mb if profile else 0}MB</div><div class="stat-label">Memory Usage</div></div>
            <div class="stat-card"><div class="stat-value">{f'{state.duration_sec:.1f}s' if state.duration_sec else 'N/A'}</div><div class="stat-label">Duration</div></div>
        </div>

        <h2>📋 Cleaning Log</h2>
        <table>
            <thead><tr><th>Time</th><th>Tool</th><th>Action</th><th>Rows</th><th>Duration</th></tr></thead>
            <tbody>{log_rows if log_rows else '<tr><td colspan="5">No transformations applied</td></tr>'}</tbody>
        </table>

        <h2>💡 Insights</h2>
        {insight_cards if insight_cards else '<p style="color:#64748b">No insights generated</p>'}

        <h2>📊 Summary Statistics</h2>
        {summary_html}

        <div class="footer">Generated by DataCleaner AI v1.0 — Automated Data Cleaning & EDA Pipeline</div>
    </div>
</body>
</html>"""
