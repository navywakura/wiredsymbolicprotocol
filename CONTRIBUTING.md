# Contribuir a ECHO-WSP

Gracias por tu interés. ECHO-WSP es el lenguaje con el que se hablan los
agentes ECHO. La versión actual es LINK-3; la v0.5, el protocolo
simbólico-emocional, sigue en `echo_wsp/v05` como versión anterior.

## Reglas (léelas antes de tocar código)

1. **La postal WSP mide 16 bytes.** Lo nuevo va en el sobre, nunca dentro.
2. **El testimonio nunca es un hecho.** Nada de lo que un agente oye se
   escribe en su memoria CAM, en su modelo del mundo ni en su tabla Q.
   `tests/` lo comprueba con un gemelo sordo que debe terminar idéntico.
3. **Solo enteros en el camino rápido** (módem y decisión).
4. **Lo evaluado no se edita.** `echo_wsp/link1..3`, `nexus0` y `navi10_*`
   son el código que se midió (`tests/test_custody.py`). Una idea nueva va en
   una versión nueva (`echo_wsp/link4`, …) que importa a las anteriores.
5. **Contrato antes que código.** Una versión nueva empieza con
   `docs/LINKn-DESIGN.md`: qué cambia, atacantes y predicciones con números.
   Se fija por hash (`results/linkn/eval-preflight.json`), un revisor
   independiente intenta romperla y se evalúa una sola vez con semillas
   nuevas. Una predicción roja se publica en rojo.
6. **Sin dependencias de ejecución** fuera de la librería estándar.

## Flujo de trabajo

```bash
git clone https://github.com/navywakura/wiredsymbolicprotocol
cd wiredsymbolicprotocol
python3 -m unittest discover -s tests       # LINK-1/2/3 y custodia
python3 -m unittest discover -s tests/v05   # versión anterior
python3 -m echo_wsp demo                    # prueba de humo
```

Abre un Pull Request explicando qué se mide y qué predices, no solo qué
código tocas.

## Ideas especialmente bienvenidas

- Atacantes nuevos contra LINK-3 (`echo_wsp/link3/bench.py` tiene los
  actuales). El inflado del valor de esperar sigue sin defensa.
- Mundos donde equivocarse o huir cueste.
- Más máscaras físicas para la postal, con medidas en aire real.

## Licencia

Al contribuir aceptas que tu código se publique bajo la licencia
[Apache-2.0](LICENSE) del proyecto.
