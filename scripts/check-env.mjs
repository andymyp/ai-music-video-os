#!/usr/bin/env node
// Cross-platform Phase 00 toolchain check (replaces scripts/check-env.sh).
// Works on Windows, macOS and Linux. Exits 1 when a required tool is missing.
import { execSync, spawnSync } from "node:child_process";

const REQUIRED = ["python", "uv", "node", "pnpm", "ffmpeg", "ffprobe", "git"];
const OPTIONAL = ["temporal"]; // needed only for 'pnpm dev:temporal'

const isWin = process.platform === "win32";
const whereCmd = isWin ? "where" : "which";

/** Resolve a command to its absolute path, or null if not on PATH. */
function resolve(cmd) {
  try {
    const out = execSync(`${whereCmd} ${cmd}`, { stdio: ["ignore", "pipe", "ignore"] })
      .toString()
      .trim();
    return out.split(/\r?\n/)[0] || null;
  } catch {
    return null;
  }
}

/** Run `<resolved> <args>` and return the first non-empty output line, or null. */
function versionLine(path, args) {
  const res = spawnSync(path, args, { encoding: "utf8", timeout: 15_000 });
  if (res.error || res.status !== 0) return null;
  return (res.stdout + "\n" + res.stderr)
    .split(/\r?\n/)
    .map((l) => l.trim())
    .find((l) => l.length > 0) || null;
}

let failed = false;

console.log("== Tooling ==");
for (const tool of REQUIRED) {
  const path = resolve(tool);
  if (!path) {
    console.log(`  [MISSING] ${tool}`);
    failed = true;
    continue;
  }
  const args = tool === "ffmpeg" || tool === "ffprobe" ? ["-version"] : ["--version"];
  const line = versionLine(path, args);
  console.log(`  [ok] ${tool} -> ${line ?? path}`);
}

console.log("== Temporal CLI ==");
const temporal = resolve("temporal");
if (temporal) {
  console.log(`  [ok] temporal -> ${versionLine(temporal, ["--version"]) ?? temporal}`);
} else {
  console.log("  [MISSING] temporal (needed for 'pnpm dev:temporal')");
  console.log(isWin ? "            install: winget install --id Temporal.TemporalCLI"
                    : "            install: brew install temporal (macOS) / see https://temporal.io/cli");
}

if (failed) {
  console.error("\nMissing required tool(s). Install them and re-run 'pnpm check'.");
  process.exit(1);
}
console.log("\nAll required tools present.");
