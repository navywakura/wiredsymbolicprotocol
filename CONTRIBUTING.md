# Contribuir a ROGEX-WSP

Gracias por tu interés. ROGEX-WSP es un protocolo experimental de comunicación
simbólico-emocional: un núcleo de significado, muchas máscaras físicas. Las
contribuciones son bienvenidas si respetan esa arquitectura.

## Reglas de arquitectura (léelas antes de tocar código)

1. **El núcleo de 32 átomos es estable.** No se añaden primitivos nuevos a
   `primitives.py`: los 32 caben en 5 bits y eso es parte del contrato binario.
   Si crees que falta un concepto, casi seguro se expresa como **concepto
   derivado** (capa G, `concepts.py`) componiendo átomos existentes.
2. **El significado no vive en la máscara.** Los renderizadores (texto, audio,
   glifo, binario) son intercambiables y no pueden guardar estado semántico
   propio. Todo significado nuevo entra por el paquete simbólico.
3. **Cero dependencias en el núcleo.** `rogex_wsp/` usa solo la librería
   estándar de Python. Herramientas de desarrollo (linters, etc.) son
   negociables; dependencias de ejecución, no.
4. **Todo cambio de formato es cambio de especificación.** Si tocas el JSON,
   la forma compacta o el binario, actualiza `docs/SPEC.md` y
   `docs/BINARY_FORMAT.md` en el mismo PR, y añade tests de ida y vuelta.

## Flujo de trabajo

```bash
git clone https://github.com/n4vv4r/RogexWSP
cd RogexWSP
python3 -m unittest discover -s tests   # todo debe estar en OK antes y después
python3 -m rogex_wsp demo               # humo: genera JSON + WAV + SVG
```

- Crea una rama desde `main`, haz cambios pequeños y enfocados.
- Añade tests para cualquier comportamiento nuevo (usamos `unittest`, sin
  pytest ni dependencias).
- Abre un Pull Request explicando **qué significado** aporta el cambio, no solo
  qué código toca.

## Ideas especialmente bienvenidas

- Conceptos derivados nuevos con buena justificación semántica y firma
  emocional (ver `concepts.py` y `examples/nostalgia_definida.json`).
- Frases canónicas nuevas para el intérprete (`text_to_symbol.py`) con sus
  tests de ida y vuelta.
- Avances de la hoja de ruta v0.2 (`docs/ROADMAP.md`): sonido→símbolo,
  glifo→símbolo, JSON Schema, demo web.

## Licencia

Al contribuir aceptas que tu código se publique bajo la licencia
[Apache-2.0](LICENSE) del proyecto.
