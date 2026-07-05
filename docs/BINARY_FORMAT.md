# Formato binario de ROGEX-WSP v0.1

El render binario es la máscara de más bajo nivel del protocolo: compacta,
autocontenida y decodificable sin diccionario externo. Esta página detalla el
formato byte a byte; la visión general está en [`SPEC.md`](SPEC.md) §3.3.

## Estructura general

```text
┌─────────────┬──────────┬────────────┬──────────────────────────┐
│ magic "WSP" │ versión  │ nº paquetes│ paquete 1 … paquete N    │
│ 3 bytes     │ 1 byte   │ 1 byte     │ longitud variable        │
│ 57 53 50    │ 01       │ 01..FF     │                          │
└─────────────┴──────────┴────────────┴──────────────────────────┘
```

## Estructura de un paquete

```text
┌────────┬──────────────────────────────┬──────────────┐
│ flags  │ conceptos presentes, en orden│ emoción      │
│ 1 byte │ longitud variable            │ 6 bytes      │
└────────┴──────────────────────────────┴──────────────┘
```

### El byte de flags

Cada bit indica la presencia de una ranura. Los conceptos aparecen después
**en el orden de los bits**:

| Bit | Máscara | Ranura |
|----:|---------|--------|
| 0 | `0x01` | source (origen) |
| 1 | `0x02` | relation (relación) |
| 2 | `0x04` | action (acción anidada) |
| 3 | `0x08` | target (destino) |
| 4 | `0x10` | time (tiempo) |
| 5 | `0x20` | space (espacio) |

### Codificación de un concepto

**Primitivo** (átomo del núcleo): 1 byte con su código `0..31` (bit alto a 0).

**Derivado** (concepto compuesto): viaja con su composición y su nombre, para
que un receptor que no lo conozca lo aprenda del propio mensaje
(*generatividad por el cable*):

```text
┌──────────────┬───────────────────┬──────────────┬─────────────┐
│ 0x80 | n     │ n códigos de átomo│ long. nombre │ nombre UTF-8│
│ 1 byte       │ n bytes           │ 1 byte       │ 0..255 bytes│
└──────────────┴───────────────────┴──────────────┴─────────────┘
```

donde `n` (5 bits bajos) es el número de átomos componentes (1..31).

### La emoción

6 bytes **con signo** (two's complement), cada eje multiplicado por 100
(rango efectivo `-100..+100`), siempre en este orden:

```text
V (valencia) · A (activación) · D (dominancia) · C (certeza) · U (urgencia) · B (vínculo)
```

## Ejemplo anotado: «te quiero»

`wsp binary --text "te quiero"` produce 24 bytes:

```text
57 53 50 01 01 1b 02 83 00 03 0b 04 41 4d 4f 52 03 08 5f 3c 00 50 00 62
```

| Bytes | Significado |
|-------|-------------|
| `57 53 50` | magic `"WSP"` |
| `01` | versión 1 del formato binario |
| `01` | 1 paquete |
| `1b` | flags `0b011011`: source + relation + target + time (sin action ni space) |
| `02` | source = átomo 2 = **YO** |
| `83` | relation: `0x80 \| 3` → derivado con 3 átomos |
| `00 03 0b` | componentes: SER (0) + OTRO (3) + UNIR (11) |
| `04` | nombre de 4 bytes |
| `41 4d 4f 52` | `"AMOR"` en UTF-8 |
| `03` | target = átomo 3 = **OTRO** |
| `08` | time = átomo 8 = **AHORA** |
| `5f 3c 00 50 00 62` | emoción: V+0.95, A+0.60, D+0.00, C+0.80, U+0.00, B+0.98 |

Es decir: `YO → AMOR → OTRO @AHORA | E[V+0.95 A+0.60 D+0.00 C+0.80 U+0.00 B+0.98]`
— y AMOR viaja con su definición (`SER+OTRO+UNIR`), así que cualquier receptor
puede decodificarlo aunque nunca haya visto ese concepto.

## Decodificación de derivados

Al leer un derivado, el receptor:

1. Lee los `n` átomos componentes y el nombre.
2. Si el nombre ya está en su registro, usa su definición local.
3. Si no, **lo registra** con los componentes recibidos: a partir de ese
   momento el concepto existe para él (implementación de referencia:
   `symbol.py::_decode_concept`).

## Límites del formato v0.1

- Máx. **255 paquetes** por mensaje (contador de 1 byte).
- Máx. **31 átomos** por concepto derivado (5 bits del byte de cabecera).
- Máx. **255 bytes** de nombre UTF-8 por concepto.
- La resolución emocional es de **0.01** por eje (bytes con signo ×100).
- Los campos `meta` del JSON **no viajan** en binario (la máscara binaria
  transporta solo significado, no procedencia).

Implementación de referencia: `rogex_wsp/symbol.py`
(`Symbol.to_bytes`, `Symbol.from_bytes`, `Message.to_bytes`, `Message.from_bytes`).
Tests de ida y vuelta: `tests/test_core.py::TestSymbolSerialization` y
`TestGenerativity`.
