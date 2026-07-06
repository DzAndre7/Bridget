# Bridget2 — Optimización de estabilidad, rapidez y producción

Bridget2 es una copia de prueba del proyecto **Pizza** (`asistente_v2`),
creada para optimizar el código sin tocar el original. Reutiliza el entorno
virtual de Pizza (`~/proyectos/Pizza/venv311`) para no duplicar 9.7 GB.

## Cómo correr las pruebas

```bash
source ~/proyectos/Pizza/venv311/bin/activate
cd ~/proyectos/Bridget2/asistente_v2
python -m pytest tests/ -q      # 43 tests (funciones puras + rutas optimizadas)
python tests/bench.py           # benchmark de las 2 rutas calientes
```

## Resultados de rapidez (benchmark reproducible)

Ambas rutas corren en **cada turno de conversación** dentro de `consultar_llama`.

| Ruta caliente | Antes | Después | Mejora |
|---|---|---|---|
| Memoria semántica (2000 recuerdos × 768 dims) | 258 ms | **2.0 ms** | **~127×** |
| Búsqueda en el cerebro (300 notas) | 61 ms | **12 ms** | **~5×** |

En conjunto, el trabajo de código propio por turno pasó de **~320 ms a ~14 ms**.
(La latencia total de una respuesta la domina la generación del LLM dolphin3:8b,
~30–40 s en esta máquina, que es independiente de estas optimizaciones.)

## Cambios aplicados

### Rapidez
1. **`memoria_semantica.py`** — la similitud coseno se vectorizó con numpy y se
   agregó un **caché en memoria** de la matriz de embeddings y sus normas,
   invalidado por `mtime`. Antes se releía y reparseaba el JSON completo
   (cientos de KB) y se recalculaban las normas en Python puro en cada turno.
2. **`cerebro.consultar_cerebro`** — ahora hace **una sola pasada** por el disco.
   Antes releía todo el vault una vez por cada palabra de la consulta, y otra
   vez más para levantar el contenido de las notas top.
3. **`brain.consultar_llama`** — `context.md` se lee una vez y se cachea, en vez
   de tocar disco en cada turno.

### Estabilidad
4. **BUG corregido en `brain.extraer_consulta_busqueda`** — con una consulta
   formada solo por palabras de comando (p. ej. `"busca google"`) la variable
   `consulta` quedaba sin asignar y lanzaba `UnboundLocalError`, que tumbaba
   `procesar_comando` entero (500 en la API). Ahora devuelve `None` de forma
   ordenada. También dejó de filtrarse el conector `"en"` en la consulta.
5. **Búsquedas blindadas** — `recordar()` y `consultar_cerebro()` se envuelven en
   `try/except` dentro de `consultar_llama`: un fallo de ollama/embeddings o un
   vault mal configurado ya no rompe la respuesta entera.
6. **Historial acotado** (`MAX_HISTORIAL = 20`) — antes `HISTORIAL_CONVERSACION`
   crecía sin límite: cada turno se hacía más lento/caro y terminaba desbordando
   la ventana de contexto.
7. **`memory.py`** — `MEMORY_FILE` pasó de ruta relativa a **absoluta** anclada a
   la raíz del proyecto. Antes apuntaba a archivos distintos según desde qué
   carpeta se lanzara (raíz en modo escritorio vs. `asistente_v2/` en modo web).

### Producción
8. **Concurrencia de audio** — `voice.generar_audio` y el endpoint `/audio`
   escriben ahora a **archivos temporales únicos** (uuid). Antes compartían un
   único `/tmp/*.wav`, así que dos requests concurrentes se pisaban el audio.
   `/speak` además borra su temporal al terminar (no llena `/tmp`).
9. **`requirements.txt`** — congelado desde el venv (no existía), para instalar
   el entorno de forma reproducible.

## Red de pruebas (43 tests)

- `test_brain_logic.py` — parsing e intención (incluye el bug corregido).
- `test_cerebro_logic.py` — nombres de archivo, construcción y clasificación de notas.
- `test_memoria_semantica.py` — correctitud de la similitud coseno.
- `test_optimizaciones.py` — equivalencia numpy, caché por mtime, ranking del
  cerebro en una pasada, blindaje de vault y tope de historial.
