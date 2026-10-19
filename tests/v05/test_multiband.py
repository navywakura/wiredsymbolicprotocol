"""Tests de la v0.4 «Third Kind»: análisis multibanda y saludo de contacto.

El saludo de cinco tonos (RE–MI–DO–DO↓–SOL) se proyecta uno a uno sobre
las cinco ranuras del paquete WSP. El tono base es dinámico: el primer
tono define el 1:1, en cualquier frecuencia.
"""

import math
import os
import tempfile
import unittest

from echo_wsp.v05 import Primitive, encode, render_message, resolve
from echo_wsp.v05.multiband import (
    analyze,
    emit_handshake,
    fold_ratio,
    split_bands,
    translate_alien_handshake,
)

P = Primitive
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _sine(freq: float, duration: float, sr: int) -> list[float]:
    return [0.5 * math.sin(2 * math.pi * freq * i / sr) for i in range(int(duration * sr))]


class TestBandas(unittest.TestCase):
    def test_cada_banda_aisla_su_frecuencia(self):
        sr = 44100
        mix = [a + b + c for a, b, c in zip(
            _sine(100, 0.5, sr), _sine(440, 0.5, sr), _sine(3000, 0.5, sr)
        )]
        bands = split_bands(mix, sr)

        def rms(x):
            return math.sqrt(sum(v * v for v in x) / len(x))

        # en cada capa debe dominar su propia frecuencia (medimos contra la mezcla)
        self.assertGreater(rms(bands["low"]), 0.15)
        self.assertGreater(rms(bands["mid"]), 0.15)
        self.assertGreater(rms(bands["high"]), 0.15)
        # y una señal fuera de banda debe quedar fuertemente atenuada
        solo_agudo = split_bands(_sine(3000, 0.5, sr), sr)
        self.assertLess(rms(solo_agudo["low"]), 0.02)
        self.assertLess(rms(solo_agudo["mid"]), 0.05)

    def test_plegado_de_octavas(self):
        base = 293.66
        # DO4 respecto a RE4: segunda mayor descendente = clase 16/9, octava -1
        pitch_class, octave, error = fold_ratio(base * 8 / 9, base)
        self.assertAlmostEqual(pitch_class, 16 / 9)
        self.assertEqual(octave, -1)
        self.assertLess(error, 0.01)
        # DO3: misma clase de tono, una octava más abajo
        pitch_class, octave, _ = fold_ratio(base * 4 / 9, base)
        self.assertAlmostEqual(pitch_class, 16 / 9)
        self.assertEqual(octave, -2)


class TestSaludoDeContacto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _roundtrip(self, base: float):
        path = os.path.join(self.tmp.name, f"hs_{int(base)}.wav")
        emit_handshake(path, base=base)
        return translate_alien_handshake(path)

    def test_emitir_y_traducir_el_saludo(self):
        """RE4 como en la película: los 5 tonos → las 5 ranuras del paquete."""
        message = self._roundtrip(293.66)
        self.assertIsNotNone(message)
        s = message.packets[0]
        self.assertIs(s.source, P.YO)
        self.assertIs(s.relation, P.SER)
        self.assertEqual(s.action.name, "BUSCAR")
        self.assertEqual(s.target.name, "CONEXION")
        self.assertIs(s.space, P.AQUI)
        self.assertGreaterEqual(s.meta["contact"]["score"], 0.95)
        self.assertEqual(
            render_message(message, "es"), "Existo y busco un vínculo aquí."
        )

    def test_tono_base_dinamico(self):
        """El saludo funciona en cualquier tonalidad: el primer tono define el 1:1."""
        for base in (220.0, 392.0):
            message = self._roundtrip(base)
            self.assertIsNotNone(message, f"base {base}")
            self.assertAlmostEqual(
                message.packets[0].meta["contact"]["base_hz"], base, delta=base * 0.02
            )

    def test_el_do_grave_ancla_en_la_capa_baja(self):
        """Con base RE4, el DO grave (130.8 Hz) cae en la capa de graves."""
        path = os.path.join(self.tmp.name, "hs_grave.wav")
        emit_handshake(path, base=293.66)
        report = analyze(path)
        self.assertTrue(
            any(abs(f - 130.5) / 130.5 < 0.05 for f, _, _ in report.low_tones),
            f"low_tones={report.low_tones}",
        )
        message = translate_alien_handshake(report)
        self.assertTrue(message.packets[0].meta["contact"]["grounded_in_bass"])

    def test_audio_wsp_no_es_saludo(self):
        for name in ("te_quiero.wav", "peligro.wav"):
            path = os.path.join(_ROOT, "examples", "v0.5", "gallery", name)
            self.assertIsNone(translate_alien_handshake(path), name)


class TestBuscar(unittest.TestCase):
    def test_buscar_es_concepto_derivado(self):
        buscar = resolve("BUSCAR")
        self.assertIn(P.DESEAR, buscar.components)
        self.assertIn(P.OBSERVAR, buscar.components)
        self.assertIn(P.DESCONOCIDO, buscar.components)

    def test_frase_canonica_del_contacto(self):
        message = encode("busco un vínculo aquí")
        s = message.packets[0]
        self.assertEqual(s.action.name, "BUSCAR")
        self.assertEqual(s.target.name, "CONEXION")
        self.assertIs(s.space, P.AQUI)
        self.assertEqual(render_message(message, "es"), "Existo y busco un vínculo aquí.")
        self.assertEqual(render_message(message, "en"), "I exist and I seek a bond here.")


if __name__ == "__main__":
    unittest.main()
