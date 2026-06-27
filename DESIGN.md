# Build Decisions & Features

Why the Whitsundays Sailing Companion is built the way it is, what each feature does,
and where it could go next. Pair this with `CLAUDE.md` (the practical rules for editing).

---

## The problem

Planning a Whitsundays bareboat charter from the water. You want, at a glance: where am I,
which approved overnight spots are near, how far/what bearing to reach them, is tonight's
forecast wind going to leave me exposed there, and when are the tides. The catch that drives
every technical decision: **out among the islands there is no reliable mobile signal.**

This is a *planning aid that complements* the boat's real chart plotter — not a replacement.
The plotter is the navigation source of truth; this app is the "what are my options tonight"
companion that everyone in the family can have on their own phone.

---

## Core decisions

### 1. Offline-first, single self-contained file
The whole app is one `index.html` with HTML, CSS, JS and all the anchorage data inlined.
Zero external dependencies at load: no map tiles, no CDN scripts, no web fonts. Once a device
has opened it while online, it runs forever with the network off.

Why: anything that fetches at load time is a thing that fails at sea. A single file is also
trivially shareable (AirDrop it) and trivially hostable (one file on GitHub Pages).

GPS is the happy exception to "no network" — the location chip works off satellites and needs
no data connection, only the browser's permission. So live position keeps updating mid-channel.

### 2. Service worker for guaranteed cold-launch offline
The browser's default caching is *probably* enough, but iOS can be flaky about launching a
home-screen web app with no connection if it hasn't been told to cache. `sw.js` precaches the
app shell and serves it stale-while-revalidate: instant from cache, refreshed in the background
when online. This makes "open the app on a mooring with airplane mode on" reliable rather than
hopeful. Cross-origin requests (the tide API) are deliberately not intercepted.

### 3. The map is an honest schematic, not a fake chart
The Chart tab plots spots from their own coordinates with a lat/lon grid, island labels, a
north arrow and a scale bar — but **no coastlines**. Drawing approximate coastlines would look
authoritative and invite someone to trust it for navigation. Since the boat has a real plotter,
the app's job is relative geometry ("that spot is 3.2 nm at 145°"), not cartography. Rendering
is hand-rolled SVG with custom pan/zoom/pinch so it needs no mapping library.

An *optional* cached chart layer can sit behind the schematic: a dimmed OpenStreetMap base
plus the OpenSeaMap seamark overlay, fetched and cached-as-you-browse while online (no bulk
download — coverage is wherever you panned). It is deliberately framed as *context only* —
dimmed, captioned "not for navigation", and never the source of truth. The boat's plotter
still is. The layer is a per-device toggle (default on) and degrades to the pure schematic
wherever tiles aren't cached.

### 4. Tides: two paths, because signal is exactly where you won't have it
- **Pre-fetch at the marina** (`fetchTides`): while still on wifi, pull the whole trip's
  highs/lows + hourly heights from the WorldTides API (free tier; a 7-day fetch ≈ 1 credit),
  cached to the device for the week.
- **Manual entry** (`saveManual`): paste the official MSQ/BOM tide table; a tolerant parser
  reads both `YYYY-MM-DD HH:MM L 0.6` and `DD/MM HH:MM H 3.4` shapes. No key, no signal, ever.

Current height between published extremes is a cosine interpolation (`tideNow`) — the standard
"rule of twelfths" smoothed. Heights are **chart datum (CD ≈ LAT)**: add them to charted depths.
WorldTides may be CORS-blocked from some hosts/browsers, so manual entry is the dependable
fallback and the UI says so.

### 5. localStorage with a fallback
`store` wraps localStorage in try/catch and falls back to an in-memory object. This means the
app behaves in sandboxed previews (where storage may throw) and persists for real when hosted.

### 6. Visual identity: marine instrument / chart plotter
Dark navy-black (`#0a1622`), night-safe and high-contrast for a dim cockpit. Monospace for
every number (bearings, distances, coords, heights) so they read like instrument output. Cyan
= data, amber = caution, green = protected/fits, red = exposed. Bottom tab bar (Chart / Nearby
/ Tides / Plan / Setup); an always-visible top bar shows the GPS fix and its state
(LIVE / DEMO / last-fix).

---

## Features

**Live GPS fix bar** — deg-min coordinates, accuracy, speed/heading, and a clear state badge.
Falls back to a cached last fix, or a demo position at Shute Harbour (-20.288, 148.787) so the
app is explorable on dry land.

**Chart tab** — schematic plot of all spots + your position; tap a point for its detail sheet;
pan/zoom/pinch; fit-all and centre-on-me controls.

**Nearby tab** — every spot sorted by distance from you, each showing distance, bearing, ETA
(at your planning speed) and an overnight/day badge. Filter chips: type, "protected tonight",
"fits my boat", and show/hide day-use. This is the day-to-day workhorse.

**Wind-protection matching** — enter the forecast wind direction + strength in Setup; each spot
gets a Protected/Exposed verdict for tonight by testing the forecast direction against the
charter list's clockwise protection arc. The detail sheet draws a compass rose shading the
protected arc — the signature UI element.

**Boat-fit filter** — enter boat length + hull (mono/multi); spots with public moorings flag
which classes (T/A/B/C/D) your vessel actually fits, by length and hull.

**Plan tab** — string spots into an ordered voyage; see per-leg distance/bearing and running
totals (nm + ETA at planning speed). A quick "can we get round the islands this week" sketch.

**Tides tab** — tide curve with the current interpolated height, the day's highs/lows, the
WorldTides pre-fetch, and the manual paste box. Reference ports: Hamilton Island, Shute Harbour,
Mackay.

---

## Data

`SPOTS` holds 46 approved overnight anchorages/moorings (ids 1–46) plus 11 day-use public
moorings (ids 101–111), each with approximate coordinates, type, a clockwise wind-protection
arc, a skipper note, and public-mooring class counts where they match the GBRMPA map. Sources:
the GBRMPA Whitsundays public moorings map and the charter operator's approved-anchorage list.

Coordinates were eyeballed from those references to drive the distance sort and the rough chart.
They are **approximate and not for navigation** — that caveat is surfaced throughout the UI and
must stay.

---

## Known limitations

- Coordinates are approximate; the chart has no coastlines (both by design).
- Tide interpolation is cosine between published extremes — good enough for planning, not a
  harmonic prediction.
- WorldTides may be CORS-blocked in-browser; manual entry is the reliable path.
- Wind matching uses a single forecast direction/strength for "tonight"; it doesn't model wind
  shifts through the night.

---

## Future ideas

- **More precise coordinates** from the charter's own waypoints or the plotter, if available.
- **Sun/moon + civil twilight** for an anchoring-by-dark cue (computable offline from lat/lon
  + date, no network).
- **Per-spot "tide gate" warnings** baked into the data (e.g. Gulnare — enter on a rising tide;
  Nara/Macona depth notes) that cross-reference the current tide state.
- **Bearing-to-spot as a live "go-to"** that updates with heading while underway.
- **Distance-to-go vs daylight remaining** on the Plan tab.
- **Downloadable trip bundle**: pre-fetch tides + freeze the forecast into the cache as a
  one-tap "ready for the week" action at the marina.
- **Anchor-watch**: set a position + radius and alert on drift (uses GPS only, works offline).
