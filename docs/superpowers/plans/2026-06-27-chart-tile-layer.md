# Chart Tile Layer (OpenSeaMap) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional, cached-as-you-browse OpenSeaMap nautical tile layer behind the schematic Chart tab, aligned to the existing projection, working offline for tiles already viewed.

**Architecture:** Keep the hand-rolled SVG schematic and its equirectangular `project()`. In `drawChart()`, draw a layer of `<image>` tiles *behind* the grid/spots, each Web-Mercator tile pinned to its true geographic corners via `project()` (separable & linear → tiles seam perfectly and spots stay aligned). The service worker caches the two tile hosts cache-first into a dedicated cache, giving cache-as-you-browse offline.

**Tech Stack:** Vanilla JS, hand-rolled SVG, service worker Cache API. OSM base tiles (`tile.openstreetmap.org`) + OpenSeaMap seamark overlay (`tiles.openseamap.org/seamark`). No libraries, no build step.

## Global Constraints

Copied verbatim from the spec / CLAUDE.md — every task must honor these:

- **Single file, zero runtime deps.** All app code stays in `index.html`; only `sw.js` and the two doc files are also touched. Tiles are runtime *data* fetches, not scripts/libraries. No npm/CDN/web-fonts/build step.
- **Offline-capable.** App shell must still cold-launch offline. Tiles are cache-first; offline + uncached tile → renders nothing → schematic shows through. No bulk download.
- **Never present coordinates as navigation-grade.** Imagery is a dimmed *context* layer; the "context only — not for navigation" caption + OSM/OpenSeaMap attribution stay visible whenever the layer is on. Existing framing unchanged.
- **No frameworks.** Vanilla JS matching existing style.
- **Allowed network calls** now: WorldTides fetch (user-triggered), **chart-layer tiles (this feature)**, and the SW background cache refresh.
- **No test suite (per CLAUDE.md).** Verification = `node --check` syntax checks + targeted Node math assertions (Task 1) + manual browser exercise. This replaces red-green unit TDD, which is not applicable to embedded SVG rendering. The syntax check command is:
  ```bash
  sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin && node --check sw.js
  ```
- **Bump `sw.js` `CACHE`** when the app shell (`index.html`) changes, so devices pick up the new code (done in Task 3).
- **Colours via CSS vars**; reuse `--cyan`/`--muted2`/`--line` etc., don't hard-code new hex where a var exists.

---

### Task 1: Web-Mercator tile-math helpers (pure functions)

**Files:**
- Modify: `index.html` — insert after `const BASE_SPAN=0.55;` (currently line 485)
- Test: `/tmp/tilemath.test.js` (ephemeral; not committed)

**Interfaces:**
- Consumes: nothing (pure math).
- Produces (used by Task 2):
  - `TILE_HOSTS` → `{base:string, sea:string}` URL prefixes
  - `tileZoom(lonSpan:number, vw:number) → int` (clamped 9..16)
  - `lonToTileX(lon, z) → int`, `latToTileY(lat, z) → int`
  - `tileXToLon(x, z) → deg`, `tileYToLat(y, z) → deg`

- [ ] **Step 1: Write the math-validation test**

Create `/tmp/tilemath.test.js`:

```js
const assert = require('assert');
function tileZoom(lonSpan,vw){ return Math.max(9,Math.min(16,Math.round(Math.log2(360*vw/(256*lonSpan))))); }
function lonToTileX(lon,z){ return Math.floor((lon+180)/360*Math.pow(2,z)); }
function latToTileY(lat,z){ const r=lat*Math.PI/180; return Math.floor((1-Math.asinh(Math.tan(r))/Math.PI)/2*Math.pow(2,z)); }
function tileXToLon(x,z){ return x/Math.pow(2,z)*360-180; }
function tileYToLat(y,z){ return Math.atan(Math.sinh(Math.PI*(1-2*y/Math.pow(2,z))))*180/Math.PI; }

// z=0 spans the whole world — exact, well-known anchors
assert.strictEqual(tileXToLon(0,0), -180);
assert.strictEqual(tileXToLon(1,0),  180);
assert.ok(Math.abs(tileYToLat(0,0) - 85.0511287) < 1e-3, 'north edge');
assert.ok(Math.abs(tileYToLat(1,0) + 85.0511287) < 1e-3, 'south edge');

// containment: the tile a point falls in must bracket that point (Shute Harbour)
const lat=-20.288, lon=148.787, z=13;
const x=lonToTileX(lon,z), y=latToTileY(lat,z);
assert.ok(tileXToLon(x,z) <= lon && lon < tileXToLon(x+1,z), 'lon containment');
assert.ok(tileYToLat(y,z) >= lat && lat >  tileYToLat(y+1,z), 'lat containment');

// monotonic: further south -> larger tile y
assert.ok(latToTileY(-21,13) > latToTileY(-20,13), 'y increases southward');

// zoom picks a sane level across the app's zoom range (vw=400)
assert.ok(tileZoom(0.55,400) >= 9 && tileZoom(0.0611,400) <= 16, 'zoom clamp');

console.log('all tile-math assertions passed');
```

- [ ] **Step 2: Run the test to verify the math**

Run: `node /tmp/tilemath.test.js`
Expected: prints `all tile-math assertions passed`, exit 0. (If any assert throws, the math is wrong — fix before transplanting.)

- [ ] **Step 3: Transplant the validated helpers into `index.html`**

Insert immediately after the line `const BASE_SPAN=0.55; // deg longitude visible at zoom 1`:

```js
/* ---- Web-Mercator tile helpers (optional cached chart layer) ---- */
const TILE_HOSTS={base:'https://tile.openstreetmap.org',sea:'https://tiles.openseamap.org/seamark'};
function tileZoom(lonSpan,vw){ return Math.max(9,Math.min(16,Math.round(Math.log2(360*vw/(256*lonSpan))))); }
function lonToTileX(lon,z){ return Math.floor((lon+180)/360*Math.pow(2,z)); }
function latToTileY(lat,z){ const r=lat*Math.PI/180; return Math.floor((1-Math.asinh(Math.tan(r))/Math.PI)/2*Math.pow(2,z)); }
function tileXToLon(x,z){ return x/Math.pow(2,z)*360-180; }
function tileYToLat(y,z){ return Math.atan(Math.sinh(Math.PI*(1-2*y/Math.pow(2,z))))*180/Math.PI; }
```

- [ ] **Step 4: Syntax check**

Run: `sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin`
Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(chart): add Web-Mercator tile-math helpers"
```

---

### Task 2: Render the cached tile layer in `drawChart()`

**Files:**
- Modify: `index.html` — `S` object (line ~417), CSS map section (line ~92), map markup (line ~208), `drawChart()` (lines ~507, ~515, ~571)

**Interfaces:**
- Consumes (from Task 1): `TILE_HOSTS`, `tileZoom`, `lonToTileX`, `latToTileY`, `tileXToLon`, `tileYToLat`. Existing: `project(lat,lon,vw,vh)`, `MAP`, `BASE_SPAN`, `S`.
- Produces (used by Task 4): `S.chartLayer:boolean` (default `true`); DOM element `#chartcap`; the tile layer is drawn whenever `S.chartLayer` is truthy.

- [ ] **Step 1: Add the persisted `chartLayer` flag to `S`**

In the `S={...}` object, add this line after `route:store.get('route',[]),`:

```js
  chartLayer:store.get('chartLayer',true),  // optional cached map tiles behind the schematic
```

- [ ] **Step 2: Add CSS for the dimmed base layer and the attribution caption**

In the `/* ---- map ---- */` CSS block, after the `.ilbl{...}` rule, add:

```css
  .tilebase{filter:brightness(.62) saturate(.6) contrast(.95)}
  #chartcap{position:absolute;right:10px;bottom:7px;max-width:64%;text-align:right;
    font-family:var(--sans);font-size:9.5px;line-height:1.25;color:var(--muted2);
    text-shadow:0 1px 2px rgba(0,0,0,.85);z-index:4;pointer-events:none}
```

- [ ] **Step 3: Add the caption element to the map markup**

In `#mapwrap`, immediately after `<svg id="chart" preserveAspectRatio="xMidYMid meet"></svg>`, add:

```html
      <div id="chartcap">© OpenStreetMap · OpenSeaMap — context only, not for navigation</div>
```

- [ ] **Step 4: Declare the tile string and draw tiles behind the schematic**

(a) In `drawChart()`, change `let out='';` to also declare the tile buffer:

```js
  let out='', tiles='';
```

(b) Immediately after the line `const latSpan=lonSpan*(vh/vw)/kx;` (it sits just before the latitude-grid loop), insert:

```js
  /* ---- cached chart tile layer (drawn first, behind the schematic) ---- */
  const cap=document.getElementById('chartcap'); if(cap)cap.style.display=S.chartLayer?'block':'none';
  if(S.chartLayer){
    const z=tileZoom(lonSpan,vw);
    const west=MAP.cy-lonSpan/2, east=MAP.cy+lonSpan/2;
    const north=MAP.cx+latSpan/2, south=MAP.cx-latSpan/2;
    const x0=lonToTileX(west,z), x1=lonToTileX(east,z);
    const y0=latToTileY(north,z), y1=latToTileY(south,z);
    if((x1-x0+1)*(y1-y0+1)<=64){           // safety guard against pathological ranges
      let base='', sea='';
      for(let x=x0;x<=x1;x++)for(let y=y0;y<=y1;y++){
        const[xL,yT]=project(tileYToLat(y,z),tileXToLon(x,z),vw,vh);
        const[xR,yB]=project(tileYToLat(y+1,z),tileXToLon(x+1,z),vw,vh);
        const a=`x="${xL.toFixed(1)}" y="${yT.toFixed(1)}" width="${(xR-xL+1).toFixed(1)}" height="${(yB-yT+1).toFixed(1)}" pointer-events="none"`;
        base+=`<image ${a} href="${TILE_HOSTS.base}/${z}/${x}/${y}.png"/>`;
        sea +=`<image ${a} href="${TILE_HOSTS.sea}/${z}/${x}/${y}.png"/>`;
      }
      tiles=`<g class="tilebase">${base}</g><g>${sea}</g>`;
    }
  }
```

(Note: a broken/offline SVG `<image>` renders nothing — no broken-icon — so no `onerror` handling is needed; uncached areas simply show the schematic.)

(c) Change the render line `svg.innerHTML=out;` to prepend the tiles so they sit behind everything:

```js
  svg.innerHTML=tiles+out;
```

- [ ] **Step 5: Syntax check**

Run: `sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin`
Expected: no output, exit 0.

- [ ] **Step 6: Manual browser check (online)**

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```
Expected, on the Chart tab while online:
- A dimmed map (land/sea) with OpenSeaMap seamarks appears behind the cyan/amber spot dots.
- Spot dots sit on the correct islands (e.g. your position dot near Shute Harbour aligns with the OSM "Shute Harbour" area). This confirms tile↔spot alignment.
- Pinch/scroll zoom: tiles re-tile without gaps as zoom changes; pan loads new tiles.

- [ ] **Step 7: Commit**

```bash
git add index.html
git commit -m "feat(chart): draw cached OSM+OpenSeaMap tile layer behind schematic"
```

---

### Task 3: Service-worker tile caching (cache-as-you-browse) + CACHE bump

**Files:**
- Modify: `sw.js` (CACHE constant line 13, activate handler line ~37, fetch handler lines ~42-65)

**Interfaces:**
- Consumes: tile requests to `tile.openstreetmap.org` and `tiles.openseamap.org` issued by the Task 2 `<image>` elements.
- Produces: a dedicated `wts-tiles` cache, populated on successful tile fetches and preserved across shell upgrades.

- [ ] **Step 1: Bump CACHE and add tile-cache + host constants**

Change `const CACHE = 'wts-v1';` to:

```js
const CACHE = 'wts-v2';
const TILES = 'wts-tiles';                       // chart-layer tiles, kept across shell upgrades
const TILE_HOSTS = ['tile.openstreetmap.org', 'tiles.openseamap.org'];
```

- [ ] **Step 2: Preserve the tile cache in the activate cleanup**

In the `activate` handler, change the filter so it never deletes the tile cache:

```js
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE && k !== TILES).map((k) => caches.delete(k))))
```

- [ ] **Step 3: Add a cache-first tile branch to the fetch handler**

In the `fetch` listener, immediately after `const url = new URL(req.url);` and **before** the `if (url.origin !== self.location.origin) return;` line, insert:

```js
  // Chart-layer tiles: cache-first into a dedicated cache (cache-as-you-browse).
  if (TILE_HOSTS.includes(url.hostname)) {
    e.respondWith(
      caches.open(TILES).then((c) =>
        c.match(req).then((hit) =>
          hit || fetch(req)
            .then((res) => {
              // tiles are no-cors (opaque) or cors; cache either when we got bytes
              if (res && (res.ok || res.type === 'opaque')) c.put(req, res.clone());
              return res;
            })
            .catch(() => hit)              // offline + uncached -> let the <image> render nothing
        )
      )
    );
    return;
  }
```

- [ ] **Step 4: Syntax check**

Run: `node --check sw.js`
Expected: no output, exit 0.

- [ ] **Step 5: Manual offline check**

Serve over `http://localhost:8000` (SW needs localhost/HTTPS). With DevTools open:
1. Online, Chart tab: pan around the island group so tiles load. Confirm in Application → Cache Storage that a `wts-tiles` cache fills.
2. DevTools → Network → **Offline**. Reload the app: it still launches (shell from `wts-v2`).
3. On the Chart tab offline: previously-viewed tiles still render; pan to an un-visited area → those tiles are absent and the schematic shows through (no broken icons).
4. Confirm `wts-tiles` survived the `wts-v2` activation (still present in Cache Storage).

- [ ] **Step 6: Commit**

```bash
git add sw.js
git commit -m "feat(sw): cache chart tiles cache-first in a dedicated cache; bump CACHE to v2"
```

---

### Task 4: Layer toggle control (default ON, persisted)

**Files:**
- Modify: `index.html` — map markup (`#maptools`, line ~213), CSS (`.mtbtn` block, line ~95), DOMContentLoaded wiring (line ~1081)

**Interfaces:**
- Consumes (from Task 2): `S.chartLayer`, `drawChart()`, `store`.
- Produces: a `#mt-layer` toggle button that flips/persists `S.chartLayer` and reflects state with an `.on` class.

- [ ] **Step 1: Add the toggle button to the map tools**

In `#maptools`, after the `mt-fit` button, add (layers icon matching the app's existing SVG icon style):

```html
        <button class="mtbtn" id="mt-layer" title="Chart layer on/off"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 22 8.5 12 15 2 8.5 12 2"/><polyline points="2 15.5 12 22 22 15.5"/></svg></button>
```

- [ ] **Step 2: Add the active-state style**

After the `.mtbtn{...}` rule, add:

```css
  .mtbtn.on{background:var(--cyan);color:#04222a;border-color:var(--cyan)}
```

- [ ] **Step 3: Wire the toggle (and set its initial state)**

In the DOMContentLoaded block, after the `mt-fit` listener line, add:

```js
  const layerBtn=document.getElementById('mt-layer');
  layerBtn.classList.toggle('on',S.chartLayer);
  layerBtn.addEventListener('click',()=>{
    S.chartLayer=!S.chartLayer; store.set('chartLayer',S.chartLayer);
    layerBtn.classList.toggle('on',S.chartLayer); drawChart();
  });
```

- [ ] **Step 4: Syntax check**

Run: `sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin`
Expected: no output, exit 0.

- [ ] **Step 5: Manual check**

On `http://localhost:8000`, Chart tab:
- Button starts highlighted (`.on`) and tiles show (default ON).
- Tap it → tiles + caption disappear, button un-highlights → pure schematic.
- Reload → the off/on choice persists (per device).

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "feat(chart): add persisted chart-layer toggle button (default on)"
```

---

### Task 5: Documentation updates

**Files:**
- Modify: `CLAUDE.md` (hard constraint #2), `DESIGN.md` (decision #3)

**Interfaces:** none (docs only).

- [ ] **Step 1: Update CLAUDE.md constraint #2**

Replace the sentence:

```
   fetch (explicitly user-triggered) and the service worker's background cache refresh.
```

with:

```
   fetch (explicitly user-triggered), the optional chart-layer map tiles (OSM base +
   OpenSeaMap seamarks, cached-as-you-browse for offline use), and the service worker's
   background cache refresh.
```

- [ ] **Step 2: Update DESIGN.md decision #3**

At the end of the "### 3. The map is an honest schematic, not a fake chart" paragraph (after "...so it needs no mapping library."), append a new paragraph:

```
An *optional* cached chart layer can sit behind the schematic: a dimmed OpenStreetMap base
plus the OpenSeaMap seamark overlay, fetched and cached-as-you-browse while online (no bulk
download — coverage is wherever you panned). It is deliberately framed as *context only* —
dimmed, captioned "not for navigation", and never the source of truth. The boat's plotter
still is. The layer is a per-device toggle (default on) and degrades to the pure schematic
wherever tiles aren't cached.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md DESIGN.md
git commit -m "docs: record the optional cached chart tile layer"
```

---

## Final end-to-end verification (after all tasks)

- [ ] Run the full syntax check: `sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin && node --check sw.js` → exit 0.
- [ ] Serve on `http://localhost:8000`. Online: tiles appear, dots align, zoom/pan re-tiles, `wts-tiles` cache fills.
- [ ] Toggle off → pure schematic; reload → choice remembered.
- [ ] DevTools Offline + reload: app launches, viewed tiles persist, un-viewed areas fall back to schematic, no broken-image icons.
- [ ] Attribution/"not for navigation" caption visible whenever the layer is on.

## Self-Review (completed during planning)

- **Spec coverage:** Rendering (Task 2) ✓; offline cache-as-you-browse SW (Task 3) ✓; UI toggle default-ON + attribution caption (Task 2 caption, Task 4 toggle) ✓; doc updates (Task 5) ✓; testing approach (Global Constraints + per-task) ✓; not-for-navigation framing (caption Task 2) ✓; no bulk download (guard + cache-first only) ✓.
- **Type consistency:** helper names (`tileZoom`/`lonToTileX`/`latToTileY`/`tileXToLon`/`tileYToLat`/`TILE_HOSTS`) defined in Task 1 and consumed identically in Task 2; `S.chartLayer` defined in Task 2, consumed in Tasks 2 & 4; `#mt-layer`/`#chartcap`/`.tilebase`/`wts-tiles`/`TILES`/`TILE_HOSTS` used consistently across tasks.
- **Placeholder scan:** every code/edit step shows literal content; no TBD/TODO.
