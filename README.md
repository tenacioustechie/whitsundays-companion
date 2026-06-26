# Whitsundays Sailing Companion

A self-contained, **offline-first** planning aid for a Whitsundays bareboat charter.
Shows your live GPS position, the approved overnight anchorages and public moorings,
distance/bearing/ETA to each, wind-protection matching for tonight's forecast, a simple
voyage planner, and tide times/heights.

The whole app is a single `index.html` file with **zero external dependencies** — no map
tiles, no CDN, no web fonts. Once a device has loaded it, it keeps working with no mobile
signal at all (GPS works off satellites and needs no data connection). The only thing that
wants the internet is fetching tide predictions, and there's an offline fallback for that too.

> ⚠️ **Not for navigation.** Spot coordinates are approximate, eyeballed from the GBRMPA
> moorings map and the charter's approved-anchorage list to drive the distance sort and the
> rough chart. Use your chart plotter and official charts for actual navigation. Take care
> with tide-gated inlets (Gulnare on a rising tide; Nara/Macona depths) and always eyeball
> the lee shore on arrival.

---

## Deploy to GitHub Pages

You only need to do this once. After that the family just open a link and tap "Add to Home Screen".

### Option A — push and let the Action deploy (recommended)

```bash
# from the folder that contains index.html
git init
git add .
git commit -m "Whitsundays Sailing Companion"
git branch -M main
git remote add origin https://github.com/<you>/whitsundays-companion.git
git push -u origin main
```

Then, in the repo on github.com: **Settings → Pages → Build and deployment → Source:
"GitHub Actions"**. The included workflow (`.github/workflows/deploy.yml`) runs on every push
to `main` and publishes the site. Watch progress in the **Actions** tab; when it's green your
URL is shown there and under Settings → Pages, usually:

```
https://<you>.github.io/whitsundays-companion/
```

### Option B — no command line

Create a new repo on github.com, click **Add file → Upload files**, drag in everything from
this folder (the `index.html`, the three `icon-*.png` files, `manifest.json`, `.nojekyll`, and
the `.github` folder), and commit. Then either set **Settings → Pages → Source: GitHub Actions**
(uses the workflow), or pick **Deploy from a branch → main → / (root)**. Either works; give it
a minute and your URL appears under Settings → Pages.

---

## Put it on the family's phones and iPads

1. Open the Pages URL in **Safari** (iPhone/iPad) or **Chrome** (Android).
2. Allow the location permission when prompted — that's what makes the GPS bar go live.
3. **iPhone/iPad:** Share button → **Add to Home Screen**. **Android:** menu (⋮) → **Add to
   Home screen / Install app**.
4. It now has its own compass icon and opens full-screen like a normal app, working offline.

HTTPS matters here: browsers only hand GPS to secure origins, and GitHub Pages is HTTPS, so
the hosted copy is the reliable way to get live position on every device. (You *can* also just
AirDrop the `index.html` file to a device and open it locally, but the hosted link is tidier
for a group.)

---

## Tides (the one online bit)

Two ways to get tide data, set up under the **Tides** tab and **Setup**:

- **Pre-fetch at the marina.** While you still have wifi/signal, fetch the whole trip from the
  WorldTides API (free tier covers a week). It's cached on the device and then available all
  week offline.
- **Manual entry (always works, no signal, no key).** Paste the official MSQ or BOM tide table
  for Hamilton Island, Shute Harbour or Mackay into the box; it parses the highs/lows and
  interpolates the current height. Grab a printed copy as backup regardless.

Heights are **chart datum** — add them to your charted depths.

---

## What's in this repo

| File | Purpose |
|---|---|
| `index.html` | The entire app (open this to run it) |
| `sw.js` | Service worker — guarantees the app launches offline once cached |
| `manifest.json` | Web app manifest for "Add to Home Screen" / install |
| `icon-180.png` | Apple touch icon (home screen) |
| `icon-192.png`, `icon-512.png` | Manifest / Android icons |
| `.nojekyll` | Tells Pages to serve files as-is (no Jekyll processing) |
| `.github/workflows/deploy.yml` | Auto-deploys to Pages on push to `main` |
| `CLAUDE.md` | Working context for continuing development in Claude Code |
| `DESIGN.md` | Build decisions, feature notes, and future ideas |

No build step, no dependencies, nothing to install. Edit `index.html` directly and push.

## Continuing development

Open this repo in Claude Code — it'll read `CLAUDE.md` for the constraints (single file,
offline-first, no dependencies) and `DESIGN.md` for the *why* behind each decision and a list
of feature ideas. Adding an anchorage is as simple as appending one object to the `SPOTS`
array in `index.html`; see the data-model section in `CLAUDE.md`.

> **Offline caching note:** after you push a change, devices pick it up on their *next online*
> launch (the service worker refreshes the cache in the background). To force a clean refresh
> across all devices, bump the `CACHE` constant at the top of `sw.js` (e.g. `wts-v1` → `wts-v2`).
