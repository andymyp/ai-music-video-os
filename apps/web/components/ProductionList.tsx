"use client";

/**
 * Recent productions table for the dashboard (TDD-001 §73, PRD-001 §49-50).
 * Each row links to the production detail page; status and completion state are
 * read straight from the backend summary (authoritative per MAD-001 §46).
 */
import Link from "next/link";

import { StatusBadge } from "@/components/StatusBadge";
import { formatDate, type ProductionSummary } from "@/types";

export function ProductionList({
  productions,
}: {
  productions: ProductionSummary[];
}) {
  if (productions.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-sm text-zinc-500">
        No productions yet. Create your first one with the “New” button.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-zinc-800 bg-zinc-900/60 text-xs uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="px-4 py-3 font-medium">Production</th>
            <th className="px-4 py-3 font-medium">Mode</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="hidden px-4 py-3 font-medium md:table-cell">Created</th>
            <th className="hidden px-4 py-3 font-medium md:table-cell">Completed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/70">
          {productions.map((production) => (
            <tr key={production.id} className="hover:bg-zinc-900/40">
              <td className="px-4 py-3">
                <Link
                  href={`/productions/${production.id}`}
                  className="font-mono text-xs text-indigo-300 hover:text-indigo-200"
                >
                  {production.id}
                </Link>
                <div className="mt-0.5 text-xs text-zinc-500">
                  {production.genre ?? "—"}
                  {production.branding_text
                    ? ` · ${production.branding_text}`
                    : ""}
                </div>
              </td>
              <td className="px-4 py-3 capitalize text-zinc-300">
                {production.mode}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={production.status} />
              </td>
              <td className="hidden px-4 py-3 text-zinc-400 md:table-cell">
                {formatDate(production.created_at)}
              </td>
              <td className="hidden px-4 py-3 text-zinc-400 md:table-cell">
                {production.completed_at ? formatDate(production.completed_at) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
