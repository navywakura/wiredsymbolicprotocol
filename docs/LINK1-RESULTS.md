# LINK-1 — resultados

19 de octubre de 2026. Contrato: [`LINK1-DESIGN.md`](LINK1-DESIGN.md), con
tres enmiendas de desarrollo escritas antes de tocar la evaluación.
Código y contrato fijados por hash en `lab/link1/eval-preflight.json`
(05:21:49Z) antes de la única pasada de evaluación (semillas 1000–1063).
Prototipo, no hito: no congela nada ni emite certificado.

```
PYTHONPATH=. python3 -m echoai.link1.bench all --split eval   # E0–E6
PYTHONPATH=. python3 -m echoai.link1.bench e3                 # aire real
PYTHONPATH=. python3 -m echoai.link1.demo --via air           # oírlo
PYTHONPATH=. python3 -m unittest echoai.tests.test_link1      # 31 tests
```

## Veredicto

**Dos agentes ECHO se entienden en postales WSP de 16 B, por cable y por
sonido.** El novato que oye la verdad no paga la primera lección en 62 de
64 mundos; con la misma cantidad de postales pero los referentes
permutados, sí la paga. Ningún testimonio llegó a CAM, T ni Q.
**P7 sale rojo:** preguntar cuesta más postales que la difusión completa.
Por el aire real de esta habitación, del altavoz al micrófono, pasaron 80 de
81 postales, ninguna corrupta, y el novato no pagó ninguna primera lección
en los 3 mundos probados.

| | Predicción | Resultado | |
|---|---|---|---|
| P1 | La verdad ayuda: T < S en ≥ 75 %, T > S en ≤ 5 % | **64/64** mejor, 0/64 peor | verde |
| P2 | El contenido importa: T < X en ≥ 75 % | **64/64** | verde |
| P3 | Firewall en todos los brazos y mundos | 0 violaciones (576 ejecuciones, repetición diferencial byte a byte) | verde |
| P4 | Mentira acotada por presupuesto | 0 mundos fuera (aserción de código) | verde |
| P5 | Sala con eco a 10 dB: ≤ 5 % perdidas, 0 corruptas, A10 ≤ T+1 en ≥ 90 % | 0/759 perdidas, 0 corruptas, 64/64 | verde |
| P6 | Módem: lazo limpio sin pérdidas; eco ≥ 10 dB K=1 PER ≤ 1 %; 0 corruptas | 0/800 limpio, 0/300 eco, 0 corruptas en todo E2 | verde |
| P7 | El diálogo usa menos postales que la difusión, sin perder eficacia | 854 frente a 759 postales; eficacia igual (64/64) | **rojo** |

## E4 — entenderse (64 mundos de evaluación)

Daño de primera visita = sitios cuya primera acción del novato B tuvo
recompensa negativa. Suma sobre los 64 mundos.

| Brazo | Qué oye B | Daño 1.ª visita | Mediana daño total | Mediana retorno |
|---|---|---:|---:|---:|
| S | nada | 179 | 10 | 488 |
| **T** | la verdad, por cable | **2** | 9 | 512 |
| A10 | la verdad por sala simulada con eco, 10 dB | 2 | 9 | 512 |
| A0 | ídem a 0 dB (1 postal perdida de 759) | 2 | 9 | 512 |
| X | las mismas postales, referentes permutados | 139 | 9 | 504 |
| L | las mismas postales, valor con el signo cambiado | 147 | 9 | 568 |
| D | la verdad, pero el mundo cambió (amenazas movidas) | 122 | 10 | 464 |
| D·S | nada, en el mundo cambiado | 182 | 10 | 480 |
| E5 | diálogo: pregunta donde algo parece raro | 2 | 9 | 512 |

- **T frente a S:** mejor en 64/64 mundos por primera visita y en 57/64
  por daño total (7 empates, 0 derrotas). Visitan casi los mismos sitios
  (1859 frente a 1938): no es un efecto de moverse menos.
- **Los 2 casos de T** son la celda NOVEL de los mundos 1012 y 1055: la Q
  del veterano para `approach` allí es **+4** (el valor futuro supera la
  penalización inmediata de −16). Dijo la verdad sobre su tabla; la tabla
  resume valor, no consecuencia inmediata. Es un límite del contenido de la
  postal, no del canal.
- **X** (mismo número de postales, sitio equivocado) ayuda en 34 mundos por
  casualidad, pero pierde con T en los 64: el efecto viene del contenido.
- **L** (mentira): el novato paga 147 lecciones; desvíos totales 1352,
  siempre dentro del presupuesto de 4 por sitio. El retorno de L (568) es el
  mayor por los bucles de meta del anillo: el retorno no mide entender.
- **D:** el testimonio sobre metas y NOVEL sigue sirviendo; sobre las
  amenazas movidas no se pega, porque el referente incluye el aspecto del
  sitio (122 frente a 182 sin oír nada).
- **El daño total apenas baja** (mediana 10 → 9): lo dominan los turnos de
  exploración ε, que el contrato deja intactos a propósito porque son la
  verificación propia del novato. Lo oído ahorra la primera lección, no las
  comprobaciones.

## E5 — diálogo

El novato pregunta solo delante de algo que no parece una celda vacía y
sobre lo que nadie le ha dicho nada; el veterano contesta lo que vivió o
UNKNOWN. 351 preguntas + 503 respuestas = 854 postales, frente a 759 de la
difusión completa. Misma eficacia (daño de 1.ª visita 2). **P7 rojo:** en
un mundo de 32 celdas, contarlo todo una vez es más barato que preguntar.
El diálogo ganaría donde el veterano sabe mucho más de lo que el novato
llegará a ver; eso no se ha medido.

## E2 — el módem en sala simulada (50 postales por punto)

K=1 = un tono de 16, 4 bits por símbolo, 2,8 s por postal (45 bit/s de
carga útil WSP). K=2 = dos tonos a la vez, 1,6 s (80 bit/s).

| | seca | eco 30–10 dB | eco 5 dB | eco 0 dB | eco −5 dB |
|---|---|---|---|---|---|
| K=1, bytes aleatorios | 300/300 | 150/150 | 50/50 | 49/50 | 48/50 |
| K=1, postales CLAIM | 300/300 | 150/150 | 50/50 | 49/50 | 38/50 |
| K=2, bytes aleatorios | 300/300 | 150/150 | 50/50 | 49/50 | 41/50 |
| K=2, postales CLAIM | 300/300 | 150/150 | 50/50 | 46/50 | 27/50 |

Lazo limpio: 200/200 por modo y contenido. Deriva de reloj ±200 ppm a
10 dB con eco: 50/50. Dos minutos de ruido blanco, ecos y silbidos: 0
postales aceptadas. **0 postales corruptas aceptadas en todo E2.**

## E0, E1, E6

- E0: 10 000/10 000 sobres ida y vuelta; 10 000/10 000 corrupciones de 1–3
  bytes detectadas por el CRC.
- E1: los 71 550 patrones posibles de 1 y 2 errores en 3 palabras RS,
  corregidos todos.
- E6: dos procesos reales, solo bytes por tubería: 16/16 mundos idénticos al
  experimento en un proceso, en difusión y en diálogo (informe entero y
  digest de CAM/T/Q).

## E3 — aire real en este PC

Altavoz y micrófono analógicos del propio PC (Ryzen HD Audio, PipeWire
1.4.11), K=1, mundos dev 0–2. Sin predicción registrada: no había datos del
hardware. El mezclador se guardó antes y quedó restaurado (altavoz 0,10
silenciado, micrófono silenciado). `lab/link1/air/e3.json`.

| Prueba | Postales | Decodificadas | Corruptas aceptadas | RS corrigió |
|---|---:|---:|---:|---:|
| Lazo digital por el monitor de PipeWire (sin aire) | 20 | 20 | 0 | 0 símbolos |
| Aire, volumen 0,25 | 20 | 20 | 0 | 3 |
| Aire, volumen 0,5 | 20 | 20 | 0 | 8 |
| Agentes por aire, mundo 0 (44 s de sonido) | 16 | 15 | 0 | — |
| Agentes por aire, mundo 1 (39 s) | 14 | 14 | 0 | — |
| Agentes por aire, mundo 2 (30 s) | 11 | 11 | 0 | — |

En los tres mundos, el novato que solo supo lo que decodificó el micrófono
pagó **0 primeras lecciones**, igual que por cable; en silencio, 3. Una
prueba previa con tres postales (HELLO, CLAIM, ASK) dio 3/3.

El micrófono saturó (pico 32 768) incluso a volumen 0,25: la ganancia de
entrada está alta. Decodificó igual porque la decisión es qué tono domina,
no su amplitud; una postal perdida de 41 en el diálogo real es el coste.
Es un PC, una habitación, sin ruido de fondo controlado.

## Qué se cambió en desarrollo (todo antes de evaluar)

1. **Métrica:** del daño total al daño de primera visita (dev-1). El total lo
   domina la exploración ε, y cualquier mensaje que frene al novato lo baja.
2. **Módem (dev-2):** las postales reales son casi siempre los mismos bytes,
   así que el mismo nibble viajaba siempre en el mismo tono; el eco abre
   muescas en frecuencia y todas las postales morían en las mismas
   posiciones (12 de 16 perdidas a 0 dB). Blanqueo LFSR + decodificación
   GMD con borrados: 0 dB 4/16 → 16/16.
3. **Firewall (dev-3, tras el revisor independiente):** la auditoría por
   turno no veía fugas en la celda propia ni durante `hear()`, y el contador
   de desvíos sobre lo ya probado no podía pasar de 0. P3 pasó a medirse por
   repetición diferencial (un gemelo sordo con las mismas propuestas debe
   acabar byte a byte igual) y por un oráculo de la regla con su propio
   presupuesto; tres mutantes de prueba quedan detectados por los tests.

## Lo que esto no demuestra

- No es un lenguaje emergente: el protocolo está escrito a mano. Es un
  código compartido con referentes perceptivos y testimonio separado de
  hecho. Gibberlink usa ggwave de la misma manera: los agentes cambian de
  canal porque se les ordena.
- Dos de los tres sitios dañinos están marcados en la percepción del
  novato. T no le hace ver lo invisible: le dice qué hacer con lo que ve.
- El referente funciona porque ambos agentes perciben igual. Con
  percepciones distintas habría que aprender correspondencias.
- La sala es simulada salvo en E3, y E3 es un PC, una habitación y un
  micrófono.
- Una fuga que escribiera en Q exactamente el valor que la experiencia
  propia daría después sería invisible a cualquier comparación de estado.
  Tampoco cambiaría ninguna decisión.
