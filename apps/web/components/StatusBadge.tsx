"use client";

/**
 * Color-coded chip for a production status (TDD-001 §74 — Status component).
 * Styling is grouped by family so the palette reads at a glance: neutral for
 * created, amber for in-flight stages, green for completed, red for failed.
 */
import type { ProductionStatus } from "@/types";

const STYLES: Record<ProductionStatus, string> = {
  created: "bg-zinc-800 text-zinc-300 border-zinc-600",
  planning: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  concept_ready: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  generating_music: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  music_ready: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  generating_visual: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  visual_ready: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  analyzing_audio: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  rendering_master: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  master_ready: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  selecting_short: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  rendering_short: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  short_ready: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  generating_metadata: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  quality_check: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  completed: "bg-emerald-500/10 text-emerald-300 border-emerald-500/40",
  failed: "bg-red-500/10 text-red-300 border-red-500/40",
  cancelled: "bg-slate-500/10 text-slate-300 border-slate-500/40",
};

const LABELS: Record<ProductionStatus, string> = {
  created: "Created",
  planning: "Planning",
  concept_ready: "Concept Ready",
  generating_music: "Generating Music",
  music_ready: "Music Ready",
  generating_visual: "Generating Visual",
  visual_ready: "Visual Ready",
  analyzing_audio: "Analyzing Audio",
  rendering_master: "Rendering Master",
  master_ready: "Master Ready",
  selecting_short: "Selecting Short",
  rendering_short: "Rendering Short",
  short_ready: "Short Ready",
  generating_metadata: "Generating Metadata",
  quality_check: "Quality Check",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function StatusBadge({ status }: { status: ProductionStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}
      data-testid="status-badge"
    >
      {LABELS[status]}
    </span>
  );
}
