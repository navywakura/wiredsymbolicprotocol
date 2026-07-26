# Changelog

Todos los cambios notables de ROGEX-WSP se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado sigue [SemVer](https://semver.org/lang/es/).

## [0.5.0] — «Project Hail Mary»

Módulo de contacto exótico: comunicación con un emisor cuya biología,
canal, vocabulario y sintaxis no compartimos. Elimina los cuatro
presupuestos que el protocolo arrastraba desde la v0.1, sin tocar el
núcleo congelado de 32 átomos. Especificación en
[`docs/SPEC_V0.5.md`](docs/SPEC_V0.5.md).

### Añadido

- **`multiphonic.py` — capa M polifónica.** Un acorde de voces
  simultáneas transporta un campo entero: raíz 1/1 + etiqueta de 4 bits
  (9/8 · 5/4 · 3/2 · 15/8) + carga de 5 bits (9/4 · 5/2 · 3/1 · 15/4 ·
  9/2) + paridad (5/1). Como todo en WSP, es una retícula de **ratios**:
  la misma frase a 120, 180 o 260 Hz produce el mismo símbolo. Un
  concepto derivado viaja como su composición, no como su nombre. Un
  fallo de paridad rebaja la certeza en vez de descartar el paquete.
- **`grammar.py` — sintaxis agnóstica.** Cada campo viaja con su
  etiqueta, así que el orden deja de ser estructura: para toda
  permutación de los campos, el símbolo recompuesto es el mismo. El
  orden observado se conserva en `meta.grammar.order` —es la firma
  sintáctica del hablante, no ruido— y `SyntaxProfile` lo aprende para
  **responder en la sintaxis del otro**. Trama binaria etiquetada
  (versión 0x02), compatible con la posicional 0x01.
- **`primitives_science.py` — plano científico de la capa I.** Códigos
  32..127 (el núcleo de 5 bits sigue congelado): magnitudes, operadores
  relacionales, estructura de la materia. `Dimension` es un vector de 7
  exponentes SI que se multiplica y divide —comparar magnitudes de
  distinta dimensión lanza `ValueError`, no una opinión—. `Quantity` usa
  mantisa entera binaria, independiente de la base numérica del emisor.
  **Un elemento es su número atómico**: `Element(6)` no significa
  carbono, *es* Z=6; "C" y "carbono" son máscaras humanas.
- **`discovery.py` — descubrimiento fonético (el módulo Grace).** Mide
  audio de una fuente desconocida, agrupa las firmas espectrales que se
  repiten y construye el diccionario desde cero. Las firmas son
  **invariantes a la altura** (ratios sobre su propia raíz, cuantizados
  en buckets de 30 cents): sin eso no hay diccionario posible con un
  emisor cuyo registro no controlamos. `learn_from_sequence` ata por
  alineación con contexto conocido y se niega a alinear longitudes
  distintas. La cobertura de la escucha se convierte en el eje de
  certeza.
- **CLI**: `wsp chord` (emitir/leer polifonía), `wsp calibrate`
  (descubrir firmas), `wsp map` (atar firmas a átomos), `wsp xeno`
  (decodificar audio exótico con el mapa aprendido).
- **`examples/hail_mary.py`**: el arco completo con audio real, de la
  primera emisión incomprensible a la respuesta polifónica en la
  sintaxis del interlocutor.
- 63 tests nuevos (136 en total).

### Cambiado

- El render textual conjuga según el origen del paquete: con
  `source=OTRO` habla en segunda persona («Me observas aquí»), que es el
  caso normal al escuchar a un interlocutor ajeno.
- La carga científica llega a la máscara humana: «¿Preguntas por la masa
  del carbono aquí?» en vez de perder el contenido del plano de
  extensión.

### Corregido

- Preposición duplicada en el render («respondo a» + «a ti» → «Respondo
  a ti»), y clíticos aplicados a verbos que ya traen pronombre
  («Te unes a mí» en vez de «Me te unes a»). Defectos presentes desde
  v0.1, visibles al aparecer paquetes con origen distinto de YO.
- `Element.lookup` acepta la forma `"Z=6"` además de `"C"`, `"carbono"`
  y `"6"`.

## [0.4.0] — 2026-07-14 «Third Kind»

Primer paso hacia audio ajeno al protocolo: análisis multibanda con tono
base dinámico, y el saludo de *Close Encounters* como fixture normativa.

### Añadido

- **`multiband.py`** — arquitectura de tres capas espectrales concurrentes:
  graves (20–150 Hz, contexto espacio-temporal), medios (150–1200 Hz,
  melodía de átomos) y agudos (>1200 Hz, transitorios de sincronización).
  Filtros biquad Butterworth (RBJ) escritos a mano — el núcleo sigue siendo
  stdlib pura, sin SciPy — con diezmado por banda y descarte de fantasmas
  sub-octava por solapamiento temporal.
- **Plegado de octavas**: cada frecuencia se cuantiza como clase de tono en
  [1, 2) + desplazamiento de octava. La octava es canal semántico propio:
  la caída al grave ancla el contexto (@AQUI).
- **`wsp contact señal.wav`** — reconoce el saludo de cinco tonos
  (RE–MI–DO–DO↓–SOL) con tono base en cualquier frecuencia y lo proyecta
  uno a uno sobre las cinco ranuras del paquete:
  `YO → SER(BUSCAR) → CONEXION @AHORA @AQUI` — «Existo y busco un vínculo
  aquí.» Emparejamiento por subsecuencia (tolera ≤2 tonos espurios),
  score ≥ 0.95, sin falsos positivos sobre los WAV canónicos.
- **`wsp contact --emit saludo.wav`** — emite el saludo por ratios
  (1:1 · 9:8 · 8:9 · 4:9 · 2:3), nunca por notas absolutas.
- **Concepto derivado `BUSCAR`** = DESEAR + OBSERVAR + DESCONOCIDO (capa G).
- Frase canónica nueva: «busco un vínculo aquí».

## [0.3.0] — «Resilient Matrix»

### Añadido
- Calibración dinámica de f0 desde el pulso inicial de identidad.
- Squelch RMS adaptativo y tolerancia logarítmica a vibrato/jitter.
- Capa M multi-agente con atribución `YO`/`OTRO` y `agent_id` diagnóstico.
- Burst Arpeggio microtonal con longitud, UTF-8 y checksum para destinos compuestos.
- Decodificación temporal estrecha del burst mediante banco Goertzel/STFT ligero.
- Inspección SVG topológica sin glosa y entrada de micrófono WebAudio en la demo.

### Cambiado
- `listen.py` calibra ratios por paquete en vez de asumir 220 Hz.
- La segmentación usa umbral de ruido de fondo y elimina toggles transitorios.
- Los metadatos acústicos incluyen jitter, agente y estado del burst.

### Corregido
- Falsos silencios semánticos provocados por ruido ambiente.
- Saltos de cuantización causados por pequeñas desviaciones de voz humana.
- Pérdida de identidad de destinos no genéricos en el retorno WAV.

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
