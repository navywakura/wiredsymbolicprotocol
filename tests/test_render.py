"""Tests de los renderizadores físicos (capa M): audio WAV y glifo SVG."""

import os
import tempfile
import unittest
import wave
import xml.etree.ElementTree as ET

from rogex_wsp import encode, render_svg, render_wav, synthesize


class TestAudio(unittest.TestCase):
    def test_synthesize_produce_muestras_validas(self):
        samples = synthesize(encode("te quiero"))
        self.assertGreater(len(samples), 1000)
        self.assertTrue(all(-1.0 <= s <= 1.0 for s in samples))
        self.assertTrue(any(abs(s) > 0.05 for s in samples), "no debería ser silencio")

    def test_urgencia_acorta_y_vinculo_alarga(self):
        rapido = synthesize(encode("¡peligro!"))
        lento = synthesize(encode("te quiero"))
        self.assertLess(len(rapido), len(lento))

    def test_negacion_contiene_silencio(self):
        # OLVIDAR codifica la ausencia como un tramo de silencio dentro del mensaje.
        from rogex_wsp import Message, Primitive, Symbol

        message = Message(packets=[Symbol(source=Primitive.YO, relation=Primitive.OLVIDAR)])
        samples = synthesize(message)
        longest = run = 0
        for s in samples:
            run = run + 1 if abs(s) < 1e-6 else 0
            longest = max(longest, run)
        self.assertGreater(longest, 4000, "debe existir un silencio sostenido (ausencia)")

    def test_render_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "msg.wav")
            render_wav(encode("estoy aquí"), path)
            with wave.open(path, "rb") as f:
                self.assertEqual(f.getnchannels(), 1)
                self.assertEqual(f.getsampwidth(), 2)
                self.assertGreater(f.getnframes(), 0)


class TestGlyph(unittest.TestCase):
    def test_svg_bien_formado(self):
        svg = render_svg(encode("te quiero"))
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))

    def test_amor_es_onda_dentro_de_campo(self):
        svg = render_svg(encode("te quiero"))
        self.assertIn("polyline", svg)  # la onda
        self.assertIn("ellipse", svg)   # el campo del vínculo

    def test_wired_dibuja_reticula(self):
        svg = render_svg(encode("quiero hablar contigo en la wired"))
        self.assertGreater(svg.count("#b03030"), 5)

    def test_multipaquete_apila_filas(self):
        uno = render_svg(encode("estoy aquí"))
        dos = render_svg(encode("estoy solo pero quiero conectar"))
        h1 = int(ET.fromstring(uno).attrib["height"])
        h2 = int(ET.fromstring(dos).attrib["height"])
        self.assertEqual(h2, h1 * 2)

    def test_pregunta_es_arco_abierto(self):
        svg = render_svg(encode("¿estás ahí?"))
        self.assertIn("<path", svg)
        self.assertIn("stroke-dasharray", svg)  # certeza negativa = trazo discontinuo


if __name__ == "__main__":
    unittest.main()
