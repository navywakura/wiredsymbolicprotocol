# Changelog

Todos los cambios notables de ROGEX-WSP se documentan aquí.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado sigue [SemVer](https://semver.org/lang/es/).

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

[0.1.0]: https://github.com/n4vv4r/RogexWSP/releases/tag/v0.1.0
