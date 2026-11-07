"""Pruebas unitarias de validadores y emparejamiento (RF06)."""
import unittest
from datetime import date

from campusconnect import validators as v
from campusconnect.matching import (EmparejamientoPorHorario, ServicioEmparejamiento,
                                    minutos_en_comun)
from campusconnect.planner import Bloque

DOMINIOS = ("inacapmail.cl", "inacap.cl")


class TestValidadores(unittest.TestCase):
    def test_correo_institucional(self):
        self.assertEqual(v.correo(" Ana@InacapMail.cl ", DOMINIOS), "ana@inacapmail.cl")
        for malo in ("ana@gmail.com", "ana", "ana@@inacapmail.cl", "", None):
            with self.assertRaises(v.ErrorValidacion):
                v.correo(malo, DOMINIOS)

    def test_hora_y_tramo(self):
        self.assertEqual(v.hora_a_minutos("16:30"), 990)
        for malo in ("25:00", "9:00", "abc", "", "16:60"):
            with self.assertRaises(v.ErrorValidacion):
                v.hora_a_minutos(malo)
        self.assertEqual(v.tramo("0", "16:00", "18:00"), (0, 960, 1080))
        with self.assertRaises(v.ErrorValidacion):
            v.tramo("0", "18:00", "16:00")
        with self.assertRaises(v.ErrorValidacion):
            v.tramo("9", "16:00", "18:00")

    def test_fecha_futura(self):
        hoy = date(2026, 11, 9)
        self.assertEqual(v.fecha_futura("2026-11-12", hoy), date(2026, 11, 12))
        for mala in ("2026-11-09", "2020-01-01", "2030-01-01", "12/11/2026", "'; DROP TABLE x;--"):
            with self.assertRaises(v.ErrorValidacion):
                v.fecha_futura(mala, hoy)

    def test_entero_y_texto(self):
        self.assertEqual(v.entero("4", "x", 1, 5), 4)
        for malo in ("0", "6", "abc", "", None, "1.5"):
            with self.assertRaises(v.ErrorValidacion):
                v.entero(malo, "x", 1, 5)
        with self.assertRaises(v.ErrorValidacion):
            v.texto("   ", "Nombre", 2, 10)

    def test_politica_de_contrasenas(self):
        self.assertEqual(v.validar_contrasena("ClaveSegura123", "ana@inacapmail.cl"), [])
        self.assertTrue(v.validar_contrasena("corta1A"))
        self.assertTrue(v.validar_contrasena("sinmayuscula123"))
        self.assertTrue(v.validar_contrasena("SINMINUSCULA123"))
        self.assertTrue(v.validar_contrasena("SinNumerosAqui"))
        self.assertTrue(v.validar_contrasena("Maria1234567", "maria@inacapmail.cl"))

    def test_hay_solape(self):
        self.assertTrue(v.hay_solape([(0, 600, 700)], 0, 650, 750))
        self.assertFalse(v.hay_solape([(0, 600, 700)], 0, 700, 800))
        self.assertFalse(v.hay_solape([(0, 600, 700)], 1, 600, 700))


class TestMatching(unittest.TestCase):
    A = [Bloque(0, 960, 1200), Bloque(2, 960, 1200)]

    def test_minutos_en_comun(self):
        self.assertEqual(minutos_en_comun(self.A, [Bloque(0, 1000, 1100)]), 100)
        self.assertEqual(minutos_en_comun(self.A, [Bloque(1, 960, 1200)]), 0)

    def test_elige_el_grupo_mas_compatible(self):
        grupos = {1: [[Bloque(0, 960, 1080)]], 2: [[Bloque(0, 960, 1200), Bloque(2, 960, 1200)]]}
        mejor = ServicioEmparejamiento(EmparejamientoPorHorario(120)).mejor_grupo(self.A, grupos)
        self.assertEqual(mejor[0], 2)

    def test_sin_compatibilidad_devuelve_none(self):
        grupos = {1: [[Bloque(4, 600, 700)]]}
        self.assertIsNone(ServicioEmparejamiento(EmparejamientoPorHorario(120)).mejor_grupo(self.A, grupos))

    def test_la_estrategia_es_intercambiable(self):
        class Siempre(EmparejamientoPorHorario):
            def puntuar(self, a, b):
                return 1.0
        grupos = {7: [[Bloque(4, 600, 700)]]}
        self.assertEqual(ServicioEmparejamiento(Siempre()).mejor_grupo(self.A, grupos)[0], 7)


if __name__ == "__main__":
    unittest.main()
