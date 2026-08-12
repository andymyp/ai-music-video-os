"use client";

/**
 * Production detail view (TDD-001 §75; MASTER §32-33; PRD-001 §51-53).
 *
 * Shows the live stage/progress (polled from the backend, MAD-001 §46), the
 * production summary, and the result panels — Master/Short previews, metadata
 * and the QC report — once their artifacts exist. Actions (retry/cancel) call
 * the Phase-19 endpoints and immediately re-sync state.
 *
 * Modern pass: a gradient title, a seven-phase pipeline stepper driven by the
 * authoritative status (with a red stop-point when a production fails), a
 * "Deliverables ready" banner on completion, `surface` cards, and the rest of
 * the earlier polish (relative timestamps, live dot, two-step cancel, notices,
 * auto-scroll, grouped artifacts).
 */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { ComponentType } from "react";

import {
  BracesIcon,
  CheckIcon,
  DocumentIcon,
  DownloadIcon,
  FileIcon,
  FilmIcon,
  MusicIcon,
  ShieldIcon,
} from "@/components/icons";
import {
  MasterPreview,
  MetadataPanel,
  QCPanel,
  ShortPreview,
} from "@/components/ProductionPanels";
import { RelativeTime } from "@/components/RelativeTime";
import { StageStepper } from "@/components/StageStepper";
import { StatusBadge } from "@/components/StatusBadge";
import { useProduction } from "@/hooks/useProduction";
import { surface, textAccent } from "@/lib/ui";
import { apiUrl } from "@/services/api";
import {
  formatBytes,
  isActive,
  type ArtifactDescriptor,
  type ProductionStatus,
} from "@/types";

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
    refresh,
  } = useProduction(productionId);

  const [notice, setNotice] = useState<{
    kind: "success" | "info";
    text: string;
  } | null>(null);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const confirmTimerRef = useRef<number | null>(null);
  const resultsRef = useRef<HTMLDivElement>(null);

  const currentStatus = status ?? detail?.status;
  const active = isActive(currentStatus);

  // Remember the last in-flight status so a failed/cancelled production can
  // show where it stopped (the backend reports progress 0 for terminal states).
  const lastActiveRef = useRef<ProductionStatus | undefined>(undefined);
  useEffect(() => {
    if (currentStatus !== undefined && isActive(currentStatus)) {
      lastActiveRef.current = currentStatus;
    }
  }, [currentStatus]);

  // Auto-dismiss transient action feedback.
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  // Clear the cancel-confirmation timer on unmount.
  useEffect(
    () => () => {
      if (confirmTimerRef.current !== null) {
        window.clearTimeout(confirmTimerRef.current);
      }
    },
    [],
  );

  // Scroll to the result panels when the production transitions to completed
  // (but not on first load of an already-completed production).
  const prevStatusRef = useRef<ProductionStatus | undefined>(undefined);
  const initializedRef = useRef(false);
  useEffect(() => {
    if (!initializedRef.current) {
      initializedRef.current = true;
      prevStatusRef.current = currentStatus;
      return;
    }
    const prev = prevStatusRef.current;
    prevStatusRef.current = currentStatus;
    if (prev !== "completed" && currentStatus === "completed") {
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [currentStatus]);

  if (loading && detail === null) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="space-y-2">
          <div className="skeleton h-6 w-44" />
          <div className="skeleton h-3 w-28" />
        </div>
        <div className={`${surface} p-4`}>
          <div className="skeleton mb-3 h-4 w-20" />
          <div className="skeleton h-2 w-full" />
        </div>
      </div>
    );
  }

  if (error !== null && detail === null) {
    return (
      <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-6 text-sm text-red-300 animate-fade-in">
        <p>{error}</p>
        <button
          onClick={() => void refresh()}
          className="mt-3 rounded-md border border-red-500/40 px-3 py-1.5 text-xs font-medium text-red-200 transition-colors hover:bg-red-500/10"
        >
          Retry
        </button>
      </div>
    );
  }

  const displayName =
    detail && detail.mode === "genre" && detail.genre?.trim()
      ? detail.genre
      : "Trending";
  const shortId =
    productionId.length > 8 ? productionId.slice(0, 8) : productionId;

  const progressValue = progress?.progress ?? 0;
  const stage =
    currentStatus === "completed"
      ? "Completed"
      : currentStatus === "failed"
        ? "Failed"
        : currentStatus === "cancelled"
          ? "Cancelled"
          : (progress?.stage ?? "Pending");
  const percentText =
    currentStatus === "failed" || currentStatus === "cancelled"
      ? "—"
      : `${Math.round(progressValue * 100)}%`;

  const outcome: "running" | "completed" | "failed" | "cancelled" =
    currentStatus === "completed"
      ? "completed"
      : currentStatus === "failed"
        ? "failed"
        : currentStatus === "cancelled"
          ? "cancelled"
          : "running";
  const position: ProductionStatus =
    currentStatus !== undefined && isActive(currentStatus)
      ? currentStatus
      : (lastActiveRef.current ?? "created");

  const handleCancelClick = () => {
    if (confirmingCancel) {
      setConfirmingCancel(false);
      setNotice({ kind: "info", text: "Cancelling production…" });
      void cancel();
    } else {
      setConfirmingCancel(true);
      confirmTimerRef.current = window.setTimeout(
        () => setConfirmingCancel(false),
        4000,
      );
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div>
        <Link href="/" className="text-xs text-indigo-300 hover:text-indigo-200">
          ← Dashboard
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className={`text-xl font-semibold capitalize tracking-tight ${textAccent}`}>
            {displayName}
          </h1>
          <span
            title={productionId}
            className="rounded-md border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-xs text-zinc-500"
          >
            #{shortId}
          </span>
          {currentStatus !== undefined && <StatusBadge status={currentStatus} />}
        </div>
        {detail && (
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500">
            <span>attempt {detail.attempt}</span>
            <span className="capitalize">{detail.mode}</span>
            {detail.branding_text && <span>{detail.branding_text}</span>}
            <span>
              Created <RelativeTime iso={detail.created_at} />
            </span>
            {detail.completed_at && (
              <span>
                Completed <RelativeTime iso={detail.completed_at} />
              </span>
            )}
          </div>
        )}
      </div>

      {error !== null && (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
          {error}
        </p>
      )}

      {notice !== null && (
        <p
          className={`rounded-md border px-3 py-2 text-sm ${
            notice.kind === "success"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
              : "border-amber-500/40 bg-amber-500/10 text-amber-300"
          } animate-fade-in`}
        >
          {notice.text}
        </p>
      )}

      {/* Completion banner */}
      {currentStatus === "completed" && (
        <div className="flex items-center gap-3 rounded-xl bg-gradient-to-r from-emerald-500/15 to-teal-500/10 px-4 py-3 ring-1 ring-emerald-500/30 animate-fade-in">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-300">
            <CheckIcon className="h-4 w-4" />
          </span>
          <div>
            <p className="text-sm font-medium text-emerald-200">
              Deliverables ready
            </p>
            <p className="text-xs text-emerald-300/70">
              Both videos, metadata and the QC report are available below.
            </p>
          </div>
        </div>
      )}

      {/* Progress (TDD-001 §75 — Status/Progress) */}
      <section className={`${surface} p-4`}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
            Progress
            {active && (
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-indigo-500" />
              </span>
            )}
          </h2>
          {detail && detail.workflow_id && (
            <span className="font-mono text-xs text-zinc-600">
              {detail.workflow_id}
            </span>
          )}
        </div>

        <div className="mb-4 flex items-baseline justify-between text-sm">
          <span className="font-medium text-zinc-200">{stage}</span>
          <span className="tabular-nums text-zinc-400">{percentText}</span>
        </div>

        <StageStepper position={position} outcome={outcome} />

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

        {/* Actions (TDD-001 §75 — Actions: retry/cancel) */}
        {currentStatus !== undefined && !["completed", "cancelled"].includes(currentStatus) && (
          <div className="mt-4 flex gap-2">
            {currentStatus === "failed" && (
              <button
                onClick={() => {
                  setNotice({ kind: "info", text: "Retrying…" });
                  void retry();
                }}
                disabled={retrying}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-40"
              >
                {retrying ? "Retrying…" : "Retry"}
              </button>
            )}
            {currentStatus !== "failed" && (
              <button
                onClick={handleCancelClick}
                disabled={cancelling}
                className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-40 ${
                  confirmingCancel
                    ? "border-red-500 bg-red-500/15 text-red-200 hover:bg-red-500/25"
                    : "border-zinc-600 text-zinc-300 hover:border-red-500 hover:text-red-300"
                }`}
              >
                {cancelling
                  ? "Cancelling…"
                  : confirmingCancel
                    ? "Confirm cancel?"
                    : "Cancel"}
              </button>
            )}
          </div>
        )}
      </section>

      {/* Result panels (MASTER §33; PRD-001 §51-52) */}
      <div ref={resultsRef} className="grid scroll-mt-8 gap-6 lg:grid-cols-2">
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

// --- artifact index ----------------------------------------------------------

interface ArtifactGroup {
  title: string;
  icon: ComponentType<{ className?: string }>;
  test: (kind: string) => boolean;
}

const ARTIFACT_GROUPS: ArtifactGroup[] = [
  { title: "Video", icon: FilmIcon, test: (k) => /\.mp4$/i.test(k) },
  {
    title: "Audio",
    icon: MusicIcon,
    test: (k) => /\.(wav|mp3|ogg|flac)$/i.test(k),
  },
  { title: "Metadata", icon: BracesIcon, test: (k) => k === "metadata.json" },
  {
    title: "Quality Control",
    icon: ShieldIcon,
    test: (k) => k === "qc-report.json",
  },
  {
    title: "Planning",
    icon: DocumentIcon,
    test: (k) => /plan|concept|brief/i.test(k),
  },
];

function groupArtifacts(
  artifacts: ArtifactDescriptor[],
): (ArtifactGroup & { items: ArtifactDescriptor[] })[] {
  const used = new Set<string>();
  const groups: (ArtifactGroup & { items: ArtifactDescriptor[] })[] = [];
  for (const group of ARTIFACT_GROUPS) {
    const items = artifacts.filter(
      (artifact) => group.test(artifact.kind) && !used.has(artifact.kind),
    );
    if (items.length > 0) {
      items.forEach((artifact) => used.add(artifact.kind));
      groups.push({ ...group, items });
    }
  }
  const other = artifacts.filter((artifact) => !used.has(artifact.kind));
  if (other.length > 0) {
    groups.push({ title: "Other", icon: FileIcon, test: () => false, items: other });
  }
  return groups;
}

function ArtifactsList({
  artifacts,
  productionId,
}: {
  artifacts: ArtifactDescriptor[];
  productionId: string;
}) {
  const groups = groupArtifacts(artifacts);
  if (groups.length === 0) return null;
  return (
    <section className={`${surface} p-4`}>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-zinc-200">Artifacts</h2>
        <span className="font-mono text-xs text-zinc-600">{productionId}</span>
      </div>
      <div className="space-y-4">
        {groups.map((group) => (
          <div key={group.title}>
            <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-zinc-500">
              <group.icon className="h-3.5 w-3.5" />
              {group.title}
            </h3>
            <ul className="space-y-1">
              {group.items.map((artifact) => (
                <li
                  key={artifact.kind}
                  className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 transition-colors hover:bg-zinc-800/40"
                >
                  <span
                    title={artifact.kind}
                    className="truncate font-mono text-xs text-zinc-200"
                  >
                    {artifact.kind}
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    {artifact.exists && artifact.size_bytes !== null && (
                      <span className="text-xs tabular-nums text-zinc-500">
                        {formatBytes(artifact.size_bytes)}
                      </span>
                    )}
                    {artifact.exists ? (
                      <a
                        href={apiUrl(artifact.url)}
                        download
                        className="inline-flex items-center gap-1 rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 transition-colors hover:border-indigo-500 hover:text-indigo-200"
                      >
                        <DownloadIcon className="h-3 w-3" />
                        Download
                      </a>
                    ) : (
                      <span className="text-xs text-zinc-600">pending</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
