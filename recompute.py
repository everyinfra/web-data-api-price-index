#!/usr/bin/env python3
"""Recompute the Web Data API Price Index from its raw tables.

    python3 recompute.py            # rebuild index.csv and headlines.json, print the headline
    python3 recompute.py --check    # rebuild in memory, fail if committed outputs differ

Standard library only (Python 3.10+). Inputs, all in data/<edition>/:
    pages.csv      one row per pricing page: URL, read time (SGT), Wayback archive URL
    providers.csv  one row per provider and line: billing facts quoted from its page
    tiers.csv      one row per published way to pay (plan, pack, pay-as-you-go rate)
    changes.csv    one row per price that differs from the previous reading, with its cause
and data/<period-0>/readings.csv for the comparison with the previous reading.
Outputs: data/<edition>/index.csv, data/<edition>/headlines.json, and the headline
block in README.md (between the HEADLINE markers).
Rules: see METHODOLOGY.md. Licence: MIT (this file); data CC BY 4.0.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EDITION = "2026-q4"
EDITION_LABEL = "Q4 2026"
PERIOD0 = "2026-09-26"
READ_DATE_LABEL = "22 November 2026"
P0_LABEL = "26 September 2026"
PAID = ("subscription", "prepaid", "payg")
CAPTCHA_TYPES = ("recaptcha_v2", "recaptcha_v3", "turnstile", "hcaptcha", "image")
VOLUMES = (10_000, 100_000, 1_000_000)
INDEX_FIELDS = [
    # the eleven fields of the published row format, in order
    "line", "provider", "source_url", "read_at", "unit", "entry_usd_per_1k", "lowest_usd_per_1k",
    "billing", "min_payment_usd", "failed_calls_charged", "archive_url",
    # additional fields
    "product", "segment", "publisher", "listed", "subscription_only", "derived", "conversion",
    "usd_per_1k_at_10k", "usd_per_1k_at_100k", "usd_per_1k_at_1m", "entry_option", "entry_billing",
    "lowest_option", "lowest_billing",
    "price_quote", "lowest_quote", "verification", "period0_entry_usd_per_1k", "period0_lowest_usd_per_1k",
    "change",
]


# ---------------------------------------------------------------- input

def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def num(v: str | None) -> float | None:
    if v is None or str(v).strip() == "":
        return None
    return float(v)


def truthy(v: str | None) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


# ---------------------------------------------------------------- per option

def unit_rate(t: dict) -> tuple[float | None, float | None]:
    """USD per 1,000 billing units for one option: (low, high)."""
    lo, hi = num(t["usd_per_1k"]), num(t["usd_per_1k_max"])
    price, units = num(t["price_usd"]), num(t["units"])
    if lo is None and price is not None and units:
        lo = price / units * 1000
    return lo, (hi if hi is not None else lo)


def per_call(t: dict) -> float:
    """Billing units one base call consumes (1 unless the page says otherwise)."""
    return num(t["units_per_call"]) or 1.0


def call_rate(t: dict) -> tuple[float | None, float | None]:
    """USD per 1,000 base calls: the unit rate times the units one base call consumes."""
    lo, hi = unit_rate(t)
    k = per_call(t)
    return (None if lo is None else lo * k), (None if hi is None else hi * k)


def rate_lo(t: dict) -> float:
    v = call_rate(t)[0]
    return math.inf if v is None else v


def rate_hi(t: dict) -> float:
    v = call_rate(t)[1]
    return -math.inf if v is None else v


def usable(t: dict) -> bool:
    return (t["billing"] in PAID and not truthy(t["async"]) and t["listed"].strip().lower() != "false"
            and call_rate(t)[0] is not None)


def min_spend(t: dict, provider: dict) -> float:
    if t["billing"] == "payg":
        return num(provider.get("min_topup_usd")) or 0.0
    return num(t["price_usd"]) or 0.0


# ---------------------------------------------------------------- per product

def entry_and_lowest(opts: list[dict], provider: dict) -> tuple[dict | None, float | None, dict | None, float | None]:
    """Entry = the paid option with the smallest minimum spend (pay-as-you-go first tier: its
    highest rate); lowest = the lowest rate among all paid options of the same product."""
    paid = [t for t in opts if usable(t)]
    if not paid:
        return None, None, None, None
    payg = [t for t in paid if t["billing"] == "payg"]
    if payg:
        e = max(payg, key=lambda t: (rate_hi(t), -min_spend(t, provider)))
    else:
        e = min(paid, key=lambda t: (min_spend(t, provider), rate_lo(t)))
    low = min(paid, key=rate_lo)
    return e, call_rate(e)[1], low, call_rate(low)[0]


def volume_cost(opts: list[dict], n: int) -> float | None:
    """Cheapest published way to buy n base calls in one month (USD per 1,000).

    Uses a single flat pay-as-you-go rate, repeated prepaid packs, or one plan plus its published
    overage rate. Graduated pay-as-you-go brackets are not modelled (left blank)."""
    costs: list[float] = []
    payg = [t for t in opts if usable(t) and t["billing"] == "payg"]
    if len(payg) == 1 and num(payg[0]["usd_per_1k_max"]) is None:
        costs.append(n / 1000 * rate_lo(payg[0]))
    for t in opts:
        units = num(t["units"])
        if not usable(t) or t["billing"] == "payg" or not units:
            continue
        calls = units / per_call(t)
        price = num(t["price_usd"])
        if price is None:
            price = rate_lo(t) * calls / 1000
        overage = num(t["overage_usd_per_1k"])
        if t["billing"] == "prepaid":
            costs.append(math.ceil(n / calls) * price)
        elif calls >= n:
            costs.append(price)
        elif overage is not None:
            costs.append(price + (n - calls) / 1000 * overage * per_call(t))
    return min(costs) / n * 1000 if costs else None


def billing_class(opts: list[dict]) -> str:
    kinds = {t["billing"] for t in opts if t["billing"] in PAID}
    for k in ("payg", "prepaid", "subscription"):
        if k in kinds:
            return k
    return ""


def verification(used: list[dict]) -> str:
    """How the options behind a price were checked against the archive (METHODOLOGY.md, section 8)."""
    checks = {t["archive_check"] for t in used}
    if not used:
        return ""
    if checks & {"MISSING", "NO-ARCHIVE"} or any(t["unsupported_values"] for t in used):
        return "none"
    return "data" if "VERBATIM(data)" in checks else "page"


def conversion_note(t: dict | None) -> str:
    if not t:
        return ""
    parts = []
    k = num(t["units_per_call"])
    if k and k != 1:
        parts.append(f"{k:,g} {t['unit']}s per call")
    if t.get("assumption"):
        parts.append(t["assumption"])
    if t["currency_original"] and t["currency_original"] != "USD":
        parts.append(f"converted from {t['currency_original']}")
    return "; ".join(parts)


def is_derived(t: dict | None) -> bool:
    """True when the per-call price needs more than dividing a published price by published units."""
    return bool(t) and (num(t["units_per_call"]) not in (None, 1.0) or t["unit"] == "token"
                        or (t["currency_original"] or "USD") != "USD" or bool(t.get("assumption")))


# ---------------------------------------------------------------- formatting

def money(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v:.2f}" if v >= 0.1 else f"{v:.3f}"


def usd(v: float) -> str:
    return "$" + money(v)


def cell(v) -> str:
    """CSV cells carry four decimals (rounded), not the display rounding used in sentences."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    return str(v)


# ---------------------------------------------------------------- build

def build(edition: str = EDITION) -> tuple[list[dict], dict]:
    d = ROOT / "data" / edition
    pages = {p["page"]: p for p in read_csv(d / "pages.csv")}
    providers = read_csv(d / "providers.csv")
    tiers = read_csv(d / "tiers.csv")
    period0 = {(r["line"], r["provider"]): r for r in read_csv(ROOT / "data" / PERIOD0 / "readings.csv")}
    causes: dict[tuple, dict] = {}
    timing: dict[tuple, dict] = {}
    for ch in read_csv(d / "changes.csv"):
        key = (ch["line"], ch["provider"], ch["product"])
        causes.setdefault(key, {})[ch["field"]] = ch["cause"]
        if "price_change" in ch["cause"]:
            if ch["timing"] not in TIMINGS:
                raise SystemExit(f"changes.csv: {ch['provider']} / {ch['field']} needs timing {sorted(TIMINGS)}")
            timing.setdefault(key, {})[ch["field"]] = (ch["timing"], archive_date(ch["prior_archive_url"]))
    rows = []
    for p in providers:
        opts = [t for t in tiers if t["line"] == p["line"] and t["provider"] == p["provider"]]
        # "platform" rows only carry billing; "<product>:<mode>" rows are recorded variants
        products = sorted({t["product"] for t in opts if t["product"] != "platform" and ":" not in t["product"]})
        if p["line"] == "captcha":
            products = list(CAPTCHA_TYPES) + [x for x in products if x not in CAPTCHA_TYPES
                                              and any(usable(t) for t in opts if t["product"] == x)]
        for prod in products:
            po = [t for t in opts if t["product"] == prod]
            e, ev, lo, lv = entry_and_lowest(po, p)
            platform = [t for t in opts if t["product"] == "platform"]
            bill_opts = platform or po
            page = pages.get((e or lo or (po[0] if po else {})).get("page") or p["page"], pages.get(p["page"], {}))
            listed = any(usable(t) for t in po)
            prior = period0.get((p["line"], p["provider"]), {})
            rows.append({
                "line": p["line"], "provider": p["provider"], "source_url": p["source_url"],
                "read_at": page.get("read_at", ""), "unit": p["call_unit"] if listed else "",
                "entry_usd_per_1k": ev, "lowest_usd_per_1k": lv,
                "billing": billing_class(bill_opts), "min_payment_usd": min_payment(bill_opts, p),
                "failed_calls_charged": p["failed_calls_charged"], "archive_url": page.get("archive_url", ""),
                "product": prod, "segment": p.get("segment", ""), "publisher": truthy(p.get("publisher")),
                "listed": listed, "subscription_only": billing_class(bill_opts) == "subscription",
                "derived": is_derived(e) or is_derived(lo), "conversion": conversion_note(e or lo),
                **{f"usd_per_1k_at_{lbl}": volume_cost(po, n) for lbl, n in zip(("10k", "100k", "1m"), VOLUMES)},
                "entry_option": (e or {}).get("option", ""), "entry_billing": (e or {}).get("billing", ""),
                "lowest_option": (lo or {}).get("option", ""), "lowest_billing": (lo or {}).get("billing", ""),
                "price_quote": (e or {}).get("quote", ""), "lowest_quote": (lo or {}).get("quote", ""),
                "verification": verification([t for t in (e, lo) if t]),
                **period0_fields(p["line"], prod, prior, ev, lv),
            })
    for r in rows:
        if r["change"] != "differs":
            continue
        # every price that differs from period 0 needs a cause in changes.csv
        moved = [f for f in ("entry", "lowest") if moved_field(r[f"period0_{f}_usd_per_1k"], r[f"{f}_usd_per_1k"])]
        given = causes.get((r["line"], r["provider"], r["product"]), {})
        if sorted(moved) != sorted(given):
            raise SystemExit(f"changes.csv: {r['provider']} / {r['product']} needs rows for {moved}, has {sorted(given)}")
        r["change"] = "+".join(sorted(set(given.values())))
        r["_causes"] = given
        r["_timing"] = timing.get((r["line"], r["provider"], r["product"]), {})
    unchecked = sorted({r["provider"] for r in rows if r["verification"] == "none"})
    if unchecked:
        raise SystemExit("not verified against the archive: " + ", ".join(unchecked))
    h = headlines(rows)
    by_data = sorted({r["provider"] for r in rows if r["verification"] == "data"})
    hs = headlines([r for r in rows if r["provider"] not in by_data])
    h["verification"] = {
        "providers_checked_on_archived_page": h["providers"] - len(by_data),
        "providers_checked_on_archived_data_address": by_data,
    }
    h["strict"] = {
        "excluded": by_data,
        "search": {k: hs["search"][k] for k in ("n", "median_entry", "min_entry", "min_entry_provider", "median_lowest", "subscription_only")},
        "captcha": {k: hs["captcha"][k] for k in ("n", "no_hcaptcha_price")},
    }
    h["sentences"] = sentences(h)
    h["vendors"] = vendors(rows)
    return rows, h


def min_payment(opts: list[dict], provider: dict) -> float | None:
    paid = [t for t in opts if t["billing"] in PAID]
    if not paid:
        return None
    if any(t["billing"] == "payg" for t in paid):
        return num(provider.get("min_topup_usd"))
    prices = [v for v in (num(t["price_usd"]) for t in paid) if v is not None]
    return min(prices) if prices else None


def moved_field(old: float | None, new: float | None) -> bool:
    return (old is None) != (new is None) or (old is not None and new is not None and abs(old - new) >= 0.0051)


def period0_fields(line: str, product: str, prior: dict, ev: float | None, lv: float | None) -> dict:
    if not prior:
        return {"period0_entry_usd_per_1k": None, "period0_lowest_usd_per_1k": None, "change": "new"}
    if line == "captcha" and product not in CAPTCHA_TYPES:
        # e.g. plans not tied to one CAPTCHA type: period 0 has no column for them
        return {"period0_entry_usd_per_1k": None, "period0_lowest_usd_per_1k": None, "change": "new row"}
    if line == "data" and "-" in prior.get("entry_usd_per_1k", ""):
        # period 0 kept one range across several actors or endpoints: not comparable row by row
        return {"period0_entry_usd_per_1k": None, "period0_lowest_usd_per_1k": None, "change": "not comparable"}
    if line == "captcha":
        key = {"recaptcha_v2": "v2", "recaptcha_v3": "v3"}.get(product, product)
        old = prior.get(f"{key}_usd_per_1k", "")
        lo_old, hi_old = (old.split("-") + [old])[:2] if old else ("", "")
        pe, pl = num(hi_old), num(lo_old)
    else:
        e, low = prior.get("entry_usd_per_1k", ""), prior.get("lowest_usd_per_1k", "")
        pe = num(e.split("-")[-1]) if e else None
        pl = num(low.split("-")[0]) if low else None
    same = not moved_field(pe, ev) and not moved_field(pl, lv)
    return {"period0_entry_usd_per_1k": pe, "period0_lowest_usd_per_1k": pl, "change": "same" if same else "differs"}


# ---------------------------------------------------------------- headlines

def quartiles(xs: list[float]) -> tuple[float, float]:
    q = statistics.quantiles(xs, n=4, method="inclusive")
    return q[0], q[2]


def leave_one_out(rows: list[dict]) -> dict:
    vals = [(r["provider"], r["entry_usd_per_1k"]) for r in rows]
    meds = [(name, statistics.median([v for n, v in vals if n != name])) for name, _ in vals]
    lo = min(meds, key=lambda x: x[1])
    hi = max(meds, key=lambda x: x[1])
    return {"min": round(lo[1], 4), "min_without": lo[0], "max": round(hi[1], 4), "max_without": hi[0]}


def headlines(rows: list[dict]) -> dict:
    third = [r for r in rows if not r["publisher"]]
    search = [r for r in third if r["line"] == "search" and r["entry_usd_per_1k"] is not None]
    data_p = {r["provider"]: r for r in third if r["line"] == "data"}
    cap = [r for r in third if r["line"] == "captcha"]
    cap_providers = sorted({r["provider"] for r in cap})
    entries = [r["entry_usd_per_1k"] for r in search]
    lows = [r["lowest_usd_per_1k"] for r in search if r["lowest_usd_per_1k"] is not None]
    cheapest = min(search, key=lambda r: r["entry_usd_per_1k"])
    dearest = max(search, key=lambda r: r["entry_usd_per_1k"])
    seg = {}
    for s in ("google_serp", "web_search"):
        xs = [r["entry_usd_per_1k"] for r in search if r["segment"] == s]
        if xs:
            q1, q3 = quartiles(xs) if len(xs) > 1 else (xs[0], xs[0])
            seg[s] = {"n": len(xs), "median": round(statistics.median(xs), 4), "q1": round(q1, 4), "q3": round(q3, 4)}
    hc = [r for r in cap if r["product"] == "hcaptcha"]
    per_type = {}
    for t in CAPTCHA_TYPES:
        xs = [r["entry_usd_per_1k"] for r in cap if r["product"] == t and r["entry_usd_per_1k"] is not None]
        if xs:
            per_type[t] = {"n": len(xs), "median": round(statistics.median(xs), 4)}
    providers_all = sorted({(r["line"], r["provider"]) for r in third})
    differ = sorted({(r["line"], r["provider"]) for r in third if r["change"] not in ("same", "new", "new row", "not comparable")})
    changed = sorted({r["provider"] for r in third if "price_change" in r["change"]})
    ups = [r for r in third for f, cause in r.get("_causes", {}).items() if cause == "price_change"
           and r[f"period0_{f}_usd_per_1k"] is not None and r[f"{f}_usd_per_1k"] is not None
           and r[f"{f}_usd_per_1k"] > r[f"period0_{f}_usd_per_1k"]]
    dated = [(r["provider"], t, day) for r in third for t, day in r.get("_timing", {}).values()]
    by_timing = {t: sorted({p for p, tt, _ in dated if tt == t}) for t in sorted(TIMINGS)}
    since = min((day for _, _, day in dated), default=PERIOD0)
    return {
        "edition": EDITION_LABEL, "read_date": READ_DATE_LABEL, "period0": PERIOD0,
        "providers": len(providers_all),
        "search": {
            "n": len(search), "median_entry": round(statistics.median(entries), 4),
            "q1_entry": round(quartiles(entries)[0], 4), "q3_entry": round(quartiles(entries)[1], 4),
            "min_entry": round(cheapest["entry_usd_per_1k"], 4), "min_entry_provider": cheapest["provider"],
            "min_entry_derived": cheapest["derived"],
            "max_entry": round(dearest["entry_usd_per_1k"], 4), "max_entry_provider": dearest["provider"],
            "median_lowest": round(statistics.median(lows), 4), "n_lowest": len(lows),
            "subscription_only": sum(r["subscription_only"] for r in search),
            "leave_one_out": leave_one_out(search), "segments": seg,
        },
        "data": {"n": len(data_p), "subscription_only": sum(r["subscription_only"] for r in data_p.values())},
        "captcha": {"n": len(cap_providers), "no_hcaptcha_price": sum(not r["listed"] for r in hc),
                    "no_hcaptcha_price_providers": sorted(r["provider"] for r in hc if not r["listed"]),
                    "hcaptcha_price_providers": sorted(r["provider"] for r in hc if r["listed"]),
                    "per_type": per_type},
        "differs_from_period0": len(differ), "differs_list": [f"{l}:{p}" for l, p in differ],
        "price_changes": {"n": len(changed), "providers": changed, "increases": len(ups),
                          "since": since, "since_label": day_label(since),
                          "after_previous_reading": by_timing["after"],
                          "around_previous_reading": by_timing["around"],
                          "before_previous_reading": by_timing["before"]},
    }


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
# when the change happened, compared with the previous reading (METHODOLOGY.md, section 10)
TIMINGS = {"after", "around", "before"}


def archive_date(url: str) -> str:
    """'https://web.archive.org/web/20260913155539/...' -> '2026-09-13'."""
    stamp = url.split("/web/")[1][:8]
    return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}"


def day_label(day: str) -> str:
    y, m, d = day.split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def sentences(h: dict) -> list[str]:
    s, seg = h["search"], h["search"]["segments"]
    derived = ", converted from token pricing" if s["min_entry_derived"] else ""
    out = [
        f"We re-read the public pricing pages of {h['providers']} search, scraping and CAPTCHA APIs on "
        f"{h['read_date']} and converted every price to US dollars per 1,000 calls.",
        f"The median entry price for a search API is {usd(s['median_entry'])} per 1,000 searches "
        f"({s['n']} providers; middle half {usd(s['q1_entry'])}–{usd(s['q3_entry'])}).",
        f"Entry prices run from {usd(s['min_entry'])} ({s['min_entry_provider']}{derived}) "
        f"to {usd(s['max_entry'])} ({s['max_entry_provider']}); the median of the lowest published "
        f"prices is {usd(s['median_lowest'])}.",
    ]
    if "google_serp" in seg and "web_search" in seg:
        g, w = seg["google_serp"], seg["web_search"]
        out.append(f"APIs that return Google results have a median entry price of {usd(g['median'])} "
                   f"(n = {g['n']}); web search APIs built for AI have {usd(w['median'])} (n = {w['n']}).")
    out.append(f"{s['subscription_only']} of {s['n']} search APIs and {h['data']['subscription_only']} of "
               f"{h['data']['n']} scraping and platform-data APIs can only be bought as a monthly subscription.")
    out.append(f"{h['captcha']['no_hcaptcha_price']} of {h['captcha']['n']} CAPTCHA solvers show no hCaptcha "
               f"price on their pricing page.")
    pc = h["price_changes"]
    direction = "every change was a decrease" if pc["increases"] == 0 else f"{pc['increases']} raised a price"
    start = pc["since_label"].rsplit(" ", 1)[0] if pc["since_label"][-4:] == h["read_date"][-4:] else pc["since_label"]
    out.append(f"Between {start} and {h['read_date']}, {pc['n']} of {h['providers']} providers changed an entry "
               f"or lowest price ({', '.join(pc['providers'])}); archived copies of the earlier pages confirm each "
               f"change, and {direction}.")
    return out


# ---------------------------------------------------------------- per-provider sentences

OPTION_TEXT = {"payg": "pay as you go", "prepaid": "prepaid pack", "subscription": "monthly plan"}
PLURAL = {"request": "requests", "result": "results", "record": "records", "solve": "solves"}
TYPE_NAME = {"recaptcha_v2": "reCAPTCHA v2", "recaptcha_v3": "reCAPTCHA v3", "turnstile": "Cloudflare Turnstile",
             "hcaptcha": "hCaptcha", "image": "image CAPTCHA"}
FAILED_TEXT = {"false": "The page says failed calls are not charged.",
               "true": "The page says failed calls are charged.",
               "partial": "The page says only some kinds of failed call are free of charge."}


def anchor(name: str) -> str:
    """Stable fragment id for a provider, e.g. 'Oxylabs (Google)' -> 'oxylabs-google'."""
    return "-".join("".join(ch.lower() if ch.isalnum() else " " for ch in name).split())


def differs(a: float | None, b: float | None) -> bool:
    return a is not None and b is not None and abs(a - b) >= 0.00005


def product_sentence(r: dict, several: bool) -> str:
    unit = "searches" if r["line"] == "search" else PLURAL.get(r["unit"], r["unit"] + "s")
    name = f"{r['provider']} ({r['product']})" if several else r["provider"]
    ev, lv = r["entry_usd_per_1k"], r["lowest_usd_per_1k"]
    if ev is None:
        return f"{name}: no self-serve price for this product."
    entry = [OPTION_TEXT.get(r["entry_billing"], r["entry_billing"])]
    if r["min_payment_usd"] is not None:
        entry.append(f"minimum payment {usd(r['min_payment_usd'])}")
    text = f"{name}: {usd(ev)} per 1,000 {unit} at entry ({', '.join(entry)})"
    if differs(lv, ev):
        text += f"; lowest published price {usd(lv)} ({OPTION_TEXT.get(r['lowest_billing'], r['lowest_billing'])})"
    text += "."
    if r["subscription_only"]:
        text += " Sold only as monthly plans."
    return text


def captcha_sentence(rs: list[dict]) -> str:
    name = rs[0]["provider"]
    typed = [r for r in rs if r["product"] in CAPTCHA_TYPES]
    other = [r for r in rs if r["product"] not in CAPTCHA_TYPES and r["listed"]]
    parts = []
    for r in typed:
        if r["listed"]:
            part = f"{TYPE_NAME[r['product']]} {usd(r['entry_usd_per_1k'])}"
            if differs(r["lowest_usd_per_1k"], r["entry_usd_per_1k"]):
                part += f" (lowest {usd(r['lowest_usd_per_1k'])})"
            parts.append(part)
    missing = [TYPE_NAME[r["product"]] for r in typed if not r["listed"]]
    if parts:
        text = f"{name}, per 1,000 solves at entry: " + ", ".join(parts) + "."
        if missing:
            text += " No price shown for " + ", ".join(missing) + "."
        return text
    if other:
        r = other[0]
        text = f"{name} sells plans by number of solves, not by CAPTCHA type: {usd(r['entry_usd_per_1k'])} per 1,000 solves at entry"
        if differs(r["lowest_usd_per_1k"], r["entry_usd_per_1k"]):
            text += f", lowest published price {usd(r['lowest_usd_per_1k'])}"
        return text + ". The pricing page names no CAPTCHA type."
    return f"{name}: no per-type price on the pricing page."


def vendors(rows: list[dict]) -> list[dict]:
    out, seen = [], []
    for r in rows:
        key = (r["line"], r["provider"])
        if key not in seen:
            seen.append(key)
    for line, provider in seen:
        rs = [r for r in rows if r["line"] == line and r["provider"] == provider]
        first = rs[0]
        if line == "captcha":
            said = [captcha_sentence(rs)]
        else:
            said = [product_sentence(r, len(rs) > 1) for r in rs]
        failed = FAILED_TEXT.get(str(first["failed_calls_charged"]).strip().lower())
        if failed:
            said.append(failed)
        notes = sorted({r["conversion"] for r in rs if r["conversion"]})
        in_lines = sum(1 for x in seen if x[1] == provider)
        out.append({
            "anchor": anchor(provider) + (f"-{line}" if in_lines > 1 else ""),
            "line": line, "provider": provider, "publisher": first["publisher"],
            "source_url": first["source_url"], "read_at": first["read_at"], "archive_url": first["archive_url"],
            "sentences": said, "conversion": notes,
        })
    return out


# ---------------------------------------------------------------- output

def index_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=INDEX_FIELDS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: cell(r.get(k)) for k in INDEX_FIELDS})
    return buf.getvalue()


def headline_block(h: dict) -> str:
    return "<!-- HEADLINE:START -->\n" + "\n".join(sentences(h)) + "\n<!-- HEADLINE:END -->"


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if committed outputs differ")
    args = ap.parse_args()
    rows, h = build()
    d = ROOT / "data" / EDITION
    outputs = {d / "index.csv": index_csv(rows), d / "headlines.json": json.dumps(h, indent=2, ensure_ascii=False) + "\n"}
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    a, b = text.find("<!-- HEADLINE:START -->"), text.find("<!-- HEADLINE:END -->")
    new_readme = text[:a] + headline_block(h) + text[b + len("<!-- HEADLINE:END -->"):] if a >= 0 and b > a else text
    outputs[readme] = new_readme
    if args.check:
        bad = [str(p.relative_to(ROOT)) for p, body in outputs.items() if p.read_text(encoding="utf-8") != body]
        if bad:
            print("out of date: " + ", ".join(bad) + " (run python3 recompute.py)", file=sys.stderr)
            return 1
        print("ok: outputs match the raw tables")
    else:
        for p, body in outputs.items():
            p.write_text(body, encoding="utf-8")
    print("\n".join(sentences(h)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
