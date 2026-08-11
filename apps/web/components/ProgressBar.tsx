"use client";

/**
 * Linear progress bar (TDD-001 §75 — Progress component; MAD-001 §46).
 * `progress` is 0.0..1.0 as reported by GET /progress — the backend owns the
 * number, this component only renders it. Failed/cancelled render as 0.
 */
export function ProgressBar({
  progress,
  stage,
}: {
  progress: number;
  stage: string;
}) {
  const percent = Math.round(Math.min(1, Math.max(0, progress)) * 100);
  return (
    <div className="w-full">
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="font-medium text-zinc-200">{stage}</span>
        <span className="tabular-nums text-zinc-400">{percent}%</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-zinc-800"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full bg-indigo-500 transition-all duration-500 ease-out"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
