"""Tests de la máscara polifónica (v0.5): acordes simultáneos."""

import os
import tempfile
import unittest

from rogex_wsp import Message, Primitive, Symbol, encode, render_message, resolve
from rogex_wsp.grammar import FieldTag
from rogex_wsp.multiphonic import (
    LATTICE,
    PAYLOAD_RATIOS,
    TAG_RATIOS,
    Chord,
    chords_to_fields,
    listen_chords,
    render_wav,
    symbol_to_chords,
)
from rogex_wsp.grammar import normalize
from rogex_wsp.primitives_science import Dimension, Element, Quantity

P = Primitive


class TestAcorde(unittest.TestCase):
    def test_la_reticula_no_tiene_colisiones(self):
        self.assertEqual(len(set(LATTICE)), len(LATTICE))
        self.assertEqual(len(TAG_RATIOS), 4)
        self.assertEqual(len(PAYLOAD_RATIOS), 5)
        self.assertEqual(LATTICE[0], 1.0)  # la raíz siempre suena

    def test_la_raiz_siempre_esta_presente(self):
        for tag in (FieldTag.CONT, FieldTag.SOURCE, FieldTag.QUANTITY):
            for payload in (0, 1, 31):
                self.assertIn(1.0, Chord(tag, payload).ratios())

    def test_paridad_par(self):
        chord = Chord(FieldTag.SOURCE, 0)      # 1 bit de etiqueta, 0 de carga
        self.assertEqual(chord.parity, 1)
        self.assertIn(5.0, chord.ratios())
        chord = Chord(FieldTag.RELATION, 1)    # tag 2 (1 bit) + payload 1 (1 bit)
        self.assertEqual(chord.parity, 0)
        self.assertNotIn(5.0, chord.ratios())

    def test_carga_de_cinco_bits(self):
        with self.assertRaises(ValueError):
            Chord(FieldTag.SOURCE, 32)

    def test_el_acorde_es_simultaneo_no_secuencial(self):
        """Un campo entero suena de una vez: varias voces, un solo evento."""
        chord = Chord(FieldTag.TARGET, 31)
        self.assertGreater(len(chord.ratios()), 5)


class TestAcordesSinAudio(unittest.TestCase):
    def test_roundtrip_estructural(self):
        original = encode("quiero hablar contigo en la wired").packets[0]
        recovered = normalize(chords_to_fields(symbol_to_chords(original)))
        self.assertIs(recovered.source, P.YO)
        self.assertEqual(recovered.relation.name, "DESEAR")
        self.assertEqual(recovered.action.name, "COMUNICAR")
        self.assertEqual(recovered.space.name, "WIRED")

    def test_un_derivado_viaja_como_su_composicion(self):
        """El nombre es máscara: lo que cruza el canal son los átomos."""
        amor = resolve("AMOR")
        chords = symbol_to_chords(Symbol(source=P.YO, relation=amor))
        relation_chords = [c for c in chords if c.tag in (FieldTag.RELATION, FieldTag.CONT)]
        self.assertEqual(len(relation_chords), len(amor.components))
        recovered = normalize(chords_to_fields(chords))
        self.assertEqual(recovered.relation.name, "AMOR")

    def test_composicion_desconocida_se_aprende(self):
        from rogex_wsp.concepts import registry

        chords = [
            Chord(FieldTag.RELATION, P.SUBIR.code),
            Chord(FieldTag.CONT, P.ABRIR.code),
            Chord(FieldTag.CONT, P.POSIBLE.code),
        ]
        concept = normalize(chords_to_fields(chords)).relation
        self.assertEqual(concept.components, (P.SUBIR, P.ABRIR, P.POSIBLE))
        self.assertIn(concept.name, registry())

    def test_orden_de_acordes_irrelevante(self):
        """Cada acorde lleva su etiqueta, así que la secuencia es estilo."""
        original = encode("te quiero").packets[0]
        chords = symbol_to_chords(original)
        # mueve el bloque del destino al principio, con su continuación intacta
        target_at = next(i for i, c in enumerate(chords) if c.tag is FieldTag.TARGET)
        reordered = [chords[target_at]] + chords[:target_at] + chords[target_at + 1 :]
        self.assertEqual(
            normalize(chords_to_fields(reordered)).target.name, original.target.name
        )


class TestAudioPolifonico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _roundtrip(self, message: Message, base: float = 180.0) -> Message:
        path = os.path.join(self.tmp.name, f"poly_{abs(hash(str(message.compact())))}.wav")
        render_wav(message, path, base=base)
        return listen_chords(path)

    def test_ciclo_completo_por_audio(self):
        original = encode("te quiero")
        recovered = self._roundtrip(original)
        symbol = recovered.packets[0]
        self.assertIs(symbol.source, P.YO)
        self.assertEqual(symbol.relation.name, "AMOR")
        self.assertEqual(symbol.target.name, "OTRO")
        self.assertEqual(symbol.meta["polyphonic"]["parity_errors"], 0)
        self.assertEqual(render_message(recovered, "es"), "Te quiero.")

    def test_emocion_sobrevive_con_resolucion_de_cinco_bits(self):
        original = encode("¡peligro!")
        symbol = self._roundtrip(original).packets[0]
        want = original.packets[0].emotion
        for axis in ("valence", "arousal", "urgency"):
            self.assertAlmostEqual(
                getattr(symbol.emotion, axis), getattr(want, axis), delta=0.08, msg=axis
            )

    def test_invariancia_de_altura(self):
        """La misma frase en tres registros produce el mismo símbolo."""
        original = encode("estoy aquí")
        reference = None
        for base in (120.0, 180.0, 260.0):
            compact = self._roundtrip(original, base=base).packets[0].compact()
            reference = reference or compact
            self.assertEqual(compact, reference, f"base {base} Hz")

    def test_ciencia_por_el_canal_polifonico(self):
        """El caso Rocky: hablar de un elemento y de una masa, no de emociones."""
        symbol = Symbol(
            source=P.OTRO,
            relation=P.SER,
            meta={"science": {
                "atoms": ["MASA"],
                "element": 6,
                "quantity": {"mantissa": 12011, "exponent": -3, "dimension": [0] * 7},
            }},
        )
        recovered = self._roundtrip(Message(packets=[symbol])).packets[0]
        science = recovered.meta["science"]
        self.assertEqual(science["element"], 6)
        self.assertEqual(Element(science["element"]).symbol, "C")
        self.assertEqual(science["atoms"], ["MASA"])
        quantity = Quantity(
            science["quantity"]["mantissa"],
            science["quantity"]["exponent"],
            Dimension(*science["quantity"]["dimension"]),
        )
        self.assertAlmostEqual(quantity.value, 12.011, places=4)
        self.assertEqual(recovered.meta["polyphonic"]["parity_errors"], 0)

    def test_la_paridad_rebaja_la_certeza_en_vez_de_romper(self):
        import wave
        import struct

        path = os.path.join(self.tmp.name, "ruido.wav")
        render_wav(encode("te quiero"), path)
        with wave.open(path, "rb") as f:
            sr, frames = f.getframerate(), f.readframes(f.getnframes())
        values = list(struct.unpack(f"<{len(frames) // 2}h", frames))
        # inyecta un tono ajeno a la retícula en mitad de un acorde
        for i in range(2000, 4000):
            values[i] = max(-32767, min(32767, values[i] + 9000))
        damaged = os.path.join(self.tmp.name, "danado.wav")
        with wave.open(damaged, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sr)
            f.writeframes(b"".join(struct.pack("<h", v) for v in values))
        message = listen_chords(damaged)
        self.assertTrue(message.packets, "una señal dañada no debe vaciar el mensaje")


if __name__ == "__main__":
    unittest.main()
