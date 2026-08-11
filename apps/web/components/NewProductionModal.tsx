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
 */
import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, api } from "@/services/api";
import type { ProductionMode } from "@/types";

interface NewProductionModalProps {
  open: boolean;
  onClose: () => void;
}

export function NewProductionModal({ open, onClose }: NewProductionModalProps) {
  const router = useRouter();
  const [mode, setMode] = useState<ProductionMode>("genre");
  const [genre, setGenre] = useState("");
  const [branding, setBranding] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
          setError(caught instanceof Error ? caught.message : "Failed to start production");
        }
        setSubmitting(false);
      }
    },
    [canSubmit, mode, genre, branding, onClose, router],
  );

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-5 flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">New Production</h2>
            <p className="text-sm text-zinc-400">
              Pick a direction and generate the full content package.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            ✕
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
          description="You choose the genre"
        />
        <ModeOption
          active={value === "trending"}
          onClick={() => onChange("trending")}
          title="Trending"
          description="System picks what's hot"
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
      className={`rounded-xl border p-3 text-left transition-colors ${
        active
          ? "border-indigo-500 bg-indigo-500/10"
          : "border-zinc-700 bg-zinc-800/50 hover:border-zinc-500"
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
        Genre{disabled && <span className="ml-1 text-zinc-500">(auto-selected in Trending mode)</span>}
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
  return (
    <label className="block">
      <span className="mb-2 flex items-baseline justify-between text-sm font-medium text-zinc-300">
        <span>Branding text (optional)</span>
        <span className="text-xs tabular-nums text-zinc-500">{remaining}</span>
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
      className="w-full rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {submitting ? "Starting…" : "Generate"}
    </button>
  );
}
