"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type { SSEProgressData, SSELogData, SSECompleteData, SSEErrorData, PipelineStage } from "@/lib/types";

interface SSEState {
  stage: PipelineStage;
  progress: number;
  logs: SSELogData[];
  status: "connecting" | "connected" | "completed" | "error" | "disconnected";
  error?: string;
  outputs?: Record<string, string>;
  fallbackMode: boolean;
  durationSec?: number;
}

const MAX_RECONNECT = 3;
const RECONNECT_DELAY = 2000;

export function useSSE(sessionId: string | null) {
  const [state, setState] = useState<SSEState>({
    stage: "pending",
    progress: 0,
    logs: [],
    status: "connecting",
    fallbackMode: false,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectCountRef = useRef(0);

  const connect = useCallback(() => {
    if (!sessionId) return;

    const url = api.getStreamUrl(sessionId);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      setState((s) => ({ ...s, status: "connected" }));
      reconnectCountRef.current = 0;
    };

    es.addEventListener("progress", (e) => {
      const data: SSEProgressData = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        stage: data.stage as PipelineStage,
        progress: data.progress,
      }));
    });

    es.addEventListener("log", (e) => {
      const data: SSELogData = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        logs: [...s.logs, data],
      }));
    });

    es.addEventListener("complete", (e) => {
      const data: SSECompleteData = JSON.parse(e.data);
      setState((s) => ({
        ...s,
        stage: "completed",
        progress: 1,
        status: "completed",
        outputs: data.outputs,
        fallbackMode: data.fallback_mode,
        durationSec: data.duration_sec,
      }));
      es.close();
    });

    es.addEventListener("error", (e) => {
      try {
        const data: SSEErrorData = JSON.parse((e as MessageEvent).data);
        setState((s) => ({
          ...s,
          status: data.recoverable ? "connected" : "error",
          error: data.message,
        }));
        if (!data.recoverable) es.close();
      } catch {
        // Connection error, not a data error
        handleReconnect();
      }
    });

    es.onerror = () => {
      handleReconnect();
    };
  }, [sessionId]);

  const handleReconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    if (reconnectCountRef.current < MAX_RECONNECT) {
      reconnectCountRef.current++;
      setState((s) => ({
        ...s,
        status: "connecting",
        error: `Connection lost. Reconnecting (${reconnectCountRef.current}/${MAX_RECONNECT})...`,
      }));
      setTimeout(connect, RECONNECT_DELAY);
    } else {
      setState((s) => ({
        ...s,
        status: "disconnected",
        error: "Connection lost. Please refresh to check results.",
      }));
    }
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
    };
  }, [connect]);

  return state;
}
