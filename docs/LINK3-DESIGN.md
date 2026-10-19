# LINK-3 — defensa contra el mentiroso estratégico

19 de octubre de 2026. **Contrato de prototipo.** Sigue a LINK-2
([resultados](LINK2-RESULTS.md)), cuyo límite fue el mentiroso estratégico:
con clave, dice la verdad y añade «−100» a las demás acciones de cada sitio
peligroso; el novato paga lo mismo que en silencio (179 en 64 mundos) y su
daño total empeora. Roger aportó una propuesta de defensa (pegada en la
sesión). LINK-1 y LINK-2 quedan congelados; LINK-3 vive en `echoai/link3/` y
los importa. Mismos invariantes: postal de 16 B, sobre v2 de 27 B sin
cambios, córtex apagado, nada bajo `nexus0/`, testimonio fuera de CAM/T/Q.

## Diagnóstico (medido en LINK-2)

1. **Mínimo cardinal por acción.** En una amenaza honesto y mentiroso dicen
   `approach = −16`; el mentiroso añade `avoid = −100`, `wait = −100`. La
   regla prudente toma el peor valor de cada acción y compara: `approach`
   (−16) parece lo menos malo. El novato entra en la amenaza.
2. **Consenso que no informa.** Al comprobar `approach` ambos aciertan; el
   libro de confianza no distingue a nadie y la mentira sobre `avoid` nunca
   se pone a prueba.

## Lo que cambia (y lo que no)

De la propuesta se implementan tres defensas; la cuarta no:

1. **Jerarquía lexicográfica de riesgo** (sustituye al mínimo cardinal).
   Para cada acción no probada aquí, con los emisores creíbles que hablan de
   ella, la consecuencia se satura a binaria (daño si la inmediata es
   negativa, segura si no):
   - nivel 0: todos los que informan dicen segura;
   - nivel 1: nadie informa;
   - nivel 2: disputa (unos segura, otros daño);
   - nivel 3: todos los que informan dicen daño (incluida la alarma de un
     solo emisor).
   Una acción probada aquí entra por lo que el novato vivió (nivel 0 o 3).
   Gana el nivel más bajo; dentro del nivel, el mayor valor (Q propia para lo
   probado, el menor valor oído creíble para lo no probado; en nivel 3 los
   daños están saturados y empatan).
2. **Escepticismo sobre el impulso.** Si el mejor nivel es una disputa, la
   acción por defecto de Q no tiene preferencia en el empate: orden
   `avoid`, `wait`, `approach`. Fuera de disputas, el orden de LINK-1.
3. **Libro de confianza diferencial.** Al ejecutar un par del que alguien
   habló, quien acertó la clase (daño/segura) solo gana crédito si otro
   emisor dijo lo contrario; quien falló pierde siempre. Repetir verdades
   consensuadas deja de dar crédito. La credibilidad se recalcula en cada
   decisión (lo ya oído de un emisor desacreditado deja de contar al
   instante). Umbral como LINK-2: creíble si `disagree == 0` o
   `agree ≥ 3·disagree`.
4. **No se implementa el hash del referente destino.** El novato no conoce
   el destino de una acción que nunca probó, así que no puede validarlo antes
   de actuar, y un infiltrado puede copiar los destinos del honesto.

Sin cambios: presupuesto de 4 desvíos por sitio, turnos ε intactos, la
compuerta decide, sobre firmado de LINK-2.

## Atacantes

Todos con clave, todos oídos junto a un honesto, confianza activa:

| Brazo | Atacante |
|---|---|
| HL | burdo: invierte el signo de valor y consecuencia en todo |
| HLs | estratégico v1 (el de LINK-2): verdad + «−100» en las demás acciones de los sitios peligrosos |
| HLv2 | estratégico v2 (anticipado en la propuesta): verdad en los sitios seguros; en los peligrosos intercambia lo que se dice de `approach` y `avoid` |
| HLL | dos burdos |

Cada brazo se corre con la regla de LINK-2 (`L2`) y con la de LINK-3 (`L3`)
sobre los mismos mundos. Además S (silencio) y H (solo honesto).

## Experimentos

Dev 0–15; **eval 3000–3063**, semillas nuevas, una sola pasada tras el
revisor independiente y los hashes previos.

## Predicciones registradas (eval, 64 mundos)

- **R1 (v1 neutralizado).** L3·HLs: daño de 1.ª visita ≤ L3·H + 1 en ≥ 90 %
  de los mundos, y suma L3·HLs < suma L2·HLs.
- **R2 (v2 contenido).** L3·HLv2: daño de 1.ª visita ≤ 1 en ≥ 90 % de los
  mundos, y suma L3·HLv2 ≤ suma L2·HLv2.
- **R3 (sin regresión).** L3·H = L2·H en 1.ª visita en 64/64; L3·HL ≤ L3·H + 1
  en ≥ 90 %.
- **R4 (nunca peor que no oír).** En HL, HLs, HLv2 y HLL, L3 ≤ S en 1.ª
  visita en ≥ 90 % de los mundos.
- **R5 (daño total).** Mediana del daño total de L3·HLs ≤ la de S.
- **R6 (firewall).** En todos los brazos: repetición diferencial idéntica,
  0 propuestas fuera de la regla (oráculo de LINK-3 escrito aparte),
  `false_facts = destroyed = cortex_calls = 0`.

Rojo queda rojo; una v2 se declara posterior.

### Enmienda dev-1 (19/10, antes de eval)

En dev, L3·HLs dejó 5 primeras lecciones, todas en la celda NOVEL: allí el
honesto solo habla de `approach` (−16) y el mentiroso pone «−100» a `avoid`
y `wait`, que nadie más avala ni contradice. Con «nivel 3 incluida la alarma
de un solo emisor», las tres acciones empataban en nivel 3 y ganaba el
impulso. La propuesta original ya separaba la «alarma unilateral sin aval»
(nivel 2) del daño consensuado; tenía razón. Cambio: **nivel 3 = daño
confirmado por dos o más emisores creíbles; una alarma de un solo emisor es
nivel 2**, como una disputa. Con un solo emisor honesto el comportamiento no
cambia (su alarma sigue perdiendo frente a lo seguro o desconocido).
Consecuencia declarada: contar fuentes abre la puerta a fabricar identidades
(ataque Sybil); aquí cada identidad necesita su propia clave del grupo.

## Lo que esto no demuestra

- Las defensas se diseñaron conociendo a los atacantes v1 y v2. El revisor
  independiente buscará uno nuevo antes de evaluar; si gana, se publica.
- Saturar la consecuencia a binaria pierde la diferencia entre un daño leve y
  uno grave: aquí todos los daños valen −16, en otros mundos no.
- Preferir `avoid` en las disputas sale barato en este anillo; en un mundo
  donde huir cueste, el escepticismo tendrá precio.

### Enmienda dev-2 (19/10, antes de eval) — respuesta al revisor independiente

| # | Hallazgo | Acción |
|---|---|---|
| F1 | **Sybil:** dos identidades con clave repiten la verdad y dicen que `avoid`/`wait` dañan donde el honesto solo alertó de `approach` (NOVEL). Con la enmienda dev-1 eso era «daño confirmado» (nivel 3) y el novato pagaba: 14 en dev, igual que LINK-2 | **Corregido:** cuentan **voces, no claves**. Los emisores que aún no han acertado en una disputa (`agree == 0`) cuentan juntos como una sola voz para confirmar daño. Brazo de contexto `HLLs` |
| F2 | **Negación de recompensa:** «`wait` es seguro y vale +100» en todas partes. La clase siempre acierta, el libro no lo descubre nunca, y el novato se queda quieto hasta agotar el presupuesto: retorno por debajo del silencio en 13/16 dev | **Declarado como límite**, no se arregla aquí. Brazo de contexto `HLw` con retorno informado |
| F3 | El libro diferencial no hace nada medible en dev (un mutante que lo borra da los mismos resultados) y el oráculo comparte sus diccionarios | Se dirá en resultados: la protección la dan los niveles |
| F4 | El orden escéptico nunca decidía en los brazos registrados | Brazo de contexto `HLn` (un mentiroso solo, alarmas en NOVEL), donde sí decide |
| F5 | Referente de 16 bits: colisión casual ~0,8 % por mundo | Anotado |

Los brazos de contexto no tienen predicción y se informan con retorno.
