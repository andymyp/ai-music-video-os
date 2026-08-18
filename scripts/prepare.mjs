#!/usr/bin/env node
// Cross-platform bootstrap for `pnpm prepare` (runs automatically after
// `pnpm install`, and on demand via `pnpm prepare`).
//
//  1. Copies `.env.example` -> `.env` when `.env` does not exist (never
//     overwrites an existing configuration).
//  2. Installs the Python backend dependencies with `uv sync`.
//
// Node dependencies are installed by `pnpm install` itself, which is what
// triggers this script; the script only warns if `node_modules` is missing
// (e.g. when `prepare` was invoked without a prior install).
import { copyFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";

const ROOT = process.cwd(); // pnpm runs scripts with cwd = package root
const ENV_EXAMPLE = ROOT + "/.env.example";
const ENV = ROOT + "/.env";

const say = (msg) => console.log(`  ${msg}`);

console.log("prepare: bootstrapping the development environment");

// 1. Local configuration -----------------------------------------------------
if (existsSync(ENV)) {
  say(".env already exists — keeping your configuration");
} else if (existsSync(ENV_EXAMPLE)) {
  copyFileSync(ENV_EXAMPLE, ENV);
  say("copied .env.example -> .env (edit it to adjust settings)");
} else {
  say("no .env.example found — skipping local configuration");
}

// 2. Python dependencies ------------------------------------------------------
// `uv` ships a native binary on every platform, so no shell shim is needed.
console.log("prepare: installing Python dependencies (uv sync)");
const uv = spawnSync("uv", ["sync"], { cwd: ROOT, stdio: "inherit" });
if (uv.error) {
  console.error("prepare: could not run `uv`. Install it from https://docs.astral.sh/uv/");
  console.error(`prepare: ${uv.error.message}`);
  process.exit(1);
}
if (uv.status !== 0) {
  console.error(`prepare: \`uv sync\` failed (exit ${uv.status})`);
  process.exit(uv.status ?? 1);
}
say("Python dependencies ready (.venv)");

// 3. Node dependencies -------------------------------------------------------
if (!existsSync(ROOT + "/node_modules")) {
  console.warn("prepare: node_modules not found — run `pnpm install` to install the workspace apps.");
} else {
  say("Node dependencies ready (pnpm install)");
}

console.log("prepare: done.");
