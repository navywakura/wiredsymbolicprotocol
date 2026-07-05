# ROGEX-WSP — Wired Symbolic Protocol

[![tests](https://github.com/n4vv4r/RogexWSP/actions/workflows/tests.yml/badge.svg)](https://github.com/n4vv4r/RogexWSP/actions/workflows/tests.yml)
[![licencia](https://img.shields.io/badge/licencia-Apache--2.0-blue.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-informational.svg)](pyproject.toml)

> El significado no vive en la palabra. La palabra es solo una máscara.

**ROGEX-WSP no es una lengua inventada. Es un protocolo experimental de
comunicación simbólico-emocional: un núcleo de significado, muchas máscaras
físicas.** *(One meaning core, many physical masks.)*

ROGEX-WSP no es un idioma con palabras: es un **protocolo de significado**.
La unidad de comunicación es un paquete de **información + emoción** que puede
renderizarse como texto humano, sonido, glifo visual, JSON o binario — para que
lo hablen humanos, IAs y máquinas.

```text
L = G[S(M, I, E)]

M = soporte físico      (sonido, glifo, texto, binario…)
I = información         (los 32 átomos semánticos)
E = emoción             (6 ejes continuos)
S = símbolo             (S = I + E, el paquete)
G = regla generativa    (composición de conceptos nuevos)
```

Prototipo **v0.1**: 32 símbolos base, 6 ejes emocionales, 1 formato JSON,
y conversores texto→símbolo, símbolo→texto, símbolo→sonido, símbolo→glifo
y símbolo→binario. Python puro, **cero dependencias**.

## Instalación y uso rápido

```bash
# sin instalar nada (desde la raíz del repo):
python3 -m rogex_wsp demo

# o instalado como comando `wsp`:
pip install -e .
wsp demo
```

```bash
wsp atoms                                    # los 32 átomos del núcleo
wsp encode "te quiero"                       # texto → símbolo (JSON)
wsp encode "te quiero" --compact             # texto → forma máquina
wsp decode examples/te_quiero.json           # símbolo → español
wsp decode examples/te_quiero.json --lang en # símbolo → inglés
wsp audio --text "estoy aquí" -o presencia.wav
wsp glyph --text "te quiero" -o amor.svg
wsp binary --text "¡peligro!"                # símbolo → binario compacto (hex)
```

## Ejemplo completo

Entrada:

```text
te quiero
```

Núcleo simbólico (el idioma real es la estructura interna):

```text
YO → AMOR → OTRO @AHORA | E[V+0.95 A+0.60 D+0.00 C+0.80 U+0.00 B+0.98]
```

Renderizadores (máscaras del mismo símbolo):

| Render   | Salida |
|----------|--------|
| español  | «Te quiero.» |
| inglés   | «I love you.» |
| sonido   | consonancia 3:2 + 5:4, tempo lento, ataque suave, duración larga |
| glifo    | dos puntos unidos por onda dentro de un campo envolvente |
| binario  | `57 53 50 01 01 1b 02 83 00 03 0b 04 41 4d 4f 52 …` |

Y el caso emocionalmente compuesto:

```text
"estoy solo pero quiero conectar"
  → YO → SER → SOLEDAD @AHORA      | E[V-0.60 … B-0.70]   (estado)
  → YO → DESEAR → CONEXION @AHORA  | E[V+0.40 … B+0.60]   (deseo)
```

La IA que reciba esto no responde a las palabras: responde al símbolo emocional.

## Las capas del protocolo

| Capa | Nombre | En el código |
|------|--------|--------------|
| 1 | **Materia (M)** — el soporte físico | `audio.py`, `glyph.py`, binario |
| 2 | **Información (I)** — 32 átomos semánticos | `primitives.py` |
| 3 | **Emoción (E)** — 6 ejes: V A D C U B | `emotion.py` |
| 4 | **Símbolo (S = I + E)** — el paquete | `symbol.py` |
| 5 | **Relación** — `[ORIGEN][RELACIÓN][DESTINO]` | `Symbol.source/relation/target` |
| 6 | **Tiempo y espacio** — coordenadas, no palabras | `Symbol.time/space` |
| 7 | **Generatividad (G)** — conceptos nuevos por composición | `concepts.py` |

Documentación:

- [`docs/SPEC.md`](docs/SPEC.md) — especificación normativa del protocolo
- [`docs/PHILOSOPHY.md`](docs/PHILOSOPHY.md) — la tesis: por qué no palabras
- [`docs/BINARY_FORMAT.md`](docs/BINARY_FORMAT.md) — el formato binario byte a byte
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — hoja de ruta (v0.2 «Signal Return»)
- [`examples/gallery/`](examples/gallery/) — **galería**: glifos y audio de las frases canónicas

## Generatividad: el idioma crece

No hay lista cerrada de palabras. Un concepto nuevo es una composición de átomos:

```python
from rogex_wsp import define, Primitive as P, Emotion

define(
    "NOSTALGIA",
    [P.RECORDAR, P.ANTES, P.DESEAR, P.OTRO],
    es="nostalgia",
    emotion=Emotion(valence=-0.3, bond=0.7),
)
```

Y los mensajes pueden **transportar sus definiciones** (`"defines"` en el JSON,
o codificadas en el binario): el receptor aprende el concepto al decodificar el
mensaje. Ver [`examples/nostalgia_definida.json`](examples/nostalgia_definida.json).

## El sonido: ratios, no hercios

El audio no depende de frecuencias absolutas sino de **relaciones entre ondas**,
para que sea igual de legible en cualquier dispositivo:

```text
1:1  = identidad / ser        9:8   = movimiento / tensión suave
3:2  = conexión / relación    16:15 = tensión / disonancia
5:4  = armonía / afinidad     silencio = ausencia / negación
4:3  = estabilidad            ascendente = pregunta · descendente = cierre
```

La emoción se codifica como música: tempo = urgencia, volumen = intensidad,
brillo = valencia, vibrato = duda, duración = importancia/vínculo.

## El glifo: geometría, no letras

```text
punto = ser        círculo = campo/mundo     onda    = información
línea = relación   flecha  = dirección/deseo ruptura = negación
zigzag = tensión   espiral = generatividad   eco     = memoria
```

El estilo es la emoción: color = valencia, grosor = activación,
trazo discontinuo = duda, púas radiales = urgencia, campo envolvente = vínculo.

## Estructura del repositorio

```text
rogex_wsp/
  primitives.py      # capa I: los 32 átomos (códigos de 5 bits)
  emotion.py         # capa E: los 6 ejes emocionales
  concepts.py        # capa G: conceptos derivados + registro abierto
  symbol.py          # capa S: paquete, JSON y binario
  text_to_symbol.py  # intérprete: español → símbolo
  symbol_to_text.py  # render: símbolo → español / inglés
  audio.py           # render: símbolo → WAV (ratios de frecuencia)
  glyph.py           # render: símbolo → SVG (geometría)
  cli.py             # comando `wsp`
docs/                # SPEC, filosofía, formato binario, hoja de ruta
examples/            # mensajes canónicos en JSON + galería (SVG/WAV)
tests/               # 36 tests (unittest, stdlib)
```

```bash
python3 -m unittest discover -s tests   # ejecutar los tests
```

## Estado y rumbo

Esto es una **prueba de concepto**: la v0.1 no necesita ser universal, necesita
demostrar que una frase puede convertirse en estructura simbólica — y ya lo hace
en ambos sentidos. La siguiente meta es la **v0.2 «Signal Return»**: que el
sonido y el glifo vuelvan al símbolo (`wsp listen`, `wsp inspect`), JSON Schema
oficial y demo web. Plan completo en [`docs/ROADMAP.md`](docs/ROADMAP.md);
cómo contribuir en [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

*Rogex Laboratories — un lenguaje universal simbólico-emocional, no basado en
palabras, sino en información, emoción, matemática, sonido y forma.*
