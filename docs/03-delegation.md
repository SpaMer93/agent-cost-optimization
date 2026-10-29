# 03 · Delegación a Luna + handoff a ChatGPT Work — CIERRE

**Fecha:** 2026-09-29 ~23:00 PDT · **Autor:** Hermes · **Modelo principal:** `deepseek-v4.1-flash` (opencode-go) — **sin cambios**
**Ámbito:** sesión 3 de la optimización. No se escribió `config.yaml` (ver *Gate*).

---

## 1. Resumen en una tabla

| Pieza | Estado | Detalle |
|---|---|---|
| Modelo principal DeepSeek | **ACTIVO, intacto** | `deepseek-v4.1-flash` @ opencode-go |
| Cuenta Luna (openai-codex) | **ACTIVA y verificada** | logueada, `gpt-5.6-luna` responde, 62 llamadas OK hoy |
| Cupo ChatGPT (Free, mensual) | **84 % disponible** | 16 % usado · resetea 2026-10-29 21:13 PDT |
| `delegation.provider/model` → Luna | **APLICADA y validada en vivo (23:55 PDT)** | gate de Sesión 2 detectado; diff de 4 líneas exactas; **hijo real en `gpt-5.6-luna`/`openai-codex`** (23:55:31 · 12.977 in / 29 out · SUCCESS · sesión `20260929_235528_6bdbe8`); backup + rollback listos |
| Auxiliares de texto → Luna | **NO mover ninguno** | veredicto medido en §4 |
| Visión (`glm-5.3-flash`) | **ACTIVA, se queda** | decisión confirmada, no se toca |
| Rutas `omniroute-renascor auto/*`, `auto/smart` | **MUERTAS, demostrado; nada apagado** | evidencia en §5 |
| Plantilla + mecanismo de handoff | **ACTIVO y probado** | skill `chatgpt-work-handoff` + `handoff.py` |
| Paquete real de ejemplo | **LISTO para pegar** | `~/handoffs/readme-linux/REQUEST.md` |

---

## 2. Gate de configuración (por qué no se aplicó el cambio)

Requisito del Jefe: no tocar `config.yaml` hasta que exista el cierre de Sesión 2.

```
$ ls ~/docs/hermes-optimization-2026-09-29/02-context-DONE.md
No such file or directory          → GATE CERRADO
$ sha256 de config.yaml antes/después de toda la sesión: 1ecec9b5f9445b89 (idéntico)
```

`apply_delegation_luna.sh --dry-run` → **exit 3, "BLOQUEADO: falta 02-context-DONE.md. Nada aplicado."**

**Puerta automática — ya disparó (y se desarmó)** (mismo patrón que la Sesión 2, sin LLM y sin ruido).
Disparó el 2026-09-29 23:55 al aparecer el marcador; el job se eliminó al cerrar, para no dejar ruido.
Volver a armarla solo si el pin se revierte:

| Pieza | Valor |
|---|---|
| Cron | `Sesion 3 delegacion Luna - puerta 02-context (silenciosa)` · id `d480a5e1a2a3` · cada 10 m · `no_agent` · 0 tokens · `deliver=all` |
| Vigilante | `~/.hermes/scripts/delegation_luna_watch.py` (selftest verde: silencio / aplica+valida+cierre / idempotente) |
| Dispara cuando | existe `02-context-DONE.md` (cierre de la Sesión 2) |
| Escribe | solo `delegation.provider` y `delegation.model`; backup previo; **exige diff de exactamente 4 líneas (2 claves) y nada más**; si no cuadra → alerta + rollback, sin dar por bueno |
| Aborta sin escribir | si `delegation.*` no está en su valor previo (`opencode-go` / `kimi-k2.7-code`): otro lo movió → revisión humana |
| Idempotente | fichero de estado `~/.hermes/state/delegation_luna_applied.json`; actúa una sola vez |
| Deja | `03-delegation-APPLIED.md` (no sobrescribe este informe) y avisa por Telegram |
| Desarmar | `cronjob_manage update job_id=d480a5e1a2a3 paused=true` |

Activación manual (si se prefiere a mano, o si la puerta alertara):

```bash
bash ~/.hermes/scripts/apply_delegation_luna.sh
# → backup en ~/.hermes/backups/config.yaml.<ts>.bak
# → hermes config set delegation.provider openai-codex
# → hermes config set delegation.model    gpt-5.6-luna
# → imprime la verificación y el ROLLBACK exacto
```

Rollback: `cp -a ~/.hermes/backups/config.yaml.<ts>.bak ~/.hermes/config.yaml`
(o `hermes config set delegation.provider opencode-go && … model kimi-k2.7-code`).

La sintaxis de los dos `config set` ya se probó en un `HERMES_HOME` desechable (`/tmp/hh`) y
escribió exactamente `delegation: {provider: openai-codex, model: gpt-5.6-luna}`.

---

## 3. Validación de la configuración actual de Luna (evidencia real)

| Comprobación | Resultado |
|---|---|
| Credencial | `hermes status` → **OpenAI Codex ✓ logged in** (`~/.hermes/auth.json`, refrescada 2026-09-29 21:12:19 PDT, source `manual:device_code`) |
| Resolución del bundle | `resolve_runtime_provider("openai-codex", "gpt-5.6-luna")` → **OK**: `api_mode=codex_responses`, `base_url=https://chatgpt.com/backend-api/codex`, token de 1682 chars |
| Uso real | `model_usage.jsonl`: **62 llamadas hoy** (`gpt-5.6-luna` 61 + `gpt-6-luna` 1), **todas SUCCESS**, 0 errores |
| Ventana de contexto | `context_length_cache.yaml`: `gpt-5.6-luna @ …/backend-api/codex = 272 000` |
| Slug NO disponible | `gpt-5.6-sol` → 2 ERROR (sin entitlement). No prometerlo. |
| Cupo | `codex_meter.py` → **Free · 84 % restante (16 % usado) · resetea 29d 22h** |
| Aislamiento | Los hijos de `delegate_task` tienen contexto propio → no rompen el cache del chat principal |

Conclusión: **Luna está sana y es apta** para recibir delegación acotada. Lo único que falta es
el pin de `delegation.*`.

### 3b. E2E del pin, en un `HERMES_HOME` aislado (no tocó la config viva)

Prueba real: se copió `config.yaml` a `/tmp/lunadeleg`, se puso ahí
`delegation.provider=openai-codex` / `delegation.model=gpt-5.6-luna`, y se corrió un agente
efímero que delegó **una** tarea trivial. Resultado, sacado de la `state.db` de ese run:

| Dato | Valor |
|---|---|
| Sesión padre | `20260929_230010_744cac` — **deepseek-v4.1-flash / opencode-go** (2 calls, 11 836 in / 272 out) |
| Sesión hija (creada por `delegate_task`) | `20260929_230016_640171` — **gpt-5.6-luna / openai-codex** |
| `billing_base_url` de la hija | `https://chatgpt.com/backend-api/codex` |
| `billing_mode` / `cost_status` | **`subscription_included` / `included`** |
| Coste de la hija | **1 API call · 7 428 in / 7 out** (`max_iterations: 12` respetado) |
| Salida | el subagente devolvió `PING-LUNA` y el padre la recibió |

O sea: **el pin funciona de punta a punta** — el padre sigue en DeepSeek, el hijo nace en Luna,
gastado del cupo de la suscripción, y la respuesta vuelve. Lo que falta es solo aplicar las dos
líneas en `config.yaml`; el mecanismo ya no está en duda. (`/tmp/lunadeleg` se borró al terminar.)

---

## 4. Veredicto: qué auxiliares de texto pueden moverse a Luna (respuesta: ninguno)

Medición que decide (skill `hermes-model-config/references/aux-task-routing.md`): 483 llamadas
auxiliares con **98,4 % de cache-hit** sobre el modelo principal → **$0,97** en total. Las tareas
auxiliares **cabalgan la conversación**: moverlas a otro proveedor rompe el cache y las
encarece ~20x, y aquí además gastarían el cupo mensual que el Jefe necesita para Work.

| Tarea auxiliar | ¿Cabalga la conversación? | ¿A Luna? | Motivo |
|---|---|---|---|
| `compression` | sí (98 % cache) | NO | rompe cache; es lo que mantiene viva la sesión larga |
| `approval` | sí + es SEGURIDAD | **NO, nunca** | frontera DeepSeek: una decisión destructiva |
| `review` / `background_review` | sí | NO | el criterio es el producto |
| `mcp` | sí (loop de agente) | NO | parte del loop |
| `triage_specifier` | no, pero calidad | NO | especificar mal envenena todo lo que sigue |
| `kanban_decomposer` | no, pero criterio | NO | descomposición = decisión agentic |
| `skills_hub` | no | opcional, **no rentable** | centavos; fragmenta el cache sin ganancia |
| `title_generation` | no | opcional, **no rentable** | centavos |
| `profile_describer` | no | opcional | volumen mínimo |
| `curator` | no (background) | NO | cura la biblioteca de skills: es juicio |
| `vision` | no (una llamada con imagen, nunca tuvo cache) | **NO — se queda `glm-5.3-flash`** | ya es la opción barata correcta (orden del Jefe, confirmada) |
| `moa_reference` / `moa_aggregator` | — | n/a | MoA no está activo |

Estado real hoy: **el único override configurado es `vision` → `opencode-go/glm-5.3-flash`**;
el resto está en `auto` (usa el principal). `auxiliary.free_only: true`. **No se cambió nada.**

El único camino por el que Luna recibe trabajo es `delegation.*` → hijos con contexto aislado.

---

## 5. Rutas muertas `omniroute-renascor auto/*` y `auto/smart` — demostración, sin apagar nada

Evidencia recogida (nada se detuvo; el servicio sigue arriba):

| Prueba | Dato |
|---|---|
| Último uso desde Hermes | `model_usage.jsonl`: **2026-09-25 23:59:47** (`auto/best-free`, y además `ERROR`). Cero llamadas en 4 días, mientras opencode-go hizo **5 557** |
| `auto/smart` (77 llamadas) | eran `route=primary` del proveedor `custom` **viejo**; último uso 25-sep. Ya no es el primario |
| Última petición servida por OmniRoute | `~/.omniroute/call_logs/2026-09-28/…00-40-10.json`: `auto/smart`, HTTP 200, provider openrouter, `apiKeyName: Hermes SpaMer93PC`, **2026-09-28T00:40:10Z**. **No existe carpeta `2026-09-29` ni `2026-09-30`** |
| ¿Quién lo consume ahora? | `ss`: **ninguna conexión** a 9443. OpenClaw usa `api.deepseek.com` directo, no 9443 |
| ¿Está en la cadena canónica? | NO. `hermes fallback list` (real) = **1. glm-5.2 (opencode-go) · 2. gpt-oss:120b-cloud (ollama-launch) · 3. qwen2.5vl:3b (ollama-launch)**. La entrada `omniroute-renascor` vive solo en el bloque legacy `fallback.chain`, y **`grep` en el código: nadie lee `fallback.chain`** (solo `fallback_providers`) |
| ¿Podría funcionar si se usara? | No: `~/.omniroute/logs` repite `PROXY_UNREACHABLE | connect ECONNREFUSED 127.0.0.1:20128` — su proxy de salida está caído |
| Coste de tenerlo vivo | **~690 MB RSS** (`omniroute v16.3.1` 572 MB + wrapper 118 MB) en una caja de 13,8 GB donde los jobs de Hermes ya murieron por OOM |

**Conclusión:** las rutas están muertas para Hermes; nada las usa y no podrían servir aunque
quisieran. **No apagué nada** (orden explícita). Si el Jefe quiere limpiar, la limpieza
preparada es, en este orden y con OK suyo:

1. `hermes config unset fallback.chain` — clave legacy, ningún lector en el código.
2. Quitar el bloque `custom_providers: omniroute-renascor` — sin tráfico, es solo la definición.
3. (`systemctl --user stop omniroute` — recupera ~690 MB. Requiere OK explícito del Jefe.)

---

## 6. Mecanismo de handoff (creado y probado)

No hay integración: Hermes **prepara**, el Jefe **pega**, ChatGPT devuelve **solo el resultado**,
Hermes **verifica**.

| Artefacto | Ruta |
|---|---|
| Skill (frontera + flujo + pitfalls) | `~/.hermes/skills/autonomous-ai-agents/chatgpt-work-handoff/SKILL.md` |
| Plantilla canónica de 6 secciones | `…/templates/handoff-request.md` |
| Constructor + validador | `…/scripts/handoff.py` (`prep` / `check` / `--selftest`) |
| Medidor de cupo | `…/scripts/codex_meter.py` |
| Paquete de ejemplo real | `~/handoffs/readme-linux/REQUEST.md` (+ `archivos/`, `manifest.json`) |

Plantilla (las 6 secciones obligatorias): **OBJETIVO · CONTEXTO MÍNIMO · ARCHIVOS (rutas + sha256
+ tamaño) · RESTRICCIONES · ENTREGABLE · VALIDACIÓN**, más una *declaración de frontera* de 4
casillas (sin credenciales / no es diagnóstico-seguridad-producción-decisión / autocontenido /
la validación la corre el receptor).

Flujo verificado:

```bash
python3 …/handoff.py prep --slug X --objetivo "…" --archivo a.py --archivo b.md \
        --entregable "salida.csv=…" --validacion "pytest -q" --outdir ~/handoffs/X
#  el Jefe pega REQUEST.md en Work  →  trae el resultado
python3 …/handoff.py check --dir ~/handoffs/X --devuelto ~/Downloads/resultado
#  exit 0 = todo dentro de ENTREGABLE ; exit 2 = rechazo (archivo fuera de alcance)
```

`--selftest` pasa: devolución legítima → OK; archivo de más (`secreto_extra.py`) → **RECHAZADO**.
Un archivo declarado que vuelve byte-idéntico se marca `SIN CAMBIOS` (sospecha de "no hizo nada").

---

## 7. Qué podemos descargar desde mañana

**A Luna (subagente, automático — cuando el gate abra):** lotes acotados y verificables.
Renombrados y refactors mecánicos **con tests**, parsers/lotes (N ítems iguales), limpieza de
texto/datasets, docstrings en bloque, changelog/README, extracción y estructuración, traducción
de documentos, triage/deduplicación.

**A Work (navegador, paquete autocontenido):** lo grande y de un tiro — un README que exige leer
20 KB, una migración de formato de un dataset completo, una traducción larga, un changelog de un
mes. Con el medidor en mano.

**Ya listo para el primer lote (ejemplo real, sin compromiso):**
`~/handoffs/readme-linux/REQUEST.md` — README.md para `~/docs/linux/` (8 archivos, sin README
propio). Se pega tal cual y su validación es contable (`grep -c '^| ' README.md` = 10).

**Se queda en DeepSeek, siempre:** diagnóstico y causa raíz, seguridad, producción, herramientas
con estado vivo (SSH/browser/docker/kanban), decisiones agentic y la verificación final.

---

## 8. Evidencia cruda (reproducible)

```bash
hermes status | grep -A3 "Auth Providers"            # OpenAI Codex ✓
hermes fallback list                                 # cadena real (sin omniroute)
hermes config get delegation                         # opencode-go / kimi-k2.7-code (sin cambios)
cd ~/.hermes/hermes-agent && venv/bin/python /tmp/probe_delegation.py   # resolución de Luna OK
cd ~/.hermes/hermes-agent && venv/bin/python …/scripts/codex_meter.py   # 84 % restante
grep -c '"model":"auto/' ~/.hermes/logs/model_usage.jsonl               # 0 desde 2026-09-26
ls ~/.omniroute/call_logs/                                              # última carpeta: 2026-09-28
sha256sum ~/.hermes/config.yaml                                       # 1ecec9b5f9445b89 (idéntico)
```
