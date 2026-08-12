"use client";

/**
 * Pipeline phase stepper (modern UI pass).
 *
 * Condenses the backend's 16-status `_PRODUCTION_FLOW` into 7 readable phases
 * (verified against apps/api/src/api/domain/production.py) so the user can see
 * where a production is at a glance rather than a flat percent. State is driven
 * by the authoritative status: `position` is the effective in-flow status and
 * `outcome` adds the terminal color so a failure/cancellation shows where it
 * stopped.
 */
import { Fragment } from "react";

import { CheckIcon } from "@/components/icons";
import type { ProductionStatus } from "@/types";

const PHASES: readonly {
  label: string;
  statuses: readonly ProductionStatus[];
}[] = [
  { label: "Plan", statuses: ["created", "planning", "concept_ready"] },
  { label: "Music", statuses: ["generating_music", "music_ready"] },
  { label: "Visual", statuses: ["generating_visual", "visual_ready"] },
  { label: "Audio", statuses: ["analyzing_audio"] },
  { label: "Master", statuses: ["rendering_master", "master_ready"] },
  {
    label: "Short",
    statuses: ["selecting_short", "rendering_short", "short_ready"],
  },
  { label: "Publish", statuses: ["generating_metadata", "quality_check"] },
];

type Outcome = "running" | "completed" | "failed" | "cancelled";

function phaseIndexFor(status: ProductionStatus): number {
  const index = PHASES.findIndex((phase) => phase.statuses.includes(status));
  return index === -1 ? 0 : index;
}

export function StageStepper({
  position,
  outcome,
}: {
  position: ProductionStatus;
  outcome: Outcome;
}) {
  const currentIndex =
    outcome === "completed" ? PHASES.length : phaseIndexFor(position);

  return (
    <div aria-label="Pipeline progress">
      <div className="flex items-center">
        {PHASES.map((phase, index) => {
          const done = index < currentIndex || outcome === "completed";
          const current = !done && index === currentIndex;
          return (
            <Fragment key={phase.label}>
              {index > 0 && (
                <div
                  aria-hidden="true"
                  className={`mx-1 h-0.5 flex-1 rounded-full transition-colors ${
                    index <= currentIndex ? "bg-indigo-500/60" : "bg-zinc-800"
                  }`}
                />
              )}
              <div
                title={phase.label}
                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full transition-all ${
                  done
                    ? "bg-indigo-500 text-white"
                    : current
                      ? outcome === "failed"
                        ? "bg-red-500 ring-4 ring-red-500/25 animate-pulse"
                        : outcome === "cancelled"
                          ? "bg-zinc-500 ring-4 ring-zinc-500/25"
                          : "bg-indigo-500 ring-4 ring-indigo-500/25 animate-pulse"
                      : "bg-zinc-800 ring-1 ring-white/10"
                }`}
              >
                {done && <CheckIcon className="h-3 w-3" />}
              </div>
            </Fragment>
          );
        })}
      </div>
      <div className="mt-2 flex">
        {PHASES.map((phase, index) => (
          <span
            key={phase.label}
            className={`flex-1 text-center text-[10px] font-medium ${
              index <= currentIndex ? "text-zinc-300" : "text-zinc-600"
            }`}
          >
            {phase.label}
          </span>
        ))}
      </div>
    </div>
  );
}
