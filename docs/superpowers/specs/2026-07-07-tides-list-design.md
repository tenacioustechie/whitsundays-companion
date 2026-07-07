# Tides List Redesign — Design

**Date:** 2026-07-07
**Status:** Approved design, pre-implementation
**Topic:** Show date/day in the Tides list and make the full downloaded dataset scrollable.

---

## Problem / goal

The Tides tab shows a "height now" summary, a 24h curve, and an upcoming-events list.
Two gaps:

1. **No date/day in the list.** Each row shows `HH:MM` only (`fmtClock`), so in a multi-day
   dataset you can't tell which day a tide belongs to.
2. **Only ~2 days visible.** The list is capped at `slice(0, 8)`, so most of a 7- or 14-day
   WorldTides download (or a long manual table) is invisible.

Goal: group the **entire** downloaded dataset by day with dated headers, in a scrollable list
that opens at the current time.

## Non-goals

- No change to the "height now" summary or the 24h `drawTideCurve` (both stay as-is).
- No new network calls, no data-model change. `tideEvents()` already returns the complete
  sorted set of `{t, h, type}` (fetched extremes + manual). Fully offline, single file.
- No collapsing/filtering of days, no per-day summaries. YAGNI.

## Constraints honored

- **Single file / offline:** pure rendering change inside `index.html`; no external calls.
- **Colours via CSS vars; numbers in `var(--mono)`:** reuse existing `.tev/.tt/.tk/.th`,
  `--cyan/--amber/--muted` etc.
- **Tide heights are chart datum (CD):** framing unchanged (help text below the list stays).

## Design

### 1. Data → day groups
Use the full `tideEvents()` list (remove the `slice(0, 8)` cap and the `now-3h` filter). Walk
it in time order, grouping consecutive events by **local calendar day**. Each group renders a
day header followed by its tide rows.

- Rows reuse the current markup: `HH:MM` (`fmtClock`) · `High`/`Low` (`.tk high|low`) ·
  `X.XX m` (`.th`). Past events (`t < now`) keep the existing dimmed `.past` class.
- New helper `fmtDay(t)` → `"Sun 6 Jul"` using fixed short weekday/month arrays (no locale
  dependence, matching the app's hand-rolled date style). Today's header reads
  `"Today · Sun 6 Jul"` (today detected by comparing local y/m/d against `Date.now()`).

### 2. Scrollable container
Wrap the day groups in a fixed-height scroll box:

- `.tscroll { max-height: 44vh; overflow-y: auto; position: relative; }`
  (`position: relative` makes it the offset parent for auto-scroll math).
- Day headers are `position: sticky; top: 0` within the box, so the current day label stays
  pinned while scrolling.
- The fetch and manual-entry sections below the list are unchanged and remain reachable.

### 3. "Now" marker + auto-scroll-to-now
- Insert a thin `NOW` divider (`.tnowline`) between the last past event and the first upcoming
  event.
- After `el.innerHTML` is assigned, set `box.scrollTop = max(0, nowEl.offsetTop − box.clientHeight * 0.3)`
  so the NOW divider sits ~30% down from the top: land on the current tide, scroll **up** for
  earlier days, **down** through the rest of the download.

### 4. Edge cases
| Case | Behavior |
|---|---|
| No data | Existing empty-state banner (unchanged). |
| All events in the past (stale download) | NOW divider at the end; box opens scrolled to the bottom (most recent). |
| All events in the future | NOW divider at the top; box opens at the top. |
| Single day / manual-only | Groups correctly; short list simply doesn't fill the box. |

Implementation note: the NOW divider is emitted exactly once — before the first event with
`t > now`, or at the very end if no such event exists. It doubles as the scroll anchor
(`id="tnow"`); if it can't be found post-render, leave the box at the top.

## Testing

- Syntax: `sed -n '/<script>/,/<\/script>/p' index.html | sed '1d;$d' | node --check /dev/stdin`.
- Browser (served on a fresh port — port 8000 has a stale SW from another project):
  1. Load multi-day fetched data → day headers show weekday + date; today reads "Today · …".
  2. All downloaded days are present and scrollable; headers stick; list opens at NOW.
  3. Past rows dimmed; NOW divider between past and upcoming.
  4. Empty, all-past, and all-future cases behave per the table above.
- Bump `sw.js` `CACHE` (`wts-v3` → `wts-v4`) so devices pick up the shell change.

## Risks / open questions

- **`44vh` box height** may need a nudge on very small phones vs iPad — cosmetic, tune by eye.
- **Sticky headers inside a scroll box** are well supported on iOS/Safari; verify in the manual
  pass.
