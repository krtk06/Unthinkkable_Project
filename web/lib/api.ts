import type {
  CandidateDetail,
  MatchesPage,
  NormalizedRequirements,
  SessionStatus,
  UploadResult,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function parseError(response: Response): Promise<never> {
  let code = "UNKNOWN_ERROR";
  let message = `Request failed with status ${response.status}`;
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } };
    if (body.error?.code) code = body.error.code;
    if (body.error?.message) message = body.error.message;
  } catch {
    // keep fallbacks
  }
  throw new ApiError(code, message, response.status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) return parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface MatchQuery {
  threshold?: number;
  top_n?: number;
  min_required_coverage?: number;
  min_experience_months?: number;
  work_mode?: string;
  location?: string;
  required_skills_complete?: boolean;
  cursor?: string | null;
  limit?: number;
}

function buildMatchParams(query: MatchQuery): string {
  const params = new URLSearchParams();
  if (query.threshold !== undefined) params.set("threshold", String(query.threshold));
  if (query.top_n !== undefined) params.set("top_n", String(query.top_n));
  if (query.min_required_coverage !== undefined)
    params.set("min_required_coverage", String(query.min_required_coverage));
  if (query.min_experience_months !== undefined)
    params.set("min_experience_months", String(query.min_experience_months));
  if (query.work_mode) params.set("work_mode", query.work_mode);
  if (query.location) params.set("location", query.location);
  if (query.required_skills_complete !== undefined)
    params.set("required_skills_complete", String(query.required_skills_complete));
  if (query.cursor) params.set("cursor", query.cursor);
  params.set("limit", String(query.limit ?? 50));
  return params.toString();
}

export const api = {
  createSession(jobDescription?: string): Promise<{ session_id: string }> {
    return request("/v1/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_description: jobDescription || null }),
    });
  },

  saveJobDescription(sessionId: string, text: string): Promise<{
    session_id: string;
    status: string;
    normalized_requirements: NormalizedRequirements;
  }> {
    return request(`/v1/sessions/${sessionId}/job-description`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  },

  uploadJobDescriptionFile(
    sessionId: string,
    file: File
  ): Promise<{
    session_id: string;
    status: string;
    normalized_requirements: NormalizedRequirements;
  }> {
    const form = new FormData();
    form.append("file", file, file.name);
    return request(`/v1/sessions/${sessionId}/job-description/file`, {
      method: "POST",
      body: form,
    });
  },

  uploadResumes(
    sessionId: string,
    files: File[],
    idempotencyKey?: string
  ): Promise<UploadResult> {
    const form = new FormData();
    for (const file of files) form.append("files", file, file.name);
    const headers: Record<string, string> = {};
    const key =
      idempotencyKey ??
      (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : undefined);
    if (key) headers["Idempotency-Key"] = key;
    return request(`/v1/sessions/${sessionId}/resumes`, {
      method: "POST",
      body: form,
      headers,
    });
  },

  getSessionStatus(sessionId: string): Promise<SessionStatus> {
    return request(`/v1/sessions/${sessionId}/status`);
  },

  getMatches(sessionId: string, query: MatchQuery = {}): Promise<MatchesPage> {
    return request(`/v1/sessions/${sessionId}/matches?${buildMatchParams(query)}`);
  },

  getCandidate(candidateId: string): Promise<CandidateDetail> {
    return request(`/v1/candidates/${candidateId}`);
  },

  deleteSession(sessionId: string): Promise<void> {
    return request(`/v1/sessions/${sessionId}`, { method: "DELETE" });
  },
};
