/**
 * Typed API client for the AMV production backend (Phase 20 — Frontend).
 *
 * Wraps the Phase-19 HTTP contract (apps/api/src/api/routes/productions.py):
 *
 *     POST /api/productions                    create
 *     GET  /api/productions                    list
 *     GET  /api/productions/{id}               detail
 *     POST /api/productions/{id}/retry         retry failed
 *     POST /api/productions/{id}/cancel        cancel running
 *     GET  /api/productions/{id}/progress      live progress
 *     GET  /api/productions/{id}/artifacts     artifact listing
 *     GET  /api/productions/{id}/artifacts/{k} artifact download
 *
 * The backend remains the single source of truth for production state
 * (MAD-001 §46); the client only reads it. All errors surface as ApiError so
 * components can react to 4xx/5xx distinctly.
 */
import type {
  ArtifactsResponse,
  CreateProductionRequest,
  CreateProductionResponse,
  ProductionDetail,
  ProductionSummary,
  ProgressResponse,
} from "@/types";

export const API_BASE: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** URL-safe base for artifact downloads (relative urls come from the API). */
export function apiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body — fall through to a generic message
    }
    throw new ApiError(
      response.status,
      detail ?? `request failed (${response.status})`,
    );
  }
  return (await response.json()) as T;
}

/** Fetch a JSON artifact body (metadata / qc-report). Returns null on 404. */
async function fetchJson(
  url: string,
): Promise<Record<string, unknown> | null> {
  const response = await fetch(apiUrl(url));
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new ApiError(response.status, `failed to fetch ${url}`);
  }
  return (await response.json()) as Record<string, unknown>;
}

export const api = {
  async createProduction(
    payload: CreateProductionRequest,
  ): Promise<CreateProductionResponse> {
    return request<CreateProductionResponse>("/api/productions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async listProductions(
    limit = 50,
    offset = 0,
  ): Promise<ProductionSummary[]> {
    return request<ProductionSummary[]>(
      `/api/productions?limit=${limit}&offset=${offset}`,
    );
  },

  async getProduction(id: string): Promise<ProductionDetail> {
    return request<ProductionDetail>(`/api/productions/${id}`);
  },

  async retryProduction(id: string): Promise<ProductionDetail> {
    return request<ProductionDetail>(`/api/productions/${id}/retry`, {
      method: "POST",
    });
  },

  async cancelProduction(id: string): Promise<ProductionDetail> {
    return request<ProductionDetail>(`/api/productions/${id}/cancel`, {
      method: "POST",
    });
  },

  async getProgress(id: string): Promise<ProgressResponse> {
    return request<ProgressResponse>(`/api/productions/${id}/progress`);
  },

  async getArtifacts(id: string): Promise<ArtifactsResponse> {
    return request<ArtifactsResponse>(`/api/productions/${id}/artifacts`);
  },

  /** JSON payload of a metadata/qc artifact, or null while unproduced. */
  async getJsonArtifact(url: string): Promise<Record<string, unknown> | null> {
    return fetchJson(url);
  },
};
