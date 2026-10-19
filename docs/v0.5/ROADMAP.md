# Hoja de ruta de ECHO-WSP

## Principios que no cambian entre versiones

- El núcleo de **32 átomos** es estable (contrato binario de 5 bits).
- El núcleo del paquete (`echo_wsp/v05/`) se mantiene en **Python puro, sin
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

## v0.3 — «Resilient Matrix» ✅ (publicada)

- ✅ Tolerancia a ruido y jitter de voz humana: squelch RMS adaptativo,
  tolerancia logarítmica, calibración dinámica del tono base por paquete.
- ✅ Identidad del destino en audio: ráfaga-arpegio microtonal con
  longitud, UTF-8 y checksum, decodificada por banco Goertzel.
- ✅ Atribución multi-agente (`YO`/`OTRO` + `agent_id`) y entrada de
  micrófono en la demo web.

## v0.4 — «Third Kind» ✅ (publicada)

Primer contacto con audio ajeno al protocolo (`multiband.py`):

- ✅ **Análisis multibanda** en tres capas espectrales concurrentes:
  graves (20–150 Hz → contexto espacio-temporal), medios (150–1200 Hz →
  átomos) y agudos (>1200 Hz → transitorios de sincronización). Biquads
  Butterworth a mano, diezmado por banda, descarte de fantasmas sub-octava.
- ✅ **Plegado de octavas**: clase de tono en [1, 2) + octava como canal
  semántico (la caída al grave = anclaje de contexto).
- ✅ **El saludo de contacto** (*Close Encounters*, RE–MI–DO–DO↓–SOL) como
  fixture normativa: `wsp contact` lo reconoce en cualquier tonalidad
  (f0 dinámico) y `wsp contact --emit` lo emite por ratios.

## v0.5 — «Project Hail Mary»: contacto exótico ✅ (publicada)

Elimina los presupuestos que impedían hablar con un emisor ajeno
(especificación completa en [`SPEC_V0.5.md`](SPEC_V0.5.md)):

- ✅ **Polifonía** (`multiphonic.py`): un acorde de voces simultáneas
  transporta un campo entero (etiqueta + carga + paridad), sobre una
  retícula de ratios invariante a la altura.
- ✅ **Sintaxis agnóstica** (`grammar.py`): campos autoetiquetados, orden
  libre, trama binaria 0x02, y `SyntaxProfile` para responder en la
  sintaxis del interlocutor.
- ✅ **Plano científico** (`primitives_science.py`): códigos 32..127,
  dimensiones SI con álgebra, cantidades de mantisa binaria y elementos
  identificados por su Z.
- ✅ **Descubrimiento fonético** (`discovery.py`): firmas espectrales
  invariantes a la altura, agrupamiento, atadura por contexto conocido y
  mapa persistente; la cobertura de la escucha se vuelve certeza.

Pendiente heredado de esta versión (ver §7 de la SPEC): audio orgánico
real, aprendizaje sin contexto, numerales del emisor y gramática
compuesta.

## v0.6 — Más máscaras, más intérpretes

- Renderizadores nuevos: **color** (paleta emocional), **vibración**
  (patrones hápticos), **MIDI** (interoperar con instrumentos y DAWs).
- **Vectores semántico-emocionales**: proyección del paquete a un vector
  denso estable para interoperar con modelos de IA (embeddings).
- Operadores relacionales encadenados: `A causa B`, `A recuerda B`,
  mensajes con referencias entre paquetes.
- Diccionario comunitario de conceptos derivados (`concepts/` versionado),
  con firma emocional y justificación de composición.

## Ideas en órbita (sin versión asignada)

- Puente EEG/neurofeedback como render de entrada (línea echolabs).
- Conversación WSP↔WSP entre dos agentes IA sin pasar por texto humano.
- Estudio perceptivo: ¿los humanos reconocen la emoción de los renders
  sonoros sin entrenamiento previo?
