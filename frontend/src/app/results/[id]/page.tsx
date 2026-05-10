"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { formatDuration, formatBytes } from "@/lib/utils";
import type { PipelineState, PlotData, Insight } from "@/lib/types";
import { Download, ArrowLeft, Table2, BarChart3, Lightbulb, History, FileDown, CheckCircle2, AlertTriangle, Info } from "lucide-react";

// Lazy load Plotly (3.5MB bundle)
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false, loading: () => <div className="skeleton h-[400px]" /> });

type Tab = "table" | "charts" | "insights" | "audit";

export default function ResultsPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [state, setState] = useState<PipelineState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("table");
  const [tablePage, setTablePage] = useState(0);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getResults(sessionId);
        setState(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="skeleton h-20 w-full" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-24" />)}
        </div>
        <div className="skeleton h-96" />
      </div>
    );
  }

  if (error || !state) {
    return (
      <div className="max-w-2xl mx-auto text-center py-20">
        <AlertTriangle className="w-16 h-16 text-[var(--accent-rose)] mx-auto mb-4" />
        <h1 className="text-2xl font-bold mb-2">Results Not Found</h1>
        <p className="text-[var(--text-muted)] mb-6">{error || "Session not found or expired."}</p>
        <button onClick={() => router.push("/")} className="btn-primary">← Back to Upload</button>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "table", label: "Data Table", icon: <Table2 className="w-4 h-4" /> },
    { key: "charts", label: "Charts", icon: <BarChart3 className="w-4 h-4" /> },
    { key: "insights", label: "Insights", icon: <Lightbulb className="w-4 h-4" /> },
    { key: "audit", label: "Audit Log", icon: <History className="w-4 h-4" /> },
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button onClick={() => router.push("/")} className="text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] flex items-center gap-1 mb-2">
            <ArrowLeft className="w-4 h-4" /> New Upload
          </button>
          <h1 className="text-2xl font-bold">{state.filename}</h1>
          <p className="text-sm text-[var(--text-muted)]">
            {state.duration_sec ? `Completed in ${formatDuration(state.duration_sec)}` : "Processing..."} 
            {state.fallback_mode && " • ⚠️ Fallback Mode"}
          </p>
        </div>
        <div className="flex gap-2">
          {Object.entries(state.outputs).map(([type, url]) => (
            <a
              key={type}
              href={api.getDownloadUrl(sessionId, type)}
              download
              className="btn-secondary flex items-center gap-2 text-sm"
            >
              <FileDown className="w-4 h-4" />
              {type.toUpperCase()}
            </a>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {[
          { label: "Rows", value: state.profile?.row_count?.toLocaleString() || "—", color: "blue" },
          { label: "Columns", value: state.profile?.col_count || "—", color: "purple" },
          { label: "Duplicates", value: state.profile?.duplicate_count || 0, color: "amber" },
          { label: "Outlier Cols", value: Object.keys(state.profile?.outlier_counts || {}).length, color: "rose" },
          { label: "Transforms", value: state.cleaning_log.length, color: "emerald" },
          { label: "Memory", value: `${state.profile?.memory_mb || 0}MB`, color: "cyan" },
        ].map((s) => (
          <div key={s.label} className="glass-card p-4">
            <p className={`text-2xl font-bold text-[var(--accent-${s.color})]`}>{s.value}</p>
            <p className="text-xs text-[var(--text-muted)]">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl bg-[var(--bg-secondary)]">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.key
                ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-lg"
                : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            }`}
          >
            {tab.icon}
            {tab.label}
            {tab.key === "insights" && state.insights.length > 0 && (
              <span className="badge badge-blue ml-1">{state.insights.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="glass-card p-6">
        {activeTab === "table" && <DataTableView state={state} page={tablePage} setPage={setTablePage} />}
        {activeTab === "charts" && <ChartsView plots={state.plots} />}
        {activeTab === "insights" && <InsightsView insights={state.insights} />}
        {activeTab === "audit" && <AuditView state={state} />}
      </div>
    </div>
  );
}

// ── Data Table Tab ──
function DataTableView({ state, page, setPage }: { state: PipelineState; page: number; setPage: (p: number) => void }) {
  const profile = state.profile;
  if (!profile) return <p className="text-[var(--text-muted)]">No data available</p>;

  const pageSize = 25;
  const columns = profile.columns;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--text-muted)]">{profile.row_count.toLocaleString()} rows × {profile.col_count} columns</p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border-subtle)]">
        <table className="w-full data-table text-sm">
          <thead>
            <tr>
              <th className="w-10">#</th>
              {columns.slice(0, 12).map((col) => (
                <th key={col.name} className="whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    {col.name}
                    <span className={`badge ${col.is_numeric ? "badge-blue" : col.is_datetime ? "badge-purple" : "badge-emerald"}`} style={{ fontSize: "0.6rem", padding: "1px 6px" }}>
                      {col.is_numeric ? "NUM" : col.is_datetime ? "DATE" : "TXT"}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {columns.length > 0 && [...Array(Math.min(pageSize, profile.row_count))].map((_, i) => (
              <tr key={i}>
                <td className="text-[var(--text-muted)]">{page * pageSize + i + 1}</td>
                {columns.slice(0, 12).map((col) => (
                  <td key={col.name} className="text-[var(--text-secondary)]">
                    {col.top_values[0]?.value ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Column Stats */}
      <h3 className="text-sm font-semibold text-[var(--text-secondary)] mt-6">Column Statistics</h3>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
        {columns.map((col) => (
          <div key={col.name} className="p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)]">
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium text-sm">{col.name}</span>
              <span className={`badge ${col.is_numeric ? "badge-blue" : "badge-emerald"}`}>{col.dtype}</span>
            </div>
            <div className="grid grid-cols-2 gap-1 text-xs text-[var(--text-muted)]">
              <span>Missing: {col.missing_pct}%</span>
              <span>Unique: {col.unique_count}</span>
              {col.mean != null && <span>Mean: {col.mean.toFixed(2)}</span>}
              {col.std != null && <span>Std: {col.std.toFixed(2)}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Charts Tab ──
function ChartsView({ plots }: { plots: PlotData[] }) {
  if (!plots.length) return <p className="text-[var(--text-muted)] py-8 text-center">No charts generated</p>;

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {plots.map((plot, i) => (
        <div key={i} className={`chart-container ${plot.type === "correlation" || plot.type === "scatter" ? "md:col-span-2" : ""}`}>
          <h3 className="text-sm font-semibold mb-3">{plot.title}</h3>
          {plot.figure ? (
            <Plot
              data={(plot.figure as any).data || []}
              layout={{
                ...((plot.figure as any).layout || {}),
                autosize: true,
                margin: { l: 50, r: 20, t: 30, b: 50 },
                paper_bgcolor: "transparent",
                plot_bgcolor: "rgba(17, 24, 39, 0.5)",
                font: { color: "#94a3b8" },
              }}
              config={{ responsive: true, displayModeBar: false }}
              style={{ width: "100%", height: "400px" }}
            />
          ) : plot.data ? (
            <div className="overflow-x-auto">
              <table className="w-full data-table text-sm">
                <thead>
                  <tr>
                    {Object.keys(plot.data[0] || {}).map((key) => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {plot.data.slice(0, 20).map((row: any, j: number) => (
                    <tr key={j}>
                      {Object.values(row).map((val: any, k: number) => (
                        <td key={k} className="text-[var(--text-secondary)]">{val != null ? String(val) : "—"}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-[var(--text-muted)] text-sm">{plot.message || "No data"}</p>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Insights Tab ──
function InsightsView({ insights }: { insights: Insight[] }) {
  if (!insights.length) return <p className="text-[var(--text-muted)] py-8 text-center">No insights generated</p>;

  const iconMap = { info: <Info className="w-5 h-5" />, warning: <AlertTriangle className="w-5 h-5" />, critical: <AlertTriangle className="w-5 h-5" /> };
  const colorMap = { info: "blue", warning: "amber", critical: "rose" };

  return (
    <div className="space-y-4">
      {insights.map((ins, i) => (
        <div key={i} className={`insight-card ${ins.severity}`}>
          <div className="flex items-start gap-3">
            <div className={`text-[var(--accent-${colorMap[ins.severity]})] mt-0.5`}>
              {iconMap[ins.severity]}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className={`badge badge-${colorMap[ins.severity]}`} style={{ fontSize: "0.65rem" }}>
                  {ins.severity.toUpperCase()}
                </span>
                <h3 className="font-semibold text-sm">{ins.title}</h3>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">{ins.description}</p>
              {ins.affected_columns.length > 0 && (
                <div className="flex gap-1 mt-2 flex-wrap">
                  {ins.affected_columns.map((col) => (
                    <span key={col} className="badge badge-purple" style={{ fontSize: "0.65rem" }}>{col}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Audit Log Tab ──
function AuditView({ state }: { state: PipelineState }) {
  const logs = state.cleaning_log;

  if (!logs.length) return <p className="text-[var(--text-muted)] py-8 text-center">No transformations recorded</p>;

  return (
    <div className="space-y-4">
      <div className="relative pl-6 border-l-2 border-[var(--border-subtle)] space-y-6">
        {logs.map((entry, i) => (
          <div key={i} className="relative">
            {/* Timeline dot */}
            <div className="absolute -left-[29px] w-4 h-4 rounded-full bg-[var(--accent-blue)] border-2 border-[var(--bg-card)]" />

            <div className="p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)]">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="badge badge-blue">{entry.tool}</span>
                  <span className="text-xs text-[var(--text-muted)]">{entry.duration_ms}ms</span>
                </div>
                <span className="text-xs text-[var(--text-muted)]">{entry.timestamp.slice(11, 19)}</span>
              </div>
              <p className="text-sm text-[var(--text-secondary)]">{entry.message}</p>
              <div className="flex items-center gap-4 mt-2 text-xs text-[var(--text-muted)]">
                <span>Rows: {entry.rows_before} → {entry.rows_after}</span>
                {entry.cols_affected.length > 0 && (
                  <span>Cols: {entry.cols_affected.slice(0, 5).join(", ")}{entry.cols_affected.length > 5 ? ` +${entry.cols_affected.length - 5}` : ""}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
