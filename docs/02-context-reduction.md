# 02 · Reduccion de contexto DeepSeek (Etapa 1: 120k/20 -> 80k/16) — CIERRE

**Fecha:** 2026-09-29 23:51 PDT · **Autor:** Hermes (Sesion 2) · **Modelo:** `deepseek-v4.1-flash` (opencode-go) — sin cambios
**Estado:** APLICADA Y VALIDADA. Este fichero cierra la Sesion 2 y abre el gate de la Sesion 3.


## 1. Cambio aplicado (solo 2 claves, nada mas)

| Clave | Antes | Despues |
|---|---|---|
| `compression.threshold_tokens` | 120000 | **80000** |
| `compression.protect_last_n` | 20 | **16** |

- Umbral efectivo resuelto con el codigo de produccion (`context_stage1_verify.py`): **80000** tok
  (contexto 1,000,000 · porcentaje 0.5 · cap 80000).
- Backup previo al cambio: `~/.hermes/config.yaml.bak-stage1-apply-20260929-235137`
- `sha256 config.yaml` antes `1ecec9b5f9445b895c08da0a383a6b1581ec182449cb8c0c9b1689fff753bc46` -> despues `d0fbd4890046708f2c20aca9ebdbc10c6cec4f9d953813fdaecce97943253eca`
- Diff (solo esas claves): `['-  protect_last_n: 20', '-  threshold_tokens: 120000', '+  protect_last_n: 16', '+  threshold_tokens: 80000']`
- No se cambio modelo, routing, Luna, ni el Efficiency Supervisor (sigue en `observe`).

## 2. Baseline medido (7 dias, 2026-09-23 00:00 -> 2026-09-29 23:53 PDT)

Snapshot limpio tomado tras aplicar (el cambio entro 23:51, asi que la ventana es baseline al 99,9 %).
Fuente: `evidencia-01-metricas-7d.txt` y `evidencia-02-bandas-costo.txt` (salida cruda, read-only, sin LLM).

```
calls=6,321 (903/dia de media; ultimos 3 dias 2,063+1,307+1,426 = 1,599/dia)
cache-read=1,019.0M   fresh-in=54.5M   out=7.34M   hit-ratio=0.9492
ctx/call: media 146.1k · p50 93.6k · p95 381.4k · max 445.4k
llamadas >80k=3,827 (7d)   >120k=2,744 (7d)
compresiones=89 pasadas · disparo medio 168.6k (min 97.4k, max 505.6k)
sesiones 102 · api_calls 4,432 · tool_calls 3,797 · messages 6,642
ineffective_compressions=0 · rewinds=0 · errores 75 (7d)
costo 7d = $26.15 de un cap semanal de $30 (input $13.83 · output $7.10 · cache-read $5.22)
```

Proyeccion del cambio (modelo: el contexto por encima de 80k baja 40k, suelo 80k):
**cache-read -13,9 % (~-137 M tok/semana)**; el gasto NO baja: mas compresiones implican mas
cache-breaks (input fresco), estimado +$1,4..2,7/semana.

Como medirlo (todo read-only, sin LLM):

```bash
python3 ~/.hermes/scripts/context_stage1_metrics.py --days 2   # tabla dia a dia + compresiones
python3 ~/.hermes/scripts/context_stage1_verify.py             # umbral efectivo (debe decir 80000/16)
cronjob 'Consumo tokens OpenCode Go (diario)' (03:00)          # $/dia y % de cada ventana Go
```

Que mirar en la primera ventana de 24 h: `>80k` y `>120k` por dia (deben bajar), `comp` (pasadas de
compresion: si se multiplican x3+, aviso), `errs`, `calls` y `$`/dia. Calidad: `ineffective_compressions`,
`rewinds`, calls/sesion y tool_calls/call en la misma tabla.

## 3. Rollback

```bash
# QUIRURGICO (preferido: no revierte cambios de otras sesiones)
~/.hermes/hermes-agent/venv/bin/hermes config set compression.threshold_tokens 120000
~/.hermes/hermes-agent/venv/bin/hermes config set compression.protect_last_n 20

# TOTAL (solo si nada mas toco config.yaml despues)
cp -p ~/.hermes/config.yaml.bak-stage1-apply-20260929-235137 ~/.hermes/config.yaml
```

## 4. Que revisar manana

1. `compresiones/dia` y `compression_ineffective_count`: si hay thrash (varias pasadas seguidas con el
   mismo contexto ~80k), bajar NO es gratis -> evaluar volver a 100k o subir `protect_last_n`.
2. `$`/ventana de 7 dias: el objetivo es no acercarse al cap de $30.
3. Llamadas/dia: este knob NO las baja (sube las auxiliares de resumen). Si el objetivo es
   1534 -> 430-470, el lever esta en otra parte (4,7 k llamadas/7d: review de memoria, titulos,
   notificaciones de background, cron) — pendiente de decidir.
4. Senales de calidad: `ineffective_compressions`, `rewinds`, errores, y continuidad en sesiones largas.
5. Decision de la Etapa 2 (60k/12): solo con estos datos en la mano.

## 5. Nota de coordinacion

`02-context-DONE.md` se creo SOLO cuando el cambio quedo aplicado y validado: es el gate que la
Sesion 3 (`apply_delegation_luna.sh`) vigila por existencia de fichero. Crearlo antes habria permitido
que la Sesion 3 escribiera `config.yaml` en desorden. El baseline `1ecec9b5f944` ya no aplica a
partir de aqui.
