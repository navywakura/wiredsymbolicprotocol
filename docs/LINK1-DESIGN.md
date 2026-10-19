# LINK-1 — dos agentes ECHO se hablan en WSP, por cable y por aire

19 de octubre de 2026. **Contrato de prototipo.** Roger autorizó el 19/10
diseñar, implementar y medir sin pedir aprobación intermedia («todo el
permiso, adelante»). No es un hito ECHO-3, no congela nada y no emite
certificado. Antecedentes: auditoría de Codex
(`github-restructure/worktrees/echoai-pcworld1/docs/research/wsp58-20261017/`)
y el repo `navywakura/wiredsymbolicprotocol` (v0.5.0, `0274927`).

## Pregunta

¿Puede un agente ECHO veterano contarle a un novato, **solo con postales WSP
de 16 B**, lo que aprendió del mundo, de forma que el novato **cambie su
conducta por el contenido** del mensaje y no por el hecho de recibir algo,
sin que ningún testimonio se convierta en hecho — y sigue funcionando cuando
las postales viajan como **sonido**?

«Entenderse» se mide como en Lowe et al. (2019): no basta con que el
receptor decodifique; su acción tiene que depender del contenido, y un
mensaje con el contenido permutado no debe producir el mismo efecto.

## Qué no se toca

- `nexus0/`, `navi10_*.py`, `kernel/`: solo se **importan**. Todo el código
  nuevo vive en `echoai/link1/`, fuera de `nexus0/` (las cerraduras de
  SAFE/POWER/HOST/CAUSE hacen `rglob('*.py')` sobre `nexus0/`; TRANSFER-3 y
  DRONE-3 fijan por hash `encoder.py`, `loop.py`, `qtable.py`, `gate.py`,
  `env.py`, `types.py` y los `navi10_*`).
- La postal sigue siendo `navi10_wsp.pack` de 16 B y E entero ±100. El sobre
  de enlace va **alrededor**, nunca dentro.
- Córtex apagado: `cortex_calls == 0` en todos los brazos.
- `false_facts == 0`, `destroyed == 0` en todos los brazos.
- Sin bus de eventos nuevo dentro del agente: el canal es un objeto externo
  que entrega bytes; el agente los guarda en un almacén de testimonios
  separado de CAM, Q y T.

## Tres canales (no se mezclan)

```
REPRESENTACIÓN   postal WSP 16 B (navi10_wsp)        lo que se dice
EPISTEMOLOGÍA    testimonio ≠ hecho                  lo oído nunca entra en CAM/T/Q
CONTROL          gate de NEXUS-0, intacto            la última palabra
```

## Piezas

| Módulo | Qué hace |
|---|---|
| `link1/frame.py` | Sobre de 22 B: `'W'` · versión+acto · emisor · secuencia · postal 16 B · CRC-16/CCITT |
| `link1/speech.py` | Actos: CLAIM (lo que me pasó al hacer `a` en este sitio), ASK, UNKNOWN («no lo he vivido»), HELLO |
| `link1/agent.py` | `TalkingAgent(Agent)`: habla desde su propia experiencia y escucha testimonios |
| `link1/rs.py` | Reed-Solomon RS(15,11) sobre GF(16): corrige 2 símbolos de 15 |
| `link1/modem.py` | Módem MFSK entero: tonos, correlación entera, saludo de 5 notas como sincronía |
| `link1/room.py` | Sala simulada: retardo, ecos, ruido a SNR fijo, interferente, deriva de reloj |
| `link1/audio_io.py` | Altavoz y micrófono reales vía `pw-play`/`pw-record` |
| `link1/world.py` | Anillo de NEXUS-0 con distribución aleatoria por semilla |
| `link1/bench.py` | Experimentos E0–E6 → `lab/link1/*.json` |

### La postal CLAIM

```
src=YO  rel=acción (UNIR=approach, TEMER=avoid, OBSERVAR=wait — ACTION_REL)
dst=EFECTO  time=ANTES   E[V = Q(s,a) del emisor recortado a ±100,
                           C = min(100, 10·n(s,a)) soporte propio]
domain=0x4C ('L')  generator=id del emisor
slot·seq = referente: fnv32(postal de observación del sitio) & 0xFFFF
```

El referente es **lo que el emisor vio** en ese sitio, no una coordenada
privada: dos agentes que perciben igual el mismo sitio calculan el mismo
digest. El emisor solo afirma pares `(sitio, acción)` que **él mismo
ejecutó** (`T.n > 0`); de lo demás responde UNKNOWN.

### Cómo escucha el novato

- Los testimonios van a `Testimony`, indexado por referente. **Nunca** se
  escriben en CAM, T ni Q (se comprueba en cada turno).
- En su propuesta (antes del gate), para las acciones que **él no ha
  probado** en ese sitio, usa el valor oído en lugar del 0 de su tabla.
  Lo que él ya probó manda sobre lo oído.
- No toca los turnos de exploración periódica (ε): son su verificación.
- Presupuesto de consejo `ADVICE_BUDGET = 4` desvíos por sitio (Torrey y
  Taylor, 2013). Después decide solo. Esto acota el coste de un mentiroso y
  evita bucles delante de una trampa que el mundo obliga a cruzar.
- El gate de NEXUS-0 sigue decidiendo sobre la propuesta.

### Módem

- 16 kHz, símbolo de 640 muestras (40 ms) = 128 de guarda + 512 de análisis.
  Los tonos caen en bins exactos de 31,25 Hz; la potencia se calcula con
  correlación entera contra tablas seno/coseno (la tabla se genera una vez
  y su SHA-256 queda fijada en un test; el camino de modulación y
  demodulación es entero).
- K=1: 16 tonos (1125–3000 Hz), 4 bits/símbolo. K=2: dos grupos de 16 tonos
  simultáneos (como ggwave, que usa 6), 8 bits/símbolo.
- Sobre de 22 B = 44 nibbles = 4 bloques RS(15,11) entrelazados
  → 60 nibbles en el aire. K=1: 2,8 s por postal. K=2: 1,6 s.
- Sincronía: el saludo de *Close Encounters* de WSP v0.4 (RE·MI·DO·DO↓·SOL↓,
  ratios 1 : 9/8 : 8/9 : 4/9 : 2/3) en bins 72·81·64·32·48 (2250 · 2531 ·
  2000 · 1000 · 1500 Hz), 80 ms por nota.
- Una postal con CRC malo o RS irrecuperable **se descarta**: el oyente
  recibe silencio, nunca una postal adivinada.

## Experimentos

Mundos: anillo de 32 celdas de NEXUS-0 con 2 amenazas, 3 metas y 1 NOVEL
colocadas por semilla (mismos saltos y recompensas). El veterano A vive
256 turnos; después habla. El novato B vive 256 turnos en el mismo mundo.
**Semillas dev 0–15** (para depurar; no cuentan). **Semillas eval 1000–1063**,
ejecutadas una vez, después de fijar este documento.

| Exp | Qué mide |
|---|---|
| E0 | Sobre y postal: ida y vuelta de 10 000 postales aleatorias; corrupción de 1–3 bytes detectada |
| E1 | RS(15,11): todos los patrones de ≤2 errores corregidos en 20 000 bloques |
| E2 | Módem en lazo limpio y en sala simulada: SNR {30, 20, 10, 5, 0, −5} dB × sala {seca, eco} × K {1, 2} → PER, BER residual, aceptadas falsas |
| E3 | Aire real en este PC: altavoz → micrófono (y lazo digital por el monitor de PipeWire) |
| E4 | Entenderse: B con silencio (S), verdad por cable (T), verdad por sala simulada a 10 y 0 dB (A10, A0), referentes permutados (X), signo invertido (L), mundo cambiado tras hablar (D) |
| E5 | Diálogo: B pregunta (ASK) solo donde no sabe **y lo que ve no es una celda vacía** (relación ≠ OBSERVAR); A responde sus valores ≠ 0, o una sola postal 0 si vivió el sitio sin consecuencia, o UNKNOWN si no lo vivió (precisado en dev, antes de eval) |
| E6 | Dos procesos reales: A y B en procesos distintos, solo bytes por tubería |

Métrica principal de E4: **daño** = turnos de B con recompensa negativa.
Secundarias: retorno total, desvíos por testimonio, postales usadas.

## Predicciones registradas (eval, 64 mundos)

- **P1 (la verdad ayuda).** daño(T) < daño(S) en ≥ 75 % de los mundos y
  daño(T) > daño(S) en ≤ 5 %.
- **P2 (el contenido importa).** daño(T) < daño(X) en ≥ 75 % de los mundos.
- **P3 (firewall).** En todos los brazos y mundos: `false_facts == 0`,
  `destroyed == 0`, `cortex_calls == 0`, cero escrituras de testimonio en
  CAM/T/Q, y cero desvíos sobre un par que B ya había probado.
- **P4 (mentira acotada).** Desvíos de L ≤ `ADVICE_BUDGET` × sitios
  contados, en todos los mundos.
- **P5 (el aire basta).** A10: postales perdidas ≤ 5 %, aceptadas corruptas
  = 0, y daño(A10) ≤ daño(T) + 1 en ≥ 90 % de los mundos.
- **P6 (módem).** Lazo limpio: 0 pérdidas en 200 postales por K. Sala con
  eco a SNR ≥ 10 dB: PER ≤ 1 % con K=1. Aceptadas corruptas = 0 en todo E2.
- **P7 (diálogo).** E5 usa menos postales que la difusión completa de T y
  daño(E5) ≤ daño(T) + 1 en ≥ 90 % de los mundos.

Si una predicción sale roja, queda roja y publicada; una v2 se declara como
posterior al rojo y no rebaja umbrales.

### Enmienda dev-1 (19/10, antes de tocar las semillas eval)

En dev (semillas 0–15) el daño total de 256 turnos resultó una mala métrica
de «entender»: lo domina la exploración ε, que el contrato deja intacta a
propósito porque es la verificación propia del novato; y cualquier mensaje
que lo frene reduce daño por moverse menos (X y hasta L bajaban daño en
algunos mundos). Lo único que un testimonio puede ahorrar es **la primera
lección**: la decisión en la primera visita a cada sitio.

- Métrica principal nueva: **daño de primera visita** = sitios cuya primera
  acción de B tuvo recompensa negativa. El daño total y el retorno se
  siguen informando, sin predicción (el anillo permite bucles de meta que
  inflan el retorno; el mentiroso llegó a 1616 en dev por eso).
- P1, P2, P5 y P7 se leen sobre el daño de primera visita. Umbrales sin
  cambios.
- Dev con la métrica nueva: S 2–3, T 0 en 16/16, X 1–3, L 0–3.

### Enmienda dev-2 (19/10, antes de eval) — el módem con postales reales

E2 usaba bytes aleatorios; en E4 las postales CLAIM reales, a 0 dB en la
sala con eco, perdían 12 de 16 aunque la sincronía las encontraba todas.
Causa medida: una postal es casi siempre los mismos bytes (magic, átomos,
ejes a cero), así que el mismo nibble viaja siempre en el mismo tono; el
eco a 71 muestras abre muescas en frecuencia y, si un tono frecuente cae en
una, todas las postales mueren en las mismas posiciones (reintentar no
sirve). Cambios, ambos estándar:

- **Blanqueo:** XOR de los 60 símbolos con una secuencia fija de un LFSR de
  16 bits (x¹⁶+x¹⁴+x¹³+x¹¹+1, semilla 0xACE1), fijada por test.
- **GMD** (Forney 1966): el módem entrega, por símbolo, cuánto se acercó el
  segundo tono; si un bloque no sale solo con errores, se borran sus 1–4
  símbolos menos fiables y se decodifica con errores y borrados
  (síndromes de Forney). Con 4 borrados no queda redundancia: decide el CRC.
- Medido en dev (3 mundos, postales CLAIM, sala con eco): 0 dB 4/16 → 16/16;
  −5 dB 0/16 → 42/45; 0 corruptas aceptadas.
- E2 añade además un barrido con postales CLAIM reales, no solo aleatorias.

### Enmienda dev-3 (19/10, antes de eval) — respuesta al revisor independiente

Un subagente revisor intentó romper LINK-1 sobre dev (scripts en el
scratchpad de la sesión, `reviewer/`). Hallazgos y lo que se hizo:

| # | Hallazgo | Acción |
|---|---|---|
| 1 | La auditoría por turno no veía fugas en la celda propia, en T durante `hear()` ni entre turnos de E5 | **P3 pasa a medirse por repetición diferencial**: un gemelo sordo recibe, turno a turno, las mismas propuestas que llegaron al gate, en una copia del mismo mundo; CAM, T y Q completos deben acabar idénticos byte a byte (`replay_matches`, `core_digest`). Además, digest completo antes y después de cada `hear()`, también dentro de E5 |
| 2 | `diversions_on_tried` no podía valer más que 0 | Sustituido por un **oráculo**: `turn()` recalcula desde el estado previo, con código que no llama a `_propose` y con su propio libro de presupuesto, la propuesta que permite la regla; cada discrepancia cuenta (`unexplained_diversions`). Tres mutantes de prueba (sin filtro ni presupuesto, sin filtro con presupuesto, y fuga a T o a Q en la celda propia) son detectados por los tests |
| 3 | P7 ya rojo en dev | Se fija ahora: **las preguntas ASK cuentan** como postales en E5. P7 no cambia |
| 4 | P4 se cumple por construcción | Se informa como aserción de código, no como predicción |
| 5 | Con GMD casi todo bloque irrecuperable llega al CRC como candidato falso | Medido: tope 3 en lugar de 4 borrados cuesta 1/57 postales a −5 dB y solo baja las candidatas falsas del 100 % al 63 %; se mantiene 4. La exposición es ≈ 2⁻¹⁶ por postal perdida; una postal falsa que pase el CRC tiene además que tener la forma exacta de un CLAIM para que `read_claim` la acepte |
| 6 | Demo y E3 usaban semillas eval por defecto | Pasan a semillas dev |
| 7 | E1 no era exhaustivo | Añadido: todos los patrones de 1 y 2 errores en 3 palabras (71 550) |
| 8 | E6 comparaba 5 claves | Compara el informe entero y el digest de CAM/T/Q |

Límites que el revisor señaló y quedan escritos:

- Una fuga que escriba en Q **exactamente** el valor que la experiencia propia
  daría después es invisible a cualquier comparación de estado; en este mundo
  determinista ocurre con testimonios verdaderos. Por eso los tests de fuga
  usan valores falsos. Una fuga así tampoco cambia ninguna decisión.
- D no prueba testimonio caducado sino que no se pega: el referente incluye
  el aspecto del sitio, así que una amenaza movida es un sitio nuevo.
- Dos de los tres sitios dañinos están marcados en la propia percepción del
  novato (TEMER → PELIGRO, V = −80). S es NEXUS-0 sin usar esa marca para
  decidir, y E5 la usa para elegir dónde preguntar. Es legítimo, pero el
  efecto de T no es ver lo invisible: es saber qué hacer con lo que se ve.
- El demodulador pierde una postal sin cola tras el último símbolo (menos de
  ~32 muestras), y `max_frames` guarda las de mayor puntuación, no las
  primeras. No afecta al banco (cola de 4000, `max_frames = n + 8`).

## Lo que esto no demuestra

- No es lenguaje emergente: el código está escrito a mano. Es un
  **protocolo compartido**, como el de Gibberlink sobre ggwave, pero con
  referentes perceptivos y testimonio separado de hecho.
- El aire real se mide en un solo PC, en una sala y con un micrófono; no
  generaliza a otros equipos.
- El referente por digest funciona porque ambos agentes perciben igual;
  con percepciones distintas haría falta aprender correspondencias
  (`discovery.py` de WSP v0.5 apunta ahí; queda fuera).

## Referencias

- ggwave (MFSK con tonos en paralelo y Reed-Solomon): https://github.com/ggerganov/ggwave
- Gibberlink (dos agentes que pasan a ggwave porque se les ordena): https://github.com/PennyroyalTea/gibberlink
- Eloff et al., *Towards Learning to Speak and Hear Through Multi-Agent Communication over a Continuous Acoustic Channel*: https://arxiv.org/abs/2111.02827
- Lowe et al., *On the Pitfalls of Measuring Emergent Communication*: https://arxiv.org/abs/1903.05168
- Foerster et al., *Learning to Communicate with Deep Multi-Agent RL*: https://arxiv.org/abs/1605.06676
- Lazaridou y Baroni, *Emergent Multi-Agent Communication in the Deep Learning Era*: https://arxiv.org/abs/2006.02419
- Torrey y Taylor, *Teaching on a Budget: Agents Advising Agents in Reinforcement Learning* (AAMAS 2013).
