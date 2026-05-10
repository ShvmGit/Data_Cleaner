"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { formatBytes, getFileIcon } from "@/lib/utils";
import type { UploadResponse, CleaningCriteria, MissingStrategy, OutlierMethod, PlotType } from "@/lib/types";
import { DEFAULT_CRITERIA } from "@/lib/types";
import { Upload, FileSpreadsheet, Settings2, Sparkles, ChevronDown, X, Play } from "lucide-react";

export default function HomePage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [fileInfo, setFileInfo] = useState<UploadResponse | null>(null);
  const [criteria, setCriteria] = useState<CleaningCriteria>(DEFAULT_CRITERIA);
  const [starting, setStarting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // ── Upload Handler ──
  const handleFile = useCallback(async (file: File) => {
    const validExts = [".csv", ".txt", ".xls", ".xlsx"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!validExts.includes(ext)) {
      toast.error("Unsupported file format", { description: `Supported: ${validExts.join(", ")}` });
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      toast.error("File too large", { description: "Maximum size is 100MB" });
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    // Simulate progress
    const interval = setInterval(() => {
      setUploadProgress((p) => Math.min(p + 10, 90));
    }, 200);

    try {
      const result = await api.upload(file);
      setFileInfo(result);
      setUploadProgress(100);
      toast.success("File uploaded", { description: `${result.row_count} rows × ${result.col_count} columns` });
    } catch (err: any) {
      toast.error("Upload failed", { description: err.message });
      setFileInfo(null);
    } finally {
      clearInterval(interval);
      setUploading(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  }, [handleFile]);

  // ── Start Pipeline ──
  const handleStart = useCallback(async () => {
    if (!fileInfo) return;
    setStarting(true);
    try {
      const result = await api.startPipeline(fileInfo.file_id, criteria);
      toast.success("Pipeline started!", { description: "Redirecting to progress..." });
      setTimeout(() => router.push(`/pipeline/${result.session_id}`), 500);
    } catch (err: any) {
      toast.error("Failed to start", { description: err.message });
      setStarting(false);
    }
  }, [fileInfo, criteria, router]);

  const togglePlot = (plot: PlotType) => {
    setCriteria((c) => ({
      ...c,
      eda_plots: c.eda_plots.includes(plot)
        ? c.eda_plots.filter((p) => p !== plot)
        : [...c.eda_plots, plot],
    }));
  };

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="text-center py-8">
        <h1 className="text-4xl md:text-5xl font-extrabold mb-4">
          <span className="gradient-text">Clean Your Data</span>
          <span className="text-[var(--text-primary)]"> with AI</span>
        </h1>
        <p className="text-lg text-[var(--text-secondary)] max-w-2xl mx-auto">
          Upload your CSV, TXT, or Excel file and let our AI-powered pipeline clean, analyze, and
          generate insights in seconds — not hours.
        </p>
      </div>

      <div className="grid lg:grid-cols-5 gap-8">
        {/* Left: Upload */}
        <div className="lg:col-span-3 space-y-6">
          {/* Drop Zone */}
          <div
            className={`upload-zone p-10 text-center transition-all ${dragActive ? "active" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.txt,.xls,.xlsx"
              className="hidden"
              onChange={handleInputChange}
              onClick={(e) => e.stopPropagation()}
            />

            {uploading ? (
              <div className="space-y-4">
                <div className="w-16 h-16 mx-auto rounded-2xl flex items-center justify-center bg-[var(--bg-secondary)]">
                  <Upload className="w-8 h-8 text-[var(--accent-blue)] animate-bounce" />
                </div>
                <p className="text-[var(--text-secondary)]">Uploading...</p>
                <div className="w-64 mx-auto h-2 rounded-full bg-[var(--bg-secondary)] overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%`, background: "var(--gradient-primary)" }}
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="w-16 h-16 mx-auto rounded-2xl flex items-center justify-center bg-[var(--bg-secondary)]">
                  <Upload className="w-8 h-8 text-[var(--text-muted)]" />
                </div>
                <div>
                  <p className="text-lg font-semibold text-[var(--text-primary)]">
                    Drop your file here or click to browse
                  </p>
                  <p className="text-sm text-[var(--text-muted)] mt-1">
                    CSV, TXT, XLS, XLSX — up to 100MB
                  </p>
                </div>
                <div className="flex justify-center gap-2">
                  {[".csv", ".txt", ".xlsx", ".xls"].map((ext) => (
                    <span key={ext} className="badge badge-blue">{ext}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* File Preview */}
          {fileInfo && (
            <div className="glass-card p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{getFileIcon(fileInfo.filename)}</span>
                  <div>
                    <p className="font-semibold">{fileInfo.filename}</p>
                    <p className="text-sm text-[var(--text-muted)]">
                      {formatBytes(fileInfo.size_bytes)} • {fileInfo.row_count.toLocaleString()} rows • {fileInfo.col_count} columns
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setFileInfo(null)}
                  className="p-2 rounded-lg hover:bg-[var(--bg-secondary)] transition-colors"
                >
                  <X className="w-4 h-4 text-[var(--text-muted)]" />
                </button>
              </div>

              {/* Column badges */}
              <div className="flex flex-wrap gap-2">
                {fileInfo.columns.slice(0, 15).map((col) => (
                  <span key={col} className="badge badge-purple">{col}</span>
                ))}
                {fileInfo.columns.length > 15 && (
                  <span className="badge badge-blue">+{fileInfo.columns.length - 15} more</span>
                )}
              </div>

              {/* Preview table */}
              <div className="overflow-x-auto rounded-lg border border-[var(--border-subtle)]">
                <table className="w-full data-table text-sm">
                  <thead>
                    <tr>
                      {fileInfo.columns.slice(0, 8).map((col) => (
                        <th key={col} className="whitespace-nowrap">{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {fileInfo.preview.slice(0, 5).map((row, i) => (
                      <tr key={i}>
                        {fileInfo.columns.slice(0, 8).map((col) => (
                          <td key={col} className="whitespace-nowrap text-[var(--text-secondary)]">
                            {row[col] != null ? String(row[col]) : <span className="text-[var(--accent-rose)] opacity-50">null</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Right: Config Panel */}
        <div className="lg:col-span-2 space-y-6">
          <div className="glass-card p-6 space-y-6">
            <div className="flex items-center gap-2">
              <Settings2 className="w-5 h-5 text-[var(--accent-blue)]" />
              <h2 className="text-lg font-semibold">Cleaning Configuration</h2>
            </div>

            {/* Missing Values */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-secondary)]">Missing Value Strategy</label>
              <select
                value={criteria.missing_strategy}
                onChange={(e) => setCriteria((c) => ({ ...c, missing_strategy: e.target.value as MissingStrategy }))}
                className="w-full px-4 py-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-sm focus:border-[var(--accent-blue)] focus:outline-none transition-colors"
              >
                <option value="median">Median (recommended)</option>
                <option value="mean">Mean</option>
                <option value="mode">Mode</option>
                <option value="ffill">Forward Fill</option>
                <option value="drop">Drop Rows</option>
              </select>
            </div>

            {/* Outlier Method */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-secondary)]">Outlier Handling</label>
              <select
                value={criteria.outlier_method}
                onChange={(e) => setCriteria((c) => ({ ...c, outlier_method: e.target.value as OutlierMethod }))}
                className="w-full px-4 py-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-subtle)] text-[var(--text-primary)] text-sm focus:border-[var(--accent-blue)] focus:outline-none transition-colors"
              >
                <option value="iqr_cap">IQR Cap (recommended)</option>
                <option value="iqr_remove">IQR Remove</option>
                <option value="zscore">Z-Score</option>
                <option value="none">None</option>
              </select>
            </div>

            {/* Duplicates */}
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-[var(--text-secondary)]">Remove Duplicates</label>
              <button
                type="button"
                onClick={() => setCriteria((c) => ({ ...c, remove_duplicates: !c.remove_duplicates }))}
                className={`w-12 h-6 rounded-full transition-colors relative ${criteria.remove_duplicates ? "bg-[var(--accent-blue)]" : "bg-[var(--bg-secondary)]"}`}
              >
                <div className={`w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform ${criteria.remove_duplicates ? "translate-x-6" : "translate-x-0.5"}`} />
              </button>
            </div>

            {/* EDA Plots */}
            <div className="space-y-3">
              <label className="text-sm font-medium text-[var(--text-secondary)]">EDA Visualizations</label>
              {(["correlation", "distribution", "scatter", "boxplot", "summary"] as PlotType[]).map((plot) => (
                <label key={plot} className="flex items-center gap-3 cursor-pointer group" onClick={(e) => { e.preventDefault(); togglePlot(plot); }}>
                  <div
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                      criteria.eda_plots.includes(plot) ? "bg-[var(--accent-blue)] border-[var(--accent-blue)]" : "border-[var(--border-subtle)] group-hover:border-[var(--text-muted)]"
                    }`}
                  >
                    {criteria.eda_plots.includes(plot) && <span className="text-white text-xs">✓</span>}
                  </div>
                  <span className="text-sm capitalize">{plot === "boxplot" ? "Box Plots" : plot === "correlation" ? "Correlation Heatmap" : plot}</span>
                </label>
              ))}
            </div>

            {/* Start Button */}
            <button
              type="button"
              onClick={handleStart}
              disabled={!fileInfo || starting}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {starting ? (
                <>
                  <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  Run AI Pipeline
                </>
              )}
            </button>

            {!fileInfo && (
              <p className="text-xs text-center text-[var(--text-muted)]">Upload a file first to start the pipeline</p>
            )}
          </div>

          {/* Feature cards */}
          <div className="grid grid-cols-2 gap-3">
            {[
              { icon: "🤖", label: "AI-Powered", desc: "Groq LLM" },
              { icon: "⚡", label: "Fast", desc: "2-5 seconds" },
              { icon: "🔒", label: "Private", desc: "No raw data sent" },
              { icon: "📊", label: "Interactive", desc: "Plotly charts" },
            ].map((f) => (
              <div key={f.label} className="glass-card p-4 text-center">
                <span className="text-2xl">{f.icon}</span>
                <p className="text-sm font-semibold mt-1">{f.label}</p>
                <p className="text-xs text-[var(--text-muted)]">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
