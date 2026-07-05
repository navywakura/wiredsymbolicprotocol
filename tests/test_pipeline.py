"""Tests del pipeline bidireccional: texto → símbolo → texto."""

import unittest

from rogex_wsp import Primitive, encode, render_message

P = Primitive


class TestTextToSymbol(unittest.TestCase):
    def test_te_quiero(self):
        message = encode("te quiero")
        self.assertEqual(len(message.packets), 1)
        s = message.packets[0]
        self.assertIs(s.source, P.YO)
        self.assertEqual(s.relation.name, "AMOR")
        self.assertIs(s.target, P.OTRO)
        self.assertGreater(s.emotion.bond, 0.9)
        self.assertGreater(s.emotion.valence, 0.9)

    def test_estoy_aqui(self):
        s = encode("Estoy aquí.").packets[0]
        self.assertIs(s.relation, P.SER)
        self.assertIs(s.space, P.AQUI)
        self.assertIs(s.time, P.AHORA)
        self.assertGreater(s.emotion.certainty, 0.9)

    def test_quiero_hablar_contigo_en_la_wired(self):
        s = encode("quiero hablar contigo en la wired").packets[0]
        self.assertIs(s.relation, P.DESEAR)
        self.assertEqual(s.action.name, "COMUNICAR")
        self.assertIs(s.target, P.OTRO)
        self.assertEqual(s.space.name, "WIRED")

    def test_soledad_y_conexion_son_dos_paquetes(self):
        message = encode("estoy solo pero quiero conectar")
        self.assertEqual(len(message.packets), 2)
        estado, deseo = message.packets
        self.assertEqual(estado.target.name, "SOLEDAD")
        self.assertLess(estado.emotion.valence, 0)
        self.assertEqual(deseo.target.name, "CONEXION")
        self.assertGreater(deseo.emotion.valence, 0)

    def test_pregunta_de_presencia(self):
        s = encode("¿Estás ahí?").packets[0]
        self.assertIs(s.relation, P.PREGUNTAR)
        self.assertIs(s.action, P.SER)
        self.assertIs(s.space, P.ALLI)
        self.assertLess(s.emotion.certainty, 0)

    def test_peligro(self):
        s = encode("¡peligro!").packets[0]
        self.assertEqual(s.target.name, "PELIGRO")
        self.assertGreater(s.emotion.urgency, 0.8)
        self.assertLess(s.emotion.valence, -0.8)

    def test_fallback_generico_por_lexico(self):
        s = encode("observo la wired ahora").packets[0]
        self.assertIs(s.relation, P.OBSERVAR)
        self.assertEqual(s.space.name, "WIRED")
        self.assertIs(s.time, P.AHORA)

    def test_frase_desconocida_marca_incertidumbre(self):
        s = encode("bzzt fmmm zzz").packets[0]
        self.assertIs(s.target, P.DESCONOCIDO)
        self.assertTrue(s.meta.get("unparsed"))
        self.assertLess(s.emotion.certainty, 0)


class TestSymbolToText(unittest.TestCase):
    def _roundtrip(self, text: str, lang: str = "es") -> str:
        return render_message(encode(text), lang=lang)

    def test_roundtrips_canonicos_es(self):
        self.assertEqual(self._roundtrip("te quiero"), "Te quiero.")
        self.assertEqual(self._roundtrip("estoy aquí"), "Estoy aquí.")
        self.assertEqual(
            self._roundtrip("quiero hablar contigo en la wired"),
            "Quiero comunicarme contigo en la Wired.",
        )
        self.assertEqual(
            self._roundtrip("estoy solo pero quiero conectar"),
            "Me siento solo. Quiero conectar.",
        )
        self.assertEqual(self._roundtrip("¿estás ahí?"), "¿Estás ahí?")
        self.assertEqual(self._roundtrip("¡peligro!"), "¡Peligro!")

    def test_renders_en(self):
        self.assertEqual(self._roundtrip("te quiero", "en"), "I love you.")
        self.assertEqual(self._roundtrip("estoy aquí", "en"), "I am here.")
        self.assertEqual(self._roundtrip("¿estás ahí?", "en"), "Are you there?")
        self.assertEqual(
            self._roundtrip("quiero hablar contigo en la wired", "en"),
            "I want to communicate with you in the Wired.",
        )

    def test_glosa_emocional(self):
        text = render_message(encode("te quiero"), lang="es", emotion_gloss=True)
        self.assertIn("(", text)
        self.assertIn("cercano", text)


if __name__ == "__main__":
    unittest.main()
