"use client";

/**
 * Production detail view (TDD-001 §75; MASTER §32-33; PRD-001 §51-53).
 *
 * Shows the live stage/progress (polled from the backend, MAD-001 §46), the
 * production summary, and the result panels — Master/Short previews, metadata
 * and the QC report — once their artifacts exist. Actions (retry/cancel) call
 * the Phase-19 endpoints and immediately re-sync state.
 */
import Link from "next/link";

import { ProgressBar } from "@/components/ProgressBar";
import {
  MasterPreview,
  MetadataPanel,
  QCPanel,
  ShortPreview,
} from "@/components/ProductionPanels";
import { StatusBadge } from "@/components/StatusBadge";
import { useProduction } from "@/hooks/useProduction";
import { apiUrl } from "@/services/api";
import { formatBytes, type ArtifactDescriptor } from "@/types";

export function ProductionDetail({ productionId }: { productionId: string }) {
  const {
    detail,
    progress,
    artifacts,
    status,
    error,
    loading,
    retrying,
    cancelling,
    retry,
    cancel,
  } = useProduction(productionId);

  if (loading && detail === null) {
    return <div className="p-8 text-sm text-zinc-500">Loading production…</div>;
  }

  if (error !== null && detail === null) {
    return (
      <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-6 text-sm text-red-300">
        {error}
      </div>
    );
  }

  const stage = progress?.stage ?? "Pending";
  const progressValue = progress?.progress ?? 0;
  const currentStatus = status ?? detail?.status;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          href="/"
          className="text-xs text-indigo-300 hover:text-indigo-200"
        >
          ← Dashboard
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-sm text-zinc-100">{productionId}</h1>
          {currentStatus !== undefined && <StatusBadge status={currentStatus} />}
          {detail && (
            <span className="text-xs text-zinc-500">
              attempt {detail.attempt} ·{" "}
              {detail.mode === "genre" ? detail.genre ?? "genre" : "trending"}
              {detail.branding_text ? ` · ${detail.branding_text}` : ""}
            </span>
          )}
        </div>
      </div>

      {error !== null && (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
          {error}
        </p>
      )}

      {/* Progress (TDD-001 §75 — Status/Progress) */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-200">Progress</h2>
          {detail && detail.workflow_id && (
            <span className="font-mono text-xs text-zinc-600">
              {detail.workflow_id}
            </span>
          )}
        </div>
        <ProgressBar progress={progressValue} stage={stage} />
        {currentStatus === "failed" && (
          <p className="mt-3 text-sm text-red-300">
            This production failed and can be retried.
          </p>
        )}
        {currentStatus === "cancelled" && (
          <p className="mt-3 text-sm text-zinc-400">
            This production was cancelled.
          </p>
        )}
        {currentStatus === "completed" && (
          <p className="mt-3 text-sm text-emerald-300">
            Production complete — all deliverables are available below.
          </p>
        )}

        {/* Actions (TDD-001 §75 — Actions: retry/cancel) */}
        {(currentStatus === "failed" || (currentStatus !== undefined && !["completed", "cancelled"].includes(currentStatus))) && (
          <div className="mt-4 flex gap-2">
            {currentStatus === "failed" && (
              <button
                onClick={() => void retry()}
                disabled={retrying}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
              >
                {retrying ? "Retrying…" : "Retry"}
              </button>
            )}
            {currentStatus !== "failed" &&
              currentStatus !== undefined &&
              !["completed", "cancelled"].includes(currentStatus) && (
                <button
                  onClick={() => void cancel()}
                  disabled={cancelling}
                  className="rounded-lg border border-zinc-600 px-3 py-1.5 text-sm font-medium text-zinc-300 hover:border-red-500 hover:text-red-300 disabled:opacity-40"
                >
                  {cancelling ? "Cancelling…" : "Cancel"}
                </button>
              )}
          </div>
        )}
      </section>

      {/* Result panels (MASTER §33; PRD-001 §51-52) */}
      <div className="grid gap-6 lg:grid-cols-2">
        <MasterPreview artifacts={artifacts} />
        <ShortPreview artifacts={artifacts} />
        <MetadataPanel artifacts={artifacts} />
        <QCPanel artifacts={artifacts} />
      </div>

      {/* Full artifact index */}
      <ArtifactsList artifacts={artifacts} productionId={productionId} />
    </div>
  );
}

function ArtifactsList({
  artifacts,
  productionId,
}: {
  artifacts: ArtifactDescriptor[];
  productionId: string;
}) {
  if (artifacts.length === 0) return null;
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <h2 className="mb-3 text-sm font-semibold text-zinc-200">
        Artifacts ({productionId})
      </h2>
      <ul className="divide-y divide-zinc-800/70 text-sm">
        {artifacts.map((artifact) => (
          <li
            key={artifact.kind}
            className="flex items-center justify-between py-2"
          >
            <span
              className={`font-mono text-xs ${
                artifact.exists ? "text-zinc-200" : "text-zinc-600"
              }`}
            >
              {artifact.kind}
            </span>
            <span className="flex items-center gap-2">
              {artifact.exists && artifact.size_bytes !== null && (
                <span className="text-xs tabular-nums text-zinc-500">
                  {formatBytes(artifact.size_bytes)}
                </span>
              )}
              {artifact.exists ? (
                <a
                  href={apiUrl(artifact.url)}
                  download
                  className="text-xs text-indigo-300 hover:text-indigo-200"
                >
                  download
                </a>
              ) : (
                <span className="text-xs text-zinc-600">pending</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
