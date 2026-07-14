# Hoja de ruta de ROGEX-WSP

## Principios que no cambian entre versiones

- El núcleo de **32 átomos** es estable (contrato binario de 5 bits).
- El núcleo del paquete (`rogex_wsp/`) se mantiene en **Python puro, sin
  dependencias**; las herramientas satélite (demo web, análisis de audio)
  pueden vivir aparte con las suyas.
- Ningún renderizador guarda significado propio: **una máscara nunca es el
  original**.
- Todo cambio de formato actualiza `docs/SPEC.md` + tests de ida y vuelta.

## v0.1 — Prueba de concepto ✅ (publicada)

- 32 átomos, 6 ejes emocionales, paquete simbólico, capa G generativa.
- texto→símbolo (es), símbolo→texto (es/en), símbolo→WAV, símbolo→SVG,
  símbolo↔JSON, símbolo↔binario.
- CLI `wsp`, 36 tests, SPEC normativa, ejemplos canónicos.

## v0.2 — «Signal Return»: bidireccionalidad real ✅ (publicada)

El ciclo está cerrado: las máscaras físicas vuelven al símbolo.

1. ✅ **`wsp listen archivo.wav`** — sonido→símbolo (`listen.py`).
   Envolvente RMS → autocorrelación → cuantización a ratios → emparejamiento
   por distancia de edición contra las firmas de todas las relaciones.
   El silencio se interpreta por duración: marcador de ausencia/negación
   dentro del paquete, separador entre paquetes si es largo (≥0.6 s).
2. ✅ **`wsp inspect archivo.svg`** — glifo→símbolo (`glyph_reader.py`).
   Estructura exacta desde la etiqueta de glosa; sin etiqueta, clasificación
   geométrica de formas y emoción desde el estilo del trazo.
3. ✅ **JSON Schema oficial** (`docs/schema/wsp-message.schema.json`).
4. ✅ **Más frases canónicas**: la transmisión («no tengan miedo de lo que no
   conocen»), miedo, recuerdo, ausencia, deseo, unión, separación, identidad
   («¿quién eres?») y conciencia («¿qué es real?»).
5. ✅ **Demo web** (`web/index.html`): port JS autocontenido con glifo en vivo,
   audio WebAudio, JSON, binario y autotest contra la referencia Python.

Criterio de cierre — cumplido: `encode(texto) → wav → listen(wav)` recupera
relación y signo emocional correctos en las frases canónicas
(`tests/test_signal_return.py::TestListen::test_criterio_de_cierre_v02`).
Extra: el parser de forma compacta (`compact.py`) convierte también esa
máscara en bidireccional.

## v0.3 — Más máscaras, más intérpretes

- Audio de entrada **no generado por WSP**: tolerancia a ruido, tono base
  variable, voz humana tarareando los ratios. Origen distinto de YO
  (hoy `listen` asume tono base = 1:1).
- Recuperar la **identidad del destino** en audio (hoy solo consonancia:
  OTRO/DESCONOCIDO aproximados) — quizá codificando los átomos del destino
  como arpegio rápido.

- Renderizadores nuevos: **color** (paleta emocional), **vibración**
  (patrones hápticos), **MIDI** (interoperar con instrumentos y DAWs).
- **Vectores semántico-emocionales**: proyección del paquete a un vector
  denso estable para interoperar con modelos de IA (embeddings).
- Operadores relacionales encadenados: `A causa B`, `A recuerda B`,
  mensajes con referencias entre paquetes.
- Diccionario comunitario de conceptos derivados (`concepts/` versionado),
  con firma emocional y justificación de composición.

## Ideas en órbita (sin versión asignada)

- Puente EEG/neurofeedback como render de entrada (línea Rogex Laboratories).
- Conversación WSP↔WSP entre dos agentes IA sin pasar por texto humano.
- Estudio perceptivo: ¿los humanos reconocen la emoción de los renders
  sonoros sin entrenamiento previo?
