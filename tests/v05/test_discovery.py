"""Tests del descubrimiento fonético (v0.5): construir el diccionario desde cero."""

import os
import tempfile
import unittest

from echo_wsp.v05 import Primitive, render_message
from echo_wsp.v05.discovery import (
    Observation,
    PhoneticMap,
    cluster,
    decode_with_map,
    observe,
    write_exotic,
)

P = Primitive

# Una lengua ajena: acordes que no pertenecen a la retícula de WSP.
ERIDIANO = {
    "YO": (1.0, 1.32, 1.79),
    "OTRO": (1.0, 1.19, 2.38),
    "OBSERVAR": (1.0, 1.51, 2.11, 2.77),
    "AQUI": (1.0, 1.41),
    "DESEAR": (1.0, 1.62, 2.24),
}


class TestObservacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _emit(self, utterance, name="x.wav"):
        path = os.path.join(self.tmp.name, name)
        write_exotic(utterance, path)
        return path

    def test_mide_los_parciales_de_cada_evento(self):
        path = self._emit([(ERIDIANO["YO"], 210.0), (ERIDIANO["AQUI"], 215.0)], "obs.wav")
        observations = observe(path)
        self.assertEqual(len(observations), 2)
        self.assertAlmostEqual(observations[0].root_hz, 210.0, delta=6.0)
        self.assertEqual(len(observations[0].ratios), 3)
        self.assertEqual(len(observations[1].ratios), 2)

    def test_la_firma_es_invariante_a_la_altura(self):
        """Sin esta propiedad no hay diccionario posible con un emisor ajeno."""
        path = self._emit(
            [(ERIDIANO["YO"], 190.0), (ERIDIANO["YO"], 380.0), (ERIDIANO["YO"], 265.0)],
            "alturas.wav",
        )
        fingerprints = {o.fingerprint for o in observe(path)}
        self.assertEqual(len(fingerprints), 1, "la misma emisión debe dar una sola firma")

    def test_firmas_distintas_no_se_confunden(self):
        path = self._emit(
            [(ERIDIANO["YO"], 200.0), (ERIDIANO["OTRO"], 200.0),
             (ERIDIANO["OBSERVAR"], 200.0), (ERIDIANO["AQUI"], 200.0)],
            "distintas.wav",
        )
        self.assertEqual(len({o.fingerprint for o in observe(path)}), 4)

    def test_agrupamiento_cuenta_repeticiones(self):
        path = self._emit(
            [(ERIDIANO["YO"], 200.0), (ERIDIANO["OTRO"], 240.0),
             (ERIDIANO["YO"], 410.0), (ERIDIANO["YO"], 190.0)],
            "cluster.wav",
        )
        signatures = cluster(observe(path))
        self.assertEqual(len(signatures), 2)
        self.assertEqual(signatures[0].occurrences, 3)  # el más frecuente primero


class TestMapaFonetico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.lesson = os.path.join(cls.tmp.name, "leccion.wav")
        write_exotic(
            [(ERIDIANO["YO"], 210.0), (ERIDIANO["OBSERVAR"], 205.0),
             (ERIDIANO["OTRO"], 198.0), (ERIDIANO["AQUI"], 215.0)],
            cls.lesson,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _learned(self) -> PhoneticMap:
        phonetic = PhoneticMap(speaker="eridiano")
        phonetic.learn_from_sequence(
            observe(self.lesson), ["YO", "OBSERVAR", "OTRO", "AQUI"]
        )
        return phonetic

    def test_aprende_de_una_leccion_alineada(self):
        phonetic = self._learned()
        self.assertEqual(len(phonetic.bound()), 4)
        self.assertEqual(len(phonetic.unbound()), 0)
        bindings = {s.binding for s in phonetic.signatures.values()}
        self.assertEqual(bindings, {"YO", "OBSERVAR", "OTRO", "AQUI"})

    def test_la_alineacion_exige_longitudes_iguales(self):
        phonetic = PhoneticMap()
        with self.assertRaises(ValueError):
            phonetic.learn_from_sequence(observe(self.lesson), ["YO", "OTRO"])

    def test_no_se_pueden_atar_conceptos_inexistentes(self):
        phonetic = PhoneticMap.from_observations(observe(self.lesson))
        first = next(iter(phonetic.signatures))
        with self.assertRaises(ValueError):
            phonetic.bind(first, "no-es-un-atomo-de-wsp")
        with self.assertRaises(KeyError):
            phonetic.bind("SIG-99", "YO")

    def test_persistencia(self):
        path = os.path.join(self.tmp.name, "mapping.json")
        self._learned().save(path)
        loaded = PhoneticMap.load(path)
        self.assertEqual(loaded.speaker, "eridiano")
        self.assertEqual(len(loaded.bound()), 4)

    def test_ata_a_atomos_cientificos_y_elementos(self):
        phonetic = PhoneticMap.from_observations(observe(self.lesson))
        ids = sorted(phonetic.signatures)
        phonetic.bind(ids[0], "MASA")
        phonetic.bind(ids[1], "carbono")
        self.assertEqual(phonetic.signatures[ids[0]].binding, "MASA")
        self.assertEqual(phonetic.signatures[ids[1]].binding, "carbono")


class TestDecodificacionXeno(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.lesson = os.path.join(cls.tmp.name, "leccion.wav")
        write_exotic(
            [(ERIDIANO["YO"], 210.0), (ERIDIANO["OBSERVAR"], 205.0),
             (ERIDIANO["OTRO"], 198.0), (ERIDIANO["AQUI"], 215.0)],
            cls.lesson,
        )
        cls.phonetic = PhoneticMap(speaker="eridiano")
        cls.phonetic.learn_from_sequence(
            observe(cls.lesson), ["YO", "OBSERVAR", "OTRO", "AQUI"]
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _emit(self, utterance, name):
        path = os.path.join(self.tmp.name, name)
        write_exotic(utterance, path)
        return path

    def test_decodifica_habla_espontanea_en_otro_registro_y_otro_orden(self):
        """Rocky habla más agudo y con su sintaxis: el mensaje llega igual."""
        path = self._emit(
            [(ERIDIANO["OTRO"], 455.0), (ERIDIANO["AQUI"], 470.0),
             (ERIDIANO["OBSERVAR"], 441.0), (ERIDIANO["YO"], 460.0)],
            "espontaneo.wav",
        )
        message = decode_with_map(path, self.phonetic)
        symbol = message.packets[0]
        self.assertEqual(symbol.relation.name, "OBSERVAR")
        self.assertIs(symbol.space, P.AQUI)
        self.assertEqual(symbol.meta["discovery"]["coverage"], 1.0)
        self.assertEqual(render_message(message, "es"), "Me observas aquí.")

    def test_lo_no_aprendido_baja_la_certeza(self):
        """La duda es parte del protocolo: media emisión entendida, certeza 0."""
        path = self._emit(
            [(ERIDIANO["YO"], 220.0), (ERIDIANO["DESEAR"], 230.0)], "mitad.wav"
        )
        symbol = decode_with_map(path, self.phonetic).packets[0]
        self.assertAlmostEqual(symbol.meta["discovery"]["coverage"], 0.5, places=2)
        self.assertAlmostEqual(symbol.emotion.certainty, 0.0, delta=0.01)
        self.assertEqual(len(symbol.meta["discovery"]["unknown"]), 1)

    def test_emision_totalmente_desconocida(self):
        path = self._emit([(ERIDIANO["DESEAR"], 300.0)], "desconocido.wav")
        symbol = decode_with_map(path, self.phonetic).packets[0]
        self.assertEqual(symbol.meta["discovery"]["coverage"], 0.0)
        self.assertEqual(symbol.emotion.certainty, -1.0)

    def test_silencio_no_produce_paquete(self):
        path = os.path.join(self.tmp.name, "silencio.wav")
        write_exotic([((1.0,), 200.0)], path)
        # un archivo sin eventos audibles no debe inventar significado
        import wave, struct
        with wave.open(path, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(22050)
            f.writeframes(b"".join(struct.pack("<h", 0) for _ in range(11025)))
        self.assertEqual(decode_with_map(path, self.phonetic).packets, [])


if __name__ == "__main__":
    unittest.main()
