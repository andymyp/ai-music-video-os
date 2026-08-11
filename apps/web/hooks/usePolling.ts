"use client";

/**
 * Poll a callback on an interval while `active` is true (MAD-001 §46).
 *
 * The backend is authoritative for production state, so the UI polls rather
 * than computing progress locally. An immediate call fires on activation and
 * the interval stops as soon as `active` flips false (e.g. terminal status).
 */
import { useEffect, useRef } from "react";

export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  active: boolean,
): void {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!active) return;
    let stopped = false;
    let timer: ReturnType<typeof setInterval> | undefined;

    const tick = async () => {
      if (stopped) return;
      await callbackRef.current();
    };

    void tick();
    timer = setInterval(() => void tick(), intervalMs);
    return () => {
      stopped = true;
      if (timer !== undefined) clearInterval(timer);
    };
  }, [intervalMs, active]);
}
