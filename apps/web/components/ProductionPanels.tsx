"use client";

/**
 * Result panels (TDD-001 §75 — MasterPreview, ShortPreview, MetadataPanel,
 * QCPanel; MASTER §33; PRD-001 §51-52).
 *
 * Videos stream from the backend artifact endpoint via the download url, so
 * "the user must be able to access the generated local artifacts" (MASTER §33)
 * without exposing filesystem paths (TDD-001 §72). Metadata and QC JSON are
 * fetched through the same safe endpoint and rendered as structured cards.
 */
import { useEffect, useState } from "react";

import { api, apiUrl } from "@/services/api";
import {
  ARTIFACT_KINDS,
  formatBytes,
  type ArtifactDescriptor,
} from "@/types";

function findArtifact(
  artifacts: ArtifactDescriptor[],
  kind: string,
): ArtifactDescriptor | undefined {
  return artifacts.find((artifact) => artifact.kind === kind);
}

// --- video previews ----------------------------------------------------------

function VideoPanel({
  kind,
  label,
  aspectClass,
  artifact,
}: {
  kind: string;
  label: string;
  aspectClass: string;
  artifact?: ArtifactDescriptor;
}) {
  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">{label}</h3>
        {artifact?.exists && (
          <a
            href={apiUrl(artifact.url)}
            download
            className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:border-zinc-500"
          >
            Download {artifact.size_bytes !== null ? formatBytes(artifact.size_bytes) : ""}
          </a>
        )}
      </div>
      {artifact?.exists ? (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <video
          key={artifact.url}
          controls
          preload="metadata"
          className={`w-full rounded-lg bg-black ${aspectClass}`}
          src={apiUrl(artifact.url)}
        />
      ) : (
        <div
          className={`flex ${aspectClass} w-full items-center justify-center rounded-lg border border-dashed border-zinc-800 text-sm text-zinc-600`}
        >
          {label} not available yet
        </div>
      )}
    </section>
  );
}

export function MasterPreview({
  artifacts,
}: {
  artifacts: ArtifactDescriptor[];
}) {
  return (
    <VideoPanel
      kind={ARTIFACT_KINDS.master_video}
      label="Master Video (16:9)"
      aspectClass="aspect-video"
      artifact={findArtifact(artifacts, ARTIFACT_KINDS.master_video)}
    />
  );
}

export function ShortPreview({
  artifacts,
}: {
  artifacts: ArtifactDescriptor[];
}) {
  return (
    <VideoPanel
      kind={ARTIFACT_KINDS.short_video}
      label="Short Video (9:16)"
      aspectClass="aspect-[9/16] max-h-[420px]"
      artifact={findArtifact(artifacts, ARTIFACT_KINDS.short_video)}
    />
  );
}

// --- JSON panels -------------------------------------------------------------

function useJsonArtifact(url: string | undefined) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!url) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .getJsonArtifact(url)
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  return { data, loading };
}

function readString(data: unknown, key: string): string | null {
  if (typeof data === "object" && data !== null && key in data) {
    const value = (data as Record<string, unknown>)[key];
    return typeof value === "string" ? value : null;
  }
  return null;
}

export function MetadataPanel({
  artifacts,
}: {
  artifacts: ArtifactDescriptor[];
}) {
  const artifact = findArtifact(artifacts, ARTIFACT_KINDS.metadata);
  const { data, loading } = useJsonArtifact(artifact?.url);
  const master = data?.master as Record<string, unknown> | undefined;
  const short = data?.short as Record<string, unknown> | undefined;

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">Metadata</h3>
        {artifact?.exists && (
          <a
            href={apiUrl(artifact.url)}
            download
            className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:border-zinc-500"
          >
            metadata.json
          </a>
        )}
      </div>
      {loading ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : data === null ? (
        <p className="text-sm text-zinc-600">Metadata not produced yet.</p>
      ) : (
        <div className="space-y-3 text-sm">
          <MetadataBlock title="Master" metadata={master} />
          <MetadataBlock title="Short" metadata={short} />
        </div>
      )}
    </section>
  );
}

function MetadataBlock({
  title,
  metadata,
}: {
  title: string;
  metadata?: Record<string, unknown>;
}) {
  const metaTitle = metadata && readString(metadata, "title");
  const description = metadata && readString(metadata, "description");
  const hashtags = metadata?.hashtags;
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-zinc-500">
        {title}
      </h4>
      <p className="font-medium text-zinc-200">{metaTitle ?? "—"}</p>
      <p className="mt-1 text-zinc-400">{description ?? "—"}</p>
      {Array.isArray(hashtags) && hashtags.length > 0 && (
        <p className="mt-1 text-indigo-300">
          {(hashtags as string[]).join(" ")}
        </p>
      )}
    </div>
  );
}

export function QCPanel({ artifacts }: { artifacts: ArtifactDescriptor[] }) {
  const artifact = findArtifact(artifacts, ARTIFACT_KINDS.qc_report);
  const { data, loading } = useJsonArtifact(artifact?.url);
  const passed = typeof data?.passed === "boolean" ? data.passed : null;
  const score = typeof data?.score === "number" ? data.score : null;
  const issues = Array.isArray(data?.issues) ? (data.issues as string[]) : [];
  const warnings = Array.isArray(data?.warnings)
    ? (data.warnings as string[])
    : [];

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">Quality Control</h3>
        {artifact?.exists && (
          <a
            href={apiUrl(artifact.url)}
            download
            className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:border-zinc-500"
          >
            qc-report.json
          </a>
        )}
      </div>
      {loading ? (
        <p className="text-sm text-zinc-500">Loading…</p>
      ) : data === null ? (
        <p className="text-sm text-zinc-600">Quality report not produced yet.</p>
      ) : (
        <div className="space-y-3 text-sm">
          <div className="flex items-center gap-2">
            {passed !== null && (
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                  passed
                    ? "bg-emerald-500/10 text-emerald-300"
                    : "bg-red-500/10 text-red-300"
                }`}
              >
                {passed ? "PASSED" : "FAILED"}
              </span>
            )}
            {score !== null && (
              <span className="text-zinc-400">
                score <span className="tabular-nums text-zinc-200">{score.toFixed(2)}</span>
              </span>
            )}
          </div>
          {issues.length > 0 && (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-red-400">
                Issues
              </h4>
              <ul className="list-inside list-disc space-y-0.5 text-zinc-300">
                {issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
          {warnings.length > 0 && (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-400">
                Warnings
              </h4>
              <ul className="list-inside list-disc space-y-0.5 text-zinc-400">
                {warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
