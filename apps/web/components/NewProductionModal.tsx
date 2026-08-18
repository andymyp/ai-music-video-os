"use client";

/**
 * New Production Modal (TDD-001 §74; MASTER §31).
 *
 * Composed of the four required pieces:
 *   - ModeSelector   — Genre | Trending
 *   - GenreSelector  — genre text input, disabled/hidden when Trending
 *   - BrandingInput  — optional branding text (≤80 chars)
 *   - GenerateButton — submits to POST /api/productions
 *
 * On success it navigates to the new production's detail page, where live
 * progress takes over.
 *
 * Polish pass: dialog semantics + ESC to close + focus trap/restore + body
 * scroll lock, a submit spinner, one-tap genre suggestions, a color-shifting
 * branding counter, and a clearer Trending description.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Spinner, XIcon } from "@/components/icons";
import { primaryButton } from "@/lib/ui";
import { ApiError, api } from "@/services/api";
import type { ProductionMode } from "@/types";

const GENRE_SUGGESTIONS = ["lofi", "ambient", "synthwave", "chillhop", "downtempo"];

/** Trap Tab/Shift+Tab inside `container` so focus can't escape the dialog. */
function trapTab(container: HTMLElement | null, event: KeyboardEvent): void {
  if (!container) return;
  const focusables = Array.from(
    container.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
    ),
  );
  if (focusables.length === 0) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const active = document.activeElement;
  if (event.shiftKey && (active === first || active === container)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

interface NewProductionModalProps {
  open: boolean;
  onClose: () => void;
}

export function NewProductionModal({ open, onClose }: NewProductionModalProps) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<ProductionMode>("genre");
  const [genre, setGenre] = useState("");
  const [branding, setBranding] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const close = useCallback(() => {
    if (!submitting) onClose();
  }, [submitting, onClose]);

  // Lock body scroll and manage focus while the dialog is open.
  useEffect(() => {
    if (!open) return;
    const previouslyFocused =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusTarget =
      dialogRef.current?.querySelector<HTMLElement>('input[type="text"]') ??
      dialogRef.current?.querySelector<HTMLElement>("button");
    focusTarget?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [open]);

  // ESC closes; Tab stays inside the dialog.
  useEffect(() => {
    if (!open || submitting) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      } else if (event.key === "Tab") {
        trapTab(dialogRef.current, event);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, submitting, onClose]);

  const genreValid = mode === "trending" || genre.trim().length > 0;
  const canSubmit = genreValid && !submitting;

  const submit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      if (!canSubmit) return;
      setSubmitting(true);
      setError(null);
      try {
        const created = await api.createProduction({
          mode,
          genre: mode === "genre" ? genre.trim() : null,
          branding_text: branding.trim() || null,
        });
        onClose();
        router.push(`/productions/${created.id}`);
      } catch (caught) {
        if (caught instanceof ApiError) {
          setError(caught.message);
        } else {
          setError(
            caught instanceof Error ? caught.message : "Failed to start production",
          );
        }
        setSubmitting(false);
      }
    },
    [canSubmit, mode, genre, branding, onClose, router],
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 animate-fade-in"
      onClick={close}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-production-title"
        className="w-full max-w-md rounded-2xl border border-white/[0.08] bg-zinc-900/90 p-6 shadow-2xl backdrop-blur-md"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-5 flex items-start justify-between">
          <div>
            <h2
              id="new-production-title"
              className="text-lg font-semibold text-zinc-100"
            >
              New Production
            </h2>
            <p className="text-sm text-zinc-400">
              Pick a direction and generate the full content package.
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            disabled={submitting}
            aria-label="Close"
            className="rounded-md p-1 text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-5">
          <ModeSelector value={mode} onChange={setMode} />
          <GenreSelector mode={mode} value={genre} onChange={setGenre} />
          <BrandingInput value={branding} onChange={setBranding} />

          {error !== null && (
            <p className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-300">
              {error}
            </p>
          )}

          <GenerateButton disabled={!canSubmit} submitting={submitting} />
        </form>
      </div>
    </div>
  );
}

// --- sub-components ----------------------------------------------------------

export function ModeSelector({
  value,
  onChange,
}: {
  value: ProductionMode;
  onChange: (mode: ProductionMode) => void;
}) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium text-zinc-300">Mode</legend>
      <div className="grid grid-cols-2 gap-2">
        <ModeOption
          active={value === "genre"}
          onClick={() => onChange("genre")}
          title="Genre"
          description="You pick the genre & vibe"
        />
        <ModeOption
          active={value === "trending"}
          onClick={() => onChange("trending")}
          title="Trending"
          description="Researches what's hot, then generates"
        />
      </div>
    </fieldset>
  );
}

function ModeOption({
  active,
  onClick,
  title,
  description,
}: {
  active: boolean;
  onClick: () => void;
  title: string;
  description: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border p-3 text-left transition-all ${
        active
          ? "border-indigo-500/60 bg-gradient-to-b from-indigo-500/15 to-violet-500/5 shadow-lg shadow-indigo-500/10"
          : "border-white/[0.08] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]"
      }`}
      aria-pressed={active}
    >
      <span className="block text-sm font-medium text-zinc-100">{title}</span>
      <span className="mt-0.5 block text-xs text-zinc-400">{description}</span>
    </button>
  );
}

export function GenreSelector({
  mode,
  value,
  onChange,
}: {
  mode: ProductionMode;
  value: string;
  onChange: (value: string) => void;
}) {
  const disabled = mode === "trending";
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-zinc-300">
        Genre
        {disabled && (
          <span className="ml-1 text-zinc-500">
            (auto-selected in Trending mode)
          </span>
        )}
      </span>
      <input
        type="text"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        placeholder={disabled ? "— system chooses —" : "e.g. lo-fi, synthwave, chillhop"}
        className={`w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-colors focus:border-indigo-500 ${
          disabled ? "cursor-not-allowed opacity-50" : ""
        }`}
      />
      {!disabled && (
        <span className="mt-2 flex flex-wrap gap-1.5">
          {GENRE_SUGGESTIONS.map((suggestion) => {
            const active = value.trim().toLowerCase() === suggestion;
            return (
              <button
                key={suggestion}
                type="button"
                onClick={() => onChange(active ? "" : suggestion)}
                aria-pressed={active}
                className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                  active
                    ? "border-indigo-500 bg-indigo-500/15 text-indigo-200"
                    : "border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200"
                }`}
              >
                {suggestion}
              </button>
            );
          })}
        </span>
      )}
    </label>
  );
}

export function BrandingInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const remaining = 80 - value.length;
  const counterClass =
    remaining <= 0
      ? "text-red-400"
      : remaining < 10
        ? "text-amber-400"
        : "text-zinc-500";
  return (
    <label className="block">
      <span className="mb-2 flex items-baseline justify-between text-sm font-medium text-zinc-300">
        <span>Branding text (optional)</span>
        <span className={`text-xs tabular-nums ${counterClass}`}>
          {remaining}
        </span>
      </span>
      <input
        type="text"
        value={value}
        maxLength={80}
        onChange={(event) => onChange(event.target.value)}
        placeholder="e.g. MY CHANNEL"
        className="w-full rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-colors focus:border-indigo-500"
      />
    </label>
  );
}

export function GenerateButton({
  disabled,
  submitting,
}: {
  disabled: boolean;
  submitting: boolean;
}) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className={`${primaryButton} w-full px-4 py-2.5 text-sm`}
    >
      {submitting ? (
        <>
          <Spinner className="h-4 w-4" />
          Starting…
        </>
      ) : (
        "Generate"
      )}
    </button>
  );
}
