# Dónde se iba el dinero de mi agente de IA

Corro un agente (Hermes) contra el modelo `deepseek-v4.1-flash`. La factura venía entre 25 y 26 dólares por semana, con un techo de 30. Sabía cuánto pagaba y no tenía idea de por qué. Esto es lo que salió al medirlo: cuatro etapas, cada una con su evidencia guardada, y varias conclusiones que no me gustaron.

## Tres palabras que hay que entender primero

**Contexto.** El agente no recuerda nada entre llamadas: en cada llamada reenvía la conversación completa. A las cuarenta rondas, cada respuesta vuelve a cargar las cuarenta anteriores.

**Caché.** El proveedor cobra mucho menos por el texto que ya vio igualito. Un byte distinto al principio y la caché se rompe: ese turno se paga completo.

**Compresión.** Cuando el contexto pasa de cierto tamaño, el agente resume el historial para no crecer sin freno. Útil para que la conversación no se caiga, pero resumir cambia el texto, y cambiar el texto rompe la caché.

Con eso se entiende el resto.

## Lo que cambié

| Clave | Antes | Después |
|---|---|---|
| `compression.threshold_tokens` | 120,000 | **80,000** |
| `compression.protect_last_n` | 20 | **16** |

En palabras llanas: resumir antes y proteger menos mensajes al final. Dos claves, nada de modelo, nada de enrutamiento.

La proyección sobre el histórico decía que las lecturas de caché bajarían 13.7 %, unos 137 millones de tokens por semana. Se veía bien.

**Y salió al revés.** La factura no baja: sube entre 1.4 y 2.7 dólares por semana. Comprimir más seguido rompe la caché más seguido, y ese pedazo se paga a precio completo. Lo que sí mejora es la latencia y el tamaño del contexto. Lo escribí en el reporte de cierre en vez de esconderlo, porque una medición que solo sirve cuando confirma la hipótesis no es una medición.

## Mi primera sospecha estaba mal

Yo estaba seguro de que el dinero se iba en las esperas: comandos largos, compilaciones, cosas que dejan el agente dando vueltas. La telemetría tenía 36 filas marcadas como `WAIT_LONG_COMMAND`.

Fui a verlas una por una contra el código. Eran 26 esperas reales, no 36. Y de 54 llamadas revisadas, 13 no eran esperas: ocho eran `write_file` y `patch` cuyo *contenido* menciona `sleep` o `timeout` (escribir un vigilante no es esperar), y cinco eran guardas `timeout 12`. La métrica contaba la palabra, no el hecho.

Las esperas reales costaban 28 minutos y 2.1 millones de tokens. Reales, medibles y no eran el problema.

## El problema era la ronda de más

Un solo día tuvo 867 llamadas y 68.5 millones de tokens de entrada. Una sola sesión se llevó 32.6 millones, el 47 % del día, con 110,863 tokens de entrada por llamada. Cuando una llamada ya carga 110 mil tokens, cada ronda extra cuesta una vez y media lo que cuesta en una sesión normal.

Debajo de eso había tres patrones que se repetían:

- 196 de 762 llamadas (26 %) repetían la misma firma dentro del mismo turno, y había 55 relecturas del mismo archivo.
- 50 de 148 rondas (34 %) ocurrían después del último cambio real del turno: 3.7 millones de tokens para seguir hablando de algo ya terminado.
- 150 resultados de más de 8 kB volvían a entrar ronda tras ronda. Dos de 51 mil y 40 mil caracteres viajaron 45 y 65 rondas después de haber servido: entre 0.4 y 0.65 millones de tokens cada uno.

Ahí estaba el dinero. No en esperar, en repetir.

## Cómo lo medí

Todo sale de fuentes de solo lectura: el registro de uso del modelo, la base de estado abierta en modo lectura y los logs del supervisor. Ningún análisis pasa por un modelo de lenguaje. Si la medición la hace el mismo sistema que se está midiendo, la medición no vale.

Los precios van escritos en el script, con tarifa peak y off-peak, no un promedio inventado. Cada etapa cierra con un documento que incluye el cambio exacto, el hash de la configuración antes y después, un respaldo para volver atrás y el comando para revertir. Las etapas se prueban en un entorno aparte, con su propio directorio de trabajo: la prueba valida el script de aplicación, no la configuración viva.

## Los números, para quien quiera revisarlos

Siete días de operación real: 6,321 llamadas, 1,019 millones de tokens leídos de caché, 54.5 millones de entrada fresca, 7.34 millones de salida. Contexto por llamada: media 146 mil, mediana 93.6 mil, p95 381 mil. Costo semanal 25 a 26 dólares sobre un techo de 30.

| Etapa | Estado |
|---|---|
| 01 · Estabilidad | Cerrada |
| 02 · Reducción de contexto | Aplicada y validada |
| 03 · Delegación | Cerrada |
| 04 · Eficiencia | Análisis y diseño terminados; parche preparado, sin activar |

## Reproducir

```bash
python3 analysis/stage1_compcost.py        # costo real de cada pasada de compresión
python3 analysis/stage1_analysis.py        # tamaños de contexto y su distribución
python3 analysis/stage1_money.py           # reparto del gasto de 7 días, peak y off-peak
python3 analysis/make_chart.py             # regenera el gráfico desde la evidencia
```

`evidence/` guarda la salida cruda tal como salió, sin retocar.

## Sobre el código

Los scripts de medición van publicados para que el método se pueda repetir y verificar. La documentación es de exhibición.

© 2026 Javier Cuevas. Todos los derechos reservados. Disponible bajo licencia por contacto.
