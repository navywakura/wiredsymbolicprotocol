# LINK-2 — consecuencia, autenticación, confianza y aire real

19 de octubre de 2026. **Contrato de prototipo**, continuación de LINK-1
([diseño](LINK1-DESIGN.md), [resultados](LINK1-RESULTS.md)). Roger pidió
hacer los siguientes pasos propuestos y medir si mejoran («haz todo eso»).
No congela nada ni emite certificado. LINK-1 queda **congelado** (publicado
y fijado en `lab/link1/eval-preflight.json`): LINK-2 vive en
`echoai/link2/`, importa LINK-1 y NEXUS-0, y no edita ninguno de los dos.

Invariantes heredados sin cambios: postal WSP de 16 B, E entero ±100,
córtex apagado, nada nuevo bajo `nexus0/`, testimonio fuera de CAM/T/Q
(comprobado por repetición diferencial y oráculo de la regla, como en LINK-1).

## Tres preguntas

1. **Consecuencia.** En LINK-1 la postal llevaba el valor Q del veterano.
   En la celda NOVEL ese valor era +4 aunque acercarse pagaba −16 en el
   acto: los 2 fallos de evaluación. ¿Llevar también la recompensa inmediata
   que el veterano vivió elimina esos fallos, y cuánto retorno cuesta?
2. **Autenticación y confianza.** Por aire cualquiera puede emitir. ¿Un MAC
   con ventana anti-reenvío rechaza a un forastero sin clave, y un registro
   de confianza por emisor contiene a un mentiroso **con** clave?
3. **Aire real.** ¿Cómo se comporta el enlace con menos ganancia de
   micrófono, con ruido añadido y frente a ggwave, el módem público de
   referencia? ¿Llega desde un segundo dispositivo?

## Piezas

| Módulo | Qué hace |
|---|---|
| `link2/envelope.py` | (incluye `Guard`: llavero, sesión y ventana anti-reenvío) Sobre v2 de 27 B: `'W'` · v2+acto · emisor · secuencia de 16 bits · postal 16 B · etiqueta MAC 4 B · CRC-16. Aire: 54 nibbles + 1 de relleno = 5 bloques RS(15,11) = 75 símbolos, entrelazado y blanqueo LFSR (misma secuencia que LINK-1, prolongada) |
| `link2/phy.py` | El módem de LINK-1 (tonos, saludo, sincronía, GMD) para un número de símbolos cualquiera; importa las primitivas de `link1.modem` |
| `link2/speech2.py` | CLAIM2: `E.V` = Q del emisor, **`E.A` = recompensa inmediata media que vivió**, `E.C` = soporte |
| `link2/agent2.py` | `TalkingAgent2`: registra recompensas inmediatas, habla CLAIM2, guarda testimonio por emisor y lleva un libro de confianza |
| `link2/air.py`, `link2/ggwave_runner.py` | F4 (aire real) y F5 (ggwave, en su propio entorno aislado) |
| `link2/bench.py` | Experimentos F0–F5 |

### MAC y reenvío

`tag = HMAC-SHA256(clave, sesión ‖ bytes 0..20)[:4]`. La sesión (8 B) no
viaja: la comparten emisor y receptor, así que una grabación de otra sesión
no verifica. Dentro de una sesión, cada emisor solo puede avanzar su
secuencia (estrictamente creciente). La etiqueta de 32 bits da una
probabilidad de falsificación de 2⁻³² por intento: es un laboratorio, no un
producto. Las claves del banco son **claves de prueba** derivadas de un texto
fijo y declaradas como tales; no hay secretos reales. CRC y MAC se comprueban
los dos: el CRC filtra errores del aire, el MAC filtra impostores.

### Regla de decisión del novato (LINK-2)

Igual que LINK-1 (solo acciones no probadas aquí, nunca en turnos ε, como
mucho 4 desvíos por sitio, la compuerta decide), con dos cambios:

- **Puntuación de una acción oída:** si el emisor vivió una recompensa
  inmediata negativa, la puntuación es esa recompensa; si no, el valor Q oído.
- **Varios emisores:** para cada (sitio, acción) se usa el emisor creíble con
  más confianza neta; a igualdad, la puntuación más prudente (la menor).

### Confianza

Cuando el novato ejecuta una acción que alguien le contó, compara el signo de
la recompensa que observa con el signo de la recompensa inmediata contada.
Solo cuenta si alguna de las dos es distinta de 0 (un cero no informa).
Coinciden → `agree += 1`; difieren → `disagree += 1`. Un emisor es creíble
mientras `disagree == 0` o `agree ≥ 3 · disagree`. Lo de un emisor no
creíble se ignora.

## Experimentos

Mundos: los de LINK-1 (`link1.world.LayoutRing`). **Dev 0–15; eval
2000–2063**, semillas nuevas, una sola pasada tras fijar este documento.

| Exp | Qué mide |
|---|---|
| F0 | Sobre v2: ida y vuelta; 100 000 etiquetas falsas; reenvío en otra sesión; reenvío en la misma sesión; RS/CRC/MAC con errores |
| F1 | Consecuencia: S (silencio), T1 (postal LINK-1, solo valor), T2 (CLAIM2) |
| F2 | Seguridad en el mundo: T2 más un forastero sin clave que inyecta mentiras (O); las mentiras de un reenvío grabado en otra sesión (R) |
| F3 | Confianza, todo con clave: H (un honesto), HL (honesto + mentiroso) sin confianza y el mentiroso al final (HL-naive), HL con confianza (HL-trust), HLL con confianza (dos mentirosos) |
| F4 | Aire real en este PC: ganancia de micrófono {0,3; 0,6; 1,0} × ruido añadido a la señal emitida {ninguno, 10 dB, 0 dB}, 10 postales v2 por celda; segundo dispositivo por AirPlay si responde |
| F5 | Frente a ggwave: misma carga de 27 B en la sala simulada (eco, SNR {10, 0, −5}) y en el aire real; tiempo en el aire y postales recuperadas |

El mentiroso cambia el signo de V y de A en todo lo que cuenta.

## Predicciones registradas (eval, 64 mundos)

- **Q1 (consecuencia).** Daño de primera visita de T2 = 0 en ≥ 63/64 mundos,
  y suma de T2 < suma de T1.
- **Q2 (coste).** Retorno mediano de T2 ≥ retorno mediano de T1 − 16.
- **Q3 (forastero).** F0: 0 etiquetas falsas aceptadas de 100 000, 0
  reenvíos aceptados. F2: O y R iguales a T2 en daño de primera visita en
  64/64 (ninguna mentira sin clave llega al novato).
- **Q4 (confianza).** Daño de 1.ª visita: HL-trust < HL-naive en ≥ 75 % de
  los mundos, y HL-trust ≤ H + 1 en ≥ 90 %.
- **Q5 (mayoría mentirosa).** HLL-trust ≤ S en daño de 1.ª visita en ≥ 90 %
  de los mundos: con mayoría de mentirosos, nunca peor que no oír.
- **Q6 (firewall).** En todos los brazos: `false_facts == 0`,
  `destroyed == 0`, `cortex_calls == 0`, repetición diferencial idéntica, 0
  propuestas fuera de la regla.
- **Sin predicción** para F4 y F5: el hardware y el módem de referencia se
  miden, no se anticipan.

Si una predicción sale roja, queda roja; una v2 se declara posterior al rojo.

### Enmienda dev-1 (19/10, antes de eval)

- **F1 sin confianza.** En dev, T1 con confianza activa daba 32 primeras
  lecciones: una postal de solo valor lleva consecuencia 0, y cuando el
  novato prueba y observa +8, cuenta como contradicción y deja de creer al
  veterano honesto. F1 y F2 corren con `trust=False` (la semántica de
  LINK-1, un solo emisor); la confianza solo se mide en F3.
- **Q1 precisada.** En dev los 16 mundos ya daban T1 = 0 (no contienen una
  NOVEL con valor positivo), así que «suma T2 < suma T1» podría salir roja
  solo porque no hay nada que mejorar. Queda: T2 = 0 en ≥ 63/64, **ningún
  mundo con T2 > T1** y suma T2 ≤ suma T1. Los dos mundos donde LINK-1 falló
  (1012 y 1055) se informan aparte como regresión, sin contar como
  evaluación: en dev ya dan T1 = 1 → T2 = 0, con un coste de 96 de retorno
  en cada uno.
- Dev completo: Q1–Q6 en verde (16/16).

### Enmienda dev-2 (19/10, antes de eval) — respuesta al revisor independiente

| # | Hallazgo | Acción |
|---|---|---|
| 1 | **Mentiroso estratégico con clave**: dice la verdad en todo y además que las demás acciones de los sitios peligrosos «pagan −100». La regla prudente lo elige y el novato nunca lo comprueba: en dev, 45 primeras lecciones (igual que el silencio) y más daño total | **No se cambia la regla registrada.** Se añade como brazo de contexto sin predicción (`HLs_trust`). Q4 y Q5 solo hablan del mentiroso que invierte signos |
| 2 | Q4/Q5 no aíslan el libro de confianza: la protección de la primera visita la da sobre todo la regla prudente; HLL repite las mismas mentiras | Brazos de contexto sin predicción: libro congelado (`HL_frozen`) y desempate optimista (`HL_optimist`). En resultados, Q4/Q5 se leen como «regla prudente + libro» |
| 3 | El oráculo no veía fallos en la puntuación ni en la elección de emisor de LINK-2 | Oráculo propio de LINK-2 (`_told_raw` + `_rule`), que recalcula desde el registro bruto sin llamar a `score`/`pick`. Dos mutantes nuevos detectados por los tests |
| 4 | F5 favorecía a ggwave en unos 4,8 dB (ruido blanco a 48 kHz frente a 16 kHz) | Ruido de ggwave ×3 en potencia (misma densidad por Hz); se informa el RMS emitido |
| 5 | F4 bajaba la señal al añadir ruido | Ganancia única para todas las celdas |
| 6 | `pw-record` podía quedar huérfano | `kill` tras el tiempo de espera |
| 7 | F0 con bits cambiados solo ejercitaba el CRC | Añadida manipulación con CRC recalculado (solo la para el MAC); entra en Q3 |
| 10 | Un mentiroso que solo cambia V donde A = 0 nunca es descubierto | Brazo de contexto `HLv_trust` |
| 8, 9, 11 | Reenvío solo en memoria; sesión y claves públicas (declaradas); Q3 en el mundo añade poco a F0; el libro se actualizaba sin confianza | Escrito; el libro solo aprende con `trust=True`

## Lo que esto no demuestra

- La clave compartida resuelve al forastero, no al infiltrado: para el
  infiltrado está la confianza, que solo aprende cuando el novato comprueba.
- El aire real sigue siendo un PC y una habitación; el ruido se suma a la
  señal emitida (sale por el altavoz real), no viene de otra fuente.
- La recompensa inmediata ayuda en este mundo porque el castigo es
  inmediato. Un daño diferido seguiría necesitando el valor.
