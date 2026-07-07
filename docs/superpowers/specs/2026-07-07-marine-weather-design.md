# Design — Automatic BOM Marine Weather for the Whitsundays

**Date:** 2026-07-07
**Status:** Approved (design); implementation plan to follow.

## Goal

Automatically download the daily BOM marine (coastal waters) forecast for the
Whitsundays area, cache it as a same-origin asset so it works fully offline, let the
user review the last few days and see what has changed between issues, and
auto-populate the app's "Tonight's forecast wind" (direction + strength) that drives the
Protected/Exposed anchorage verdict.

## Source data

- **Product:** `IDQ11306` — *"Mackay Coastal Waters Forecast: Bowen to St Lawrence"*.
  This coastal-waters zone (`QLD_MW008`) covers the entire Whitsundays and explicitly
  references Hamilton Island.
- **Machine-readable feed:** `https://www.bom.gov.au/fwo/IDQ11306.xml` (HTTP 200, ~6 KB,
  clean XML per the BOM `product.xsd` v1.7 schema). The `.txt` sibling 404s; XML is the
  target.
- **XML shape (relevant parts):**
  - `product/amoc/identifier` = `IDQ11306`
  - `product/amoc/issue-time-local` (tz EST), `issue-time-utc`, `expiry-time`
  - synoptic situation: `area[type=sub-region] / forecast-period / text[type=synoptic_situation]`
  - the forecast: `area[aac=QLD_MW008] / forecast-period[index=0..3]`, each with
    `text[type=forecast_winds]`, `text[type=forecast_seas]`, `text[type=forecast_swell1]`,
    `text[type=forecast_weather]`. `index=0` = today-until-midnight (i.e. "tonight" for an
    overnight-anchorage app); `index=1..3` = the following three days.
  - Example winds wording: `"Southeasterly 20 to 25 knots, reaching up to 30 knots
    offshore north of Hamilton Island during the afternoon and evening."`
- **Warnings:** a Strong Wind Warning line appears on the HTML page but is a separate BOM
  product; treat any warning text as best-effort (`null` when absent), never required.

### The CORS constraint (why this architecture)

BOM sends no CORS headers and blocks non-browser user-agents, so the app **cannot** fetch
`IDQ11306.xml` directly from the browser — a request from the GitHub Pages origin is
blocked. Data must be fetched server-side. The repo already deploys via GitHub Actions,
which is the natural place to do it. Confirmed: a server-side `curl` with a browser
User-Agent returns HTTP 200.

## Architecture & data flow

```
BOM IDQ11306.xml ──(GitHub Action, cron)──▶ parse ──▶ weather/mackay-coast.json ──commit──▶ repo (main)
                                                                                              │
                                                                 GitHub Pages deploy ◀────────┘
                                                                            │
   index.html ── fetch('weather/mackay-coast.json') ── same-origin, no CORS ◀┘
        ├── service worker caches it (stale-while-revalidate) → offline
        └── auto-applies tonight's wind → Protected/Exposed verdict
```

No browser→BOM call ever happens. The app only reads a same-origin JSON file that the
service worker caches like the rest of the app shell.

## Component 1 — Scheduled workflow (`.github/workflows/weather.yml`)

**Purpose:** fetch BOM, merge into a committed JSON history, redeploy the site.
**Interface:** produces/updates `weather/mackay-coast.json` at the repo root; redeploys Pages.
**Depends on:** BOM XML endpoint; repo write + Pages deploy permissions.

- **Triggers:** `schedule` cron ~3×/day, timed shortly after BOM's routine issues (BOM
  issues roughly 4×/day; e.g. run at ~20:15, 02:15, 08:15 UTC ≈ morning/afternoon/evening
  EST) + `workflow_dispatch` for manual runs.
- **Steps:**
  1. `actions/checkout@v5` (full history not needed; default is fine).
  2. Fetch `IDQ11306.xml` with a descriptive browser-like User-Agent (e.g.
     `Whitsundays-Companion/1.0 (+https://github.com/tenacioustechie/whitsundays-companion)`
     — if BOM rejects a custom UA, fall back to a standard browser UA string).
  3. Run a Python parser (`scripts/fetch_weather.py`, stdlib only —
     `urllib`/`xml.etree`/`json`) that extracts the fields below and merges into
     `weather/mackay-coast.json`.
  4. Commit the JSON back to `main` **only if it changed** (so history persists across
     runs and no empty commits pile up).
  5. **Only if the JSON changed** (gated on step 4): `actions/configure-pages@v5` →
     `actions/upload-pages-artifact@v3` (path `.`) → `actions/deploy-pages@v4`. This
     workflow deploys itself because a `GITHUB_TOKEN` commit does **not** re-trigger
     `deploy.yml`.
- **Permissions:** `contents: write`, `pages: write`, `id-token: write`.
- **Concurrency:** share the existing `group: pages` (as `deploy.yml`) to avoid clashing
  deploys.
- **Robustness / dedupe / cap:**
  - If the fetch is non-200 or the XML fails to parse, exit successfully **without
    touching** the JSON — existing history is never wiped. When the JSON is unchanged
    (failed fetch, or a duplicate issue) the workflow **skips both the commit and the
    deploy** (no-op run); it commits and deploys only when the file actually changed.
  - **Dedupe:** append a new history entry only when the parsed `issued` (BOM issue-time)
    differs from the newest stored entry — 3 cron runs against 1 BOM issue yield 1 entry.
  - **Cap:** keep the newest **20 distinct issues** (~5 days; file < ~25 KB).

Two workflows now call `deploy-pages` (`deploy.yml` on push, `weather.yml` on cron/commit);
the shared concurrency group serialises them.

## Component 2 — Data file (`weather/mackay-coast.json`)

**Purpose:** the offline-cached, same-origin forecast history the app reads.
**Interface:** stable JSON contract below; the app depends only on this shape, not on BOM XML.

```jsonc
{
  "product": "IDQ11306",
  "title": "Mackay Coastal Waters Forecast: Bowen to St Lawrence",
  "attribution": "© Commonwealth of Australia, Bureau of Meteorology",
  "history": [                       // newest first, max 20 entries
    {
      "issued": "2026-07-07T15:00:00+10:00",   // BOM issue-time-local (identity for dedupe)
      "fetched": "2026-07-07T05:30:00Z",       // when the workflow fetched it (UTC)
      "synopsis": "A ridge extends over the north Queensland waters…",
      "warning": "Strong Wind Warning for Mackay Coast",   // or null
      "periods": [
        { "label": "Tonight",   "winds": "Southeasterly 20 to 25 knots, reaching…",
          "seas": "1 to 1.5 metres…", "swell": "Easterly below 1 metre…",
          "weather": "Mostly clear. 60% chance of showers." },
        { "label": "Wed 8 Jul", "winds": "Southeasterly 20 to 25 knots.", "seas": "…",
          "swell": "…", "weather": "…" }
        // …index 0..3
      ]
    }
    // …up to 20 issues
  ]
}
```

- The workflow extracts **text + timestamps only** (a trivial, stable XML→JSON pass). It
  does **not** interpret wind direction/speed — that is done in the app so the logic lives
  in the single `index.html` and can be tweaked without re-running CI.
- `periods[i].label`: `index=0` → `"Tonight"`; `index≥1` → a short weekday+date derived
  from the period `start-time-local` (e.g. `"Wed 8 Jul"`).

## Component 3 — In-app Weather tab

**Purpose:** display the forecast + history; host the wind auto-populate.
**Interface:** a new `.view` panel + a 6th `.tab` button; a `renderWeather()` render fn wired
into `setView`; a `fetchWeather()` loader mirroring the `fetchTides` pattern (but
same-origin, no API key, and auto-invoked).
**Depends on:** `weather/mackay-coast.json`, `store`, `S`, `roseSVG`, `parseBomWind`,
`compass`, `DIRDEG`.

Layout (top → bottom):
- **Header:** `"Issued 3:00 pm Tue 7 Jul"`; amber staleness note when the latest issue is
  old (e.g. *"Forecast is 2 days old — may be out of date"*). Warning banner when
  `warning` present.
- **Synopsis** line.
- **Tonight card** (highlighted): reuse `roseSVG` for the parsed wind, plus winds / seas /
  swell / weather text (raw BOM wording, so the full range is visible).
- **Next 3 days:** compact cards (winds / seas / swell / weather each).
- **History:** dated list of the stored issues grouped by day, latest expanded; tapping an
  older entry expands it. When an issue's tonight headline wind differs from the
  chronologically previous issue, show a one-line flag: *"↑ was SE 15–20, now SE 20–25"*
  (↑/↓ by strength; plain marker for a direction change).
- **Footer:** BOM attribution + the app's standard "planning aid, not for navigation —
  verify before you commit" framing.

State additions on `S` (persisted via `store`):
- `S.weather` — the loaded JSON (cached copy for offline; seeded from `store.get`).
- `S.windFromForecast` — issue-time string the app last auto-applied (so it only
  re-applies on a *newer* issue).
- `S.windManualSince` — set when the user manually changes wind; see auto-populate rules.

## Component 4 — Wind auto-populate

**`parseBomWind(text)` → `{ deg, knLow, knHigh, dirWord }`** (in `index.html`):
- Direction words → degrees, 8- and 16-point: `Northerly`, `North to northeasterly`,
  `Northeasterly`, `East to northeasterly`, `Easterly`, `East to southeasterly`,
  `Southeasterly`, `South to southeasterly`, `Southerly`, … plus `Variable`
  (→ `deg = null`, treated as no protection preference). Map to nearest existing
  `DIRDEG` 8-point for chip highlighting; keep the finer degree for the rose/verdict.
- Speed: extract the **primary** `"X to Y knots"` range; ignore trailing clauses like
  `"reaching up to 30 knots offshore…"` (anchorages are inshore). Single value `"N knots"`
  → `knLow = knHigh = N`.
- The verdict uses `knHigh` (upper of range); the UI displays the raw range.
- Tolerant: unrecognised wording → `deg = null`, `kn = null`; caller skips auto-apply.

**Apply rules:**
- On load and whenever `fetchWeather()` refreshes data: if the latest issue's
  `issued` ≠ `S.windFromForecast` **and** parsing tonight succeeds, set
  `S.windDir`/`S.windKn` from tonight, set `S.windFromForecast = issued`, clear
  `S.windManualSince`. Setup shows *"from BOM forecast issued <time>"*.
- **Manual override wins:** a manual change in Setup sets `S.windManualSince` and persists;
  auto-apply is suppressed until a *newer* issue arrives (i.e. it only overrides a manual
  value when a genuinely new forecast is downloaded). Setup gains a small *"Reset to
  forecast"* affordance to re-apply the latest on demand.
- If no weather data is present, wind behaves exactly as today (manual only).

## Component 5 — Service worker

- Add `weather/mackay-coast.json` to the app-shell `ASSETS` array so it is precached and
  served **stale-while-revalidate** (instant offline; refreshes when online). Cross-origin
  handling is unchanged (BOM is never fetched by the browser, so nothing new there).
- Bump `CACHE` → `wts-v6`.

## Error handling / offline / staleness

- **No data yet / fetch fails offline:** Weather tab shows *"No forecast cached yet —
  connect while in range to download."* Wind auto-apply is skipped; manual entry still works.
- **Stale data:** clearly labelled with age; never presented silently as current.
- **Malformed/partial period:** missing field renders as `"—"`; the parse never throws.
- **Workflow failure:** never wipes existing history (see Component 1).

## Attribution & terms

BOM material is © Commonwealth of Australia (Bureau of Meteorology) and reusable with
attribution. Attribute BOM in the Weather tab footer, retain the app's "not for navigation"
framing, and have the workflow use a descriptive User-Agent at a modest cadence
(good-citizen scraping).

## Testing

- **Workflow parser:** run `scripts/fetch_weather.py` against a saved `IDQ11306.xml`
  fixture offline; assert JSON shape, dedupe (same issue-time twice → 1 entry), cap
  (21 issues → 20), and that a non-200/parse-failure leaves the JSON untouched.
- **JS:** `sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin`;
  `node --check sw.js`; lint the Python with `python3 -m py_compile`.
- **App (browser, fresh port; clear the app's own SW + caches first):** serve with a
  fixture JSON and verify — Weather tab renders (tonight card, 3 days, history);
  `parseBomWind` unit-checks for representative BOM strings; tonight's wind auto-applies;
  manual override sticks and "Reset to forecast" re-applies; staleness banner shows for an
  old fixture; empty/no-data state; and offline load from SW cache.

## Out of scope (YAGNI)

Multiple BOM regions, wind/wave graphs, push notifications, MetEye/gridded data,
tide↔weather integration. Just the Mackay Coast text forecast, its history, and the wind
auto-populate.

## Defaults chosen (not asked; easy to change)

- Cron cadence: ~3×/day.
- History depth: last 20 distinct issues (~5 days).
