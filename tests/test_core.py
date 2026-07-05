"""Tests del núcleo: átomos, emoción, paquete simbólico y serialización."""

import unittest

from rogex_wsp import (
    Emotion,
    Message,
    Primitive,
    Symbol,
    define,
    is_builtin,
    resolve,
)


class TestPrimitives(unittest.TestCase):
    def test_hay_exactamente_32_atomos(self):
        self.assertEqual(len(Primitive), 32)

    def test_codigos_unicos_de_5_bits(self):
        codes = sorted(p.code for p in Primitive)
        self.assertEqual(codes, list(range(32)))

    def test_lookup_tolerante(self):
        self.assertIs(Primitive.lookup("aquí"), Primitive.AQUI)
        self.assertIs(Primitive.lookup("AQUI"), Primitive.AQUI)
        self.assertIs(Primitive.lookup("here"), Primitive.AQUI)
        self.assertIs(Primitive.lookup("no-ser"), Primitive.NO_SER)
        self.assertIsNone(Primitive.lookup("xyzzy"))


class TestEmotion(unittest.TestCase):
    def test_clamp(self):
        e = Emotion(valence=3.0, bond=-9.0)
        self.assertEqual(e.valence, 1.0)
        self.assertEqual(e.bond, -1.0)

    def test_dict_roundtrip_claves_cortas_y_largas(self):
        e = Emotion(valence=0.7, certainty=0.9, bond=0.8)
        self.assertEqual(Emotion.from_dict(e.to_dict()), e)
        self.assertEqual(Emotion.from_dict({"V": 0.7, "C": 0.9, "B": 0.8}), e)

    def test_describe(self):
        e = Emotion(valence=0.9, arousal=0.6, bond=0.95)
        self.assertEqual(e.describe("es"), "positivo, intenso, cercano")
        self.assertEqual(Emotion().describe("es"), "neutro")

    def test_signature(self):
        self.assertIn("V+0.95", Emotion(valence=0.95).signature())


class TestSymbolSerialization(unittest.TestCase):
    def _packet(self) -> Symbol:
        return Symbol(
            source=Primitive.YO,
            relation=Primitive.DESEAR,
            action=resolve("COMUNICAR"),
            target=Primitive.OTRO,
            time=Primitive.AHORA,
            space=resolve("WIRED"),
            emotion=Emotion(valence=0.7, arousal=0.4, certainty=0.9, urgency=0.3, bond=0.8),
        )

    def test_json_roundtrip(self):
        message = Message(packets=[self._packet()])
        recovered = Message.from_json(message.to_json())
        packet = recovered.packets[0]
        self.assertIs(packet.source, Primitive.YO)
        self.assertEqual(packet.action.name, "COMUNICAR")
        self.assertEqual(packet.space.name, "WIRED")
        self.assertAlmostEqual(packet.emotion.bond, 0.8)

    def test_json_forma_de_paquete_unico(self):
        raw = """
        {
          "protocol": "rogex-wsp", "version": "0.1",
          "symbol": {"source": "self", "relation": "exist", "space": "here", "time": "now"},
          "emotion": {"certainty": 0.96}
        }
        """.replace("exist", "ser").replace("self", "yo")
        message = Message.from_json(raw)
        self.assertEqual(len(message.packets), 1)
        self.assertIs(message.packets[0].space, Primitive.AQUI)

    def test_binario_roundtrip(self):
        message = Message(packets=[self._packet()])
        data = message.to_bytes()
        self.assertEqual(data[:3], b"WSP")
        recovered = Message.from_bytes(data)
        packet = recovered.packets[0]
        self.assertIs(packet.target, Primitive.OTRO)
        self.assertEqual(packet.action.name, "COMUNICAR")
        self.assertAlmostEqual(packet.emotion.valence, 0.7, places=2)

    def test_compact(self):
        compact = self._packet().compact()
        self.assertIn("YO → DESEAR(COMUNICAR) → OTRO", compact)
        self.assertIn("@WIRED", compact)
        self.assertIn("E[", compact)

    def test_atoms_descompone_derivados(self):
        atoms = self._packet().atoms()
        self.assertIn(Primitive.UNIR, atoms)      # de COMUNICAR y WIRED
        self.assertIn(Primitive.PREGUNTAR, atoms)  # de COMUNICAR


class TestGenerativity(unittest.TestCase):
    def test_definir_concepto_nuevo(self):
        nostalgia = define(
            "NOSTALGIA_TEST",
            [Primitive.RECORDAR, Primitive.ANTES, Primitive.DESEAR],
            es="nostalgia", en="nostalgia",
            emotion=Emotion(valence=-0.3, bond=0.5),
        )
        self.assertIs(resolve("nostalgia_test"), nostalgia)
        self.assertFalse(is_builtin("NOSTALGIA_TEST"))

    def test_colision_con_primitivo_falla(self):
        with self.assertRaises(ValueError):
            define("DESEAR", [Primitive.SER])

    def test_generatividad_por_el_cable_json(self):
        # Un mensaje que transporta la definición de un concepto no registrado.
        raw = """
        {
          "protocol": "rogex-wsp", "version": "0.1",
          "defines": {
            "SAUDADE_TEST": {"components": ["RECORDAR", "OTRO", "SEPARAR"], "es": "saudade"}
          },
          "packets": [
            {"symbol": {"source": "YO", "relation": "SER", "target": "SAUDADE_TEST"},
             "emotion": {"valence": -0.4, "bond": 0.6}}
          ]
        }
        """
        message = Message.from_json(raw)
        target = message.packets[0].target
        self.assertEqual(target.name, "SAUDADE_TEST")
        self.assertIn(Primitive.RECORDAR, target.components)

    def test_generatividad_por_el_cable_binario(self):
        concept = define("UMBRAL_TEST", [Primitive.ABRIR, Primitive.CAMBIAR])
        message = Message(packets=[Symbol(source=Primitive.YO, relation=concept)])
        recovered = Message.from_bytes(message.to_bytes())
        self.assertEqual(recovered.packets[0].relation.name, "UMBRAL_TEST")


if __name__ == "__main__":
    unittest.main()
