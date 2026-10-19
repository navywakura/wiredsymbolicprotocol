# Documentación de ECHO-WSP

| Versión | Contrato (antes de evaluar) | Resultados |
|---|---|---|
| LINK-3 (actual) | [LINK3-DESIGN.md](LINK3-DESIGN.md) | [LINK3-RESULTS.md](LINK3-RESULTS.md) |
| LINK-2 | [LINK2-DESIGN.md](LINK2-DESIGN.md) | [LINK2-RESULTS.md](LINK2-RESULTS.md) |
| LINK-1 | [LINK1-DESIGN.md](LINK1-DESIGN.md) | [LINK1-RESULTS.md](LINK1-RESULTS.md) |
| v0.5 (anterior) | [v0.5/SPEC.md](v0.5/SPEC.md), [v0.5/SPEC_V0.5.md](v0.5/SPEC_V0.5.md) | [v0.5/README.md](v0.5/README.md) |

Los contratos se fijaron por hash antes de cada evaluación
(`results/linkN/eval-preflight.json`) y se publican sin tocar, así que
citan las rutas del árbol de echoAI donde se escribieron. En este repo:

| En los documentos | Aquí |
|---|---|
| `echoai/link1`, `echoai/link2`, `echoai/link3` | `echo_wsp/link1`, `echo_wsp/link2`, `echo_wsp/link3` |
| `echoai/nexus0`, `navi10_*.py` | `echo_wsp/nexus0`, `echo_wsp/navi10_*.py` |
| `PYTHONPATH=. python3 -m echoai.link3.bench --split eval` | `python3 -m echo_wsp bench3 --split eval` |
| `lab/linkN/…` | `results/linkN/…` (lo publicado) y `echo_wsp/lab/linkN/…` (lo que generas al ejecutar) |
| `tests/test_linkN.py` | `tests/test_linkN.py`, adaptados; la custodia está en `tests/test_custody.py` |

Las evidencias de aire real de LINK-1 y LINK-2 se publican sin nombres ni
direcciones de los aparatos.
