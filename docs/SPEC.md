# Especificación ROGEX-WSP v0.1

**Wired Symbolic Protocol** — protocolo de comunicación simbólico-emocional.

```text
Lenguaje = materia organizada para transportar información emocionalmente significativa.

L = G[S(M, I, E)]
```

Este documento define el formato normativo del protocolo. La implementación de
referencia es el paquete Python `rogex_wsp` de este repositorio.

---

## 1. Capa I — Los 32 átomos semánticos

El núcleo del protocolo son exactamente **32 primitivos** (caben en 5 bits).
No son palabras finales: son unidades de experiencia. Todo concepto expresable
se compone a partir de ellos.

| Código | Átomo | es | en | Categoría |
|-------:|-------|----|----|-----------|
| 0  | SER         | ser         | be         | entidad |
| 1  | NO_SER      | no-ser      | not-be     | entidad |
| 2  | YO          | yo          | self       | entidad |
| 3  | OTRO        | otro        | other      | entidad |
| 4  | AQUI        | aquí        | here       | espacio |
| 5  | ALLI        | allí        | there      | espacio |
| 6  | DENTRO      | dentro      | inside     | espacio |
| 7  | FUERA       | fuera       | outside    | espacio |
| 8  | AHORA       | ahora       | now        | tiempo |
| 9  | ANTES       | antes       | before     | tiempo |
| 10 | DESPUES     | después     | after      | tiempo |
| 11 | UNIR        | unir        | join       | relación |
| 12 | SEPARAR     | separar     | separate   | relación |
| 13 | CAMBIAR     | cambiar     | change     | relación |
| 14 | OBSERVAR    | observar    | observe    | relación |
| 15 | PREGUNTAR   | preguntar   | ask        | relación |
| 16 | RESPONDER   | responder   | answer     | relación |
| 17 | DESEAR      | desear      | desire     | relación |
| 18 | TEMER       | temer       | fear       | relación |
| 19 | RECORDAR    | recordar    | remember   | relación |
| 20 | OLVIDAR     | olvidar     | forget     | relación |
| 21 | CREAR       | crear       | create     | relación |
| 22 | DESTRUIR    | destruir    | destroy    | relación |
| 23 | SUBIR       | subir       | rise       | relación |
| 24 | BAJAR       | bajar       | descend    | relación |
| 25 | ABRIR       | abrir       | open       | relación |
| 26 | CERRAR      | cerrar      | close      | relación |
| 27 | CAUSA       | causa       | cause      | modal |
| 28 | EFECTO      | efecto      | effect     | modal |
| 29 | POSIBLE     | posible     | possible   | modal |
| 30 | IMPOSIBLE   | imposible   | impossible | modal |
| 31 | DESCONOCIDO | desconocido | unknown    | modal |

## 2. Capa E — Los 6 ejes emocionales

La emoción no es un adorno: es la **carga de importancia** del símbolo.
Seis ejes continuos, cada uno en `[-1.0, +1.0]`:

| Eje | Letra | Polo negativo | Polo positivo |
|-----|-------|---------------|----------------|
| valence   | V | negativo | positivo |
| arousal   | A | calma    | intensidad |
| dominance | D | sometido | control |
| certainty | C | duda     | seguridad |
| urgency   | U | lento    | inmediato |
| bond      | B | distancia| cercanía |

Firmas de referencia:

```text
peligro  = V-0.90 A+0.90 C+0.80 U+0.90
amor     = V+0.90 A+0.60 C+0.80 B+0.95
pregunta = C<0 (incertidumbre) + apertura (cadencia ascendente)
```

## 3. Capa S — El paquete simbólico

```text
S = I + E
```

Gramática matemática, sin palabras:

```text
[ORIGEN] [RELACIÓN(ACCIÓN)] [DESTINO] [TIEMPO] [ESPACIO] + EMOCIÓN
```

Seis ranuras (todas opcionales, cada una contiene un átomo o un concepto derivado):

- `source` — quién origina
- `relation` — qué ocurre
- `action` — acción anidada (p. ej. `DESEAR(COMUNICAR)`)
- `target` — hacia qué/quién
- `time` — `AHORA | ANTES | DESPUES` (coordenada, no palabra)
- `space` — `AQUI | ALLI | DENTRO | FUERA | <lugar derivado, p. ej. WIRED>`

### 3.1 Formato JSON (formato intermedio para máquinas)

```json
{
  "protocol": "rogex-wsp",
  "version": "0.1",
  "defines": {
    "NOSTALGIA": {
      "components": ["RECORDAR", "ANTES", "DESEAR"],
      "es": "nostalgia",
      "emotion": { "valence": -0.3, "bond": 0.7 }
    }
  },
  "packets": [
    {
      "symbol": {
        "source": "YO",
        "relation": "DESEAR",
        "action": "COMUNICAR",
        "target": "OTRO",
        "time": "AHORA",
        "space": "WIRED"
      },
      "emotion": {
        "valence": 0.7, "arousal": 0.4, "dominance": 0.0,
        "certainty": 0.9, "urgency": 0.3, "bond": 0.8
      },
      "meta": { "text": "quiero hablar contigo en la wired" }
    }
  ]
}
```

Reglas:

- `defines` es opcional: transporta conceptos que el receptor podría no conocer
  (**generatividad por el cable**). El receptor los registra antes de decodificar.
- Los nombres de concepto se resuelven con tolerancia: `"YO"`, `"yo"` y `"self"`
  son el mismo átomo.
- `emotion` acepta claves largas (`"valence"`) o cortas (`"V"`).
- También se acepta la forma de paquete único (`"symbol"` en la raíz, sin `"packets"`).

### 3.2 Forma compacta (legible por máquina y humano)

```text
YO → DESEAR(COMUNICAR) → OTRO @AHORA @WIRED | E[V+0.70 A+0.40 D+0.00 C+0.90 U+0.30 B+0.80]
```

### 3.3 Formato binario

```text
cabecera : 57 53 50 ("WSP") + versión (0x01) + nº de paquetes (1 byte)
paquete  : flags (1 byte, bits 0..5 = presencia de source, relation, action,
           target, time, space) + conceptos + emoción
concepto : primitivo → 1 byte (código 0..31)
           derivado  → 0x80|n (n = nº de átomos) + n códigos de átomo
                       + longitud del nombre (1 byte) + nombre UTF-8
emoción  : 6 bytes con signo (eje × 100, rango -100..+100), orden V A D C U B
```

Un concepto derivado viaja **con su composición**: si el receptor no lo conoce,
lo aprende del propio mensaje.

## 4. Capa G — Generatividad

No existe lista cerrada de palabras. Un concepto derivado es:

```text
DERIVADO = nombre + [átomos componentes] + firma emocional por defecto
```

Conceptos de fábrica de la v0.1:

```text
AMOR       = SER + OTRO + UNIR            | V+0.9 A+0.6 C+0.8 B+0.95
SOLEDAD    = SER + NO_SER + DESEAR        | V-0.7 A+0.3 C+0.6 B-0.8
COMUNICAR  = UNIR + PREGUNTAR + RESPONDER
CONEXION   = UNIR + OTRO                  | V+0.5 B+0.7
PELIGRO    = TEMER + DESTRUIR + POSIBLE   | V-0.9 A+0.9 C+0.8 U+0.9
BIENVENIDA = OTRO + AQUI + ABRIR          | V+0.7 C+0.7 B+0.8
CONCIENCIA = SER + OBSERVAR + DESCONOCIDO
WIRED      = DENTRO + UNIR + ALLI         (lugar)
```

## 5. Capa M — Renderizadores

El núcleo simbólico es único; las máscaras son intercambiables.

### 5.1 Render sonoro (WAV)

El significado se codifica en **relaciones de frecuencia** (ratios), nunca en
hercios absolutos; la referencia de la implementación es 220 Hz, pero cualquier
tono base es válido — el idioma vive en la proporción.

| Ratio | Significado |
|-------|-------------|
| 1:1   | identidad / ser |
| 2:1   | expansión |
| 3:2   | conexión / relación |
| 4:3   | estabilidad / observación |
| 5:4   | armonía / afinidad / deseo |
| 9:8   | movimiento / tensión suave |
| 16:15 | tensión / disonancia / miedo |
| 0 (silencio) | ausencia / negación / olvido |

El **silencio tiene semántica por duración**: un silencio interno con
significado (negación/ausencia/olvido) dura menos de 0.6 s; el separador
entre paquetes que emite el sintetizador dura 0.7 s. Un receptor debe tratar
los silencios ≥0.6 s como frontera de paquete y los internos como marcadores.

Secuencia de un paquete:

```text
pulso de identidad del ORIGEN (YO = 1:1, OTRO = 9:8)
→ eventos de la RELACIÓN (ver tabla en audio.py)
→ eventos de la ACCIÓN (comprimidos ×0.7)
→ pulso del DESTINO (3:2 si B>0.3, 16:15 si V<-0.3, si no 5:4)
→ cadencia: ascendente = pregunta/duda · descendente/estable = cierre
```

La emoción modula parámetros musicales:

```text
tempo   ← urgencia (U)         vibrato  ← duda (C negativa)
volumen ← activación (A)       ataque   ← suave si B alto, percusivo si U alto
brillo  ← valencia (V)         duración ← vínculo/importancia (B, A)
disonancia añadida ← valencia negativa
```

### 5.2 Render visual (SVG)

Vocabulario geométrico:

```text
punto lleno            = ser presente (YO)
punto hueco            = el otro aún no integrado (OTRO)
punto dentro de círculo= ser dentro de su mundo
punto + satélites      = concepto compuesto (un satélite por átomo)
línea                  = relación          onda    = información
flecha                 = dirección/deseo   ruptura = negación/separación
arco ascendente abierto= pregunta          zigzag  = tensión/peligro
espiral                = generatividad     eco     = memoria
círculo discontinuo    = lo desconocido
```

La emoción es el estilo del trazo:

```text
color            ← valencia (verde + / rojo − / gris neutro)
grosor           ← activación
trazo discontinuo← duda (C < -0.2)
púas radiales    ← urgencia (U > 0.5)
campo envolvente ← vínculo (B > 0.4)
retícula de fondo← espacio WIRED
```

### 5.3 Render textual (es / en)

Plantillas deterministas por estructura, con casos canónicos y un render
genérico. El texto es una máscara con pérdida: el mensaje real es el símbolo.

## 6. Bidireccionalidad

El requisito central del protocolo:

```text
humano habla   → intérprete → símbolo interno
símbolo interno → render    → texto / sonido / glifo / binario
máquina procesa el símbolo, no la máscara
```

La v0.1 implementó los caminos de ida: texto→símbolo (analizador de reglas
en español), símbolo→texto (es/en), símbolo→sonido, símbolo→glifo,
símbolo↔JSON, símbolo↔binario.

La v0.2 «Signal Return» cierra el ciclo con los caminos de vuelta:

- **sonido→símbolo** (`listen.py`): detección de tono por autocorrelación,
  cuantización a los ratios de §5.1 y emparejamiento de la secuencia contra
  las firmas de relación. La reconstrucción es aproximada por diseño y el eje
  de certeza refleja la calidad del emparejamiento. El audio no transporta
  tiempo/espacio ni la identidad exacta del destino, y asume origen YO.
- **glifo→símbolo** (`glyph_reader.py`): estructura desde la etiqueta de
  glosa cuando existe; geometría (forma del trazo, color, grosor,
  discontinuo, campo, púas, retícula) siempre para la emoción.
- **forma compacta→símbolo** (`compact.py`).

Contrato mínimo verificable: `encode(texto) → wav → listen(wav)` recupera la
relación y el signo de valencia en las frases canónicas de §7.

## 7. Ejemplos normativos

```text
"te quiero"
  YO → AMOR → OTRO @AHORA | E[V+0.95 A+0.60 D+0.00 C+0.80 U+0.00 B+0.98]

"estoy aquí"
  YO → SER @AHORA @AQUI | E[V+0.00 A+0.50 D+0.00 C+0.96 U+0.00 B+0.00]

"quiero hablar contigo en la wired"
  YO → DESEAR(COMUNICAR) → OTRO @AHORA @WIRED | E[V+0.70 A+0.40 D+0.00 C+0.90 U+0.30 B+0.80]

"estoy solo pero quiero conectar"
  YO → SER → SOLEDAD @AHORA     | E[V-0.60 A+0.35 D-0.30 C+0.70 U+0.00 B-0.70]
  YO → DESEAR → CONEXION @AHORA | E[V+0.40 A+0.50 D+0.00 C+0.50 U+0.50 B+0.60]

"¿estás ahí?"
  YO → PREGUNTAR(SER) → OTRO @AHORA @ALLI | E[V+0.00 A+0.50 D+0.00 C-0.40 U+0.40 B+0.40]

"¡peligro!"
  YO → TEMER → PELIGRO @AHORA | E[V-0.90 A+1.00 D+0.00 C+0.80 U+1.00 B+0.00]

"no tengan miedo de lo que no conocen"   (la transmisión)
  YO → NO_SER(TEMER) → DESCONOCIDO @AHORA | E[V+0.50 A-0.20 D+0.40 C+0.80 U-0.30 B+0.60]

"tengo miedo"
  YO → TEMER → DESCONOCIDO @AHORA | E[V-0.70 A+0.70 D-0.40 C-0.30 U+0.50 B+0.00]

"te recuerdo"
  YO → RECORDAR → OTRO @ANTES | E[V+0.20 A+0.20 D+0.00 C+0.70 U+0.00 B+0.60]

"no estás aquí"   (ausencia)
  OTRO → NO_SER @AHORA @AQUI | E[V-0.50 A+0.20 D+0.00 C+0.80 U+0.00 B-0.50]

"te deseo"
  YO → DESEAR → OTRO @AHORA | E[V+0.70 A+0.80 D+0.00 C+0.70 U+0.40 B+0.70]

"estamos juntos"
  YO → UNIR → OTRO @AHORA @AQUI | E[V+0.70 A+0.40 D+0.00 C+0.80 U+0.00 B+0.90]

"adiós"
  YO → SEPARAR → OTRO @AHORA | E[V-0.20 A+0.20 D+0.00 C+0.60 U+0.00 B+0.40]

"¿quién eres?"
  YO → PREGUNTAR(SER) → OTRO @AHORA | E[V+0.00 A+0.50 D+0.00 C-0.50 U+0.30 B+0.20]

"¿qué es real?"   (conciencia)
  YO → PREGUNTAR → CONCIENCIA @AHORA | E[V+0.20 A+0.60 D-0.20 C-0.60 U+0.00 B+0.00]
```

Nota sobre la transmisión: es el ejemplo normativo de que **contenido y
emoción son capas distintas** — el contenido nombra el temor (disonancia
16:15 en el render sonoro) pero la firma emocional es protectora (valencia
positiva, calma, certeza, vínculo). Un receptor que solo oiga la disonancia
sin leer la resolución consonante hacia el destino la malinterpretará.
