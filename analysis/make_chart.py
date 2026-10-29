#!/usr/bin/env python3
"""Genera media/context-bands.svg desde evidence/evidencia-02-bandas-costo.txt.

Sin dependencias: parsea la tabla de bandas de contexto y dibuja, por banda,
el cache-read observado frente al proyectado tras bajar el umbral a 80k.
Uso:  python3 analysis/make_chart.py
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "evidence", "evidencia-02-bandas-costo.txt")
OUT = os.path.join(ROOT, "media", "context-bands.svg")

ROW = re.compile(r"^(\d+)-(\d+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$")


def parse(path=SRC):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = ROW.match(line.strip())
            if m:
                lo, hi, calls, cached, fresh, after = m.groups()
                rows.append((int(lo), int(calls.replace(",", "")),
                             int(cached.replace(",", "")), int(after.replace(",", ""))))
    return rows


def svg(rows, width=900):
    pad_l, pad_r, top, bh, gap = 130, 40, 64, 20, 14
    height = top + len(rows) * (bh + gap) + 48
    peak = max(max(c, a) for _, _, c, a in rows)
    span = width - pad_l - pad_r - 130  # reserva para la etiqueta de la barra más larga
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" font-family="ui-sans-serif,system-ui,sans-serif">',
           '<rect width="100%" height="100%" fill="#0d1117"/>',
           f'<text x="{pad_l}" y="26" fill="#e6edf3" font-size="15" font-weight="600">'
           'Cache-read por banda de contexto (7 días)</text>',
           f'<text x="{pad_l}" y="46" fill="#8b949e" font-size="11">'
           'barra clara = observado · barra oscura = proyectado con umbral 80k</text>']
    for i, (lo, calls, cached, after) in enumerate(rows):
        y = top + i * (bh + gap)
        label = f"{lo // 1000}k+" if lo else "&lt;20k"
        out.append(f'<text x="{pad_l - 12}" y="{y + bh - 5}" fill="#8b949e" font-size="11" '
                   f'text-anchor="end">{label}</text>')
        w1 = max(1, cached / peak * span)
        w2 = max(1, after / peak * span)
        out.append(f'<rect x="{pad_l}" y="{y}" width="{w1:.1f}" height="{bh}" fill="#2f81f7" rx="3"/>')
        out.append(f'<rect x="{pad_l}" y="{y + bh - 5}" width="{w2:.1f}" height="5" fill="#1f6feb" rx="2"/>')
        out.append(f'<text x="{pad_l + w1 + 8}" y="{y + bh - 5}" fill="#8b949e" font-size="10">'
                   f'{cached / 1e6:.0f}M tok · {calls} llamadas</text>')
    out.append('</svg>')
    return "\n".join(out)


def demo():
    rows = parse()
    assert len(rows) >= 4, f"esperaba >=4 bandas, encontré {len(rows)}"
    tot = sum(c for _, _, c, _ in rows)
    proj = sum(a for _, _, _, a in rows)
    assert proj < tot, "la proyección debe ser menor que el observado"
    saving = (1 - proj / tot) * 100
    assert 5 < saving < 30, f"ahorro fuera de rango razonable: {saving:.1f}%"
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg(rows))
    print(f"bandas={len(rows)} observado={tot/1e6:.0f}M proyectado={proj/1e6:.0f}M "
          f"ahorro={saving:.1f}% -> {OUT}")


if __name__ == "__main__":
    demo()
