"use client";

/**
 * Dashboard (TDD-001 §73; PRD-001 §49; MASTER §30 — "New" → Modal → Progress).
 *
 * Lists recent productions with their status/completion state and a "New"
 * button that opens the New Production Modal. The list refreshes when a new
 * production is created so the dashboard always reflects backend state.
 */
import { useCallback, useEffect, useState } from "react";

import { NewProductionModal } from "@/components/NewProductionModal";
import { ProductionList } from "@/components/ProductionList";
import { ApiError, api } from "@/services/api";
import type { ProductionSummary } from "@/types";

export default function Dashboard() {
  const [productions, setProductions] = useState<ProductionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listProductions();
      setProductions(list);
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Failed to load productions",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              AI Music Video OS
            </h1>
            <p className="mt-1 text-sm text-zinc-400">
              Local-first instrumental music video production.
            </p>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500"
          >
            New Production
          </button>
        </header>

        {error !== null && (
          <p className="mb-4 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-300">
            {error}
          </p>
        )}

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Recent Productions
          </h2>
          {loading ? (
            <div className="rounded-xl border border-zinc-800 p-8 text-center text-sm text-zinc-500">
              Loading productions…
            </div>
          ) : (
            <ProductionList productions={productions} />
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
