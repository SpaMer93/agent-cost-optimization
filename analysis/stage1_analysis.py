#!/usr/bin/env python3
"""One-off: bands + compression-pass analysis for the Stage-1 decision (7-day window)."""
import collections, glob, json, re, sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
TZ = ZoneInfo("America/Tijuana")
USAGE = "~/.hermes/logs/model_usage.jsonl"
now = datetime.now(TZ)
start = (now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)).timestamp()
rows = [json.loads(l) for l in open(USAGE) if l.strip()]
rows = [r for r in rows if r.get("ts_epoch", 0) >= start]

bands = [(0, 20000), (20000, 40000), (40000, 80000), (80000, 120000), (120000, 200000), (200000, 10**9)]
print("band                 calls   cached_tok        fresh_in  proj_cached_after")
tot_cached = sum(r.get("cached_tokens") or 0 for r in rows)
proj_saved = 0
for lo, hi in bands:
    sel = [r for r in rows if lo <= (r.get("approx_input_tokens") or 0) < hi]
    cached = sum(r.get("cached_tokens") or 0 for r in sel)
    fin = sum(r.get("input_tokens") or 0 for r in sel)
    # shift model: context above 80k drops by 40k, floored at 80k
    proj = 0
    for r in sel:
        c = r.get("cached_tokens") or 0
        ctx = r.get("approx_input_tokens") or 0
        if ctx > 80000:
            new = max(ctx - 40000, 80000)
            proj += int(c * new / ctx)
        else:
            proj += c
    proj_saved += cached - proj
    print(f"{str(lo)+'-'+str(hi):20s} {len(sel):6d} {cached:12,d} {fin:12,d} {proj:12,d}")
print(f"\ntotal cached 7d = {tot_cached:,d}  projected after 80k = {tot_cached-proj_saved:,d}  "
      f"({100*proj_saved/max(1,tot_cached):.1f}% less)")

# compression events: repetition per session + costs
CS = re.compile(r"context compression started: session=(\S+) messages=(\d+) tokens=~([\d,]+)")
CD = re.compile(r"context compression done: session=(\S+) messages=(\d+)->(\d+) rough_tokens=~([\d,]+)")
ev = collections.defaultdict(list)
for path in sorted(glob.glob("~/.hermes/logs/agent.log*")):
    for line in open(path, errors="replace"):
        m = CS.search(line)
        if m:
            try:
                ep = datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ).timestamp()
            except ValueError:
                continue
            if ep >= start:
                ev[m.group(1)].append((line[:19], int(m.group(3).replace(",", ""))))
starts = sum(len(v) for v in ev.values())
print(f"\ncompressions 7d = {starts} over {len(ev)} sessions")
for sid, v in sorted(ev.items(), key=lambda kv: -len(kv[1]))[:6]:
    gaps = [(datetime.strptime(v[i][0], "%Y-%m-%d %H:%M:%S") - datetime.strptime(v[i-1][0], "%Y-%m-%d %H:%M:%S")).total_seconds() for i in range(1, len(v))]
    print(f"  {sid}: {len(v)} passes, triggers={[t for _, t in v][:8]}, min_gap_s={min(gaps) if gaps else '-'}")
print("compression trigger tokens: avg", int(sum(t for v in ev.values() for _, t in v)/max(1, starts)))

c = sqlite3.connect("file:~/.hermes/state.db?mode=ro", uri=True)
r = c.execute("SELECT count(*), sum(api_call_count), sum(tool_call_count), sum(COALESCE(compression_ineffective_count,0)), "
              "sum(COALESCE(rewind_count,0)), sum(COALESCE(cache_read_tokens,0)), sum(COALESCE(input_tokens,0)) "
              "FROM sessions WHERE started_at >= ?", (start,)).fetchone()
print(f"\nsessions={r[0]} api_calls={r[1]} tool_calls={r[2]} ineffective_compressions={r[3]} rewinds={r[4]} "
      f"cache_read_sessiondb={r[5]:,} input_sessiondb={r[6]:,}")
