# Changelog

Todos los cambios notables de ROGEX-WSP se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado sigue [SemVer](https://semver.org/lang/es/).

## [0.2.0] — 2026-07-14 «Signal Return»

La versión de la bidireccionalidad real: las máscaras físicas vuelven al símbolo.

### Añadido

- **`wsp listen archivo.wav`** — sonido→símbolo (`listen.py`): segmentación por
  envolvente, autocorrelación, cuantización a ratios conocidos y emparejamiento
  por distancia de edición contra las firmas de todas las relaciones. Recupera
  relación, acción anidada, cadencia (pregunta/cierre) y emoción aproximada;
  la certeza del paquete refleja la calidad del emparejamiento. Criterio de
  cierre cumplido: las frases canónicas recuperan relación y signo emocional.
- **`wsp inspect archivo.svg`** — glifo→símbolo (`glyph_reader.py`): estructura
  exacta desde la etiqueta de glosa cuando existe; sin etiqueta, clasificación
  geométrica (onda, flecha, ruptura, arco, zigzag, espiral, eco) y emoción desde
  el estilo (color, grosor, discontinuo, campo, púas, retícula).
- **Parser de forma compacta** (`compact.py`): `YO → DESEAR(COMUNICAR) → OTRO …`
  vuelve a ser símbolo; acepta `->` ASCII y emoción opcional.
- **JSON Schema oficial** (`docs/schema/wsp-message.schema.json`, draft 2020-12)
  y validador estructural sin dependencias en los tests.
- **10 frases canónicas nuevas**: la transmisión («no tengan miedo de lo que
  no conocen» → `NO_SER(TEMER) → DESCONOCIDO`, disonancia contenida con emoción
  protectora), «tengo miedo», «te recuerdo», «no estás aquí», «te deseo»,
  «estamos juntos», «adiós», «¿quién eres?», «¿qué es real?».
- **Demo web** (`web/index.html`): port JavaScript autocontenido del protocolo
  con glifo en vivo, audio WebAudio, JSON, binario y autotest contra la
  referencia Python. Sin frameworks; se abre directamente en el navegador.

### Cambiado

- El **silencio sonoro ahora se interpreta por duración**: los silencios con
  significado (negación/ausencia: NO_SER, OLVIDAR, IMPOSIBLE) son marcadores
  dentro del paquete; el separador entre paquetes pasa de 0.35 s a 0.7 s para
  que ambos sean distinguibles. `listen` usa esa distinción al emparejar.
- El render textual de `PREGUNTAR(SER) → OTRO` sin lugar pasa de «¿Estás?» a
  «¿Quién eres?» (la pregunta sin coordenada es identidad, no presencia).

## [0.1.0] — 2026-07-06

Primera versión pública: prueba de concepto completa del protocolo.

### Añadido

- **Capa I**: los 32 átomos semánticos con códigos de 5 bits (`primitives.py`).
- **Capa E**: 6 ejes emocionales continuos V A D C U B en [-1, +1] (`emotion.py`).
- **Capa S**: paquete simbólico `[ORIGEN][RELACIÓN(ACCIÓN)][DESTINO][TIEMPO][ESPACIO] + E`
  con serialización JSON, forma compacta y formato binario con cabecera `WSP` (`symbol.py`).
- **Capa G**: conceptos derivados por composición de átomos, registro abierto en
  tiempo de ejecución y *generatividad por el cable* — los mensajes transportan
  las definiciones de conceptos nuevos (`concepts.py`).
- **Capa M** (renderizadores):
  - texto español e inglés (`symbol_to_text.py`)
  - audio WAV por ratios de frecuencia, sin hercios absolutos (`audio.py`)
  - glifo SVG geométrico (`glyph.py`)
  - binario compacto autocontenido
- Intérprete español→símbolo con patrones canónicos y análisis léxico
  (`text_to_symbol.py`).
- CLI `wsp`: `atoms`, `encode`, `decode`, `audio`, `glyph`, `binary`, `demo`.
- 36 tests con `unittest` (sin dependencias externas).
- Especificación normativa v0.1 (`docs/SPEC.md`) y ejemplos canónicos en JSON.
- Documentación de proyecto: filosofía, hoja de ruta, formato binario detallado,
  galería de glifos y audio, licencia Apache-2.0, CI con GitHub Actions.

[0.2.0]: https://github.com/n4vv4r/RogexWSP/releases/tag/v0.2.0
[0.1.0]: https://github.com/n4vv4r/RogexWSP/releases/tag/v0.1.0
