# Loot Table (scifi-loot-table)

At the end of a working session, update ## Status with what changed and what's next.

"Loot Table": rank the LitRPG / progression fantasy audiobook series you've heard into S-F tiers and get
recommendations built from 900+ Reddit tier lists matched to Audible UK. Runs fully client-side, as a
website (GitHub Pages) and as a Tauri desktop app. Open PR #1 retargets it to sci-fi Kindle books on
Amazon.com.au, which is what the repo name refers to.

## Stack

- React 18.3 + TypeScript 5.6 (strict, `noUnused*`), Vite 5.4, Vitest 2, @dnd-kit for drag and drop.
- Tauri 2 (`src-tauri/`, Rust edition 2024, rust-version 1.90) with plugins opener, dialog, fs.
- Node 22. Version is kept in three places: `package.json`, `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`.

## Commands

```sh
npm install
npm run dev        # website at http://localhost:5173 (strictPort; Tauri expects it)
npm test           # vitest: scoring, share links, popularity, transfer
npm run build      # tsc -b && vite build -> dist/
npx tauri dev      # desktop app
npx tauri build    # installers in src-tauri/target/release/bundle
```

## Layout

- `src/engine/` - `data.ts` (loads `public/data.json` and indexes it), `recommend.ts` (Bradley-Terry quality,
  taste neighbours, tag similarity, author/narrator, popularity), `text.ts`. `__fixtures__/python-recs.json`
  pins expected results from the original Python model.
- `src/api.ts` - what the pages call; tier list lives in localStorage. `share.ts` encodes a list into the
  URL (permanent `sid` per series, never reuse). `transfer.ts` import/export file. `analytics.ts` GoatCounter
  (website only; the desktop app counts nothing). `external.ts` opens links in the system browser in Tauri.
- `src/pages/` (ForYou, TierList, Community, Shared), `src/components/`.
- `public/data.json` (~4.7 MB dataset). `vite.config.ts` hashes it into `__DATA_VERSION__` for cache busting.
- `.github/workflows/pages.yml` - push to `main`: `npm ci`, `npm test`, build, deploy to Pages.
  `release.yml` - push a `v*` tag: builds Windows/macOS (arm64, x64)/Linux installers into a draft release.

## Conventions

- Build output uses relative paths (`base: "./"`) so one build serves Pages subpaths and Tauri.
- Tauri CSP only allows images from Amazon's image hosts; update it if covers move elsewhere.
- Installers are unsigned (macOS ad-hoc `signingIdentity: "-"`).
- Commits are short imperative sentences; releases are a "Version x.y.z" commit plus a tag (inferred from history).
- No user data leaves the device; keep it that way (no accounts, no server).

## Memory

Use the `memory` MCP server: recall project `scifi-loot-table` before working, and remember decisions,
gotchas and todos there. Never save secrets.

## Status

- Live: v0.1.7 (18 Oct 2026) of the LitRPG app; README points to a website copy at feanaroo.github.io.
  No Actions runs are recorded in this repo yet, so its own Pages site is not set up (inferred).
- In progress: PR #1 "Sci-fi Kindle books on Amazon.com.au" - new dataset from Open Library via
  `pipeline/build_data.py`, Amazon AU links, share/analytics host `meliastech.github.io/scifi-loot-table`.
  After merging, enable Settings > Pages > Source: GitHub Actions.
- Known problems: PR #1 commits `pipeline/__pycache__/*.pyc`; drop it and ignore `__pycache__/` before merging.
- Last updated: 12 Nov 2026
