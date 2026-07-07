# Tides List Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show every downloaded tide event grouped by dated day headers in a scrollable list that opens at the current time.

**Architecture:** Pure rendering change in `index.html`. Add two date helpers (`dayKey`, `fmtDay`), then rewrite only the list section of `renderTides()` to walk the full `tideEvents()` set, group by local day with sticky dated headers, insert a NOW divider, and auto-scroll the box to it. The "height now" summary and 24h curve are untouched.

**Tech Stack:** Vanilla JS + hand-rolled DOM strings + CSS, single file. No libraries, no build step, no network.

## Global Constraints

- **Single file / offline:** all changes in `index.html` (+ `sw.js` CACHE bump). No external calls, no data-model change.
- **Colours via CSS vars; numbers in `var(--mono)`:** reuse `--panel/--line/--mono/--muted/--cyan/--amber/--green/--sans`; reuse existing `.tev/.tt/.tk/.th/.past` row markup.
- **Tide heights are chart datum (CD):** existing help text below the list stays.
- **No test suite (per CLAUDE.md):** verify with `node --check` on the extracted script + a Node assertion for the pure helpers + a manual browser pass. Syntax command:
  ```bash
  sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin
  ```
- **Local browser testing:** serve on a fresh port (NOT 8000 — a stale service worker from another project is registered there).

---

### Task 1: Date helpers (`dayKey`, `fmtDay`)

**Files:**
- Modify: `index.html` — insert after `function isoDate(...){...}` (currently line 998)
- Test: `/tmp/tideday.test.js` (ephemeral, not committed)

**Interfaces:**
- Consumes: nothing (pure).
- Produces (used by Task 2):
  - `dayKey(t:ms) → int` — `YYYYMMDD`-style integer in device-local time; equal for two timestamps on the same local day.
  - `fmtDay(t:ms) → string` — `"Sun 6 Jul"`, or `"Today · Sun 6 Jul"` when `t` is on the current local day.

- [ ] **Step 1: Write the validation test** — create `/tmp/tideday.test.js`:

```js
const assert = require('assert');
function dayKey(t){const d=new Date(t);return d.getFullYear()*10000+(d.getMonth()+1)*100+d.getDate();}
function fmtDay(t){
  const WD=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],MO=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const d=new Date(t),label=WD[d.getDay()]+' '+d.getDate()+' '+MO[d.getMonth()];
  return dayKey(t)===dayKey(Date.now())?'Today · '+label:label;
}
const now=Date.now();
// same local day -> same key; +12h may cross midnight, so test a mid-day anchor
const noon=new Date(); noon.setHours(12,0,0,0);
assert.strictEqual(dayKey(noon.getTime()), dayKey(noon.getTime()+3600000), 'same day equal');
assert.notStrictEqual(dayKey(noon.getTime()), dayKey(noon.getTime()+24*3600000), 'next day differs');
// fmtDay: today is prefixed
assert.ok(fmtDay(now).startsWith('Today · '), 'today prefixed');
// fmtDay: a non-today day matches "<WD> <D> <MO>"
const other=fmtDay(noon.getTime()+7*24*3600000);
assert.ok(/^(Sun|Mon|Tue|Wed|Thu|Fri|Sat) \d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$/.test(other), 'day label shape: '+other);
console.log('all tide-day assertions passed');
```

- [ ] **Step 2: Run it** — `node /tmp/tideday.test.js` → prints `all tide-day assertions passed`, exit 0.

- [ ] **Step 3: Transplant into `index.html`** — insert immediately after the `function isoDate(t){...}` line:

```js
function dayKey(t){const d=new Date(t);return d.getFullYear()*10000+(d.getMonth()+1)*100+d.getDate();}
function fmtDay(t){
  const WD=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],MO=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const d=new Date(t),label=WD[d.getDay()]+' '+d.getDate()+' '+MO[d.getMonth()];
  return dayKey(t)===dayKey(Date.now())?'Today · '+label:label;
}
```

- [ ] **Step 4: Syntax check** — `sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin` → exit 0.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "feat(tides): add dayKey/fmtDay date helpers"
```

---

### Task 2: Day-grouped scrollable list + NOW divider + auto-scroll

**Files:**
- Modify: `index.html` — CSS after `.tev.past{opacity:.4}` (currently line 163); list block in `renderTides()` (currently lines 916–923); scroll wiring after `if(evs.length) drawTideCurve(evs);` (currently line 955)
- Modify: `sw.js` — `CACHE` constant

**Interfaces:**
- Consumes (Task 1): `dayKey(t)`, `fmtDay(t)`. Existing: `tideEvents()`, `fmtClock(t)`, `drawTideCurve(evs)`.
- Produces: DOM `#tscroll` (the scroll box) and `#tnow` (the NOW divider / scroll anchor).

- [ ] **Step 1: Add CSS** — insert after the line `.tev.past{opacity:.4}`:

```css
  .tscroll{max-height:44vh;overflow-y:auto;position:relative;-webkit-overflow-scrolling:touch}
  .tday{position:sticky;top:0;z-index:1;background:var(--panel);border-bottom:1px solid var(--line);
    padding:7px 12px 5px;font-family:var(--sans);font-size:11px;font-weight:700;
    letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
  .tday.today{color:var(--cyan)}
  .tnowline{display:flex;align-items:center;gap:8px;padding:5px 12px;
    font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.08em;color:var(--green)}
  .tnowline::before,.tnowline::after{content:"";flex:1;height:1px;background:var(--green);opacity:.5}
```

- [ ] **Step 2: Replace the list block** — swap this exact block:

```js
    // upcoming list
    const now=Date.now();
    html+=`<div class="card tlist">`+evs.filter(e=>e.t>now-3*3600000).slice(0,8).map(e=>{
      const past=e.t<now;
      return `<div class="tev ${past?'past':''}"><div class="tt">${fmtClock(e.t)}</div>
        <div class="tk ${e.type}">${e.type==='high'?'High':'Low'}</div>
        <div class="th">${e.h.toFixed(2)} m</div></div>`;
    }).join('')+`</div>`;
```

with the full-list, day-grouped version:

```js
    // full multi-day list: grouped by local day, scrollable, with a NOW divider
    const now=Date.now(), todayK=dayKey(now);
    let rows='', lastK=null, nowPlaced=false;
    const nowDivider=`<div class="tnowline" id="tnow">NOW</div>`;
    evs.forEach(e=>{
      if(!nowPlaced && e.t>now){ rows+=nowDivider; nowPlaced=true; }
      const k=dayKey(e.t);
      if(k!==lastK){ lastK=k; rows+=`<div class="tday${k===todayK?' today':''}">${fmtDay(e.t)}</div>`; }
      const past=e.t<now;
      rows+=`<div class="tev ${past?'past':''}"><div class="tt">${fmtClock(e.t)}</div>
        <div class="tk ${e.type}">${e.type==='high'?'High':'Low'}</div>
        <div class="th">${e.h.toFixed(2)} m</div></div>`;
    });
    if(!nowPlaced) rows+=nowDivider;   // all events in the past -> divider at the end
    html+=`<div class="card tlist tscroll" id="tscroll">${rows}</div>`;
```

- [ ] **Step 3: Add auto-scroll-to-now** — immediately after the line `if(evs.length) drawTideCurve(evs);`:

```js
  const box=document.getElementById('tscroll'), nowEl=document.getElementById('tnow');
  if(box&&nowEl) box.scrollTop=Math.max(0, nowEl.offsetTop - box.clientHeight*0.3);
```

- [ ] **Step 4: Bump the service-worker cache** — in `sw.js`, change `const CACHE = 'wts-v3';` to `const CACHE = 'wts-v4';`.

- [ ] **Step 5: Syntax check** — `sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin && node --check sw.js` → exit 0.

- [ ] **Step 6: Manual browser check** — serve on a fresh port (e.g. `python3 -m http.server 8137`), open the Tides tab. To exercise multi-day data without a WorldTides key, paste a multi-day table into the manual box and Save, e.g.:
  ```
  2026-07-07 05:12 L 0.6
  2026-07-07 11:23 H 3.4
  2026-07-07 17:40 L 0.8
  2026-07-08 00:02 H 3.1
  2026-07-08 06:01 L 0.5
  2026-07-08 12:14 H 3.6
  2026-07-09 01:10 H 3.0
  ```
  Confirm: day headers show weekday + date; today reads "Today · …"; **all** days present and scrollable; headers stick to the top while scrolling; the list opens scrolled to the NOW divider; past rows are dimmed. Then check the empty state (clear data) and that a single-day table still groups correctly.

- [ ] **Step 7: Commit**

```bash
git add index.html sw.js
git commit -m "feat(tides): dated day-grouped scrollable list, opens at now"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** date/day headers (Task 2 §2 + `fmtDay` Task 1) ✓; full dataset, no cap (Task 2 §2 drops `slice(0,8)`) ✓; scroll box + sticky headers (Task 2 §1) ✓; NOW divider + auto-scroll + edge cases all-past/all-future (Task 2 §2–3) ✓; CACHE bump (Task 2 §4) ✓; empty state untouched (out of scope, preserved) ✓.
- **Type consistency:** `dayKey`/`fmtDay` defined in Task 1, consumed with the same signatures in Task 2; `#tscroll`/`#tnow` produced in Task 2 §2 and read in §3.
- **Placeholder scan:** every step has literal code/commands; no TBD/TODO.
