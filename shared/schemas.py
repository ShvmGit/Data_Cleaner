"""Shared Pydantic models — single source of truth for all API contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────

class MissingStrategy(str, Enum):
    DROP = "drop"
    MEAN = "mean"
    MEDIAN = "median"
    MODE = "mode"
    FFILL = "ffill"


class OutlierMethod(str, Enum):
    IQR_CAP = "iqr_cap"
    IQR_REMOVE = "iqr_remove"
    ZSCORE = "zscore"
    NONE = "none"


class PipelineStage(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    PROFILING = "profiling"
    CLEANING = "cleaning"
    ANALYZING = "analyzing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


class PlotType(str, Enum):
    CORRELATION = "correlation"
    DISTRIBUTION = "distribution"
    SCATTER = "scatter"
    BOXPLOT = "boxplot"
    SUMMARY = "summary"


class SSEEventType(str, Enum):
    PROGRESS = "progress"
    LOG = "log"
    COMPLETE = "complete"
    ERROR = "error"


class InsightSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ─── Data Profile Models ────────────────────────────────────

class ColumnProfile(BaseModel):
    """Statistical profile of a single column."""
    name: str
    dtype: str
    missing_count: int = 0
    missing_pct: float = 0.0
    unique_count: int = 0
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min_val: float | str | None = Field(default=None, alias="min")
    max_val: float | str | None = Field(default=None, alias="max")
    skewness: float | None = None
    top_values: list[dict[str, Any]] = Field(default_factory=list)
    is_numeric: bool = False
    is_datetime: bool = False

    model_config = {"populate_by_name": True}


class DataProfile(BaseModel):
    """Complete statistical profile of the dataset."""
    row_count: int
    col_count: int
    memory_mb: float
    columns: list[ColumnProfile]
    correlation_matrix: dict[str, dict[str, float]] | None = None
    outlier_counts: dict[str, int] = Field(default_factory=dict)
    duplicate_count: int = 0
    duplicate_pct: float = 0.0


# ─── Cleaning Models ────────────────────────────────────────

class CleaningCriteria(BaseModel):
    """User-configurable cleaning preferences."""
    missing_strategy: MissingStrategy = MissingStrategy.MEDIAN
    outlier_method: OutlierMethod = OutlierMethod.IQR_CAP
    remove_duplicates: bool = True
    eda_plots: list[PlotType] = Field(
        default_factory=lambda: [PlotType.CORRELATION, PlotType.DISTRIBUTION, PlotType.BOXPLOT]
    )
    custom_columns: list[str] | None = None


class CleaningLogEntry(BaseModel):
    """Record of a single cleaning transformation."""
    timestamp: str
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    rows_before: int
    rows_after: int
    cols_affected: list[str] = Field(default_factory=list)
    message: str
    duration_ms: int


# ─── Insight Model ──────────────────────────────────────────

class Insight(BaseModel):
    """AI-generated data insight."""
    title: str
    description: str
    severity: InsightSeverity = InsightSeverity.INFO
    affected_columns: list[str] = Field(default_factory=list)
    category: str = "general"


# ─── Pipeline State ─────────────────────────────────────────

class PipelineState(BaseModel):
    """Complete state of a data cleaning pipeline session."""
    session_id: str
    file_id: str
    filename: str
    stage: PipelineStage = PipelineStage.PENDING
    progress: float = 0.0
    profile: DataProfile | None = None
    criteria: CleaningCriteria | None = None
    cleaning_log: list[CleaningLogEntry] = Field(default_factory=list)
    plots: list[dict[str, Any]] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    outputs: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: str | None = None
    fallback_mode: bool = False
    duration_sec: float | None = None


# ─── API Request/Response Models ────────────────────────────

class UploadResponse(BaseModel):
    """Response after successful file upload."""
    file_id: str
    filename: str
    size_bytes: int
    row_count: int
    col_count: int
    columns: list[str]
    preview: list[dict[str, Any]]


class PipelineStartRequest(BaseModel):
    """Request to start a cleaning pipeline."""
    file_id: str
    criteria: CleaningCriteria = Field(default_factory=CleaningCriteria)


class PipelineStartResponse(BaseModel):
    """Response after pipeline is started."""
    session_id: str
    status: str = "started"


class SSEEvent(BaseModel):
    """Server-Sent Event payload."""
    event: SSEEventType
    data: dict[str, Any]


class ErrorResponse(BaseModel):
    """Standardized error response."""
    error: dict[str, Any]

    @classmethod
    def create(cls, code: str, message: str, details: dict[str, Any] | None = None) -> "ErrorResponse":
        return cls(error={"code": code, "message": message, "details": details or {}})


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
