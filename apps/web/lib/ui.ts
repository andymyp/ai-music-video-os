/**
 * Shared design tokens (modern UI pass).
 *
 * One source of truth for the surfaces, buttons and accent treatment so every
 * screen composes the same classes instead of hand-rolling them. Sized
 * utilities (padding, text size) stay inline where a token is reused at
 * different scales.
 */

/** Soft dark card with a hairline ring and a faint drop shadow. */
export const surface =
  "rounded-xl bg-zinc-900/50 ring-1 ring-white/[0.06] shadow-lg shadow-black/10";

/** Secondary inset surface (video frames, list rows). */
export const surfaceInset =
  "rounded-lg bg-zinc-950/40 ring-1 ring-white/[0.04]";

/** Primary action — indigo→violet gradient with a soft glow. */
export const primaryButton =
  "inline-flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:brightness-110 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40";

/** Secondary action — quiet outline. */
export const ghostButton =
  "inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-700/80 font-medium text-zinc-300 transition-colors hover:border-zinc-500 hover:text-zinc-100 disabled:cursor-not-allowed disabled:opacity-40";

/** Gradient text accent for headings. */
export const textAccent =
  "bg-gradient-to-r from-indigo-300 via-violet-300 to-indigo-300 bg-clip-text text-transparent";
