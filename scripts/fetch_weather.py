#!/usr/bin/env python3
"""Fetch the BOM Mackay Coastal Waters forecast (IDQ11306) and merge it into a
rolling JSON history used by the Whitsundays Companion Weather tab.

Stdlib only. Design: docs/superpowers/specs/2026-07-07-marine-weather-design.md
"""
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

PRODUCT = "IDQ11306"
URL = f"https://www.bom.gov.au/fwo/{PRODUCT}.xml"
AREA_AAC = "QLD_MW008"  # Mackay Coast: Bowen to St Lawrence (covers the Whitsundays)
UA = "Whitsundays-Companion/1.0 (+https://github.com/tenacioustechie/whitsundays-companion)"
ATTRIBUTION = "© Commonwealth of Australia, Bureau of Meteorology"
MAX_ISSUES = 20
_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch(url=URL, ua=UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _label(index, start_local):
    if index == 0:
        return "Tonight"
    dt = datetime.fromisoformat(start_local)
    return f"{_DAYS[dt.weekday()]} {dt.day} {_MONS[dt.month - 1]}"  # e.g. "Wed 8 Jul"


def parse_product(xml_bytes):
    """Parse IDQ11306 XML into one issue dict. Raise ValueError if unexpected."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"invalid XML: {e}")
    amoc = root.find("amoc")
    issued = amoc.findtext("issue-time-local") if amoc is not None else None
    synopsis = None
    title = None
    periods = []
    for area in root.iter("area"):
        if area.get("type") == "sub-region":
            syn = area.find("./forecast-period/text[@type='synoptic_situation']")
            if syn is not None and syn.text:
                synopsis = syn.text.strip()
        if area.get("aac") == AREA_AAC:
            title = area.get("description")
            for fp in area.findall("forecast-period"):
                idx = int(fp.get("index"))

                def _t(tp):
                    e = fp.find(f"text[@type='{tp}']")
                    return e.text.strip() if e is not None and e.text else None

                periods.append({
                    "label": _label(idx, fp.get("start-time-local")),
                    "winds": _t("forecast_winds"),
                    "seas": _t("forecast_seas"),
                    "swell": _t("forecast_swell1"),
                    "weather": _t("forecast_weather"),
                })
    if not issued or not title or not periods:
        raise ValueError("unexpected IDQ11306 structure (missing issued/area/periods)")
    return {"issued": issued, "synopsis": synopsis, "warning": None,
            "periods": periods, "_title": title}


def merge(existing, issue, fetched_iso, product=PRODUCT, cap=MAX_ISSUES):
    entry = {"issued": issue["issued"], "fetched": fetched_iso,
             "synopsis": issue["synopsis"], "warning": issue["warning"],
             "periods": issue["periods"]}
    old = [h for h in (existing or {}).get("history", []) if h.get("issued") != entry["issued"]]
    history = ([entry] + old)[:cap]
    return {"product": product, "title": issue["_title"],
            "attribution": ATTRIBUTION, "history": history}


def _forecast_equal(a, b):
    """Compare two file dicts ignoring the volatile per-entry 'fetched' timestamp."""
    def strip(d):
        return {**d, "history": [{k: v for k, v in h.items() if k != "fetched"}
                                 for h in (d or {}).get("history", [])]}
    return strip(a) == strip(b)


def main(argv):
    path = argv[1] if len(argv) > 1 else "weather/mackay-coast.json"
    try:
        xml_bytes = fetch()
    except Exception as e:  # network/HTTP failure -> keep existing history untouched
        print(f"fetch failed: {e}", file=sys.stderr)
        return 0
    try:
        issue = parse_product(xml_bytes)
    except ValueError as e:
        print(f"parse failed: {e}", file=sys.stderr)
        return 0
    try:
        with open(path, encoding="utf-8") as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = None
    fetched_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    merged = merge(existing, issue, fetched_iso)
    if existing is not None and _forecast_equal(existing, merged):
        print("unchanged")
        return 0
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(merged, ensure_ascii=False, indent=2) + "\n")
    print(f"updated: {len(merged['history'])} issues, latest {merged['history'][0]['issued']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
