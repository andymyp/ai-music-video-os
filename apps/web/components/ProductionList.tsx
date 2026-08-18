"use client";

/**
 * Recent productions table for the dashboard (TDD-001 §73, PRD-001 §49-50).
 * Each row links to the production detail page; status and completion state are
 * read straight from the backend summary (authoritative per MAD-001 §46).
 *
 * Polish pass: friendly names + relative timestamps, a mode/duration meta line,
 * whole-row navigation, and a skeleton/empty state with a create CTA.
 */
import Link from "next/link";
import { useRouter } from "next/navigation";

import { InboxIcon, PlusIcon } from "@/components/icons";
import { RelativeTime } from "@/components/RelativeTime";
import { StatusBadge } from "@/components/StatusBadge";
import { primaryButton, surface, surfaceInset } from "@/lib/ui";
import type { ProductionMode, ProductionSummary } from "@/types";

const MODE_BADGE: Record<ProductionMode, string> = {
  genre: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300",
  trending: "border-violet-500/30 bg-violet-500/10 text-violet-300",
};

function displayName(production: ProductionSummary): string {
  if (production.mode === "genre" && production.genre?.trim()) {
    return production.genre;
  }
  return "Trending";
}

function shortId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

export function ProductionList({
  productions,
  onCreate,
}: {
  productions: ProductionSummary[];
  onCreate?: () => void;
}) {
  const router = useRouter();

  if (productions.length === 0) {
    return (
      <div className={`${surface} flex flex-col items-center justify-center gap-3 border border-dashed border-zinc-800 px-8 py-14 text-center animate-fade-in`}>
        <InboxIcon className="h-8 w-8 text-zinc-700" />
        <div>
          <p className="text-sm font-medium text-zinc-300">No productions yet</p>
          <p className="mt-1 text-sm text-zinc-500">
            Generate your first long-form + short-form music video in a couple
            of clicks.
          </p>
        </div>
        {onCreate && (
          <button
            onClick={onCreate}
            className={`${primaryButton} mt-1 px-4 py-2 text-sm`}
          >
            <PlusIcon className="h-4 w-4" />
            Create your first production
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={`${surfaceInset} overflow-hidden`}>
      <table className="w-full text-left text-sm">
        <thead className="border-b border-white/5 text-xs uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="px-4 py-3 font-medium">Production</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="hidden px-4 py-3 font-medium md:table-cell">
              Created
            </th>
            <th className="hidden px-4 py-3 font-medium md:table-cell">
              Completed
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {productions.map((production) => (
            <tr
              key={production.id}
              onClick={() =>
                router.push(`/productions/${production.id}`)
              }
              className="cursor-pointer transition-colors hover:bg-white/[0.03]"
            >
              <td className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    href={`/productions/${production.id}`}
                    onClick={(event) => event.stopPropagation()}
                    title={production.id}
                    className="text-sm font-medium capitalize text-zinc-100 hover:text-indigo-200"
                  >
                    {displayName(production)}
                  </Link>
                  <span
                    title={production.id}
                    className="rounded-md border border-zinc-800 bg-zinc-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-500"
                  >
                    {shortId(production.id)}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
                  <span
                    className={`rounded-full border px-1.5 py-0.5 capitalize ${MODE_BADGE[production.mode]}`}
                  >
                    {production.mode}
                  </span>
                  <span>~{production.target_duration_minutes}m</span>
                  {production.branding_text && (
                    <span
                      className="max-w-[12rem] truncate"
                      title={production.branding_text}
                    >
                      {production.branding_text}
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={production.status} />
              </td>
              <td className="hidden px-4 py-3 text-zinc-400 md:table-cell">
                <RelativeTime iso={production.created_at} />
              </td>
              <td className="hidden px-4 py-3 text-zinc-400 md:table-cell">
                {production.completed_at ? (
                  <RelativeTime iso={production.completed_at} />
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Shimmering placeholder rows shown while the dashboard first loads. */
export function ProductionListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className={`${surfaceInset} overflow-hidden`}>
      <div className="border-b border-white/5 px-4 py-3">
        <div className="skeleton h-3 w-28" />
      </div>
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="flex items-center gap-4 border-b border-white/[0.04] px-4 py-3 last:border-0"
        >
          <div className="flex-1 space-y-2">
            <div className="skeleton h-4 w-40" />
            <div className="skeleton h-3 w-28" />
          </div>
          <div className="skeleton hidden h-5 w-20 md:block" />
          <div className="skeleton h-5 w-24" />
        </div>
      ))}
    </div>
  );
}
