"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useSSE } from "@/hooks/useSSE";
import { STAGES } from "@/lib/types";
import type { PipelineStage, SSELogData } from "@/lib/types";
import { formatDuration } from "@/lib/utils";
import { CheckCircle2, Loader2, AlertTriangle, Clock, ArrowRight } from "lucide-react";

export default function PipelinePage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;
  const sse = useSSE(sessionId);
  const [elapsed, setElapsed] = useState(0);

  // Timer
  useEffect(() => {
    if (sse.status === "completed" || sse.status === "error") return;
    const interval = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => clearInterval(interval);
  }, [sse.status]);

  // Auto-navigate on complete
  useEffect(() => {
    if (sse.status === "completed") {
      const timer = setTimeout(() => router.push(`/results/${sessionId}`), 2500);
      return () => clearTimeout(timer);
    }
  }, [sse.status, sessionId, router]);

  const getStageIndex = (stage: PipelineStage) => {
    return STAGES.findIndex((s) => s.key === stage);
  };

  const currentIndex = getStageIndex(sse.stage);

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold">
          {sse.status === "completed" ? (
            <span className="text-[var(--accent-emerald)]">✅ Pipeline Complete!</span>
          ) : sse.status === "error" ? (
            <span className="text-[var(--accent-rose)]">❌ Pipeline Failed</span>
          ) : (
            <span className="gradient-text">Processing Your Data...</span>
          )}
        </h1>
        <div className="flex items-center justify-center gap-4 text-sm text-[var(--text-muted)]">
          <span className="flex items-center gap-1">
            <Clock className="w-4 h-4" />
            {sse.durationSec ? formatDuration(sse.durationSec) : formatDuration(elapsed)}
          </span>
          {sse.fallbackMode && (
            <span className="badge badge-amber">⚠️ Fallback Mode</span>
          )}
        </div>
      </div>

      {/* Stage Stepper */}
      <div className="glass-card p-8">
        <div className="flex items-center justify-between">
          {STAGES.map((stage, i) => {
            const isCompleted = currentIndex > i || sse.status === "completed";
            const isActive = currentIndex === i && sse.status !== "completed" && sse.status !== "error";

            return (
              <div key={stage.key} className="flex items-center flex-1">
                <div className={`stage-step flex flex-col items-center ${isActive ? "active" : ""} ${isCompleted ? "completed" : ""}`}>
                  <div className={`step-circle w-12 h-12 rounded-xl flex items-center justify-center text-lg font-bold transition-all duration-500 ${
                    isCompleted ? "bg-[var(--accent-emerald)]" :
                    isActive ? "bg-[var(--accent-blue)]" :
                    "bg-[var(--bg-secondary)] border border-[var(--border-subtle)]"
                  }`}>
                    {isCompleted ? (
                      <CheckCircle2 className="w-6 h-6 text-white" />
                    ) : isActive ? (
                      <Loader2 className="w-6 h-6 text-white animate-spin" />
                    ) : (
                      <span className="text-[var(--text-muted)]">{stage.icon}</span>
                    )}
                  </div>
                  <span className={`mt-2 text-xs font-medium ${isCompleted ? "text-[var(--accent-emerald)]" : isActive ? "text-[var(--accent-blue)]" : "text-[var(--text-muted)]"}`}>
                    {stage.label}
                  </span>
                </div>

                {i < STAGES.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-3 rounded transition-colors duration-500 ${
                    currentIndex > i || sse.status === "completed" ? "bg-[var(--accent-emerald)]" : "bg-[var(--border-subtle)]"
                  }`} />
                )}
              </div>
            );
          })}
        </div>

        {/* Overall progress */}
        <div className="mt-6">
          <div className="h-2 rounded-full bg-[var(--bg-secondary)] overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700 ease-out"
              style={{
                width: `${sse.status === "completed" ? 100 : Math.max(((currentIndex + sse.progress) / STAGES.length) * 100, 2)}%`,
                background: sse.status === "completed" ? "var(--accent-emerald)" : "var(--gradient-primary)",
              }}
            />
          </div>
        </div>
      </div>

      {/* Live Log Feed */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Live Logs</h2>
          <span className="text-xs text-[var(--text-muted)]">{sse.logs.length} entries</span>
        </div>
        <div className="log-feed max-h-72 overflow-y-auto space-y-1 pr-2">
          {sse.logs.length === 0 ? (
            <p className="text-[var(--text-muted)] text-sm py-4 text-center">Waiting for logs...</p>
          ) : (
            sse.logs.map((log, i) => (
              <div key={i} className="flex gap-3 py-1 text-sm">
                <span className="text-[var(--text-muted)] shrink-0 text-xs mt-0.5">
                  {log.timestamp?.slice(11, 19) || "..."}
                </span>
                <span className="text-[var(--text-secondary)]">{log.message}</span>
              </div>
            ))
          )}
          {sse.status !== "completed" && sse.status !== "error" && (
            <div className="flex items-center gap-2 py-1 text-sm text-[var(--accent-blue)]">
              <div className="w-2 h-2 rounded-full bg-[var(--accent-blue)] animate-pulse" />
              <span>Processing...</span>
            </div>
          )}
        </div>
      </div>

      {/* Error display */}
      {sse.error && (
        <div className="glass-card p-6 border-l-4 border-[var(--accent-amber)]">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-[var(--accent-amber)]" />
            <p className="text-[var(--accent-amber)]">{sse.error}</p>
          </div>
        </div>
      )}

      {/* Navigate to results */}
      {sse.status === "completed" && (
        <div className="text-center">
          <button
            onClick={() => router.push(`/results/${sessionId}`)}
            className="btn-primary inline-flex items-center gap-2"
          >
            View Results
            <ArrowRight className="w-5 h-5" />
          </button>
          <p className="text-xs text-[var(--text-muted)] mt-2">Redirecting automatically...</p>
        </div>
      )}
    </div>
  );
}
