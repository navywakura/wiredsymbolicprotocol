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

## v0.2 — «Signal Return»: bidireccionalidad real

El objetivo de la v0.2 es cerrar el ciclo: que las máscaras físicas vuelvan
al símbolo.

1. **`wsp listen archivo.wav`** — sonido→símbolo.
   Detección de tono base y ratios de frecuencia (autocorrelación / FFT con
   stdlib), reconstrucción aproximada del paquete: relación por ratio,
   emoción por tempo/duración/disonancia. Salida con eje de certeza bajo
   cuando la detección es ambigua (la duda es parte del protocolo).
2. **`wsp inspect archivo.svg`** — glifo→símbolo.
   Los SVG generados por WSP son estructurados: leerlos con
   `xml.etree` y reconstruir entidades (puntos/círculos), relación (onda,
   flecha, ruptura, arco, zigzag) y emoción (color, grosor, discontinuo).
3. **JSON Schema oficial** (`docs/schema/wsp-0.2.schema.json`).
   Validación estable de mensajes para implementaciones de terceros.
4. **Más frases canónicas** en el intérprete y en la SPEC:
   miedo, pregunta, recuerdo, ausencia, deseo, unión, separación, conciencia.
5. **Demo web** (`web/`): escribes «estoy aquí» y ves en vivo
   JSON + glifo + audio + binario + traducción. HTML autocontenido
   (sin frameworks) servible con `python -m http.server` o GitHub Pages.

Criterio de cierre de la v0.2: `encode(texto) → wav → listen(wav)` recupera
relación y signo emocional correctos en las 6 frases canónicas.

## v0.3 — Más máscaras, más intérpretes

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
