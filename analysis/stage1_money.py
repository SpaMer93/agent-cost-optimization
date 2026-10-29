#!/usr/bin/env python3
"""7d money split for the Stage-1 decision (pricing identical to go_daily_alert.py)."""
import collections, json, os
from datetime import datetime, timedelta, timezone
TZ = timezone(timedelta(hours=-7))
PRICES = {"peak": (0.30, 1.20, 0.006), "off": (0.15, 0.60, 0.003)}
start = (datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)).timestamp()
tot = collections.Counter()
money = collections.Counter()
rows = 0
for l in open(os.path.expanduser("~/.hermes/logs/model_usage.jsonl")):
    if not l.strip():
        continue
    r = json.loads(l)
    if r.get("ts_epoch", 0) < start:
        continue
    rows += 1
    tin, tout, tc = r.get("input_tokens") or 0, r.get("output_tokens") or 0, r.get("cached_tokens") or 0
    u = datetime.fromtimestamp(r["ts_epoch"], timezone.utc)
    h = u.hour + u.minute / 60
    mode = "off" if (h >= 16.5 or h < 0.5) else "peak"
    p = PRICES[mode]
    money["in"] += tin / 1e6 * p[0]
    money["out"] += tout / 1e6 * p[1]
    money["cache"] += tc / 1e6 * p[2]
    tot["in"] += tin; tot["out"] += tout; tot["cache"] += tc
tot["calls"] = rows
print("7d:", dict(tot))
print(f"costo 7d: input=${money['in']:.2f}  output=${money['out']:.2f}  cache-read=${money['cache']:.2f}  "
      f"TOTAL=${sum(money.values()):.2f}  (cap semanal Go = $30)")
# preparado con datos reales: corre el veredicto de mañana
