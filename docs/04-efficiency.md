# 04 — Eficiencia real en producción: desperdicio medido y medidas (2026-09-29)

**Estado:** análisis + diseño terminado. Patch preparado, **no activado**.
**Alcance:** ventana 09:10–22:18 PDT del 2026-09-29 · 4 sesiones con `WAIT_LONG_COMMAND`
(`…785711`, `…875f79`, `…2caf1c`, `…62efbb`) + `…674a5a` (la de mayor consumo del día).
**Fuentes (todas de solo lectura):**
`~/.hermes/logs/efficiency_supervisor.jsonl` · `~/.hermes/state.db` (uri `mode=ro`) ·
`~/.hermes/logs/model_usage.jsonl` · informe del cron `9ea30c49180a/2026-09-29_22-24-44.md`.
**Reproducible:** `~/lab/efficiency-2026-09-29/` (`s1…s12`, `rounds3.json`, `test_wait_matcher_patch.py`).
**Nada activado:** sin advise, sin soft enforcement, sin tocar thresholds, modelos, routing ni compresión.

---

## 0. Resumen en una página (versión fácil)

1. **El titular de 36 esperas está inflado.** Son 36 *filas* de telemetría = **26 episodios** reales,
   y de las 54 llamadas marcadas como espera **13 (24%) no son esperas**: 8 son `write_file`/`patch`
   cuyo *contenido* menciona `sleep`/`timeout` (escribir un vigilante no es esperar) y 5 son guardas
   `timeout 12/15` (una guarda no es una espera). Con el detector corregido: **54 → 41 llamadas**.
2. **Lo que las esperas cuestan de verdad:** 28 rondas (5,7% de 490), **~1.670 s = 28 min**
   de bucle bloqueado, **2,10 M tokens** de contexto reenviado (5,8% de esas 4 sesiones),
   28 llamadas LLM (3,2% del día) y 54 tool calls. Real, medible… pero **no es el mayor agujero**.
3. **El mayor agujero es la ronda de más, no la espera.** El día llevaba **867 llamadas y 68,5 M
   tokens de input** hasta las 22:18. Una sola sesión (`674a5a`, la auto-auditoría) consumió
   **32,6 M = 47% del día**, con **110.863 tokens de input por llamada** (máx. 222.182).
   Ahí cada ronda de más cuesta **1,5×** que en el resto: es donde hay que ahorrar primero.
4. **Repetición, no dificultad:** 196 de 762 llamadas (26%) repiten firma dentro del mismo turno;
   55 relecturas del mismo fichero; el mismo `gradle test` 5 veces; 8 lecturas del mismo archivo.
   10 cierres tardíos dejan **50 de 148 rondas (34%) después del último cambio real** (≈3,7 M tok).
5. **Volcados sin filtrar:** 150 resultados > 8 kB en la ventana; dos de **51 k y 40 k caracteres**
   (12,8 k y 10 k tokens) reenviados durante **45–65 rondas posteriores** → 0,4–0,65 M tokens *cada uno*.
6. **Recomendación para mañana:** empezar por **M1+M5** (cero código: nada de `sleep`-probe, nada de
   polling; una lectura por fichero por turno) y aplicar **M6** (parche de 10 líneas del detector,
   ya preparado y con test en verde) para que la métrica no mienta. Detalle en §7.

---

## 1. Método y honestidad de las cifras

- Ronda = un *api call* del bucle con `tool_calls` en `state.db`. Las rondas se deduplicaron por
  firma `(sesión, ts, args)`: `state.db` guarda **copias de compactación** de la misma ronda
  (una sesión: **287 filas para 135 rondas únicas**), lo que infla cualquier recuento ingenuo.
- El apareo con el ledger (`model_usage.jsonl`) es **por proximidad temporal (±240 s)** dentro de la
  misma sesión: los tokens son **estimaciones**, no contabilidad exacta (el ledger marca `cost=0`).
- "36 WAIT_LONG_COMMAND" son **filas** del supervisor (evento + checkpoint del mismo episodio).
  Contando episodios (agrupando ≤30 s): **26**.
- Los `tool_s` (duración) salen del `ts` del resultado de tool; se descartó un valor imposible
  (6.363 s) por reutilización de `tool_call_id`. Cifra conservadora: **~1,4–1,7 k s**.
- Categorías de espera de §2: asignadas **a mano, ronda a ronda**, viendo el comando real, no por regex.

---

## 2. Los 36 WAIT_LONG_COMMAND, uno por uno (lo pedido)

### 2.1 Recuento real

| Vista | Valor |
|---|---|
| Filas `WAIT_LONG_COMMAND` en la ventana | **36** |
| Episodios (≤30 s agrupados) | **26** |
| Llamadas marcadas como espera (28 rondas) | **54** |
| Rondas con tool_calls en esas 4 sesiones (ventana) | 490 (5,7% son de espera) |
| De las 54: contenido de `write_file`/`patch` | **8** ← falso positivo |
| De las 54: guardas `timeout 12/15` | **5** ← no esperan |
| De las 54: `timeout ≥100 s` (bloqueo real) | 12 |
| De las 54: `sleep` de shell | 23 |
| De las 54: `process_manage poll` | 5 |

Episodios por tipo: `SLEEP_CMD` 10 · `TIMEOUT_BOUND` 9 · `FP_ESCRITURA` 7 · `POLL_GESTION` 2 ·
`SIN_RONDA` 5 (no se pudo emparejar ronda a ≤45 s: mensajes ya compactados).

### 2.2 Clasificación en las 6 categorías pedidas

| Categoría | Episodios / llamadas | Evidencia real (hora, sesión) | Veredicto |
|---|---|---|---|
| **1. Espera necesaria** (el estado no estaba listo, nada más que hacer) | 5–6 rondas | `875f79` 14:06:48 `sleep 330; pgrep rsync; tail -1 log`; 14:12:04 `sleep 300; …` (rsync de 3 h); `2caf1c` 16:29 `sleep 52; date` (ventana de reintento); `785711` 13:28 `sleep 75` / `sleep 180` + `cat *_medir.log` (benchmark TTS) | **La espera es legítima; la FORMA cuesta.** Dos rondas bloqueantes consecutivas (330 s + 300 s) dentro del bucle. |
| **2. Polling innecesario** | 2 episodios / 5 llamadas + 2 sondeos | `62efbb` 21:11:35 y 21:12:52 `process_manage poll` sobre un proceso ya registrado (había notificación); `62efbb` 21:43:05 `sleep 20; pgrep -af codex_watch.py`; `875f79` 14:30:57 `sleep 30; ps -p 69873` | **Desperdicio puro.** El proceso se había lanzado 4 s antes con `background=true, notify=true`. |
| **3. Comando bloqueante correctamente usado** | 12 llamadas `timeout ≥100 s` | `timeout 400 hermes -z …`; `timeout 280 python3 watch…`; `timeout 200 hermes -z …`; y `785711` 13:59:01 `for i in $(seq …)…` (420 s en **una** tool call) | **Correcto**: acotado, sin bucle de sondeo. Solo cabe preferir background (§3.4). |
| **4. Espera que podría pasar a background** | 6–8 rondas | vigilantes/monitores (`codex_watch.py --once`, script "prueba 2" de Hermes Face), benchmark TTS, rsync, `gradle`/tests | **Alta oportunidad.** La infra ya existe y se usó… y luego se ignoró (§3.4). |
| **5. Resoluble en UNA tool call** | 12–14 rondas | patrón `sleep N; <sondeo>`: 14:06:48, 14:12:04, 21:43:05, 13:28:23 (`sleep 75/180; cat log`), y 6 rondas `nohup … & sleep 5; cat log` | **Alta oportunidad**: es el mismo trabajo con la mitad de rondas (o con `process_manage wait` + timeout, o con `background`+notify). |
| **6. Requiere al modelo de verdad** | resto del turno | `674a5a` auditoría: 21 `vision_analyze`, 85 `patch`, decisión de qué reparar; `2caf1c`: drenaje del bridge; `785711`: interpretación del benchmark | **No automatizable** sin perder la decisión. Aquí el ahorro es de *filtrado*, no de supresión. |

**Conclusión de §2:** de las 36 filas, ~7 son falso positivo, ~5 son guardas que no esperan,
~12 son bloqueos reales y acotados, ~10 son `sleep` de shell de los que **la mitad tiene forma
evitable** (sondeo dentro de la misma ronda / polling de un proceso con notificación).
**No todo WAIT es desperdicio: el desperdicio es ~1/3 del titular.**

### 2.3 Reconciliación con los titulares del cron (verificada contra su propia aritmética)

Apliqué la fórmula de `efficiency_report.py` al mismo `efficiency_supervisor.jsonl`
(`phase='turn_end'` → `totals.*`). Reproduje **exactamente** los titulares del informe del cron:

| Titular del cron | Cómo se cuenta realmente | Reproducido / medido ronda a ronda |
|---|---|---|
| 17 sesiones · 29 turnos | distintas `session_id` · filas `turn_end` | **18 · 29 ✓** (frontera de ventana) |
| Loops: 3 (1 turno) | filas `LOOP_ALTERNATION` | 3 filas = **1 bucle real** (`2caf1c` 16:53–16:57, ~4 min) |
| Esperas: **47 episodios** (36 + 11) | **son FILAS**: `WAIT_LONG_COMMAND` + `WAIT_BG_ACTIVE` | **26 + 7 = 33 episodios reales** (agrupando ≤90–120 s); el resto son pares *evento+checkpoint* |
| 44 rondas en espera · 34 por comando | suma `totals.wait_rounds` de los 29 turnos del día | **28 rondas reales** con patrón de espera en las 4 sesiones de las 36 filas (de 490); el resto son rondas ya compactadas o turnos fuera de esas 4 sesiones |
| Contexto alto: 4 avisos, **56 rondas**, pico 98k | suma `ctx_pressure_rounds` · máx `ctx_max` | **56 ✓** (`2caf1c` 46 + `62efbb` 10) y pico **98.254 ✓** |
| Cierres tardíos: 10 | `landed_mutations ≥1` **y** `rounds_since_last_mutation_at_end ≥3` | **10 ✓**; día completo: **55 de 306 rondas (18%)** tras el último cambio |
| Turnos largos: 27 y 50 | `totals.rounds` | **27 ✓** (`875f79` 14:25) y **50 ✓** (`2caf1c` 16:00); tercero: 22 (`62efbb` 21:20) |

Totales del día (turnos cerrados): **306 rondas · 45 mutaciones · 21.870 s (6,1 h)** de bucle.

**WAIT_BG_ACTIVE (11 filas → 7 episodios):** los 7 con `background_running=1`; en **3 de 7** la señal
registra `wait_command_rounds=0` y en el de las 21:42 registra **2** (3 filas no traen el dato). Es decir:
había trabajo en segundo plano **y aun así se esperó con comandos**.
Los 7: `875f79` 13:53 · `674a5a` 14:30 y 14:35 · `2caf1c` 15:31 · `62efbb` 20:59, 21:11 y 21:42 (este con
ctx 66.723). **Es la evidencia más limpia de M1**: la capacidad de no esperar ya existía.

---

## 3. Coste real de las esperas (lo pedido, cuantificado)

| Métrica | Valor medido | Nota |
|---|---|---|
| Llamadas LLM | **28** (3,2% de las 867 del día) | 1 por ronda de espera |
| Tool calls | **54** (7,1% de las 762 de esas sesiones) | 20 de ellas son sondeos (`ps`/`pgrep`/`tail`/`cat`) |
| Tiempo | **~1.670 s ≈ 28 min** de bucle bloqueado | mayor ronda: 420 s; luego 330 s, 300 s, 121 s |
| Contexto reenviado | **2,10 M tokens** (media **74.844**/ronda) | 5,8% de los 36,3 M de esas 4 sesiones |
| Sondeos | 22 rondas sólo-lectura (4,5%) + 95 mixtas | de 490 |
| Verificaciones repetidas | **196/762 llamadas (26%)** repiten firma en el turno; **55 relecturas** del mismo path | base del "una sola verificación suficiente" |
| Y lo correcto | 12 `timeout ≥100 s` bien acotados + 1 bucle `for` que resuelve en una llamada | **no tocar** |

---

## 4. Los otros ejes pedidos

### 4.1 Los 3 loops
`LOOP_ALTERNATION` ×3 → **1 episodio real** (`2caf1c`, 16:53:28 / 16:55:11 / 16:57:03, ~4 min).
El modelo alternó `read_file(…ultimo-turno.json)` con sondas de terminal (**6 firmas alternando**, la
misma lectura 2×). Coste ≈ 6 rondas ≈ **450 k tokens**. `LOOP_REPEAT_3IN10` = 0.
→ El instrumento cuenta 3 eventos donde hubo 1 bucle; el coste real está en el **reenvío de contexto**, no en el número.

### 4.2 Los 10 cierres tardíos
10 turnos siguieron ≥3 rondas tras el último cambio real: **50 de 148 rondas (34%)**, ≈**3,7 M tokens**.
Peores: `2caf1c` 18:22 (5/8 = **62%**), `62efbb` 21:20 (10/22 = **45%**).
En `674a5a`: el mismo `gradle` **5 veces** y 8 lecturas del mismo archivo.

### 4.3 Turnos de 27 y 50 rondas
| Turno | Rondas | Dur. | ctx máx | Mutaciones | Esperas | Anatomía |
|---|---|---|---|---|---|---|
| `875f79` 14:27 | **27** | 34,5 min | 86.696 | 6 | 5 rondas / **1.070 s** | 4 esperas largas (rsync) + sondeos + verificaciones |
| `2caf1c` 15:20–16:00 | **49–50** | 40 min | ~90 k | 6 | 2 rondas | **11 relecturas duplicadas**, **27 llamadas repetidas**, 46 de las 56 rondas con presión de contexto del día |

Lectura: el turno largo **no** es largo por tarea grande, es largo por **repetición**
(leer-y-volver-a-leer, sondear-y-volver-a-sondear) con contexto de ~90 k reenviado en cada ronda.

### 4.4 Presión de contexto
**56 rondas** (2caf1c 46 + 62efbb 10); pico **98.254** tok (`62efbb` 21:40). Ninguna de esas rondas
estaba haciendo trabajo nuevo: son rondas de verificación/sondeo con el contexto ya grande.

### 4.5 El elefante: dónde se quema el día (esto no salía en el informe del cron)
| Sesión | Llamadas | input medio | máx | Total input |
|---|---|---|---|---|
| `674a5a` (auto-auditoría) | **294** | **110.863** | 222.182 | **32,6 M (47% del día)** |
| 4 sesiones con WAIT (juntas) | 449 | 74.079 | — | 32,2 M (47%) |
| Día completo (hasta 22:18) | 867 | 79.000 | — | **68,5 M** |

Y dentro de ellas, los volcados sin filtrar: **150 resultados > 8 kB**; dos de **51.145 y 40.232
caracteres** (≈12,8 k y 10 k tokens) siguieron en contexto durante **45 y 65 rondas** →
0,4–0,65 M tokens **cada uno**; el conjunto de los 10 mayores ≈ **2,3 M tokens** reenviados
(4,2 M si se cuentan las copias duplicadas de compactación).
Los tres peores son `execute_code` propio, `search_files` y `session_search` con 33–40 k caracteres.

---

## 5. Medidas propuestas, priorizadas

Orden pedido: **(1) ahorro probable de llamadas · (2) riesgo · (3) dificultad · (4) evidencia real.**

| # | Medida | Ahorro probable | Riesgo | Dificultad | Evidencia real |
|---|---|---|---|---|---|
| **M1** | **Cero `sleep`-probe y cero polling.** Si hay proceso en background: `background=true, notify=true` y esperar la notificación (o **un** `process_manage wait` con timeout ≥30 s). Nunca `sleep N; <sondeo>` en el bucle. | **14–20 llamadas/día**, 1,0–1,5 M tok, ~20–28 min | **Bajo** (convención, sin código) | **Baja** | Alta: 28 rondas, 54 llamadas, y el propio caso `875f79` 14:30:53 (lanzó con notify y aun así sondeó 4 s después) |
| **M5** | **Una lectura por fichero y por turno**; si hace falta releer, leer sólo el delta (offset) y anotar lo ya visto. Deduplicar sondeos idénticos. | **55 relecturas + 196 llamadas repetidas** | **Bajo** | **Baja** | Alta: 196/762 (26%), 11 relecturas en un turno, mismo archivo 8× |
| **M6** | **Parche del detector de esperas** (excluir `write_file`/`patch`/`memory`/`skill_manage`; exigir `timeout ≥30 s`). *Preparado, no activado.* | Llamadas: 0 (no ahorra; **deja de mentir**: 54→41, 36→~24 filas) | **Bajo** (solo telemetría; advise off) | **Muy baja** (10 líneas) | Alta: replay real 54→41 + 17 asserts en verde |
| **M3** | **Filtrado antes del contexto**: volcados con tope (head/tail + `grep`), y si el resultado pasa de ~8 kB, escribirlo a fichero y leer sólo eso. | 0,5–2 M tok/día por reenvío evitado; menos rondas de "vuelve a leer" | **Bajo** | **Baja** | Media-Alta: 150 resultados >8 kB; 51 k y 40 k chars reenviados 45–65 rondas |
| **M4** | **Una sola verificación suficiente**: tras la última mutación, **una** ronda de verificación; si verde, cerrar (no volver a comprobar lo ya comprobado). | **~40 rondas/día ≈ 3 M tok** | **Bajo** | **Baja** | Alta: 10 cierres tardíos; 50/148 rondas (34%) post-mutación; `gradle` 5× |
| **M2** | **Bloque de trabajo con `execute_code`** en fases de lectura/auditoría: un script recorre los ficheros/comandos y devuelve **un digest acotado** en vez de N rondas de `read_file`. | 30–60% de las rondas de recon (en `674a5a`: 103 rondas, 57 de una sola llamada) | **Medio** (una llamada mal construida cuesta rondas; mitigar: empezar por lecturas, no mutaciones) | **Media** | Alta: 58% de las rondas (286/490) llevan **una sola** tool call |
| **M7** | **Priorizar por tamaño de contexto**: en turnos de ~110 k (>90 k por ronda) cualquier ronda ahorrada vale 1,5×; ahí va primero el esfuerzo. | Multiplica M1–M5 | **Bajo** | **Baja** | Alta: `674a5a` 111 k medio, 47% del día |
| **M8** | **NO tocar** thresholds, modelos, routing, compresión, advise. | 0 medible sin evidencia | — | — | — |

Ahorro agregado realista si se aplican M1+M3+M4+M5: **≈6–7 M tokens/día (9–10% del día)** y
**~70–90 llamadas/día (~8–10%)**, con **cero riesgo de comportamiento** (son convenciones, no código).

---

## 6. Parche preparado (NO activado)

- Copia parcheada: `~/lab/efficiency-2026-09-29/eff_sup_patchcand.py`
- Diff: `patchs/wait-matcher.patch` (45 líneas, sobre `agent/efficiency_supervisor.py`)
- Test: `test_wait_matcher_patch.py` → **17/17 asserts PASS** y **replay de la ventana real: 54 → 41**
  llamadas contadas (fuera: 8 de contenido en `write_file`/`patch`, 5 guardas `timeout 12/15`).
- El fichero vivo **no se ha tocado**. Rollback si algún día se aplica: `git -C ~/.hermes/hermes-agent checkout agent/efficiency_supervisor.py`
  (backup previo: copia del original en `lab/efficiency-2026-09-29/`).
- Efecto esperado en el informe: `WAIT_LONG_COMMAND` 36 filas → ~24 filas (~19 episodios).
  **No cambia** el comportamiento del bucle; solo lo que se reporta.

---

## 7. Qué implementar mañana (recomendación concreta)

**Paso 1 (hoy mismo/mañana, 0 código): aprobar M1+M5+M3+M4 como reglas operativas.**
Texto propuesto para el modelo operativo (F5), 8 líneas:

```
- Si algo tarda: background=true + notify=true y seguir; NO usar sleep en el bucle.
- Prohibido `sleep N; <sondeo>`. Si hay que esperar de verdad: UNA llamada
  (`process_manage wait` con timeout) o el bucle del propio comando (`for i in $(seq …)`).
- Nunca sondear un proceso que ya tiene notificacion registrada.
- Una lectura por fichero y turno; para releer, leer solo el delta.
- Tras la ultima mutacion: UNA verificacion; si verde, cerrar.
- Volcado de logs: head/tail + grep y tope de tamano; >8 kB -> fichero + leer solo lo necesario.
- Para auditar/reconocer muchos ficheros: UN execute_code que devuelva un digest acotado.
- Contexto >90k: priorizar cerrar el turno antes de encadenar sondeos.
```

**Métrica de éxito definida antes de empezar** (para no auto-engañarse):
`SLEEP_CMD` en la telemetría → **0**; rondas de espera por turno → **≤1**;
rondas por turno en tareas de recon → **≤20**; relecturas por turno → **≤1**;
en 3 días, `WAIT_LONG_COMMAND` real (con detector corregido) **< 25%** del valor de hoy.

**Paso 2 (cuando el Jefe diga): aplicar M6** para que la métrica no mienta (ya preparado, test verde).
**Paso 3 (mañana siguiente): M2 en las sesiones tipo `674a5a`**, que es donde el 1,5× está.

---

## 8. Límites de este análisis (para no sobrevender)

- El ledger y el `state.db` son instrumentos; el apareo por proximidad introduce ±10–20% en tokens.
- Las copias de compactación inflan recuentos si no se deduplica (documentado en §1).
- "36" son filas, no episodios; y el detector cuenta guardas y contenido como esperas (§2, §6).
- Clasificación de categorías: manual, ronda a ronda; los casos límite (p. ej. `sleep 330` necesario
  pero mal formado) están contados en **una** categoría, con nota.
- No se ha medido nada posterior al 22:18; la muestra son 4 sesiones (47% del input del día).
