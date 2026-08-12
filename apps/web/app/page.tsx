"use client";

/**
 * Dashboard (TDD-001 §73; PRD-001 §49; MASTER §30 — "New" → Modal → Progress).
 *
 * Lists recent productions with their status/completion state and a "New"
 * button that opens the New Production Modal. The list refreshes when a new
 * production is created so the dashboard always reflects backend state.
 *
 * Polish pass: skeleton loading rows, an error banner with retry, live
 * auto-refresh while any production is in flight (polled, not computed), a
 * manual refresh button + "last updated" indicator, and a create CTA in the
 * empty state.
 *
 * Modern pass: a sticky glass header with the gradient primary action, a soft
 * indigo top glow behind it, and a live count badge on the list heading.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { PlusIcon, RefreshIcon } from "@/components/icons";
import { NewProductionModal } from "@/components/NewProductionModal";
import {
  ProductionList,
  ProductionListSkeleton,
} from "@/components/ProductionList";
import { RelativeTime } from "@/components/RelativeTime";
import { usePolling } from "@/hooks/usePolling";
import { ghostButton, primaryButton } from "@/lib/ui";
import { ApiError, api } from "@/services/api";
import { isActive, type ProductionSummary } from "@/types";

const POLL_MS = 5000;

export default function Dashboard() {
  const [productions, setProductions] = useState<ProductionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const anyActive = useMemo(
    () => productions.some((production) => isActive(production.status)),
    [productions],
  );

  const refresh = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) setRefreshing(true);
    try {
      const list = await api.listProductions();
      setProductions(list);
      setError(null);
      setUpdatedAt(new Date());
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Failed to load productions",
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Initial load, then keep the list current while a production is in flight.
  useEffect(() => {
    void refresh();
  }, [refresh]);

  const silentRefresh = useCallback(() => refresh({ silent: true }), [refresh]);
  usePolling(silentRefresh, POLL_MS, anyActive);

  return (
    <main className="relative min-h-screen text-zinc-100">
      {/* Soft brand glow behind the header */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-indigo-500/[0.08] via-violet-500/[0.03] to-transparent"
      />

      {/* Glass header */}
      <header className="sticky top-0 z-20 border-b border-white/5 bg-zinc-950/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">
              AI Music Video OS
            </h1>
            <p className="text-xs text-zinc-400">
              Local-first instrumental music video production.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setModalOpen(true)}
              className={`${primaryButton} px-4 py-2 text-sm`}
            >
              <PlusIcon className="h-4 w-4" />
              New Production
            </button>
            <button
              onClick={() => void refresh()}
              disabled={refreshing}
              aria-label="Refresh productions"
              title="Refresh productions"
              className={`${ghostButton} px-3 py-2 text-sm`}
            >
              <RefreshIcon
                className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
              />
            </button>
          </div>
        </div>
      </header>

      <div className="relative mx-auto max-w-5xl px-6 py-8">
        {error !== null && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
            <span>{error}</span>
            <button
              onClick={() => void refresh()}
              className="rounded-md border border-amber-500/40 px-2 py-1 text-xs font-medium text-amber-200 hover:bg-amber-500/10"
            >
              Retry
            </button>
          </div>
        )}

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Recent Productions
              <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs tabular-nums text-zinc-300">
                {productions.length}
              </span>
            </h2>
            <span className="text-xs text-zinc-500">
              {refreshing ? (
                "Refreshing…"
              ) : updatedAt !== null ? (
                <>
                  Updated <RelativeTime iso={updatedAt.toISOString()} />
                </>
              ) : null}
            </span>
          </div>
          {loading ? (
            <ProductionListSkeleton rows={4} />
          ) : (
            <ProductionList
              productions={productions}
              onCreate={() => setModalOpen(true)}
            />
          )}
        </section>
      </div>

      <NewProductionModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </main>
  );
}
