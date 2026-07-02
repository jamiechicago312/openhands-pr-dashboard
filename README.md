# OpenHands PR Review Dashboard — Static Snapshot

A Next.js dashboard for monitoring community PRs and review accountability in the
OpenHands project, frozen at a single point in time.

> **This deployment is a sample.** It is backed by a static JSON snapshot of the
> live dashboard rather than live GitHub API calls. The ticker banner at the top
> of the page shows the snapshot timestamp.

## What's included

- `snapshot/dashboard.json` — KPIs, all open PRs, and reviewer statistics
  captured at `2026-07-02T02:58:14Z` (2026-07-01 21:58 UTC-5).
- `snapshot/repositories.json` — the 38 active public repositories in the
  OpenHands organisation at the time of the snapshot.
- `scripts/snapshot.py` — Python script that re-creates the snapshot using the
  same GraphQL queries the live dashboard uses. Requires a `GITHUB_TOKEN` env
  var with `read:org` and `public_repo` scopes.
- `app/api/dashboard/route.ts` — read-only API route that loads the snapshot
  and applies the same client-side filters (age, status, labels, etc.).
- `app/api/repositories/route.ts` — read-only API route that returns the
  repository list from the snapshot.
- `components/TickerBanner.tsx` — the marquee banner at the top of the page
  that reminds visitors this is a static sample.

## Quick Start (snapshot mode)

```bash
npm install
npm run dev
# open http://localhost:3000
```

No environment variables are required at runtime — the data is hard-coded into
`snapshot/dashboard.json`.

## Regenerating the snapshot

If you want to capture a new point-in-time snapshot of the live dashboard:

```bash
export GITHUB_TOKEN=ghp_...
npm run snapshot
```

This will rewrite `snapshot/dashboard.json` and `snapshot/repositories.json`.
The `SNAPSHOT_TIMESTAMP` constant in `scripts/snapshot.py` controls the
frozen time used for SLA/age calculations.

## Filters

The dashboard still supports the same filters as the live version: repository,
status, author type, draft status, age range, date range, labels, and
reviewer. Filter values are applied server-side in
`app/api/dashboard/route.ts` against the in-memory snapshot.

## Deploying to Vercel

1. Push this repository to GitHub.
2. Import the project in Vercel — no environment variables are required.
3. Vercel will run `next build` and serve the snapshot from the static API
   routes.

The total payload is roughly 750 KB of JSON plus the static Next.js assets, so
deployment and cold starts are fast.

## Tech stack

- Next.js 16 (App Router)
- TypeScript 5
- Tailwind CSS 3
- Python 3 (only needed for the snapshot script)

## License

MIT — see `LICENSE`.
