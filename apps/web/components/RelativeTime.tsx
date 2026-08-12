"use client";

/**
 * Relative timestamp that only resolves after mount (UI polish pass).
 *
 * `relativeTime()` depends on `Date.now()`, so rendering it during SSR and
 * again at hydration can produce different text (a hydration mismatch). This
 * component defers the value to a post-mount effect and keeps ticking once a
 * minute so "2m ago" stays current while the page is open. The full absolute
 * date is always available as the native tooltip.
 */
import { useEffect, useState } from "react";

import { formatDate, relativeTime } from "@/types";

export function RelativeTime({
  iso,
  className,
}: {
  iso: string;
  className?: string;
}) {
  const [label, setLabel] = useState<string | null>(null);

  useEffect(() => {
    const update = () => setLabel(relativeTime(iso));
    update();
    const timer = window.setInterval(update, 60_000);
    return () => window.clearInterval(timer);
  }, [iso]);

  return (
    <time dateTime={iso} title={formatDate(iso)} className={className}>
      {label ?? "…"}
    </time>
  );
}
