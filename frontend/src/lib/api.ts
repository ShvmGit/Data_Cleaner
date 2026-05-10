// API client — fetch wrapper for backend communication

import type { UploadResponse, PipelineStartResponse, PipelineState, CleaningCriteria } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class APIError extends Error {
  constructor(public status: number, message: string, public details?: Record<string, unknown>) {
    super(message);
    this.name = "APIError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_URL}${path}`;

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    let detail = "Request failed";
    try {
      const body = await res.json();
      detail = body.detail || body.error?.message || detail;
    } catch {
      // ignore
    }
    throw new APIError(res.status, detail);
  }

  return res.json();
}

export const api = {
  /** Upload a file for processing */
  async upload(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const url = `${API_URL}/api/upload`;
    const res = await fetch(url, { method: "POST", body: formData });

    if (!res.ok) {
      let detail = "Upload failed";
      try {
        const body = await res.json();
        detail = body.detail || detail;
      } catch {
        // ignore
      }
      throw new APIError(res.status, detail);
    }

    return res.json();
  },

  /** Start the cleaning pipeline */
  async startPipeline(fileId: string, criteria: CleaningCriteria): Promise<PipelineStartResponse> {
    return request<PipelineStartResponse>("/api/pipeline/start", {
      method: "POST",
      body: JSON.stringify({ file_id: fileId, criteria }),
    });
  },

  /** Fetch pipeline results */
  async getResults(sessionId: string): Promise<PipelineState> {
    return request<PipelineState>(`/api/pipeline/results/${sessionId}`);
  },

  /** Get SSE stream URL */
  getStreamUrl(sessionId: string): string {
    return `${API_URL}/api/pipeline/stream/${sessionId}`;
  },

  /** Get download URL */
  getDownloadUrl(sessionId: string, fileType: string): string {
    return `${API_URL}/api/download/${sessionId}/${fileType}`;
  },
};
