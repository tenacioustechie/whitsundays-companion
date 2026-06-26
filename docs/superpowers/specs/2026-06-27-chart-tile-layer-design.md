# Chart Tile Layer (OpenSeaMap) — Design

**Date:** 2026-06-27
**Status:** Approved design, pre-implementation
**Topic:** Add a cached nautical-chart tile layer behind the schematic Chart tab.

---

## Problem / goal

The Chart tab is a deliberately bare schematic — spots, grid, island labels, no
coastlines (DESIGN.md decision #3) — so it never *looks* navigation-grade. The
user wants real map imagery behind it for orientation: an **OpenSeaMap nautical
layer** (seamarks, depth contours, beacons) over a base map, fetched and cached
while online so it still works offline among the islands.

This partially relaxes the "honest schematic" decision and the "no external
network at load" constraint. Both relaxations are **explicitly authorized** by
the user for this feature. We preserve the safety intent by keeping the imagery a
*context layer* and keeping the "approximate / not for navigation — use the
plotter" framing everywhere.

## Non-goals

- Not a navigation tool. The boat's chart plotter remains the source of truth.
- No bulk "download the whole region" button (violates OSM/OpenSeaMap tile usage
  policy and risks IP throttling). Coverage = wherever the user panned while online.
- No mapping library, no build step, no framework. Vanilla, single-file ethos intact.
- Not rewriting the chart to a full Web Mercator slippy map (approach B, rejected).

## Constraints honored

| Hard constraint (CLAUDE.md) | How this design honors it |
|---|---|
| #1 Single file, zero runtime deps | Tiles are runtime *data* fetches, not scripts/libs. No new files except doc updates. No npm/CDN/build. |
| #2 Stay offline-capable | App shell still cold-launches offline. Tile fetch is a new, explicitly-authorized network category; tiles are cache-first so offline shows cached tiles, uncached → schematic fallback. |
| #3 Never present coordinates as navigation-grade | Imagery is a dimmed *context* layer behind the schematic. "Not for navigation" caption + attribution stay visible; existing framing unchanged. |
| #4 No frameworks | Hand-rolled SVG `<image>` tiles in the existing render path. |

## Chosen approach (A): tiles inside the existing SVG, positioned by `project()`

Keep the current schematic and projection. In `drawChart()`, before drawing the
grid/islands/spots, draw a layer of `<image>` tiles **behind** them. Each tile is
pinned to its true geographic corners using the existing `project(lat,lon,vw,vh)`.

Why this is correct and minimal:
- `project()` is **separable and linear**: `x` depends only on `lon`, `y` only on
  `lat`. So a Web-Mercator tile positioned by its corner lat/lon becomes an
  axis-aligned screen rectangle, adjacent tiles seam perfectly (shared edge → same
  pixel), and every spot (already projected the same way) sits on the right reef.
- The only inaccuracy is a **sub-pixel warp within a single tile** (equirectangular
  vs Mercator across ~0.02° of latitude at ~20°S) — invisible.
- No change to `fitChart`, pan, zoom, pinch, or any schematic element. One render path.

Rejected: **B** full Web Mercator rewrite (large, risky, overkill for a tiny region);
**C** separate DOM tile div (two coordinate systems to keep in sync, no upside).

## Rendering detail

In `drawChart()`, when the layer is enabled, compute the visible geographic bounds
from current state (these already define the view):

```
lonSpan = BASE_SPAN / MAP.zoom
kx      = cos(MAP.cx · π/180)
latSpan = lonSpan · (vh/vw) / kx
west  = MAP.cy - lonSpan/2 ;  east  = MAP.cy + lonSpan/2
north = MAP.cx + latSpan/2 ;  south = MAP.cx - latSpan/2
```

Pick the tile zoom `z` so tiles render near 256 px:

```
z = round( log2( 360 · vw / (256 · lonSpan) ) )    // clamp to [9, 16]
```

Web Mercator tile <-> geo (standard XYZ):

```
n = 2^z
xtile(lon) = floor( (lon + 180) / 360 · n )
ytile(lat) = floor( (1 - asinh(tan(lat·π/180))/π) / 2 · n )
lon(x) = x / n · 360 - 180
lat(y) = atan( sinh( π · (1 - 2·y/n) ) ) · 180/π
```

Enumerate `x` in `[xtile(west), xtile(east)]`, `y` in `[ytile(north), ytile(south)]`.
For each `{z,x,y}` emit two stacked `<image>` elements (base, then seamark overlay),
positioned by:

```
[xL,yT] = project( lat(y),   lon(x),   vw, vh )    // NW corner
[xR,yB] = project( lat(y+1), lon(x+1), vw, vh )    // SE corner
width  = xR - xL ;  height = yB - yT
```

URLs:
- Base:    `https://tile.openstreetmap.org/{z}/{x}/{y}.png`
- Seamark: `https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png`

The base layer carries a CSS filter for night legibility (e.g.
`filter: brightness(.6) saturate(.6) contrast(.9)`) so the cyan/amber schematic
markers stay readable on top. Seamark overlay is drawn at full opacity.
`<image onerror>` removes a tile that fails (offline + uncached) so only the
schematic shows there. Tile count per frame is bounded (~`(vw/256+2)·(vh/256+2)`)
by construction.

## Offline caching (service worker)

`sw.js` currently ignores **all** cross-origin requests. Add a narrow change:

- Keep ignoring the WorldTides API (unchanged behavior).
- For the two tile hosts only, serve **cache-first with network fallback**, and on
  a successful network fetch, `put` the response into a dedicated `tiles` cache:
  - **Online:** cache miss → fetch → cache → return. (This *is* cache-as-you-browse.)
  - **Offline:** cache hit → return cached tile; cache miss → network fails →
    `<image>` errors → schematic fallback.
- The `tiles` cache name is **independent of the app-shell `CACHE`**, so bumping the
  shell version to push code updates never evicts downloaded tiles.

Notes: opaque cross-origin responses are cacheable (these hosts serve permissive
CORS, but cache-first works either way). iOS Safari cache quotas are finite;
cache-as-you-browse keeps the footprint modest. No retry/throttle logic needed —
the browser only requests visible tiles.

## UI

- A new **layer toggle** control on the chart, alongside the existing fit/center
  buttons, persisted via `store` under a new key (e.g. `chartLayer`).
- **Default: ON.** On first online view of the Chart tab, tiles fetch and cache.
  The toggle lets a user turn it off (revert to pure schematic) and the choice is
  remembered per device.
- An always-visible caption while the layer is on:
  *"Chart layer © OpenStreetMap, OpenSeaMap — context only, not for navigation."*
  This satisfies OSM/OpenSeaMap attribution **and** the not-for-navigation framing.
- Colours/markers use existing CSS vars; the caption uses the muted label style.

## Documentation updates (part of this work)

- **CLAUDE.md** constraint #2: record the new allowed network category — tile
  fetches to the two hosts + the SW tile cache — as explicitly authorized, with the
  offline fallback behavior.
- **DESIGN.md** decision #3: note the optional, dimmed, cached *context* layer; state
  it is still not navigation-grade and the plotter remains the source of truth.

## Offline behavior matrix

| State | Layer toggle | Tile cached? | Result |
|---|---|---|---|
| Online | ON | — | Tiles fetched + cached, drawn under schematic |
| Online | OFF | — | Pure schematic, no tile fetch |
| Offline | ON | Yes | Cached tiles drawn under schematic |
| Offline | ON | No | Schematic only (broken tiles removed) |
| Offline | OFF | — | Pure schematic |
| Cold launch, offline | any | app shell cached | App loads (shell SW); tiles per above |

## Testing

- Syntax: `sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin`
  and `node --check sw.js`.
- Manual (served over localhost/HTTPS so the SW runs):
  1. Toggle layer ON while online → tiles appear; verify spots sit on the correct
     islands (alignment check).
  2. Zoom in/out → tile zoom `z` switches, tiles re-tile without gaps.
  3. Pan to new area online → new tiles load and cache.
  4. Go offline (airplane mode / devtools offline) → previously-viewed tiles persist;
     un-visited areas fall back to schematic.
  5. Bump shell `CACHE`, reload → code updates, tiles cache survives.
  6. Toggle OFF → pure schematic returns; reload → choice remembered.

## Risks / open questions

- **Tile usage policy:** light, personal, cache-as-you-browse use is within reason;
  no bulk download. If usage ever looks heavy, revisit a permitted/paid provider.
- **Base-map legibility at night:** the CSS dim filter values may need tuning during
  implementation to keep markers readable — cosmetic, decided by eye.
- **iOS PWA cache quota:** acceptable for a region this size; no action unless hit.
