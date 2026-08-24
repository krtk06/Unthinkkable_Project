import { clearToken, getToken } from "./auth";
import type {
  CandidateDetail,
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
  const token = getToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  if (response.status === 401 && !path.startsWith("/v1/auth/login")) {
    clearToken();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
  }
  if (!response.ok) return parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  login(username: string, password: string): Promise<{ access_token: string; token_type: string; username: string }> {
    return request("/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  },

  signup(username: string, email: string, password: string): Promise<{ access_token: string; token_type: string; username: string }> {
    return request("/v1/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    });
  },

  me(): Promise<{ username: string }> {
    return request("/v1/auth/me");
  },

  createSession(): Promise<{ session_id: string }> {
    return request("/v1/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_description: null }),
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

  getCandidate(candidateId: string): Promise<CandidateDetail> {
    return request(`/v1/candidates/${candidateId}`);
  },
};
