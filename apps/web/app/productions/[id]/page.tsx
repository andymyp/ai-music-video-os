"use client";

/**
 * Production detail page (TDD-001 §73; MASTER §32-33).
 *
 * Route: /productions/:id — renders the live progress view plus the result
 * panels (Master/Short previews, Metadata, QC) once artifacts exist.
 */
import { use } from "react";

import { ProductionDetail } from "@/components/ProductionDetail";

export default function ProductionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <ProductionDetail productionId={id} />
      </div>
    </main>
  );
}
