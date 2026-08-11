"use client";

/**
 * Production detail hook (Phase 20 — Frontend; TDD-001 §74-76, MAD-001 §46).
 *
 * Fetches the production detail once and then polls /progress + /artifacts
 * every `POLL_MS` while the production is still active. Progress/stage come
 * straight from the backend, so the UI can never drift from the state machine.
 * Retry/cancel call the Phase-19 endpoints and immediately re-sync.
 */
import { useCallback, useEffect, useState } from "react";

import { usePolling } from "@/hooks/usePolling";
import { ApiError, api } from "@/services/api";
import {
  type ArtifactDescriptor,
  type ProductionDetail,
  type ProductionStatus,
  type ProgressResponse,
  isActive,
} from "@/types";

const POLL_MS = 2000;

export interface UseProductionResult {
  detail: ProductionDetail | null;
  progress: ProgressResponse | null;
  artifacts: ArtifactDescriptor[];
  /** Effective status: live progress status, falling back to detail status. */
  status: ProductionStatus | undefined;
  error: string | null;
  loading: boolean;
  retrying: boolean;
  cancelling: boolean;
  retry: () => Promise<void>;
  cancel: () => Promise<void>;
  refresh: () => Promise<void>;
}

export function useProduction(productionId: string): UseProductionResult {
  const [detail, setDetail] = useState<ProductionDetail | null>(null);
  const [progress, setProgress] = useState<ProgressResponse | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactDescriptor[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"retry" | "cancel" | null>(null);

  const status: ProductionStatus | undefined =
    progress?.status ?? detail?.status;
  const active = isActive(status);

  const refresh = useCallback(async () => {
    try {
      const [nextDetail, nextProgress, nextArtifacts] = await Promise.all([
        api.getProduction(productionId),
        api.getProgress(productionId),
        api.getArtifacts(productionId),
      ]);
      setDetail(nextDetail);
      setProgress(nextProgress);
      setArtifacts(nextArtifacts.artifacts);
      setError(null);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        setError("Production not found.");
      } else {
        setError(
          caught instanceof Error ? caught.message : "Failed to load production",
        );
      }
    } finally {
      setLoading(false);
    }
  }, [productionId]);

  // Immediate first load; polling continues while the production is active.
  useEffect(() => {
    void refresh();
  }, [refresh]);

  const retry = useCallback(async () => {
    setBusy("retry");
    try {
      await api.retryProduction(productionId);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Retry failed");
    } finally {
      setBusy(null);
    }
  }, [productionId, refresh]);

  const cancel = useCallback(async () => {
    setBusy("cancel");
    try {
      await api.cancelProduction(productionId);
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Cancel failed");
    } finally {
      setBusy(null);
    }
  }, [productionId, refresh]);

  usePolling(refresh, POLL_MS, active);

  return {
    detail,
    progress,
    artifacts,
    status,
    error,
    loading,
    retrying: busy === "retry",
    cancelling: busy === "cancel",
    retry,
    cancel,
    refresh,
  };
}
