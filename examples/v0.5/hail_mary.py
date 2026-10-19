#!/usr/bin/env python3
"""Flujo completo v0.5: primer contacto con un emisor exótico.

Reproduce el arco de Grace y Rocky de principio a fin, con audio real:

    1. El otro habla. No compartimos diccionario, ni retícula, ni sintaxis.
    2. Se miden sus emisiones y se agrupan las firmas que se repiten.
    3. Una lección con contexto conocido ata firmas a átomos de WSP.
    4. El otro habla espontáneamente, en otro registro y en su orden:
       ahora se entiende, y se proyecta en máscara humana (texto y glifo).
    5. Se responde en polifonía —un acorde por campo— y **en la sintaxis
       aprendida del otro**, no en la nuestra.
    6. Se decodifica la propia respuesta para probar que el canal cierra.

    python3 examples/v0.5/hail_mary.py [-o directorio]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from echo_wsp.v05 import Message, Primitive as P, Symbol, render_message, render_svg_file
from echo_wsp.v05.discovery import PhoneticMap, decode_with_map, observe, write_exotic
from echo_wsp.v05.grammar import FieldTag, SyntaxProfile, decode_tagged
from echo_wsp.v05.multiphonic import listen_chords, render_wav, symbol_to_chords
from echo_wsp.v05.primitives_science import Dimension, Element, Quantity

# La voz del otro: acordes que no pertenecen a ninguna retícula conocida.
# Cada entrada es el conjunto de parciales relativos a su propia raíz.
ERIDIANO: dict[str, tuple[float, ...]] = {
    "YO": (1.0, 1.32, 1.79),
    "OTRO": (1.0, 1.19, 2.38),
    "PREGUNTAR": (1.0, 1.73, 2.34),
    "AQUI": (1.0, 1.41),
    "MASA": (1.0, 1.26, 1.58, 2.51),
    "CARBONO": (1.0, 1.87, 2.16),
}


def paso(numero: int, titulo: str) -> None:
    print(f"\n\033[1m── {numero}. {titulo}\033[0m")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", default="hail_mary_out", help="directorio de salida")
    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)
    out = lambda name: os.path.join(args.output, name)

    # ------------------------------------------------------------------
    paso(1, "El otro habla y no entendemos nada")
    # Enuncia mientras señala: sabemos QUÉ señala, no cómo lo llama.
    leccion = [
        (ERIDIANO["YO"], 210.0),
        (ERIDIANO["OTRO"], 198.0),
        (ERIDIANO["AQUI"], 215.0),
        (ERIDIANO["PREGUNTAR"], 204.0),
        (ERIDIANO["MASA"], 207.0),
        (ERIDIANO["CARBONO"], 201.0),
    ]
    write_exotic(leccion, out("01_leccion.wav"))
    observaciones = observe(out("01_leccion.wav"))
    print(f"   {len(observaciones)} eventos sonoros medidos en 01_leccion.wav")
    for o in observaciones[:3]:
        print(f"     {o.notation()}")
    print("     …")

    # ------------------------------------------------------------------
    paso(2, "Se atan las firmas a átomos de WSP (piedra Rosetta)")
    contexto = ["YO", "OTRO", "AQUI", "PREGUNTAR", "MASA", "carbono"]
    mapa = PhoneticMap(speaker="eridiano")
    atadas = mapa.learn_from_sequence(observaciones, contexto)
    mapa.save(out("mapping.json"))
    print(f"   {atadas} firmas atadas · mapping.json escrito")
    print("   " + mapa.report().replace("\n", "\n   "))

    # ------------------------------------------------------------------
    paso(3, "El otro pregunta, espontáneo, una octava más arriba y en su orden")
    # Su sintaxis pone el lugar primero y el sujeto al final. No importa.
    pregunta = [
        (ERIDIANO["AQUI"], 432.0),
        (ERIDIANO["CARBONO"], 415.0),
        (ERIDIANO["MASA"], 428.0),
        (ERIDIANO["PREGUNTAR"], 405.0),
        (ERIDIANO["OTRO"], 396.0),
    ]
    write_exotic(pregunta, out("03_pregunta.wav"))
    recibido = decode_with_map(out("03_pregunta.wav"), PhoneticMap.load(out("mapping.json")))
    simbolo = recibido.packets[0]
    diagnostico = simbolo.meta["discovery"]
    print(f"   símbolo   : {simbolo.compact()}")
    print(f"   cobertura : {diagnostico['coverage']:.0%} de la emisión entendida")
    print(f"   ciencia   : {simbolo.meta.get('science')}")

    # ------------------------------------------------------------------
    paso(4, "Máscara humana: la interfaz de Grace")
    print(f"   texto es  : {render_message(recibido, 'es')}")
    print(f"   texto en  : {render_message(recibido, 'en')}")
    render_svg_file(recibido, out("04_recibido.svg"))
    print(f"   glifo     : {out('04_recibido.svg')}")
    elemento = Element(simbolo.meta["science"]["element"])
    print(f"   pregunta por Z={elemento.Z} ({elemento.name()}) y por su masa")

    # ------------------------------------------------------------------
    paso(5, "La nave responde: polifonía, y en la sintaxis del otro")
    perfil = SyntaxProfile(name="eridiano")
    perfil.observe([FieldTag[n] for n in simbolo.meta["grammar"]["order"]])
    masa = elemento.atomic_mass()
    respuesta = Message(packets=[Symbol(
        source=P.YO,
        relation=P.RESPONDER,
        target=P.OTRO,
        space=P.AQUI,
        meta={"science": {
            "atoms": ["MASA"],
            "element": elemento.Z,
            "quantity": {
                "mantissa": masa.mantissa,
                "exponent": masa.exponent,
                "dimension": list(Dimension().as_tuple()),
            },
        }},
    )])
    orden = perfil.emission_order()
    acordes = symbol_to_chords(respuesta.packets[0], order=orden)
    render_wav(respuesta, out("05_respuesta.wav"), base=200.0, order=orden)
    print(f"   sintaxis aprendida : {' → '.join(t.name for t in orden)}")
    print(f"   {len(acordes)} acordes emitidos en 05_respuesta.wav")
    for acorde in acordes[:4]:
        print(f"     {acorde.notation()}")
    print("     …")

    # ------------------------------------------------------------------
    paso(6, "Se cierra el canal: leemos nuestra propia respuesta")
    vuelta = listen_chords(out("05_respuesta.wav"))
    leido = vuelta.packets[0]
    ciencia = leido.meta["science"]
    cantidad = Quantity(
        ciencia["quantity"]["mantissa"],
        ciencia["quantity"]["exponent"],
        Dimension(*ciencia["quantity"]["dimension"]),
    )
    print(f"   símbolo   : {leido.compact()}")
    print(f"   Z         : {ciencia['element']}  ({Element(ciencia['element']).symbol})")
    print(f"   cantidad  : {cantidad.notation()}  (esperado {masa.value})")
    print(f"   paridad   : {leido.meta['polyphonic']['parity_errors']} errores "
          f"en {leido.meta['polyphonic']['chords']} acordes")

    correcto = (
        ciencia["element"] == elemento.Z
        and abs(cantidad.value - masa.value) < 1e-6
        and leido.meta["polyphonic"]["parity_errors"] == 0
    )
    print(f"\n   \033[1m{'canal íntegro' if correcto else 'CANAL DEGRADADO'}\033[0m: "
          f"el significado sobrevivió al viaje por dos máscaras físicas distintas "
          f"y por dos sintaxis ajenas entre sí.")
    print(f"\n   archivos en {args.output}/")
    return 0 if correcto else 1


if __name__ == "__main__":
    raise SystemExit(main())
