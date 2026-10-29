# 01 · Estabilidad del bucle largo — CIERRE (Goal reanudado)

**Fecha:** 2026-09-29 23:50 PDT · **Autor:** Hermes · **Modelo:** `deepseek-v4.1-flash` (opencode-go) — sin cambios
**Ámbito:** recuperación de la sesión interrumpida `20260929_224930_8f5bb0` (tope de 90 iteraciones) y cierre del Goal de estabilidad.
**Archivos modificados en el core:** 2 (más 1 módulo nuevo). **`config.yaml` NO se tocó** (mtime 09:08, intacto).
**Estado:** `STABILITY: PASS` — con un pendiente **no bloqueante** de activación (§8.2).

---

## 1. Estado en una tabla

| Pieza del Goal | Estado | Evidencia |
|---|---|---|
| Causa raíz `x-opencode-session` en la ruta de resumen/cierre | **CORREGIDA** | §3, §6.1–§6.4 |
| Rutas OpenCode Go que añaden el header | **17 sitios, 0 sin clasificar** | auditor exit 0 (§6.1) |
| Ruta de cierre al agotar el tope | **PROBADA EN VIVO** (tope reducido 5/5) | §6.3 |
| Checkpoint preventivo antes del tope | **PROBADO EN VIVO** (pre 4/5, edge 5/5) | §6.3, §7 |
| Sesión nueva puede continuar desde el checkpoint | **PROBADA** (sesión nueva `…234719_7ca929`) | §6.5 |
| Pruebas finales | **17 offline + 4 en vivo + 2 turnos reales** | §6 |
| Backup + rollback | **LISTOS y verificados** | §9 |
| Modelos / routing / compresión / Luna / Efficiency Supervisor | **INTACTOS** | §11 |
| Activación en el proceso vivo | **PENDIENTE (reinicio)** | §8.2 |

---

## 2. Resumen en una página (versión fácil)

1. Un turno que se queda sin iteraciones necesita **una última llamada al modelo** para resumir lo hecho. Esa llamada se armaba a mano y **salía sin la cabecera `x-opencode-session`**, así que el proveedor la rechazaba con `MissingSessionID` — justo en el momento en que el turno ya no tenía presupuesto para reintentar. Resultado: el turno moría sin resumen y sin nada estructurado que otra sesión pudiera retomar.
2. **Arreglo:** el header se inyecta ahora en el **único embudo** por el que pasan los dos modos de resumen (chat y Anthropic), no en cada ruta por separado. Cualquier `api_mode` futuro hereda el arreglo.
3. **Segundo arreglo (continuidad):** *antes* de agotar el presupuesto se escribe un **checkpoint de progreso** (objetivo, hecho, pendiente, archivos, procesos, **siguiente acción exacta**) en `~/.hermes/checkpoints/progress/LATEST.md`. Una sesión nueva lo lee y continúa. No depende de que llegue la ronda 90 ni de que el resumen funcione.
4. La sesión interrumpida **ya había hecho** el barrido de rutas (17 sitios, 0 sin clasificar) y dejó backup/rollback; lo que faltaba eran **las pruebas finales**, el registro del checkpoint y este documento. Eso es lo que se hizo aquí, **sin repetir 90 rondas**: el tope se simuló con `--max-turns 5` y con un lab offline.
5. **Hallazgo nuevo de esta reanudación:** el refresco de checkpoint "de borde" (sin llamada al modelo) pisaba `LATEST.md` y borraba la "siguiente acción exacta" que había escrito el checkpoint enriquecido anterior → *el checkpoint más nuevo era el menos útil*. Corregido y verificado en vivo.

---

## 3. Causa raíz

`agent/chat_completion_helpers.py::handle_max_iterations()` pide el resumen de cierre por dos
caminos según `api_mode`:

- `_chat_summary_attempt()` → `_iteration_summary_chat_kwargs()` (**construye el body a mano**),
- `_anthropic_summary_attempt()` → `transport.build_kwargs(...)` (también a mano).

Los dos entregan sus kwargs **directo al cliente** (`client.chat.completions.create(**request)` /
`_anthropic_messages_create(api_kwargs)`), **saltándose `build_api_kwargs`**, que es donde el resto
del turno recibe `x-opencode-session` desde `agent/opencode_affinity.py`. Para OpenCode Go el relay
exige esa cabecera → `400 MissingSessionID: Request is missing x-opencode-session`.

Dos detalles que explican por qué tardó en verse:

1. **Fallaba exactamente donde no había margen**: el turno ya había gastado su presupuesto, así que
   no podía reintentar ni resumir. El error llegaba al final de un turno largo y se perdía.
2. **El barrido de rutas no podía verlo**: este sitio no es una llamada directa al SDK (pasa por
   `relay_llm.execute_current` + callback), así que el auditor de call-sites no lo marca; hace falta
   una prueba de comportamiento. La sesión interrumpida ya lo había documentado así (control
   negativo obligatorio).

Evidencia original: sesión `20260929_224930_8f5bb0`, mensaje `#74508` — la request
`iteration-summary:*` falló con `MissingSessionID` tras agotar las 90 iteraciones.

---

## 4. Qué había dejado la sesión interrumpida (y qué verifiqué de eso)

Recuperado de la sesión `20260929_224930_8f5bb0` (130 mensajes, `api_call_count=90`, sin `ended_at`):

| Dejó | Verificación de esta reanudación |
|---|---|
| `agent/chat_completion_helpers.py` parcheado | `git diff` **backup→ahora = exactamente 2 hunks** (merge del header + aviso del checkpoint). Sin restos ni escrituras parciales. |
| `agent/turn_iteration_prep.py` parcheado | `diff` backup→ahora = 2 hunks (hook nuevo + su llamada en el bucle). Sin restos. |
| `agent/progress_checkpoint.py` nuevo (785 líneas) | Módulo completo, `python -m agent.progress_checkpoint` → `self-check ok`. |
| Backup + rollback | `~/.hermes/backups/opencode-session-checkpoint-20260929-225616/` con copias `-p`, `GIT_HEAD.txt`, `git-status-before.txt` y `rollback.sh` funcional (§9). |
| Auditor de rutas (`scripts/audit_opencode_header_sites.py`) | Re-ejecutado: **exit 0**, 17 sitios, 0 sin clasificar, control negativo ya validado por esa sesión. |
| Pendiente | **Todo lo de §6**: pruebas finales del cierre, validación del checkpoint preventivo, continuación desde el checkpoint, y este documento. |

Nada quedó a medio escribir: no hay `.tmp` huérfanos, no hay archivos nuevos sin cerrar, y el
trabajo no commiteado de otras fases (agent_init, gateway/*, vision_tools) ya estaba así **antes**
(el backup lo registra en `git-status-before.txt`) — esta sesión no lo tocó.

---

## 5. Cambios aplicados (estado validado, SHA-256 en §10)

| # | Archivo | Cambio |
|---|---|---|
| 1 | `agent/chat_completion_helpers.py` | `_managed_summary_call()`: **merge de `x-opencode-session` en el embudo único** de los dos resúmenes (+ comentario de por qué). `handle_max_iterations()`: aviso en log de la ruta del checkpoint preventivo al agotar el tope. |
| 2 | `agent/turn_iteration_prep.py` | Hook `_progress_checkpoint_hook()` nuevo y su llamada en la preparación de cada iteración (no inyecta nada, no cambia control de flujo, se traga todo error). |
| 3 | `agent/progress_checkpoint.py` *(nuevo, 785 líneas)* | Checkpoint preventivo: etapas `pre`/`edge`, contenido determinista + enriquecido por el modelo, render Markdown + JSON, `LATEST`, prompt de continuación, apagable por env. |
| 4 | `agent/progress_checkpoint.py::_inherit_enriched()` *(nuevo, esta reanudación)* | El refresco de borde **hereda** `pending`/`next_action` del checkpoint enriquecido de la misma sesión en vez de degradar `LATEST.md` al texto "no determinado". Sin llamada al modelo, sin riesgo. |
| 5 | `scripts/audit_opencode_header_sites.py` *(nuevo)* | Auditor fail-closed de call-sites directos al SDK (exit 1 si algo queda sin clasificar). |
| 6 | `tests/agent/test_stability_lab.py` *(nuevo)* · `scripts/lab/live_summary_header.py` · `scripts/lab/live_limit_run.sh` *(nuevos)* | Labs reproducibles (offline y en vivo con tope reducido). |

**No se tocó:** `config.yaml`, modelos, routing, compresión, Luna, Efficiency Supervisor, ni datos de otras sesiones.

---

## 6. Pruebas realizadas

### 6.1 Barrido de rutas OpenCode Go — `scripts/audit_opencode_header_sites.py`

```
17 request sites in 6 functions — 1 merge the header, 16 pass through / out of scope, 0 unclassified.
OK: no unclassified direct provider request site.      exit=0
```
Clasificación: 1 `MERGED` (constructor compartido), 12 `PASSTHROUGH` (reenvían kwargs recibidos),
4 `NOT-AGENT` (herramientas standalone con su propio cliente). **0 sin clasificar.**

### 6.2 Lab offline — `venv/bin/python tests/agent/test_stability_lab.py` → **LAB PASS** (17/17)

`[A] ruta de cierre al tocar el tope`
- A1 chat_completions: el header llega al request **y al callback del SDK**.
- A2 anthropic_messages: mismo embudo, header presente.
- A3 OpenRouter: sin header (no-op, no rompe).
- A5 turno agotado (90): cierra **con el resumen**, no con el error.
- A5 el SDK recibe `x-opencode-session` en la request del resumen.
- A4 **control negativo**: neutralizando el merge, la misma ruta vuelve a fallar → el lab *puede* detectar el bug (sin esto, un "ok" no probaría nada).

`[B] checkpoint preventivo`
- B0 `checkpoint_dir` respeta `HERMES_HOME` · B1 zona segura del presupuesto 90 = **iteración 81** · B2 **no corta tareas normales** (50/90 → sin checkpoint) · B3 el hook del bucle real escribe el checkpoint · B4 trae los campos exigidos por el Goal · B5 pendiente + prompt de continuación · B6 no duplica en el mismo turno · B7 refresco de borde (pre→edge) · B8 apagable (`HERMES_PROGRESS_CHECKPOINT=off`) · B9 **una sesión nueva (proceso nuevo) retoma desde disco** · B10 el borde conserva la "siguiente acción".

### 6.3 Lab en vivo con tope reducido — `bash scripts/lab/live_limit_run.sh` (2 corridas)

`hermes chat --query-file … --max-turns 5 --yolo` → 5 llamadas de terminal reales y tope agotado:

```
23:46:56 progress checkpoint (pre)  → …20260929-234653-pre-20260929_234643_a57571.md
23:46:58 progress checkpoint (edge) → …20260929-234658-edge-20260929_234643_a57571.md
23:47:02 WARNING Iteration limit reached. Progress checkpoint … is at …edge….md — a new session can resume from it.
23:47:02 conversation_loop: Turn ended: reason=max_iterations_reached(5/5) api_calls=5/5 response_len=431
```
- El turno **cerró con resumen real** (`response_len=431`; en la primera corrida 191), **sin** `MissingSessionID`.
- El checkpoint preventivo se escribió **antes** del tope (4/5) y se refrescó en el borde (5/5).
- Ninguna ruta de resumen dejó error en `agent.log` (búsqueda de `MissingSessionID` en el tramo nuevo: 0 coincidencias).

### 6.4 Lab en vivo del header — `venv/bin/python scripts/lab/live_summary_header.py` → **LIVE PASS**

2 requests reales contra OpenCode Go, con el header observado en la **capa httpx** (último punto antes de la red):

```
L1 el turno agotado cierra con un resumen real (no con error)      ok
L2 el header x-opencode-session salió en la request del resumen    ok
   > 1 request(s) a opencode.ai vistas por httpx; header=lab-live-close-20260929
L3 control negativo: sin el merge el proveedor rechaza la misma request (MissingSessionID)  ok
L4 control negativo: la request salió sin header                   ok
```
Prueba directa: **el header sale de la máquina con el id de sesión**, y **sin el merge el proveedor rechaza la misma llamada**.

### 6.5 Continuidad real — sesión nueva `20260929_234719_7ca929`

Prompt: *"Retoma el trabajo desde el checkpoint… ejecuta la 'Siguiente acción exacta'"*.
La sesión nueva leyó `LATEST.md`, ejecutó **la acción exacta que indicaba el checkpoint**
(`pwd`, una sola llamada, sin agrupar) y reportó el resultado. **El mecanismo de continuación
funciona de punta a punta con un checkpoint escrito por un turno que murió en su tope.**

---

## 7. Checkpoint preventivo (diseño verificado)

- **Cuándo:** con presupuesto real de 90 → **iteración 81** (`pre`, enriquecido por el modelo) y **87** (`edge`, determinista, sin gastar presupuesto). No dispara antes (una tarea normal no se interrumpe) ni en presupuestos < 4.
- **Dónde:** `~/.hermes/checkpoints/progress/<stamp>-<pre|edge>-<sesión>.{md,json}` + `LATEST.md` / `LATEST.json` (lo que lee una sesión nueva).
- **Qué guarda (mínimos del Goal):** objetivo · petición en curso · trabajo completado · trabajo pendiente · **siguiente acción exacta** · archivos modificados · procesos activos · iteración usada/máx · sesión, modelo, `cwd`, `git HEAD` · cola del transcript · prompt de continuación listo para pegar.
- **Contrato:** corre desde el bucle, **no inyecta nada** en el transcript, **no cambia** el control de flujo, **nunca lanza** (cualquier error se registra y se traga). El núcleo determinista se escribe **en disco antes** del enriquecimiento, así la continuidad existe aunque toda llamada al modelo falle después.
- **Apagable:** `progress_checkpoint.enabled: false` en `config.yaml` o `HERMES_PROGRESS_CHECKPOINT=off` (margen: `HERMES_PROGRESS_CHECKPOINT_MARGIN`; enriquecimiento: `HERMES_PROGRESS_CHECKPOINT_ENRICH`).

---

## 8. Resultado

### 8.1 Veredicto
`STABILITY: PASS` — causa raíz corregida y probada por comportamiento (offline + en vivo, con control
negativo), barrido de rutas limpio (0 sin clasificar), ruta de cierre validada con tope reducido,
checkpoint preventivo escrito antes del tope, y una sesión nueva retomando desde el checkpoint.

### 8.2 Pendiente no bloqueante: activación
El proceso vivo `hermes serve` (**PID 1326**, arrancado **18:58**, antes del parche de las 22:59)
tiene en memoria los módulos previos: **el arreglo aplica a cualquier proceso nuevo** (CLI, turno
lanzado por el lab, cron, gateway reiniciado) y quedará activo en el proceso vivo **al reiniciarlo**.
No se reinició nada a propósito: había otras sesiones de Hermes en curso (exigencia del Jefe) y no
se toca el trabajo de otros. El propio CLI lo avisa: *"Gateways may still be serving pre-update modules"*.

---

## 9. Rollback

```bash
bash ~/.hermes/backups/opencode-session-checkpoint-20260929-225616/rollback.sh
```
Restaura los **bytes exactos previos** de `agent/chat_completion_helpers.py` y
`agent/turn_iteration_prep.py` (copias hechas con `-p`, que ya incluían las ediciones locales que
había en el árbol) y **borra** `agent/progress_checkpoint.py` (con él se va el arreglo `_inherit_enriched`).
No toca: `config.yaml` (nunca se modificó), datos de sesiones, ni `checkpoints/progress/` (datos, no código).
Deja inertes (no se cargan desde ningún import del runtime): `scripts/audit_opencode_header_sites.py`,
`tests/agent/test_stability_lab.py`, `scripts/lab/`.
`GIT_HEAD.txt` = `233757037df1f03f9fe1cfddc097acd5ad7f7510` (sin commits nuevos).

---

## 10. Evidencia reproducible y huellas

| Artefacto | SHA-256 (estado validado) |
|---|---|
| `agent/chat_completion_helpers.py` | `c0133d18f2a43ac52582d97768a62359a0ad0df3295bba9fd4de8969785ec14e` |
| `agent/turn_iteration_prep.py` | `ef92900b53742d66b4af0bd817f746655f911b159978b57bd525dbe74d69c7ba` |
| `agent/progress_checkpoint.py` | `73f922bef3ba9c0f850bca07b33349333e8d5708a58ce27294e1a5816c3321f1` |
| `agent/opencode_affinity.py` (sin cambios, referencia) | `6228025ffffb1b0f5d0d51482028b9de19378e0b193a8d9bb5f99396f5cccf97` |
| `scripts/audit_opencode_header_sites.py` | `baea7978da51d7ad81f0afcba5dc35541a4e361468655f124a4088993a6d0384` |
| `tests/agent/test_stability_lab.py` | `855de62f9124ae1e55716671afe439f3aa940eddad5e6ca0c13e0a79e0a525ff` |
| `scripts/lab/live_limit_run.sh` | `3a8afd9620ac0a2e8f6fdfa48238e720e6f378b342bf3be6e7df383ba5ffc4a7` |
| `scripts/lab/live_summary_header.py` | `779e717f47dfd242b333d9ce282a45efdb1cc3a7d1874b0f461c728a5ef5a604` |

Cómo repetir (nada de esto gasta 90 rondas):
```bash
cd ~/.hermes/hermes-agent
venv/bin/python scripts/audit_opencode_header_sites.py      # exit 0 = ninguna ruta sin clasificar
venv/bin/python tests/agent/test_stability_lab.py           # LAB PASS (offline, sin red)
venv/bin/python -m agent.progress_checkpoint                # self-check del checkpoint
venv/bin/python scripts/lab/live_summary_header.py          # 2 requests: header real + control negativo
bash scripts/lab/live_limit_run.sh                          # turno real con tope 5 (simula el 90)
```
Checkpoints de laboratorio dejados como evidencia (datos): `~/.hermes/checkpoints/progress/`
(`…234516-pre…93917f`, `…234523-edge…93917f`, `…234653-pre…a57571`, `…234658-edge…a57571`, `LATEST.*`).

---

## 11. Lo que NO se tocó y riesgos abiertos

- **Sin cambios** en modelos, routing, compresión, Luna ni Efficiency Supervisor; `config.yaml` intacto (mtime 09:08).
- **Otras sesiones intactas** (no se cerró, reanudó ni editó ninguna). El lab creó sesiones propias y desechables: `20260929_234500_93917f`, `20260929_234643_a57571`, `20260929_234719_7ca929`.
- **`pytest` no está instalado** en el venv del repo, así que las pruebas se dejaron como scripts ejecutables con `assert` (sin frameworks), no como suite pytest. Los tests pytest existentes del repo no se pudieron correr por eso.
- **Usuario de contexto:** la sesión de contexto queda desbloqueada por la aparición de este archivo; no se le hizo handoff manual (debe despertar por su propio mecanismo).

---

# Anexo — segunda verificación (sesión `20260929_235813_8587b1`)

**Nota de integración:** este archivo fue recreado desde el historial de la sesión
`20260929_234014_2f347a` tras un sobrescritura accidental por otra sesión. El `sha256` del original
restaurado coincide con el reportado (`95ebfb07…ade75f`) — **no se perdió contenido** — y se añade
este anexo. Todo lo de arriba sigue siendo el informe válido.

## A.1 Suite dirigida en pytest (12 pruebas)

```bash
cd ~/.hermes/hermes-agent
venv/bin/python -m pytest tests/agent/test_summary_headers_and_progress_checkpoint.py -q   # 12 passed
```

Cubre: header de resumen (merge / no pisar uno ya fijado / no tocar otros proveedores / request
inválido), matemática de etapas (`pre_stage_at(90, 10) == 81`), **una sola escritura por etapa con
rearme en el turno siguiente**, contrato del archivo resumible (las siete secciones), no reescritura,
budgets pequeño/ilimitado, hook que traga errores, y el enriquecimiento (JSON con cerca ```json → se
aplica; fallo del auxiliar → se conservan los campos deterministas).

## A.2 Tres defectos que encontró esa suite, y su corrección

| Defecto | Síntoma | Corrección |
|---|---|---|
| Marcas por etapa no persistían | El checkpoint de la misma etapa se reescribía en cada iteración de la zona segura (ruido de archivos) | `_marks` guarda referencia fuerte al budget del turno con chequeo de identidad, en vez de un `weakref` que caía al camino roto |
| `next_action` podía quedar vacío | Si el enriquecimiento no devolvía nada, la "siguiente acción exacta" quedaba en blanco | Fallback determinista (`Retomar y continuar: <pendiente>`), garantizado incluso sin modelo |
| Enriquecimiento fallido era silencioso | Imposible diagnosticar por qué `pending` salía "no determinado" | Línea de log con el motivo / fragmento de la respuesta del modelo |

Tras las correcciones: `progress_checkpoint self-check ok`, auditoría `exit 0`, y el turno en vivo de
A.3 completado sin errores.

## A.3 Segundo turno real que agota el cupo (corte reducido, sin 90 rondas)

```bash
HERMES_PROGRESS_CHECKPOINT_MARGIN=4 hermes chat -Q --max-turns 5 --yolo \
  -q "Llama a la herramienta terminal seis veces, una por iteración... al final dime cuántos pasos completaste."
```

- Sesión `20260929_235813_8587b1`: 5/5 iteraciones, cierre con resumen real
  ("completé 5 de 6 pasos"), **sin `MissingSessionID`**.
- Checkpoints escritos **antes** del límite: `20260929-235827-pre-…md` y `20260929-235832-edge-…md`.
- Último `MissingSessionID` en `~/.hermes/logs/agent.log`: **17:11:56** (el incidente original,
  sesión `674a5a`). Ninguno posterior al parche.

## A.4 Auditoría de sitios de request (clasificación completa)

```
17 request sites in 6 functions — 1 merge the header, 16 pass through / out of scope, 0 unclassified.
OK: no unclassified direct provider request site.
```

`MERGED` = fusiona el header; `PASSTHROUGH` = pasa por el relay (incl. `reflector`/`codex_runtime`);
`NOT-AGENT` = harness/plugin/herramienta offline con cliente y clave propios (`mini_swe_runner.py`,
`plugins/memory/mem0`, `trajectory_compressor.py`). Control negativo re-verificado: un sitio nuevo sin
header hace fallar el auditor.

## A.5 Rollback probado (byte por byte, en sandbox)

`rollback.sh` del backup `opencode-session-checkpoint-20260929-225616` respeta `HERMES_REPO`, así que
se probó sin tocar el repo real: repo de prueba con los archivos ya parcheados → script →
`cmp -s` contra el backup.

```
IDENTICO chat_completion_helpers.py (bytes restaurados = bytes de backup)
IDENTICO turn_iteration_prep.py
OK modulo eliminado            (agent/progress_checkpoint.py)
OK tests eliminados            (los dos test_* que importan ese módulo)
```

Se añadió el borrado de los test files al script: sin el módulo, esos tests fallarían y el árbol
quedaría rojo tras un rollback. El repo real no se tocó (sha256 del módulo sin cambios: `dfcfc614609c…`).

## A.6 Límite conocido (honesto)

En el turno real el modelo auxiliar no devolvió `pending` utilizable (`no determinado por el modelo`);
`completed` salió del ledger real de tools y `next_action` del fallback determinista. El
enriquecimiento es **best-effort por diseño**: el `.md`/`.json` deterministas se escriben primero, así
que el archivo de continuidad existe aunque el modelo auxiliar falle o no coopere.

---

# Anexo — auditoría final de cierre (2026-09-30)

Esta sección supersede cualquier hash o resultado anterior del documento.

- Suite dirigida obligatoria: **12/12 PASS** (`scripts/run_tests.sh tests/agent/test_summary_headers_and_progress_checkpoint.py -q`).
- Laboratorio completo de estabilidad: **17/17 PASS** (`tests/agent/test_stability_lab.py`).
- B10: **PASS**. El checkpoint `edge` conserva la acción del `pre` de la misma sesión; se corrigió el guard para reconocer explícitamente la etapa `pre`, incluso cuando la acción proviene del caso determinista del laboratorio.
- Auditoría de headers: **17 sitios, 0 sin clasificar**; todas las rutas relevantes de resumen/cierre/emergencia quedan cubiertas por el funnel con `x-opencode-session`.
- Los tres fixes tardíos siguen presentes: persistencia de marks, fallback determinista de `next_action` y presupuesto ilimitado.
- SHA-256 final de `agent/progress_checkpoint.py`: `553e9042c25eecec9bf9c7e6a66cff569e9eab4882f142ac475d62e22f0ada5e`.
- Backup/rollback usable: `~/.hermes/backups/opencode-session-checkpoint-20260929-225616/rollback.sh` pasa `bash -n`; incluye además `progress_checkpoint.py.pre-b10-fix`.
- El proceso Hermes no se reinició; el proceso residente debe reiniciarse en una ventana posterior para cargar el módulo final. No quedan watchers ni cron temporales asociados a este cambio.

**Cierre:** estabilidad validada; no requiere más intervención salvo el reinicio planificado del proceso cuando no haya otras sesiones activas.
