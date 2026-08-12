/**
 * Shared API types (Phase 20 — Frontend; TDD-001 §73).
 *
 * Mirrors the backend schemas in apps/api/src/api/routes/schemas.py and the
 * production domain enums (ProductionMode, ProductionStatus). The frontend
 * treats the backend as authoritative for production state (MAD-001 §46);
 * these types exist only to keep the UI in sync with the HTTP contract.
 */

export type ProductionMode = "genre" | "trending";

export type ProductionStatus =
  | "created"
  | "planning"
  | "concept_ready"
  | "generating_music"
  | "music_ready"
  | "generating_visual"
  | "visual_ready"
  | "analyzing_audio"
  | "rendering_master"
  | "master_ready"
  | "selecting_short"
  | "rendering_short"
  | "short_ready"
  | "generating_metadata"
  | "quality_check"
  | "completed"
  | "failed"
  | "cancelled";

/** Terminal statuses — once reached, a production no longer transitions. */
export const TERMINAL_STATUSES: readonly ProductionStatus[] = [
  "completed",
  "failed",
  "cancelled",
];

export function isTerminal(status: ProductionStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

/** Statuses that still expect the user-facing stage to advance. */
export function isActive(status: ProductionStatus | undefined): boolean {
  return status !== undefined && !isTerminal(status);
}

export interface ProductionSummary {
  id: string;
  mode: ProductionMode;
  genre: string | null;
  branding_text: string | null;
  status: ProductionStatus;
  target_duration_minutes: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface ProductionDetail extends ProductionSummary {
  attempt: number;
  workflow_id: string | null;
}

export interface CreateProductionRequest {
  mode: ProductionMode;
  genre?: string | null;
  branding_text?: string | null;
}

export interface CreateProductionResponse {
  id: string;
  status: string;
}

export interface ProgressResponse {
  production_id: string;
  status: ProductionStatus;
  progress: number; // 0.0 .. 1.0
  stage: string; // human-readable current stage, e.g. "Rendering Master"
  attempt: number;
}

export interface ArtifactDescriptor {
  kind: string; // filename, e.g. "master-16x9.mp4"
  url: string; // API-relative download url
  exists: boolean;
  size_bytes: number | null;
  mime_type: string;
}

export interface ArtifactsResponse {
  production_id: string;
  artifacts: ArtifactDescriptor[];
}

/** Canonical artifact filenames (TDD-001 §63) the UI surfaces directly. */
export const ARTIFACT_KINDS = {
  master_video: "master-16x9.mp4",
  short_video: "short-9x16.mp4",
  metadata: "metadata.json",
  qc_report: "qc-report.json",
} as const;

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Short human-relative timestamp ("just now", "3m ago", "2h ago", "Aug 9"). */
export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffMs = Date.now() - then;
  const secs = Math.floor(diffMs / 1000);
  if (secs < 45) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}
