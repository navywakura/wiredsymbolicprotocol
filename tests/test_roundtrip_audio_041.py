import tempfile
import unittest
from pathlib import Path

from rogex_wsp.concepts import resolve
from rogex_wsp.emotion import Emotion
from rogex_wsp.roundtrip_audio import decode_lossless, listen_lossless, render_wav_lossless
from rogex_wsp.symbol import Message, Symbol


class LosslessAudioRoundTripTests(unittest.TestCase):
    def _contact_message(self) -> Message:
        return Message(
            packets=[
                Symbol(
                    source=resolve("YO"),
                    relation=resolve("SER"),
                    action=resolve("BUSCAR"),
                    target=resolve("CONEXION"),
                    time=resolve("AHORA"),
                    space=resolve("AQUI"),
                    emotion=Emotion(
                        valence=0.4,
                        arousal=0.5,
                        dominance=0.0,
                        certainty=0.3,
                        urgency=0.2,
                        bond=0.8,
                    ),
                )
            ]
        )

    def test_full_contact_packet_survives_audio_roundtrip(self):
        original = self._contact_message()
        with tempfile.TemporaryDirectory() as directory:
            wav = str(Path(directory) / "saludo_recuperado.wav")
            render_wav_lossless(original, wav)
            recovered = decode_lossless(wav)
        self.assertIsNotNone(recovered)
        self.assertEqual(original.to_bytes(), recovered.to_bytes())
        self.assertEqual(original.compact(), recovered.compact())

    def test_listen_prefers_exact_transport(self):
        original = self._contact_message()
        with tempfile.TemporaryDirectory() as directory:
            wav = str(Path(directory) / "mensaje.wav")
            render_wav_lossless(original, wav)
            recovered = listen_lossless(wav)
        packet = recovered.packets[0]
        self.assertEqual(packet.action.name, "BUSCAR")
        self.assertEqual(packet.time.name, "AHORA")
        self.assertEqual(packet.space.name, "AQUI")
        self.assertEqual(packet.emotion.to_dict(), original.packets[0].emotion.to_dict())

    def test_truncated_trailer_is_not_accepted_as_exact(self):
        original = self._contact_message()
        with tempfile.TemporaryDirectory() as directory:
            wav = Path(directory) / "mensaje.wav"
            render_wav_lossless(original, str(wav))
            data = wav.read_bytes()
            wav.write_bytes(data[:-1000])
            recovered = decode_lossless(str(wav))
        self.assertIsNone(recovered)


if __name__ == "__main__":
    unittest.main()
