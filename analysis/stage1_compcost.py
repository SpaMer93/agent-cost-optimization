#!/usr/bin/env python3
"""One-off: real cost of a compression pass (fresh input written at each cache break)."""
import collections, glob, json, re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
TZ = ZoneInfo("America/Tijuana")
CS = re.compile(r"context compression started: session=(\S+) messages=(\d+) tokens=~([\d,]+)")
start = (datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)).timestamp()
rows = []
for l in open("~/.hermes/logs/model_usage.jsonl"):
    if l.strip():
        r = json.loads(l)
        if r.get("ts_epoch", 0) >= start:
            rows.append(r)
bysess = collections.defaultdict(list)
for r in rows:
    bysess[r.get("session_id")].append(r)

events = []
for path in sorted(glob.glob("~/.hermes/logs/agent.log*")):
    for line in open(path, errors="replace"):
        m = CS.search(line)
        if m:
            try:
                dt = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
            except ValueError:
                continue
            if dt.timestamp() >= start:
                events.append((dt, m.group(1), int(m.group(3).replace(",", ""))))

print(f"compression events in window: {len(events)}")
fresh = []
for dt, sid, trig in events:
    near = [r for r in bysess.get(sid, [])
            if -60 <= (r["ts_epoch"] - dt.timestamp()) <= 240]
    if not near:
        continue
    near.sort(key=lambda r: r["ts_epoch"])
    # first call after the pass = the summary call; it pays the prompt as fresh input
    tot_fresh = sum(r.get("input_tokens") or 0 for r in near[:2])
    tot_cached = sum(r.get("cached_tokens") or 0 for r in near[:2])
    fresh.append((trig, tot_fresh, tot_cached, len(near)))
    print(f"  {dt:%m-%d %H:%M:%S} {sid[-12:]} trigger={trig:7,d} calls_near={len(near):2d} "
          f"first2_fresh={tot_fresh:7,d} first2_cached={tot_cached:7,d}")
if fresh:
    a_f = sum(f[1] for f in fresh) / len(fresh)
    a_c = sum(f[2] for f in fresh) / len(fresh)
    print(f"\nmatched {len(fresh)} passes: avg fresh-in first 2 calls = {a_f:,.0f} tok, cached = {a_c:,.0f} tok")
    print(f"avg trigger tokens = {sum(f[0] for f in fresh)/len(fresh):,.0f}")
    per_pass = a_f
    print(f"7d fresh input total = {sum(r.get('input_tokens') or 0 for r in rows):,}")
    print(f"7d fresh input accounted by {len(fresh)} passes x {per_pass:,.0f} = {len(fresh)*per_pass:,.0f} "
          f"({100*len(fresh)*per_pass/max(1,sum(r.get('input_tokens') or 0 for r in rows)):.1f}% of all fresh input)")
else:
    print("no events matched calls in window")
