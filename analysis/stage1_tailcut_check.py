#!/usr/bin/env python3
"""Check: does protect_last_n 20 -> 16 change the MAIN compression tail cut at all?
Reuses the production ContextCompressor on a synthetic transcript (no LLM, no config write)."""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.hermes/hermes-agent"))
from agent.context_compressor import ContextCompressor  # noqa: E402


def mk(n=60):
    msgs = [{"role": "system", "content": "s" * 400}]
    for i in range(n):
        msgs.append({"role": "user" if i % 2 == 0 else "assistant",
                     "content": f"msg {i} " + "x" * 3000})
    return msgs


def run(pl):
    cc = ContextCompressor(
        model="deepseek-v4.1-flash", threshold_percent=0.5, protect_first_n=3,
        protect_last_n=pl, quiet_mode=True, config_context_length=1000000,
        threshold_tokens_cap=120000,
    )
    return cc._find_tail_cut_by_tokens(mk(), head_end=3), cc.tail_token_budget


c20, c16 = run(20), run(16)
print(f"protect_last_n=20: tail_cut={c20[0]} tail_budget={c20[1]:,}")
print(f"protect_last_n=16: tail_cut={c16[0]} tail_budget={c16[1]:,}")
assert c20[0] == c16[0], f"tail cut differs: {c20[0]} vs {c16[0]}"
print("OK: el corte del tail principal es IDÉNTICO -> protect_last_n está topado a 8 mensajes en esa ruta.")
