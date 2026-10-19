"""Tests de la sintaxis agnóstica (v0.5): el orden es estilo, no estructura."""

import random
import unittest

from echo_wsp.v05 import Message, Primitive, Symbol, encode, resolve
from echo_wsp.v05.grammar import (
    Field,
    FieldTag,
    SyntaxProfile,
    decode_tagged,
    encode_tagged,
    fields_of,
    normalize,
    sort_fields,
)
from echo_wsp.v05.primitives_science import Element, MASS, Quantity, SciPrimitive

P = Primitive


class TestCamposEtiquetados(unittest.TestCase):
    def test_descomponer_y_recomponer(self):
        original = encode("quiero hablar contigo en la wired").packets[0]
        recovered = normalize(fields_of(original))
        self.assertIs(recovered.source, original.source)
        self.assertEqual(recovered.relation.name, original.relation.name)
        self.assertEqual(recovered.action.name, original.action.name)
        self.assertEqual(recovered.space.name, original.space.name)
        self.assertEqual(recovered.emotion.to_dict(), original.emotion.to_dict())

    def test_el_orden_no_altera_el_significado(self):
        """La propiedad central de la v0.5: barajar los campos no rompe nada."""
        original = encode("quiero hablar contigo en la wired").packets[0]
        fields = fields_of(original)
        reference = normalize(fields).compact()
        rng = random.Random(20260714)
        for _ in range(12):
            shuffled = fields[:]
            rng.shuffle(shuffled)
            self.assertEqual(normalize(shuffled).compact(), reference)

    def test_el_orden_observado_se_conserva(self):
        """La sintaxis del hablante es información, no ruido."""
        fields = [
            Field(FieldTag.SPACE, P.AQUI),
            Field(FieldTag.TARGET, P.OTRO),
            Field(FieldTag.SOURCE, P.YO),
            Field(FieldTag.RELATION, P.OBSERVAR),
        ]
        symbol = normalize(fields)
        self.assertEqual(
            symbol.meta["grammar"]["order"], ["SPACE", "TARGET", "SOURCE", "RELATION"]
        )
        self.assertIs(symbol.source, P.YO)
        self.assertIs(symbol.space, P.AQUI)

    def test_etiquetas_conocen_su_ranura_y_eje(self):
        self.assertEqual(FieldTag.SOURCE.slot, "source")
        self.assertEqual(FieldTag.SPACE.slot, "space")
        self.assertIsNone(FieldTag.SOURCE.axis)
        self.assertEqual(FieldTag.EMO_BOND.axis, "bond")
        self.assertIsNone(FieldTag.EMO_BOND.slot)


class TestTramaEtiquetada(unittest.TestCase):
    def test_roundtrip_binario(self):
        original = encode("estoy solo pero quiero conectar")
        recovered = decode_tagged(encode_tagged(original))
        self.assertEqual(len(recovered.packets), 2)
        for got, want in zip(recovered.packets, original.packets):
            self.assertEqual(got.relation.name, want.relation.name)
            self.assertEqual(got.target.name, want.target.name)
            self.assertAlmostEqual(got.emotion.bond, want.emotion.bond, places=2)

    def test_la_cabecera_declara_la_version_etiquetada(self):
        data = encode_tagged(encode("te quiero"))
        self.assertEqual(data[:3], b"WSP")
        self.assertEqual(data[3], 0x02)
        with self.assertRaises(ValueError):
            decode_tagged(encode("te quiero").to_bytes())  # trama posicional v1

    def test_emitir_en_orden_ajeno_no_corrompe(self):
        """Si el otro pone el lugar primero, el paquete llega igual."""
        original = encode("quiero hablar contigo en la wired")
        alien_order = [
            FieldTag.SPACE, FieldTag.TIME, FieldTag.TARGET,
            FieldTag.ACTION, FieldTag.RELATION, FieldTag.SOURCE,
        ]
        data = encode_tagged(original, order=alien_order)
        recovered = decode_tagged(data)
        self.assertEqual(
            recovered.packets[0].compact().split(" | ")[0],
            original.packets[0].compact().split(" | ")[0],
        )
        self.assertEqual(recovered.packets[0].meta["grammar"]["order"][0], "SPACE")

    def test_campos_cientificos_en_la_trama(self):
        symbol = Symbol(
            source=P.OTRO,
            relation=P.SER,
            meta={"science": {
                "atoms": ["MASA"],
                "element": 6,
                "quantity": {"mantissa": 12011, "exponent": -3, "dimension": [0] * 7},
            }},
        )
        recovered = decode_tagged(encode_tagged(Message(packets=[symbol]))).packets[0]
        science = recovered.meta["science"]
        self.assertEqual(science["element"], 6)
        self.assertEqual(science["atoms"], ["MASA"])
        self.assertEqual(science["quantity"]["mantissa"], 12011)

    def test_campo_de_cantidad_con_dimension(self):
        quantity = Quantity.of(5.972e24, MASS)
        fields = [Field(FieldTag.QUANTITY, quantity), Field(FieldTag.SCI, SciPrimitive.MASA)]
        symbol = normalize(fields)
        message = decode_tagged(encode_tagged(Message(packets=[symbol])))
        spec = message.packets[0].meta["science"]["quantity"]
        self.assertEqual(spec["dimension"], list(MASS.as_tuple()))


class TestPerfilSintactico(unittest.TestCase):
    def test_aprende_el_orden_del_interlocutor(self):
        profile = SyntaxProfile(name="eridiano")
        alien_order = [FieldTag.SPACE, FieldTag.TARGET, FieldTag.RELATION, FieldTag.SOURCE]
        for _ in range(5):
            profile.observe(alien_order)
        self.assertEqual(profile.emission_order(), alien_order)
        self.assertEqual(profile.samples, 5)

    def test_responde_en_la_sintaxis_ajena(self):
        profile = SyntaxProfile(name="eridiano")
        alien_order = [FieldTag.SPACE, FieldTag.TIME, FieldTag.TARGET,
                       FieldTag.RELATION, FieldTag.SOURCE]
        profile.observe(alien_order)
        data = profile.render(encode("quiero hablar contigo en la wired"))
        recovered = decode_tagged(data)
        heard = recovered.packets[0].meta["grammar"]["order"]
        self.assertEqual(heard[0], "SPACE")
        self.assertIn("SOURCE", heard)
        # y el significado sobrevive intacto al cambio de sintaxis
        self.assertEqual(recovered.packets[0].relation.name, "DESEAR")

    def test_aprende_desde_mensajes_recibidos(self):
        profile = SyntaxProfile()
        message = decode_tagged(
            encode_tagged(encode("te quiero"), order=[FieldTag.TARGET, FieldTag.SOURCE])
        )
        profile.observe_message(message)
        self.assertGreater(profile.samples, 0)
        self.assertEqual(profile.emission_order()[0], FieldTag.TARGET)

    def test_sort_fields_respeta_la_sintaxis_pedida(self):
        fields = fields_of(encode("te quiero").packets[0])
        ordered = sort_fields(fields, [FieldTag.TARGET, FieldTag.SOURCE])
        self.assertEqual(ordered[0].tag, FieldTag.TARGET)
        self.assertEqual(ordered[1].tag, FieldTag.SOURCE)


if __name__ == "__main__":
    unittest.main()
