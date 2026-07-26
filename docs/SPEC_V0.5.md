# Especificación ROGEX-WSP v0.5 — «Project Hail Mary»

Extensión para **contacto exótico**: comunicación con un emisor cuya
biología, canal, vocabulario y sintaxis no compartimos.

Hasta la v0.4 el protocolo presuponía tres cosas que un primer contacto
real no concede:

| Presupuesto de v0.1–v0.4 | Realidad del contacto exótico |
|---|---|
| El canal es una **melodía** de tonos sucesivos | El otro puede hablar en **acordes simultáneos** |
| Los 32 átomos ya están **mapeados** de origen | No hay diccionario: hay que **construirlo midiendo** |
| El vocabulario es **relacional y emocional** | La primera conversación útil es **física y matemática** |
| El orden de los campos es **estructura** | El orden es **la sintaxis del hablante**, y es suya |

La v0.5 elimina los cuatro presupuestos sin tocar el núcleo congelado.
La fórmula no cambia:

```text
L = G[S(M, I, E)]
```

Cambia el alcance de cada capa:

```text
M  gana una máscara polifónica (acordes)          → multiphonic.py
I  gana un plano científico (códigos 32..127)     → primitives_science.py
S  gana campos autoetiquetados, orden libre       → grammar.py
   y una capa previa de descubrimiento fonético   → discovery.py
```

---

## 1. Sintaxis agnóstica (`grammar.py`)

### 1.1 Etiquetas de campo

Cada campo del paquete viaja con su etiqueta de 4 bits. Los mismos
códigos etiquetan la trama binaria y el acorde acústico: polifonía y
sintaxis libre son la misma idea en dos planos.

| Código | Etiqueta | Carga |
|-------:|----------|-------|
| 0 | `CONT` | continuación: añade 5 bits a la carga anterior |
| 1–6 | `SOURCE` `RELATION` `ACTION` `TARGET` `TIME` `SPACE` | concepto |
| 7–12 | `EMO_VALENCE` … `EMO_BOND` | un eje emocional |
| 13 | `QUANTITY` | cantidad física |
| 14 | `ELEMENT` | número atómico Z |
| 15 | `SCI` | átomo del plano científico |

### 1.2 Trama binaria etiquetada (versión 0x02)

```text
"WSP" | 0x02 | nº paquetes
por paquete:  nº campos | campo…
campo:        etiqueta (1 byte) | carga (según etiqueta)
```

La trama posicional de v0.1 (versión 0x01) sigue siendo válida y se lee
con `Message.from_bytes`; la etiquetada se lee con `decode_tagged`. Un
decodificador comprueba el byte de versión y no confunde una con otra.

**Propiedad normativa:** para todo permutación π de los campos de un
paquete, `normalize(π(fields))` produce el mismo símbolo. El orden no
puede alterar el significado.

### 1.3 El orden como dato

El orden observado se conserva en `meta.grammar.order`. No es ruido:
es la firma sintáctica del hablante. `SyntaxProfile` la acumula y
devuelve `emission_order()`, que permite **responder en la sintaxis del
otro** — el equivalente protocolario de la cortesía.

---

## 2. Capa M polifónica (`multiphonic.py`)

### 2.1 Retícula del acorde

Un acorde transporta un campo entero. Todas las voces suenan a la vez,
sobre la raíz f₀ **del propio acorde**:

| Slot | Ratio | Función |
|-----:|-------|---------|
| 0 | 1/1 | raíz / portadora (siempre presente, define f₀) |
| 1–4 | 9/8 · 5/4 · 3/2 · 15/8 | etiqueta, bits 0–3 |
| 5–9 | 9/4 · 5/2 · 3/1 · 15/4 · 9/2 | carga, bits 0–4 |
| 10 | 5/1 | paridad par sobre los 9 bits de datos |

Como todo en WSP, la retícula es de **ratios**: f₀ puede ser cualquier
frecuencia. La misma frase emitida a 120, 180 o 260 Hz produce el mismo
símbolo (verificado en `test_multiphonic.py`).

### 2.2 Cargas mayores de 5 bits

Se reparten en acordes `CONT` consecutivos:

```text
átomo científico  →  SCI(código≫5)      + CONT(código&31)
elemento          →  ELEMENT(Z≫5)       + CONT(Z&31)
cantidad          →  QUANTITY(nº bytes) + CONT×n (troceo de 5 bits)
concepto derivado →  SLOT(átomo₀)       + CONT(átomo₁) + CONT(átomo₂)…
```

El último caso es el más significativo: **un concepto derivado viaja
como su composición, no como su nombre**. `AMOR` cruza el canal como
`SER + OTRO + UNIR`; el receptor lo reconoce por composición, y si no lo
conoce, lo aprende (generatividad por el cable, ya presente desde v0.1).

### 2.3 Emoción por el canal polifónico

Cada eje emocional es un acorde con su etiqueta y 5 bits de carga:
`valor = (carga − 15) / 15`, es decir 31 niveles y **resolución 0.067**.
Es más basta que los 0.01 de la trama binaria: la máscara acústica pierde
precisión emocional, y eso se documenta en vez de disimularse.

### 2.4 Paridad y duda

Un fallo de paridad **no descarta el paquete**: rebaja el eje de certeza
proporcionalmente a los acordes dañados. La duda es un valor del
protocolo, no un error fatal.

### 2.5 Límite conocido

El decodificador estricto asume que los parciales de la retícula se
emiten a amplitud comparable. Una fuente natural con serie armónica
propia (una voz orgánica real) puede añadir energía en 2f₀, 3f₀, 4f₀ y
disparar bits de carga espurios. **Ese caso no lo resuelve
`multiphonic.py` sino `discovery.py`**, que no presupone retícula alguna.
La máscara polifónica es para transporte WSP↔WSP y para responder a un
emisor exótico; escuchar a un emisor exótico es trabajo del módulo de
descubrimiento.

---

## 3. Plano científico (`primitives_science.py`)

### 3.1 Regla de extensión

El núcleo de 32 átomos **no se toca**: es un contrato binario de 5 bits.
El plano científico ocupa los códigos **32..127** (el bit 0x80 sigue
reservado al marcador de concepto derivado). Un decodificador antiguo que
reciba un código ≥32 falla de forma ruidosa en vez de interpretar mal.

### 3.2 Magnitudes y dimensiones

`Dimension` es un vector de 7 exponentes SI —M, L, T, Θ, I, N, J— que se
multiplica, divide y eleva. Es la parte de una magnitud que **no depende
de la especie**: dos civilizaciones sin unidades comunes comparten
igualmente que una velocidad es L·T⁻¹ y una energía M·L²·T⁻².

```python
MASS * SPEED * SPEED == ENERGY        # M·L²·T⁻²
Quantity.of(3.0, MASS).compare(Quantity.of(3.0, LENGTH))   # ValueError
```

Comparar magnitudes de dimensión distinta es un **error de protocolo**,
no una opinión: `compare()` lanza `ValueError`. El análisis dimensional
es el primer verificador de sentido que dos especies pueden compartir.

### 3.3 Cantidades

`Quantity` = mantisa entera × 10^exponente + dimensión. La mantisa es un
**entero binario**, no una cadena de dígitos: la codificación es
independiente de la base numérica del emisor. Una especie que cuente en
base 6 lee el mismo entero desde los mismos bits.

```text
cabecera (signo+longitud) | mantisa BE | exponente | dimensión (7 bytes)
```

### 3.4 Elementos

**Un elemento es su número atómico.** `Element(6)` no "significa"
carbono: *es* Z=6. Las cadenas `"C"`, `"carbono"`, `"carbon"` son
máscaras humanas, igual que `"te quiero"` es la máscara de un paquete
simbólico. Z es universal porque cualquier especie que haya hecho química
cuenta los mismos protones. Un byte, sin vocabulario.

---

## 4. Descubrimiento fonético (`discovery.py`)

El módulo que elimina el presupuesto del diccionario compartido.

### 4.1 Firma invariante a la altura

Cada evento sonoro se mide (picos espectrales con interpolación
parabólica) y se describe como el conjunto de sus parciales **relativos a
su propia raíz**, cuantizados en buckets de 30 cents:

```python
fingerprint = tuple(sorted(round(1200·log₂(rᵢ) / 30)))
```

Sin esa invariancia no hay diccionario posible: el emisor no controla su
registro y una misma emisión una octava más arriba parecería otra
palabra. Verificado: la misma emisión a 190, 265 y 380 Hz produce una
sola firma.

### 4.2 Ciclo de aprendizaje

```text
observe(wav)              → [Observation]      medir
cluster(observations)     → [Signature]        lo que se repite es vocabulario
learn_from_sequence(…)    → ataduras           el método de la piedra Rosetta
save/load(mapping.json)   → persistencia       el diccionario de Grace
decode_with_map(wav, map) → Message            ya se entiende
```

`learn_from_sequence` **exige que el número de eventos y el de conceptos
coincida**: alinear una emisión de 6 eventos con 4 conceptos sería una
suposición disfrazada de dato, y el módulo se niega (`ValueError`).

### 4.3 La cobertura es certeza

`decode_with_map` fija el eje de certeza en `2·cobertura − 1`: entender
la mitad de una emisión produce certeza 0, no un mensaje afirmado a
ciegas. Las firmas no reconocidas se listan en `meta.discovery.unknown`.

### 4.4 Asignación de ranuras

El emisor exótico no habla nuestra gramática, así que sus átomos se
reparten por **categoría**: entidades a origen/destino, relaciones a
relación/acción, tiempo y espacio a los suyos, y lo científico al plano
de extensión. Es una heurística declarada, no una traducción.

---

## 5. Flujo completo

`examples/hail_mary.py` ejecuta el arco entero con audio real:

```text
1. el otro habla              → 01_leccion.wav      (acordes ajenos a la retícula)
2. medir y atar               → mapping.json        (6 firmas → átomos)
3. habla espontánea           → 03_pregunta.wav     (otra octava, otro orden)
   decodificación             → OTRO → PREGUNTAR @AQUI, science{Z=6, MASA}
4. máscara humana             → «¿Preguntas por la masa del carbono aquí?»
                              → 04_recibido.svg
5. respuesta polifónica       → 05_respuesta.wav    (27 acordes, sintaxis del otro)
6. lectura de la respuesta    → Z=6, 12.011, 0 errores de paridad
```

El significado sobrevive al viaje por **dos máscaras físicas distintas**
(acordes exóticos de entrada, acordes WSP de salida) y **dos sintaxis
ajenas entre sí**.

---

## 6. Comandos

```bash
wsp chord --text "te quiero" -o poly.wav   # símbolo → acordes polifónicos
wsp chord poly.wav --compact               # acordes → símbolo
wsp calibrate exotico.wav -o mapping.json --lesson "YO,OBSERVAR,OTRO"
wsp map mapping.json --bind SIG-03=MASA    # atadura manual
wsp xeno exotico.wav --map mapping.json    # audio exótico → símbolo
python3 examples/hail_mary.py              # flujo completo
```

---

## 7. Lo que la v0.5 **no** resuelve

Declararlo importa tanto como lo implementado:

- **Audio orgánico real.** Las pruebas usan señales sintéticas limpias.
  Una voz biológica trae ruido, formantes y serie armónica propia; la
  detección de picos tendría que endurecerse (§2.5).
- **Aprendizaje no supervisado.** `learn_from_sequence` necesita un
  contexto conocido. Correlacionar firmas con significados **sin**
  contexto —lo que haría un descifrador puro— sigue abierto.
- **Números en la lengua del otro.** WSP emite cantidades en su propio
  formato; leer los numerales del emisor exótico exigiría descubrir
  primero su sistema numérico. En la novela ese paso lleva semanas.
- **Gramática compuesta.** Un paquete sigue siendo una relación entre
  dos términos. Las subordinadas y las referencias entre paquetes son
  trabajo de v0.6.
