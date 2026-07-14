"""Tests de la v0.2 «Signal Return»: los caminos de vuelta al símbolo.

Criterio de cierre de la versión: encode(texto) → wav → listen(wav)
recupera la relación y el signo emocional en las 6 frases canónicas.
"""

import os
import tempfile
import unittest

from rogex_wsp import Primitive, encode, render_message, render_svg, render_wav
from rogex_wsp.compact import parse_compact, parse_compact_message
from rogex_wsp.glyph_reader import inspect_svg
from rogex_wsp.listen import listen

P = Primitive


class TestListen(unittest.TestCase):
    """encode → render_wav → listen debe recuperar relación y signo emocional."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _listen(self, text: str):
        path = os.path.join(self.tmp.name, f"{abs(hash(text))}.wav")
        render_wav(encode(text), path)
        return listen(path)

    def test_criterio_de_cierre_v02(self):
        """Las 6 frases canónicas: relación correcta y signo de valencia correcto."""
        esperado = {
            "te quiero": [("AMOR", "+")],
            "estoy aquí": [("SER", "0")],
            "quiero hablar contigo en la wired": [("DESEAR", "+")],
            "estoy solo pero quiero conectar": [("SER", "-"), ("DESEAR", "+")],
            "¿estás ahí?": [("PREGUNTAR", "0+")],
            "¡peligro!": [("TEMER", "-")],
        }
        for frase, paquetes in esperado.items():
            message = self._listen(frase)
            self.assertEqual(len(message.packets), len(paquetes), frase)
            for symbol, (relacion, signo) in zip(message.packets, paquetes):
                self.assertEqual(symbol.relation.name, relacion, frase)
                v = symbol.emotion.valence
                if signo == "+":
                    self.assertGreater(v, 0, frase)
                elif signo == "-":
                    self.assertLess(v, 0, frase)
                elif signo == "0":
                    self.assertLessEqual(abs(v), 0.45, frase)
                else:  # "0+": neutro o positivo
                    self.assertGreaterEqual(v, 0, frase)

    def test_recupera_accion_anidada(self):
        message = self._listen("quiero hablar contigo en la wired")
        symbol = message.packets[0]
        self.assertIsNotNone(symbol.action)
        self.assertEqual(symbol.action.name, "COMUNICAR")

    def test_pregunta_reconstruye_cadencia_abierta(self):
        symbol = self._listen("¿estás ahí?").packets[0]
        self.assertEqual(symbol.relation.name, "PREGUNTAR")
        self.assertLess(symbol.emotion.certainty, 0)

    def test_urgencia_del_peligro(self):
        symbol = self._listen("¡peligro!").packets[0]
        self.assertGreater(symbol.emotion.urgency, 0.6)
        self.assertGreater(symbol.emotion.arousal, 0.6)

    def test_meta_transporta_diagnostico(self):
        symbol = self._listen("te quiero").packets[0]
        info = symbol.meta["listen"]
        self.assertGreaterEqual(info["score"], 0.8)
        self.assertAlmostEqual(info["base_hz"], 220.0, delta=5.0)

    def test_texto_final_es_legible(self):
        # el ciclo completo: texto → wav → símbolo → texto
        message = self._listen("te quiero")
        self.assertEqual(render_message(message, "es"), "Te quiero.")

    def test_la_transmision_sobrevive_al_audio(self):
        """El silencio de la negación es marcador de ausencia, no separador de paquetes."""
        message = self._listen("no tengan miedo de lo que no conocen")
        self.assertEqual(len(message.packets), 1)
        symbol = message.packets[0]
        self.assertEqual(symbol.relation.name, "NO_SER")
        self.assertEqual(symbol.action.name, "TEMER")
        self.assertGreater(symbol.emotion.valence, 0)  # protector, no amenaza
        self.assertEqual(render_message(message, "es"), "No temas lo desconocido.")


class TestInspect(unittest.TestCase):
    def test_con_etiqueta_recupera_estructura_exacta(self):
        svg = render_svg(encode("quiero hablar contigo en la wired"))
        symbol = inspect_svg(svg).packets[0]
        self.assertEqual(symbol.relation.name, "DESEAR")
        self.assertEqual(symbol.action.name, "COMUNICAR")
        self.assertEqual(symbol.target.name, "OTRO")
        self.assertEqual(symbol.space.name, "WIRED")
        self.assertEqual(symbol.time.name, "AHORA")
        self.assertTrue(symbol.meta["inspect"]["label_used"])

    def test_sin_etiqueta_clasifica_formas(self):
        casos = {
            "te quiero": "AMOR",
            "estoy aquí": "SER",
            "¡peligro!": "TEMER",
            "¿estás ahí?": "PREGUNTAR",
        }
        for frase, relacion in casos.items():
            svg = render_svg(encode(frase), labels=False)
            symbol = inspect_svg(svg).packets[0]
            self.assertEqual(symbol.relation.name, relacion, frase)
            self.assertFalse(symbol.meta["inspect"]["label_used"])

    def test_emocion_desde_geometria(self):
        svg = render_svg(encode("¡peligro!"), labels=False)
        emotion = inspect_svg(svg).packets[0].emotion
        self.assertLess(emotion.valence, 0)      # trazo rojo
        self.assertGreater(emotion.arousal, 0.7)  # trazo grueso
        self.assertGreater(emotion.urgency, 0.5)  # púas radiales

    def test_multipaquete(self):
        svg = render_svg(encode("estoy solo pero quiero conectar"))
        message = inspect_svg(svg)
        self.assertEqual(len(message.packets), 2)
        self.assertEqual(message.packets[0].target.name, "SOLEDAD")
        self.assertEqual(message.packets[1].target.name, "CONEXION")


class TestCompactParser(unittest.TestCase):
    def test_roundtrip_de_forma_compacta(self):
        for frase in ("te quiero", "quiero hablar contigo en la wired", "¿estás ahí?"):
            original = encode(frase).packets[0]
            recovered = parse_compact(original.compact())
            self.assertIs(recovered.source, original.source, frase)
            self.assertEqual(recovered.relation.name, original.relation.name, frase)
            self.assertEqual(
                recovered.action.name if recovered.action else None,
                original.action.name if original.action else None,
                frase,
            )
            self.assertEqual(recovered.emotion, original.emotion, frase)

    def test_acepta_flecha_ascii_y_sin_emocion(self):
        symbol = parse_compact("YO -> DESEAR(COMUNICAR) -> OTRO @AHORA @WIRED")
        self.assertEqual(symbol.action.name, "COMUNICAR")
        self.assertEqual(symbol.space.name, "WIRED")
        self.assertTrue(symbol.emotion.is_neutral())

    def test_mensaje_multilinea(self):
        message = parse_compact_message(
            "YO → SER → SOLEDAD @AHORA | E[V-0.60 B-0.70]\n"
            "YO → DESEAR → CONEXION @AHORA | E[V+0.40 B+0.60]\n"
        )
        self.assertEqual(len(message.packets), 2)
        self.assertAlmostEqual(message.packets[0].emotion.bond, -0.7)


class TestNuevasFrasesCanonicas(unittest.TestCase):
    def test_la_transmision(self):
        """«no tengan miedo de lo que no conocen» — negación sobre el temor."""
        symbol = encode("no tengan miedo de lo que no conocen").packets[0]
        self.assertIs(symbol.relation, P.NO_SER)
        self.assertIs(symbol.action, P.TEMER)
        self.assertIs(symbol.target, P.DESCONOCIDO)
        e = symbol.emotion
        self.assertGreater(e.valence, 0)      # mensaje protector, no amenaza
        self.assertLess(e.arousal, 0)         # calma
        self.assertGreater(e.certainty, 0.7)  # seguridad del emisor
        self.assertLess(e.urgency, 0)         # sin prisa
        self.assertGreater(e.bond, 0.5)       # cercanía

    def test_roundtrips_es(self):
        casos = {
            "no temas": "No temas lo desconocido.",
            "tengo miedo": "Tengo miedo.",
            "te recuerdo": "Te recuerdo.",
            "no estás aquí": "No estás aquí.",
            "te deseo": "Te deseo.",
            "estamos juntos": "Estamos juntos.",
            "adiós": "Adiós.",
            "¿quién eres?": "¿Quién eres?",
            "¿qué es real?": "¿Qué es real?",
        }
        for entrada, esperado in casos.items():
            self.assertEqual(render_message(encode(entrada), "es"), esperado, entrada)

    def test_roundtrips_en(self):
        casos = {
            "no tengan miedo": "Do not fear the unknown.",
            "tengo miedo": "I am afraid.",
            "estamos juntos": "We are together.",
            "¿qué es real?": "What is real?",
        }
        for entrada, esperado in casos.items():
            self.assertEqual(render_message(encode(entrada), "en"), esperado, entrada)

    def test_los_originales_no_se_rompen(self):
        self.assertEqual(render_message(encode("te quiero"), "es"), "Te quiero.")
        self.assertEqual(render_message(encode("¿estás ahí?"), "es"), "¿Estás ahí?")


if __name__ == "__main__":
    unittest.main()

class TestResilientMatrixV03(unittest.TestCase):
    def test_f0_dinamica_330hz(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dynamic.wav")
            render_wav(encode("te quiero"), path, base_freq=330.0)
            symbol = listen(path).packets[0]
            self.assertEqual(symbol.relation.name, "AMOR")
            self.assertAlmostEqual(symbol.meta["listen"]["base_hz"], 330.0, delta=8.0)
            self.assertEqual(symbol.source.name, "OTRO")

    def test_squelch_resiste_ruido_de_fondo(self):
        import math, struct, wave
        with tempfile.TemporaryDirectory() as tmp:
            clean = os.path.join(tmp, "clean.wav")
            noisy = os.path.join(tmp, "noisy.wav")
            render_wav(encode("te quiero"), clean)
            with wave.open(clean, "rb") as f:
                params, raw = f.getparams(), f.readframes(f.getnframes())
            vals = list(struct.unpack(f"<{len(raw)//2}h", raw))
            vals = [max(-32768, min(32767, v + int(250*math.sin(i*.37)))) for i,v in enumerate(vals)]
            with wave.open(noisy, "wb") as f:
                f.setparams(params); f.writeframes(struct.pack(f"<{len(vals)}h", *vals))
            self.assertEqual(listen(noisy).packets[0].relation.name, "AMOR")

    def test_arpegio_reconstruye_destino_compuesto(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "target.wav")
            render_wav(encode("quiero conectar"), path)
            symbol = listen(path).packets[0]
            self.assertEqual(symbol.target.name, "CONEXION")
            self.assertTrue(symbol.meta["listen"]["target_burst"]["valid"])
