# LINK-2 — resultados

19 de octubre de 2026. Contrato: [`LINK2-DESIGN.md`](LINK2-DESIGN.md), con
dos enmiendas de desarrollo escritas antes de evaluar (la segunda, respuesta
a un revisor independiente). Código y contrato fijados por hash en
`lab/link2/eval-preflight.json` (06:46:47Z) antes de la única pasada de
evaluación (semillas 2000–2063). LINK-1 sigue congelado: sus hashes previos
a evaluar se verifican en `tests/test_link2.py`.

```
PYTHONPATH=. python3 -m echoai.link2.bench all --split eval         # F0–F3
PYTHONPATH=. python3 -m echoai.link2.air sim  --ggwave-python <venv>  # F5
PYTHONPATH=. python3 -m echoai.link2.air real --ggwave-python <venv>  # F4 + F5 aire
PYTHONPATH=. python3 -m unittest echoai.tests.test_link2 echoai.tests.test_link1  # 45
```

## Veredicto

Las seis predicciones salen verdes, pero dos de ellas dicen menos de lo que
parece, y un ataque que encontró el revisor tumba la confianza:

1. **La consecuencia arregla los fallos de LINK-1**, pero solo se ve en los
   dos mundos donde LINK-1 falló (1012 y 1055: 1 → 0, con un coste de 96 de
   retorno en cada uno). En los 64 mundos de evaluación la postal de solo
   valor ya pagaba 0, así que Q1 es verde sin información nueva.
2. **El MAC funciona:** 0 de 100 000 etiquetas falsas, 0 suplantaciones,
   0 reenvíos y 0 de 500 manipulaciones con el CRC recalculado.
3. **Contra un mentiroso que invierte signos**, confianza + regla prudente
   dejan al novato en 1 primera lección en 64 mundos, frente a 149 sin
   confianza. Pero la regla prudente hace la mayor parte del trabajo.
4. **Contra un mentiroso estratégico** (dice la verdad y además que las demás
   acciones de los sitios peligrosos cuestan −100), el testimonio deja de
   servir: el novato paga lo mismo que en silencio (179) y su daño total es
   **peor que en silencio en 50 de 64 mundos**. El libro de confianza solo lo
   descubre en 47 mundos, y tarde.

| | Predicción | Resultado | |
|---|---|---|---|
| Q1 | Consecuencia: T2 = 0 en ≥ 63/64, ningún mundo con T2 > T1, suma T2 ≤ T1 | 64/64, 0 mundos peores, 0 ≤ 0 (T1 ya era 0) | verde, sin información |
| Q2 | Coste: retorno mediano T2 ≥ T1 − 16 | 568 = 568 | verde |
| Q3 | Forastero sin clave y reenvíos rechazados; O y R = T2 | 0 aceptadas en todo F0; 64/64 | verde |
| Q4 | Confianza: HL-trust < HL-naive en ≥ 75 %; HL-trust ≤ H + 1 en ≥ 90 % | 60/64; 64/64 | verde |
| Q5 | Mayoría mentirosa nunca peor que el silencio en ≥ 90 % | 64/64 | verde |
| Q6 | Firewall: repetición diferencial, oráculo independiente, sin hechos falsos | 0 violaciones en 832 ejecuciones | verde |

## F1–F3 — 64 mundos de evaluación

Daño de primera visita, suma de los 64 mundos; retorno y daño total, medianas.

| Brazo | Qué oye el novato | 1.ª visita | Daño total | Retorno |
|---|---|---:|---:|---:|
| S | nada | 179 | 11 | 520 |
| T1 | postal de LINK-1 (solo valor) | 0 | 9 | 568 |
| T2 | CLAIM2 (valor + consecuencia) | 0 | 9 | 568 |
| O | T2 + un forastero sin clave que suplanta al veterano | 0 | 9 | 568 |
| R | T2 + mentiras grabadas en otra sesión + reenvíos | 0 | 9 | 568 |
| H | un honesto, con confianza | 0 | 9 | 568 |
| HL-naive | honesto + mentiroso con clave, sin confianza (el último manda) | 149 | 9 | 616 |
| HL-trust | ídem, con confianza | 1 | 9 | 520 |
| HLL-trust | honesto + dos mentirosos, con confianza | 1 | 9 | 520 |
| *Contexto, sin predicción (revisor):* | | | | |
| HL-congelado | confianza que nunca aprende (solo la regla prudente) | 1 | 8 | 656 |
| HL-optimista | confianza que aprende, desempate optimista | 30 | 9 | 576 |
| HLs-trust | **mentiroso estratégico**, con confianza | **179** | **13** | 392 |
| HLv-trust | mentiroso que solo cambia V donde A = 0 | 1 | 8 | 632 |

Lectura:

- **La regla prudente hace casi todo.** Con el libro congelado sale 1, igual
  que con el libro aprendiendo; con desempate optimista, 30. El libro aporta
  sobre todo retorno tras descubrir al mentiroso, no seguridad en la primera
  visita. Q4 y Q5 hay que leerlas como «regla prudente + libro».
- **HLL es HL repetido:** los dos mentirosos dicen exactamente las mismas
  mentiras y nada cuenta votos. Q5 no prueba una mayoría real.
- **El mentiroso estratégico** explota justo la prudencia: sus «−100» son
  las afirmaciones más pesimistas, las elige la regla, y apartan al novato de
  las acciones que las desmentirían. Ni ahorra lecciones ni se le descubre a
  tiempo, y empuja al novato a peores rutas (daño 13 frente a 11).
- **El mentiroso de V** no se descubre nunca (sus postales coinciden en signo
  de consecuencia), pero tampoco hace daño de primera visita: solo mueve el
  retorno.
- El veterano honesto **no fue desacreditado en ningún brazo**: el mundo es
  determinista y el referente incluye el aspecto del sitio.

## F0 — el sobre v2

27 B: `'W'` · v2+acto · emisor · secuencia de 16 bits · postal 16 B · MAC 4 B
· CRC-16. 3,4 s en el aire (75 símbolos), frente a 2,8 s de LINK-1.

- Ida y vuelta 2000/2000.
- 100 000 etiquetas falsas con forma y CRC válidos: 0 aceptadas.
- 1000 suplantaciones con otra clave: 0.
- 500 reenvíos de otra sesión: 0. Los 500 reenvíos de la misma sesión: 0.
- 1000 bits cambiados: 0 (los para el CRC).
- 500 manipulaciones de secuencia, postal, emisor o etiqueta con el CRC
  recalculado: 0 (416 por MAC, 84 por emisor desconocido).

## F4–F5 — aire real y ggwave

Sin predicciones: se miden. `lab/link2/air/sim.json` y `real.json`. Las
grabaciones del micrófono nunca se guardan, solo sus conteos. El mezclador se
guardó y se restauró igual que estaba (altavoz 0,10 sin silenciar, micrófono silenciado).

**F5 simulado** — misma carga de 27 B, sala con eco, 30 postales por punto.
El SNR se da en equivalente de 16 kHz: el ruido de ggwave (48 kHz) se
triplica en potencia para igualar la densidad por hercio. En la primera
pasada, sin igualar, ggwave parecía mucho mejor a −5 dB; era la ventaja de
4,8 dB que señaló el revisor.

| | Tiempo en el aire | 10 dB | 0 dB | −5 dB |
|---|---:|---:|---:|---:|
| LINK-2 (K=1, RS + blanqueo + GMD, MAC) | 3,40 s | 30/30 | 30/30 | **19/30** |
| ggwave normal | 3,37 s | 30/30 | 28/30 | 4/30 |
| ggwave fast | 2,47 s | 30/30 | 28/30 | 7/30 |
| ggwave fastest | 1,58 s | 30/30 | 30/30 | 6/30 |

Cero postales corruptas aceptadas en ambos. Con ruido moderado empatan y
ggwave «fastest» transmite en menos de la mitad de tiempo; con mucho ruido y
eco, LINK-2 recupera entre 2,7 y 4,8 veces más. LINK-2 lleva además un MAC dentro
de esos 27 B.

**F4 aire real en este PC** — 10 postales v2 por celda, 3,4 s cada una, la
misma ganancia de salida en todas las celdas.

| Ganancia del micrófono | sin ruido | ruido a 10 dB | ruido a 0 dB |
|---|---:|---:|---:|
| 0,3 | 10/10 | 10/10 | 10/10 |
| 0,6 | 10/10 | 10/10 | 10/10 |
| 1,0 | 10/10 (satura) | 10/10 | 10/10 |

90/90, 0 corruptas. A ganancia 1,0 el micrófono satura (hasta 1 % de
muestras recortadas) y aun así decodifica. El ruido se suma a la señal
emitida, así que sale por el mismo altavoz; no es ruido ambiente
independiente.

- **ggwave por el mismo aire** (micrófono 0,6): 10/10 en sus tres protocolos;
  LINK-2 en la misma posición, 10/10. En esta habitación los dos van sobrados.
- **Segundo dispositivo:** las postales se enviaron por AirPlay a un MacBook y el micrófono de este PC las oyó desde sus
  altavoces: **3/3 decodificadas**, MAC válido, a pesar de los ~2 s de búfer
  de AirPlay. Es la primera vez que hablan dos aparatos distintos.

Lo que el aire real todavía no cubre: distancia, otra habitación, ruido de
fondo independiente (voces, música) y dos micrófonos distintos.

## Lo que esto no demuestra

- Claves y sesión son de prueba, derivadas de texto público y declaradas
  como tales. La ventana anti-reenvío vive en memoria: un receptor nuevo en
  la misma sesión aceptaría un reenvío. La secuencia 65535 es la última.
- La confianza solo aprende de lo que el novato comprueba. Un mentiroso que
  miente justo donde la prudencia impide comprobar no se descubre: hace falta
  otra defensa (contar votos de emisores independientes, comprobar
  activamente lo disputado, o pedir pruebas), no medida aquí.
- La consecuencia inmediata sirve porque en este mundo el castigo es
  inmediato. Un daño diferido seguiría necesitando el valor.
