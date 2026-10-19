"""Validación estructural de mensajes contra el contrato de docs/v0.5/schema/.

Sin dependencias: un validador mínimo cubre el subconjunto de JSON Schema
que usa el protocolo. Si `jsonschema` está instalado, se valida además con
el schema oficial completo.
"""

import glob
import json
import os
import unittest

from echo_wsp.v05 import encode

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCHEMA_PATH = os.path.join(_ROOT, "docs", "v0.5", "schema", "wsp-message.schema.json")

_AXES = ("valence", "arousal", "dominance", "certainty", "urgency", "bond")
_SLOTS = ("source", "relation", "action", "target", "time", "space")


def _check_emotion(emotion, errors, where):
    if not isinstance(emotion, dict):
        errors.append(f"{where}: emotion debe ser objeto")
        return
    for key, value in emotion.items():
        if key not in _AXES:
            errors.append(f"{where}: eje desconocido {key!r}")
        elif not isinstance(value, (int, float)) or not -1.0 <= value <= 1.0:
            errors.append(f"{where}: {key}={value!r} fuera de [-1, 1]")


def _check_symbol(symbol, errors, where):
    if not isinstance(symbol, dict):
        errors.append(f"{where}: symbol debe ser objeto")
        return
    for key, value in symbol.items():
        if key not in _SLOTS:
            errors.append(f"{where}: ranura desconocida {key!r}")
        elif not isinstance(value, str) or not value:
            errors.append(f"{where}: {key} debe ser nombre de concepto")


def validate_structure(data) -> list[str]:
    """Errores estructurales de un mensaje WSP (lista vacía = conforme)."""
    errors: list[str] = []
    if data.get("protocol") != "echo-wsp":
        errors.append("protocol debe ser 'echo-wsp'")
    if not isinstance(data.get("version"), str):
        errors.append("version debe ser cadena")
    has_packets, has_symbol = "packets" in data, "symbol" in data
    if has_packets == has_symbol:
        errors.append("debe haber exactamente una forma: 'packets' o 'symbol'")
    for name, spec in (data.get("defines") or {}).items():
        components = spec.get("components")
        if not isinstance(components, list) or not 1 <= len(components) <= 31:
            errors.append(f"defines.{name}: components debe tener 1..31 átomos")
    if has_packets:
        packets = data["packets"]
        if not isinstance(packets, list) or not 1 <= len(packets) <= 255:
            errors.append("packets debe tener 1..255 elementos")
        else:
            for i, packet in enumerate(packets):
                _check_symbol(packet.get("symbol"), errors, f"packets[{i}]")
                if "emotion" in packet:
                    _check_emotion(packet["emotion"], errors, f"packets[{i}]")
    if has_symbol:
        _check_symbol(data["symbol"], errors, "symbol")
        if "emotion" in data:
            _check_emotion(data["emotion"], errors, "symbol")
    return errors


class TestSchema(unittest.TestCase):
    def test_el_schema_es_json_valido(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(schema["properties"]["protocol"]["const"], "echo-wsp")

    def test_ejemplos_del_repo_conformes(self):
        paths = glob.glob(os.path.join(_ROOT, "examples", "v0.5", "*.json"))
        self.assertGreater(len(paths), 3)
        for path in paths:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(validate_structure(data), [], path)

    def test_mensajes_generados_conformes(self):
        for frase in ("te quiero", "no tengan miedo", "estoy solo pero quiero conectar"):
            data = encode(frase).to_dict()
            self.assertEqual(validate_structure(data), [], frase)

    def test_detecta_mensajes_invalidos(self):
        self.assertTrue(validate_structure({"protocol": "otro"}))
        self.assertTrue(
            validate_structure(
                {"protocol": "echo-wsp", "version": "0.1",
                 "packets": [{"symbol": {"ranura_falsa": "YO"}}]}
            )
        )
        self.assertTrue(
            validate_structure(
                {"protocol": "echo-wsp", "version": "0.1",
                 "packets": [{"symbol": {"source": "YO"}, "emotion": {"valence": 7}}]}
            )
        )

    def test_con_jsonschema_si_esta_disponible(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema no instalado (opcional)")
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            schema = json.load(f)
        jsonschema.validate(encode("te quiero").to_dict(), schema)


if __name__ == "__main__":
    unittest.main()
