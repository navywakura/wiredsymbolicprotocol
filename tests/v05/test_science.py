"""Tests del plano científico (v0.5): dimensiones, cantidades y elementos."""

import unittest

from echo_wsp.v05.primitives import Primitive
from echo_wsp.v05.primitives_science import (
    DIMENSIONLESS,
    ENERGY,
    LENGTH,
    MASS,
    SPEED,
    SCI_BASE,
    SCI_MAX,
    Dimension,
    Element,
    Quantity,
    SciPrimitive,
    resolve_science,
)


class TestPlanoCientifico(unittest.TestCase):
    def test_no_invade_el_nucleo_congelado(self):
        """Los 32 átomos originales siguen siendo el contrato binario."""
        core_codes = {p.code for p in Primitive}
        sci_codes = {p.code for p in SciPrimitive}
        self.assertEqual(core_codes & sci_codes, set())
        self.assertTrue(all(SCI_BASE <= c <= SCI_MAX for c in sci_codes))
        # el bit alto sigue reservado al marcador de concepto derivado
        self.assertTrue(all(c < 0x80 for c in sci_codes))

    def test_lookup_tolerante(self):
        self.assertIs(SciPrimitive.lookup("masa"), SciPrimitive.MASA)
        self.assertIs(SciPrimitive.lookup("MASS"), SciPrimitive.MASA)
        self.assertIs(SciPrimitive.lookup("energía"), SciPrimitive.ENERGIA)
        self.assertIsNone(SciPrimitive.lookup("xyzzy"))


class TestDimensiones(unittest.TestCase):
    def test_algebra_dimensional(self):
        self.assertEqual(LENGTH / Dimension(T=1), SPEED)
        self.assertEqual(MASS * SPEED * SPEED, ENERGY)
        self.assertEqual(ENERGY.notation(), "M·L²·T⁻²")
        self.assertTrue(DIMENSIONLESS.is_dimensionless())

    def test_atomos_de_una_dimension(self):
        atoms = ENERGY.atoms()
        self.assertIn(SciPrimitive.MASA, atoms)
        self.assertIn(SciPrimitive.LONGITUD, atoms)
        self.assertIn(SciPrimitive.DURACION, atoms)

    def test_roundtrip_binario(self):
        for dimension in (ENERGY, SPEED, DIMENSIONLESS, Dimension(M=-2, J=3)):
            self.assertEqual(Dimension.from_bytes(dimension.to_bytes()), dimension)


class TestCantidades(unittest.TestCase):
    def test_valor_y_roundtrip(self):
        q = Quantity.of(12.011)
        self.assertAlmostEqual(q.value, 12.011, places=6)
        recovered, _ = Quantity.from_bytes(q.to_bytes())
        self.assertEqual(recovered, q)

    def test_mantisa_es_entero_binario(self):
        """La codificación no depende de la base numérica del emisor."""
        q = Quantity.of(12.011)
        self.assertIsInstance(q.mantissa, int)
        self.assertEqual(q.mantissa, 12011)
        self.assertEqual(q.exponent, -3)
        # los bits son los mismos sea cual sea la base en que se lea el entero
        self.assertEqual(int(bin(q.mantissa), 2), q.mantissa)
        self.assertEqual(int(oct(q.mantissa), 8), q.mantissa)
        self.assertAlmostEqual(q.value, 12.011, places=9)

    def test_negativos_y_exponentes(self):
        for value in (-273.15, 6.62607e-34, 2.998e8, 0.0):
            q = Quantity.of(value)
            recovered, _ = Quantity.from_bytes(q.to_bytes())
            self.assertAlmostEqual(recovered.value, value, delta=abs(value) * 1e-5 or 1e-9)

    def test_comparacion_exige_misma_dimension(self):
        tres_kg = Quantity.of(3.0, MASS)
        cinco_kg = Quantity.of(5.0, MASS)
        self.assertIs(tres_kg.compare(cinco_kg), SciPrimitive.MENOR)
        self.assertIs(cinco_kg.compare(tres_kg), SciPrimitive.MAYOR)
        self.assertIs(tres_kg.compare(Quantity.of(3.0, MASS)), SciPrimitive.IGUAL)
        with self.assertRaises(ValueError):
            tres_kg.compare(Quantity.of(3.0, LENGTH))

    def test_producto_conserva_dimension(self):
        masa = Quantity.of(2.0, MASS)
        c2 = Quantity.of(9.0, SPEED) * Quantity.of(1.0, SPEED)
        energia = masa * c2
        self.assertEqual(energia.dimension, ENERGY)
        self.assertAlmostEqual(energia.value, 18.0)


class TestElementos(unittest.TestCase):
    def test_la_identidad_es_Z(self):
        """El elemento es su número atómico; el nombre es máscara humana."""
        carbono = Element(6)
        self.assertEqual(carbono.Z, 6)
        self.assertEqual(carbono.symbol, "C")
        self.assertEqual(carbono.name("es"), "carbono")
        self.assertEqual(carbono.name("en"), "carbon")
        self.assertEqual(carbono, Element(6))

    def test_elemento_sin_mascara_sigue_siendo_valido(self):
        exotico = Element(113)
        self.assertEqual(exotico.symbol, "Z=113")
        self.assertIn("113", exotico.name("es"))

    def test_lookup_por_cualquier_mascara(self):
        for token in ("C", "carbono", "carbon", "6", "Z=6"):
            self.assertEqual(Element.lookup(token), Element(6), token)

    def test_rango_valido(self):
        with self.assertRaises(ValueError):
            Element(0)
        with self.assertRaises(ValueError):
            Element(200)

    def test_roundtrip_binario_en_un_byte(self):
        for z in (1, 6, 26, 92, 118):
            self.assertEqual(len(Element(z).to_bytes()), 1)
            self.assertEqual(Element.from_bytes(Element(z).to_bytes())[0], Element(z))

    def test_masa_atomica(self):
        self.assertAlmostEqual(Element(6).atomic_mass().value, 12.011, places=3)
        self.assertIsNone(Element(113).atomic_mass())

    def test_resolve_science_unifica(self):
        self.assertIs(resolve_science("energía"), SciPrimitive.ENERGIA)
        self.assertEqual(resolve_science("xenón"), Element(54))
        self.assertIsNone(resolve_science("no-existe-esto"))


if __name__ == "__main__":
    unittest.main()
