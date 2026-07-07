# CLAUDE.md — Whitsundays Sailing Companion

Context for working on this repo with Claude Code. Read `DESIGN.md` for the *why*
behind the decisions below; this file is the *how* — the rules to not break.

## What this is

A single-file, offline-first web app that helps plan a Whitsundays bareboat charter:
live GPS position, approved overnight anchorages/moorings, distance + bearing + ETA to
each, wind-protection matching for a forecast, a simple voyage planner, and tides.
It runs on family phones/iPads with **no mobile signal** out among the islands.

## Hard constraints — do not violate

1. **Single file, zero runtime dependencies.** Everything (HTML, CSS, JS, data) lives in
   `index.html`. No CDN links, no `<script src>` to external hosts, no web fonts, no npm
   packages loaded at runtime, no build step. The app must load and run from a cold cache
   with the network completely off. If you're tempted to add a library, inline it or don't.
2. **Stay offline-capable.** The only network calls allowed are the optional WorldTides
   fetch (explicitly user-triggered), the optional chart-layer map tiles (OSM base +
   OpenSeaMap seamarks, cached-as-you-browse for offline use), the service worker's
   background cache refresh, and the same-origin `weather/mackay-coast.json` fetch (served
   from the SW precache; the browser never contacts BOM directly — CI does that).
   Every feature must work fully offline. If a feature needs data, it gets pre-fetched while
   online or entered manually.
3. **Never present coordinates as navigation-grade.** Spot positions are approximate. Keep
   the "not for navigation" framing anywhere positions/distances are shown.
4. **No frameworks.** Vanilla JS only, matching the existing style.

## Files

| File | Role |
|---|---|
| `index.html` | The entire app. Structure: `<head>` meta/PWA tags → `<style>` (CSS vars + components) → markup (top fix bar, 5 `.view` panels, bottom `.tab` bar, map sheet) → `<script>` (all logic). |
| `sw.js` | Service worker. Stale-while-revalidate over the app shell; ignores cross-origin (tide API). Bump `CACHE` to force-refresh devices. |
| `manifest.json` | PWA manifest, relative paths. |
| `icon-*.png` | Home-screen / manifest icons. Regenerate via `make_icon.py` if the brand changes. |
| `DESIGN.md` | Build decisions, data model, feature notes, future ideas. |
| `weather/mackay-coast.json` | Rolling BOM Mackay Coastal Waters forecast history (last 20 issues), fetched by CI. Same-origin, SW-cached, offline. |
| `scripts/fetch_weather.py` | CI-only: fetches/parses `IDQ11306.xml` and merges into the JSON above. Stdlib Python. Not loaded by the app. |
| `.github/workflows/weather.yml` | Scheduled (cron ~3×/day) BOM fetch → commit JSON → redeploy. |

## How to run / test

- **Run:** open `index.html` in a browser. For service-worker + GPS testing you need an
  HTTPS origin (GitHub Pages) or `localhost` — `python3 -m http.server` then visit
  `http://localhost:8000`.
- **Syntax check after edits** (the JS is embedded, so extract and check):
  ```bash
  sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin
  node --check sw.js
  ```
- There is no test suite. Verify changes by loading the app and exercising the affected tab.

## Code map (functions in index.html)

- **Storage:** `store.get/set` — localStorage wrapped in try/catch with in-memory fallback
  (so it survives sandboxed previews). All persisted state keys go through this.
- **State:** the `S` object holds everything mutable (position, view, boat config, forecast
  wind, filters, route, tides). Persisted fields are seeded from `store.get(...)`.
- **Geometry:** `haversine` (nm), `bearing` (great-circle initial), `compass(deg)`,
  `fmtLat/fmtLon` (deg-min). `R_NM = 3440.065`.
- **Wind:** `parseWind(raw)` turns the charter list's arc strings ("E to SW", "All Weather",
  "Light…", "SE up to 15k") into `{kind, a, b, max?}`; `inArc(dir,a,b)` tests a clockwise arc;
  `windVerdict(s)` → protected/exposed for the forecast; `roseSVG(s)` draws the compass rose.
- **Position:** `startGeo` (watchPosition), `simPos` (demo fix at Shute Harbour), `onPos`
  (re-render hook), `renderFix` (top bar).
- **Chart tab:** `project(lat,lon,vw,vh)`, `fitChart`, `drawChart` — schematic SVG, custom
  pan/zoom. No real coastlines by design.
- **Nearby tab:** `renderNear`, `rowHTML`, `spotFits` (boat-length/hull vs mooring class),
  filter chips drive `S.filt`.
- **Detail sheet:** `selectSpot`, `openSheet/closeSheet`, `renderSheet`.
- **Plan tab:** `toggleRoute`, `renderPlan`, `clearRoute` — ordered stops, leg dist/bearing,
  totals + ETA.
- **Tides tab:** `tideEvents`, `tideNow` (cosine interp between extremes), `renderTides`,
  `drawTideCurve`, `saveManual` (paste-table parser), `fetchTides(days)` (WorldTides).
- **Weather tab:** `parseBomWind(text)` → `{deg,deg8,knLow,knHigh}`; `fmtIssued`/`issueAgeHours`; `fetchWeather()` loads the same-origin JSON; `applyForecastWind(force)` sets `S.windDir/S.windKn` from tonight's forecast (auto unless manually overridden; force re-applies); `renderWeather`, `periodCard`, `windChange` (history change flags); Setup `windSourceNote`/`resetWind`.
- **Views:** `setView(v)` switches the 5 panels and calls the matching render fn.

## Data model

`SPOTS` is the source of truth — an array of objects:

```js
{ id:1, name:'Double Bay (Eastern)', ref:'N13',
  lat:-20.178, lon:148.628,
  type:'anchor',            // 'anchor' | 'mooring' | 'both' | 'marina'
  wind:'E to SW',           // clockwise protection arc, parseWind() format
  note:'…',                 // skipper note shown in the detail sheet
  day:true,                 // optional: day-use only (excluded from overnight)
  moor:{ T:2, B:3 } }       // optional: GBRMPA public mooring class counts at this spot
```

Mooring classes live in `CLASS` (max vessel length by hull + rated wind):
T/A/B/C/D. `spotFits(s)` compares `S.boatLen`/`S.boatHull` against `s.moor`.

### Adding a spot
Append to `SPOTS` with a unique `id` (overnight 1–99 range used so far, day-use public
moorings 101+). Provide `lat`/`lon` (approx is fine), `type`, and a `wind` arc string that
`parseWind` understands. Everything else is optional. No other wiring needed — the nearby
list, chart, filters and planner all read from `SPOTS` automatically.

## Conventions

- **Colours are CSS vars** in `:root`: `--cyan` (data), `--amber` (caution), `--green`
  (protected/fits), `--red` (exposed), on `--bg` night-navy. Don't hard-code hex; reuse vars.
- **All numeric readouts use `var(--mono)`** (bearings, distances, coords, heights).
- **Tide heights are chart datum (CD)** — i.e. added to charted depths. Keep that framing.
- After editing, run the syntax check above and bump `sw.js` `CACHE` if you changed cached
  assets and want devices to pick it up promptly.
