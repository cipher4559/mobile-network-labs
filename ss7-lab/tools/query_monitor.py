#!/usr/bin/env python3
"""Rate-based detection over the mock HLR audit log.

Real SS7 firewalls and HLR fraud systems see exactly this shape of data: who
asked (source), for which subscriber (IMSI), which operation, and when. The
messages themselves are identical for a legitimate roaming partner and for an
attacker, so detection is statistical: rate per subscriber, breadth of
subscribers per source, and the mix of operations.

Usage:
  python3 tools/query_monitor.py --once
  python3 tools/query_monitor.py --once --save-baseline run/baseline.json
  python3 tools/query_monitor.py --once --baseline-file run/baseline.json
  python3 tools/query_monitor.py --follow

Exit status: 0 no finding, 1 MEDIUM, 2 HIGH (useful in CI or cron).
"""
import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict

DEFAULTS = {
    "path": "run/hlr_audit.jsonl",
    "window": 60.0,
    "warn": 6,
    "alert": 12,
    "sweep_warn": 4,
    "sweep_alert": 8,
    "distinct_ops": 3,
    "baseline_secs": 60.0,
}


def load_rows(path):
    rows = []
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "ts" in rec:
                    rows.append(rec)
    except FileNotFoundError:
        return []
    rows.sort(key=lambda r: r["ts"])
    return rows


def window_slice(rows, now, window):
    cutoff = now - window
    return [r for r in rows if r["ts"] >= cutoff]


def per_imsi(rows):
    out = defaultdict(list)
    for r in rows:
        out[r.get("imsi") or "-"].append(r)
    return out


def src_key(rec):
    """Key on the peer address, not the ephemeral port: a firewall or HLR sees
    one signalling point code / one interconnect, however many TCP flows."""
    src = rec.get("src") or "-"
    return src.rsplit(":", 1)[0] if ":" in src else src


def per_source(rows):
    out = defaultdict(list)
    for r in rows:
        out[src_key(r)].append(r)
    return out


def build_baseline(rows, window, baseline_secs):
    """Median / p95 events per IMSI per window over a quiet prefix."""
    if not rows:
        return None
    t0 = min(r["ts"] for r in rows)
    t_end = t0 + max(baseline_secs, window)
    buckets = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["ts"] > t_end:
            continue
        b = int((r["ts"] - t0) // window)
        buckets[b][r.get("imsi") or "-"] += 1
    n_buckets = (int((t_end - t0) // window)) + 1
    imsis = {r.get("imsi") or "-" for r in rows if r["ts"] <= t_end}
    per = {}
    for imsi in imsis:
        counts = [buckets[b].get(imsi, 0) for b in range(n_buckets)]
        active = [c for c in counts if c] or [0]
        per[imsi] = {
            "median": statistics.median(active),
            "p95": sorted(active)[max(0, int(round(0.95 * (len(active) - 1))))],
        }
    sweep = defaultdict(lambda: defaultdict(set))
    for r in rows:
        if r["ts"] > t_end:
            continue
        b = int((r["ts"] - t0) // window)
        sweep[b][src_key(r)].add(r.get("imsi") or "-")
    sweep_counts = [len(imsis) for imsis in (sweep[b] for b in range(n_buckets))
                    for imsis in imsis.values()]
    sweep_counts = [c for c in sweep_counts if c] or [0]
    return {
        "created": round(time.time(), 3),
        "window": window,
        "baseline_secs": baseline_secs,
        "imsis": per,
        "sweep_median": statistics.median(sweep_counts) if sweep_counts else 1,
    }


def analyse(rows, window, warn, alert, sweep_warn, sweep_alert, distinct_ops,
            baseline=None):
    if not rows:
        return {"window": window, "events": 0, "imsis": 0, "findings": []}
    now = max(r["ts"] for r in rows)
    recent = window_slice(rows, now, window)
    by_imsi = per_imsi(recent)
    findings = []

    def expected(imsi):
        if not baseline:
            return None
        return (baseline.get("imsis", {}).get(imsi) or {}).get("median")

    for imsi, rs in sorted(by_imsi.items()):
        n = len(rs)
        ops = sorted({r.get("op") for r in rs})
        sev = "HIGH" if n >= alert else ("MEDIUM" if n >= warn else None)
        exp = expected(imsi)
        if sev:
            findings.append({
                "rule": "imsi-burst", "severity": sev, "imsi": imsi,
                "count": n, "ops": ops,
                "sources": sorted({r.get("src") for r in rs}),
                "baseline_median": exp,
            })
        if n >= warn and len(ops) >= distinct_ops:
            findings.append({
                "rule": "imsi-profile", "severity": "MEDIUM", "imsi": imsi,
                "count": n, "ops": ops,
                "note": "subscriber located, profiled and authenticated in one window",
            })

    for src, rs in sorted(per_source(recent).items()):
        imsis = {r.get("imsi") or "-" for r in rs}
        sev = ("HIGH" if len(imsis) >= sweep_alert
               else "MEDIUM" if len(imsis) >= sweep_warn else None)
        if sev:
            findings.append({
                "rule": "imsi-sweep", "severity": sev, "src": src,
                "distinct_imsis": len(imsis), "count": len(rs),
                "sample": sorted(imsis)[:5],
                "baseline_median": (baseline or {}).get("sweep_median"),
            })

    order = {"HIGH": 0, "MEDIUM": 1}
    findings.sort(key=lambda f: (order[f["severity"]], f["rule"], f.get("imsi") or f.get("src")))
    return {
        "window": window,
        "now": now,
        "events": len(recent),
        "imsis": len(by_imsi),
        "sources": len(per_source(recent)),
        "findings": findings,
    }


def report(res, baseline=None):
    when = time.strftime("%H:%M:%S", time.localtime(res.get("now", time.time())))
    print("window %.0fs ending %s | events=%d imsis=%d sources=%d"
          % (res["window"], when, res["events"], res["imsis"], res.get("sources", 0)))
    if baseline:
        meds = [v["median"] for v in baseline.get("imsis", {}).values()] or [0]
        print("baseline: median %.1f events/imsi/window, sweep median %.1f imsi/source/window"
              % (statistics.median(meds), baseline.get("sweep_median", 0)))
    if not res["findings"]:
        print("result: no findings")
        return 0
    print("%-8s %-13s %-32s %s" % ("SEVERITY", "RULE", "KEY", "DETAIL"))
    for f in res["findings"]:
        key = f.get("imsi") or f.get("src")
        if f["rule"] == "imsi-sweep":
            detail = "%d distinct IMSIs, %d ops, sample %s" % (
                f["distinct_imsis"], f["count"], ",".join(f["sample"]))
            if f.get("baseline_median") is not None:
                detail += " (baseline %s)" % f["baseline_median"]
        else:
            detail = "%d ops in %.0fs: %s" % (f["count"], res["window"],
                                              ",".join(str(o) for o in f["ops"]))
            if f.get("baseline_median") is not None:
                detail += " (baseline %s/window)" % f["baseline_median"]
        print("%-8s %-13s %-32s %s" % (f["severity"], f["rule"], key, detail))
    return 2 if any(f["severity"] == "HIGH" for f in res["findings"]) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", default=DEFAULTS["path"])
    ap.add_argument("--window", type=float, default=DEFAULTS["window"])
    ap.add_argument("--warn", type=int, default=DEFAULTS["warn"])
    ap.add_argument("--alert", type=int, default=DEFAULTS["alert"])
    ap.add_argument("--sweep-warn", type=int, default=DEFAULTS["sweep_warn"])
    ap.add_argument("--sweep-alert", type=int, default=DEFAULTS["sweep_alert"])
    ap.add_argument("--distinct-ops", type=int, default=DEFAULTS["distinct_ops"])
    ap.add_argument("--baseline-secs", type=float, default=DEFAULTS["baseline_secs"])
    ap.add_argument("--save-baseline", metavar="PATH")
    ap.add_argument("--baseline-file", metavar="PATH")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    baseline = None
    if args.baseline_file:
        try:
            with open(args.baseline_file) as fh:
                baseline = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            print("warning: cannot read baseline: %s" % e, file=sys.stderr)

    if args.save_baseline:
        rows = load_rows(args.path)
        bl = build_baseline(rows, args.window, args.baseline_secs)
        if not bl:
            print("warning: audit log empty, nothing to learn", file=sys.stderr)
        else:
            with open(args.save_baseline, "w") as fh:
                json.dump(bl, fh, indent=2, sort_keys=True)
            print("baseline saved to %s (%d imsi(s), sweep median %s)"
                  % (args.save_baseline, len(bl["imsis"]), bl["sweep_median"]))
            baseline = bl

    if args.follow:
        seen = {}
        try:
            while True:
                rows = load_rows(args.path)
                res = analyse(rows, args.window, args.warn, args.alert,
                              args.sweep_warn, args.sweep_alert,
                              args.distinct_ops, baseline)
                for f in res["findings"]:
                    key = (f["rule"], f.get("imsi") or f.get("src"))
                    if time.time() - seen.get(key, 0) < 15:
                        continue
                    seen[key] = time.time()
                    print("[%s] %s %s %s" % (time.strftime("%H:%M:%S"),
                                             f["severity"], f["rule"],
                                             f.get("imsi") or f.get("src")))
                time.sleep(1.0)
        except KeyboardInterrupt:
            return 0

    rows = load_rows(args.path)
    res = analyse(rows, args.window, args.warn, args.alert,
                  args.sweep_warn, args.sweep_alert, args.distinct_ops, baseline)
    if args.json:
        print(json.dumps({"baseline": baseline, **res}, indent=2, sort_keys=True))
        return 2 if any(f["severity"] == "HIGH" for f in res["findings"]) else (
            1 if res["findings"] else 0)
    return report(res, baseline)


if __name__ == "__main__":
    sys.exit(main())
