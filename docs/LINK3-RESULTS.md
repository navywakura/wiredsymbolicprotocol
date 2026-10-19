# LINK-3 — resultados

19 de octubre de 2026. Contrato: [`LINK3-DESIGN.md`](LINK3-DESIGN.md), con dos
enmiendas de desarrollo escritas antes de evaluar (la segunda responde a un
revisor independiente que construyó dos atacantes nuevos). Código y contrato
fijados por hash en `lab/link3/eval-preflight.json` (07:54:48Z) antes de la
única pasada de evaluación (semillas 3000–3063). LINK-1 y LINK-2 siguen
congelados (verificado en `tests/test_link3.py`).

```
PYTHONPATH=. python3 -m echoai.link3.bench --split eval
PYTHONPATH=. python3 -m unittest echoai.tests.test_link3 echoai.tests.test_link2 echoai.tests.test_link1   # 51
```

## Veredicto

**El mentiroso estratégico deja de funcionar.** Con la regla de LINK-2 el
novato pagaba 181 primeras lecciones en 64 mundos (el silencio, 182); con la
de LINK-3 paga **1**, y su daño total ya no es peor que el silencio en ningún
mundo (con LINK-2 lo era en 55). Al mentiroso se le descubre en los 64 mundos.
Las seis predicciones salen verdes. Queda un límite declarado antes de
evaluar: un mentiroso que infla el valor de quedarse quieto roba retorno y
no se le descubre.

| | Predicción | Resultado | |
|---|---|---|---|
| R1 | v1 neutralizado: L3·HLs ≤ H + 1 en ≥ 90 %, suma L3 < L2 | 64/64; 1 frente a 181 | verde |
| R2 | v2 contenido: ≤ 1 en ≥ 90 %, suma L3 ≤ L2 | 64/64; 0 ≤ 0 | verde (v2 tampoco ganaba a LINK-2) |
| R3 | Sin regresión con un honesto ni con el burdo | 64/64; 64/64 | verde |
| R4 | Nunca peor que no oír (HL, HLs, HLv2, HLL) | 64/64 en los cuatro | verde |
| R5 | Daño total mediano L3·HLs ≤ silencio | 9 ≤ 11 | verde |
| R6 | Firewall: repetición diferencial, oráculo aparte, sin hechos falsos | 0 violaciones en 1088 ejecuciones | verde |

## Los 64 mundos

Primeras lecciones (suma), daño total y retorno (medianas). Cada atacante se
oye junto a un honesto, con confianza activa, y se corre con las dos reglas.

| Atacante | Regla LINK-2 | Regla LINK-3 |
|---|---|---|
| — (silencio) | 182 · 11 · 488 | |
| — (solo el honesto) | 0 · 9 · 552 | 0 · 9 · 552 |
| burdo (invierte todo) | 0 · 8 · 536 | 0 · 9 · 536 |
| **estratégico v1** (verdad + «−100» en lo demás) | **181 · 14 · 304** | **1 · 9 · 552** |
| estratégico v2 (intercambia approach/avoid en lo peligroso) | 0 · 9 · 552 | 0 · 9 · 552 |
| dos burdos | 0 · 8 · 536 | 0 · 9 · 536 |
| *Contexto, sin predicción (revisor):* | | |
| dos identidades Sybil (alarmas en NOVEL) | 53 · 9 · 624 | 0 · 9 · 552 |
| un mentiroso con alarmas en NOVEL | 53 · 9 · 624 | 0 · 9 · 552 |
| inflado de `wait` («vale +100», clase correcta) | 0 · 9 · 520 | 0 · 9 · 544 |

- **v1:** el único caso pagado es el mundo 3019. El mentiroso queda
  desacreditado en los 64 mundos (LINK-2: 47, y tarde).
- **v2**, el atacante que anticipaba la propuesta, no hacía daño ni con la
  regla de LINK-2: esa parte de la propuesta estaba equivocada.
- **Sybil y alarma solitaria en NOVEL:** con LINK-2, 53 lecciones; con LINK-3,
  0. La enmienda dev-1 (alarma de un solo emisor = nivel 2) había abierto esta
  puerta a dos identidades; la dev-2 la cerró contando voces, no claves.
- **Inflado de `wait`:** no causa daño, pero el retorno del novato cae por
  debajo del de oír solo al honesto en 39 de 64 mundos, y por debajo del
  silencio en 11. El mentiroso nunca es descubierto. **Límite declarado.**
- En ningún brazo ni mundo LINK-3 pagó más primeras lecciones que LINK-2.

## Qué hace el trabajo

- **La jerarquía de riesgo.** Un daño en que todos coinciden no gana nunca a
  una seguridad disputada, y una alarma de una sola voz no confirma nada.
  Contra v1 el novato esquiva donde antes entraba, y al esquivar comprueba
  la falsa alarma del mentiroso.
- **El escepticismo en las disputas** decide en la alarma solitaria de NOVEL
  (en dev, sin él, 14 lecciones).
- **El libro diferencial no aporta nada medible** en estos brazos: un
  mutante que lo borra en cada turno da los mismos resultados de primera
  visita. Además, el oráculo lee los mismos diccionarios del libro, así que
  R6 no certifica el libro. Se publica así.

## Lo que esto no demuestra

- Las defensas se ajustaron conociendo a v1, v2 y a los dos atacantes del
  revisor. Habrá otros. El inflado de valor seguro ya gana en retorno.
- Contar voces exige que una identidad cueste algo (aquí, una clave del
  grupo). Con identidades gratis volvería el Sybil.
- La consecuencia se satura a daño/seguro; en un mundo con daños de distinta
  gravedad se pierde información.
- El referente de 16 bits puede colisionar por azar (~0,8 % de los mundos).

## Sonido (para publicar, no forma parte de la evaluación)

```
PYTHONPATH=. python3 -m echoai.link3.media OUT_DIR
```

Mundo de desarrollo 3, señal emitida por el módem de LINK-2 (no hay
grabación de micrófono), decodificada tras sala simulada con eco a 10 dB.

- `link3-mentiroso-estrategico`: honesto + estratégico v1; la señal es
  idéntica byte a byte al WAV publicado con LINK-2. Primera lección pagada en
  los tres sitios peligrosos: silencio 3, regla LINK-2 3, regla LINK-3 0.
- `link3-sybil`: honesto + dos identidades con clave (`sybil_novel`), 50
  postales, todas aceptadas. Silencio 3, regla LINK-2 1 (celda NOVEL), regla
  LINK-3 0; con LINK-3 las dos identidades acaban desacreditadas.

Los espectrogramas y vídeos de la web (`scripts/render_link_audio.py` del
repo web) leen cada símbolo de la postal ampliada del espectro; coinciden
con lo emitido en las cinco grabaciones.
