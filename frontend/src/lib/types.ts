// TypeScript interfaces — mirrors shared/schemas.py Pydantic models

export type MissingStrategy = "drop" | "mean" | "median" | "mode" | "ffill";
export type OutlierMethod = "iqr_cap" | "iqr_remove" | "zscore" | "none";
export type PipelineStage = "pending" | "parsing" | "profiling" | "cleaning" | "analyzing" | "reporting" | "completed" | "failed";
export type PlotType = "correlation" | "distribution" | "scatter" | "boxplot" | "summary";
export type SSEEventType = "progress" | "log" | "complete" | "error";
export type InsightSeverity = "info" | "warning" | "critical";

export interface ColumnProfile {
  name: string;
  dtype: string;
  missing_count: number;
  missing_pct: number;
  unique_count: number;
  mean?: number;
  median?: number;
  std?: number;
  min?: number | string;
  max?: number | string;
  skewness?: number;
  top_values: { value: string | number; count: number }[];
  is_numeric: boolean;
  is_datetime: boolean;
}

export interface DataProfile {
  row_count: number;
  col_count: number;
  memory_mb: number;
  columns: ColumnProfile[];
  correlation_matrix?: Record<string, Record<string, number>>;
  outlier_counts: Record<string, number>;
  duplicate_count: number;
  duplicate_pct: number;
}

export interface CleaningCriteria {
  missing_strategy: MissingStrategy;
  outlier_method: OutlierMethod;
  remove_duplicates: boolean;
  eda_plots: PlotType[];
  custom_columns?: string[];
}

export interface CleaningLogEntry {
  timestamp: string;
  tool: string;
  params: Record<string, unknown>;
  rows_before: number;
  rows_after: number;
  cols_affected: string[];
  message: string;
  duration_ms: number;
}

export interface Insight {
  title: string;
  description: string;
  severity: InsightSeverity;
  affected_columns: string[];
  category: string;
}

export interface PipelineState {
  session_id: string;
  file_id: string;
  filename: string;
  stage: PipelineStage;
  progress: number;
  profile?: DataProfile;
  criteria?: CleaningCriteria;
  cleaning_log: CleaningLogEntry[];
  plots: PlotData[];
  insights: Insight[];
  outputs: Record<string, string>;
  error?: string;
  created_at: string;
  completed_at?: string;
  fallback_mode: boolean;
  duration_sec?: number;
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  size_bytes: number;
  row_count: number;
  col_count: number;
  columns: string[];
  preview: Record<string, unknown>[];
}

export interface PipelineStartResponse {
  session_id: string;
  status: string;
}

export interface SSEProgressData {
  stage: string;
  progress: number;
  message?: string;
}

export interface SSELogData {
  stage: string;
  tool?: string;
  message: string;
  timestamp: string;
}

export interface SSECompleteData {
  session_id: string;
  duration_sec: number;
  outputs: Record<string, string>;
  fallback_mode: boolean;
}

export interface SSEErrorData {
  code: string;
  message: string;
  recoverable: boolean;
}

export interface PlotData {
  type: string;
  title: string;
  figure?: Record<string, unknown>;
  column?: string;
  data?: Record<string, unknown>[];
  message?: string;
}

export const DEFAULT_CRITERIA: CleaningCriteria = {
  missing_strategy: "median",
  outlier_method: "iqr_cap",
  remove_duplicates: true,
  eda_plots: ["correlation", "distribution", "boxplot"],
};

export const STAGES: { key: PipelineStage; label: string; icon: string }[] = [
  { key: "parsing", label: "Parse", icon: "📄" },
  { key: "profiling", label: "Profile", icon: "📊" },
  { key: "cleaning", label: "Clean", icon: "🧹" },
  { key: "analyzing", label: "Analyze", icon: "📈" },
  { key: "reporting", label: "Report", icon: "📋" },
];
