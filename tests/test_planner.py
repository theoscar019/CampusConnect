"""Pruebas unitarias del algoritmo planificador (RF03, RF04, RF05)."""
import unittest
from datetime import date

from campusconnect.planner import (Bloque, Evaluacion, ESTUDIO_MAX, fusionar_bloques,
                                   generar_plan, minutos_requeridos, prioridad)

HOY = date(2026, 11, 9)  # lunes


def ev(i, dias, pond=40, dif=3, nombre=None):
    return Evaluacion(i, i, nombre or f"Asig{i}", date.fromordinal(HOY.toordinal() + dias), pond, dif)


class TestPlanner(unittest.TestCase):
    def test_minutos_requeridos_minimo_y_escala(self):
        self.assertEqual(minutos_requeridos(ev(1, 5, pond=1, dif=1)), 30)
        self.assertGreater(minutos_requeridos(ev(1, 5, pond=80, dif=5)),
                           minutos_requeridos(ev(1, 5, pond=20, dif=2)))

    def test_prioridad_aumenta_con_peso_dificultad_y_cercania(self):
        base = prioridad(ev(1, 10, pond=20, dif=2), HOY)
        self.assertGreater(prioridad(ev(1, 10, pond=60, dif=2), HOY), base)
        self.assertGreater(prioridad(ev(1, 10, pond=20, dif=5), HOY), base)
        self.assertGreater(prioridad(ev(1, 2, pond=20, dif=2), HOY), base)

    def test_fusionar_bloques_une_solapados(self):
        r = fusionar_bloques([Bloque(0, 600, 700), Bloque(0, 690, 800), Bloque(1, 600, 660)])
        self.assertEqual(r[0], [Bloque(0, 600, 800)])
        self.assertEqual(len(r[1]), 1)

    def test_sesiones_solo_en_bloques_libres_y_antes_de_la_fecha(self):
        res = generar_plan([ev(1, 4)], [Bloque(0, 960, 1200), Bloque(2, 960, 1200)], HOY)
        self.assertTrue(res.sesiones)
        for s in res.sesiones:
            self.assertIn(s.fecha.weekday(), (0, 2))
            self.assertGreaterEqual(s.inicio, 960)
            self.assertLessEqual(s.fin, 1200)
            self.assertLess(s.fecha, date.fromordinal(HOY.toordinal() + 4))

    def test_pausa_activa_despues_de_estudio_continuo(self):
        res = generar_plan([ev(1, 6, pond=80, dif=5)], [Bloque(0, 480, 780)], HOY)
        self.assertTrue(any(s.es_pausa for s in res.sesiones))
        continuo = 0
        for s in res.sesiones:          # el estudio seguido nunca supera el máximo
            if s.es_pausa:
                continuo = 0
            else:
                continuo += s.fin - s.inicio
                self.assertLessEqual(continuo, ESTUDIO_MAX)

    def test_sin_solapes_entre_sesiones(self):
        res = generar_plan([ev(1, 6), ev(2, 5, pond=70, dif=5), ev(3, 3)],
                           [Bloque(0, 540, 840), Bloque(1, 540, 840)], HOY)
        previas = sorted(res.sesiones, key=lambda s: (s.fecha, s.inicio))
        for a, b in zip(previas, previas[1:]):
            if a.fecha == b.fecha:
                self.assertLessEqual(a.fin, b.inicio)

    def test_sobrecarga_cuando_las_horas_no_alcanzan(self):
        res = generar_plan([ev(1, 6, pond=90, dif=5)], [Bloque(0, 600, 640)], HOY)
        self.assertTrue(res.sobrecarga)
        self.assertGreater(res.deficit[1], 0)

    def test_sin_bloques_todo_es_deficit(self):
        res = generar_plan([ev(1, 5), ev(2, 5)], [], HOY)
        self.assertEqual(res.sesiones, [])
        self.assertEqual(set(res.deficit), {1, 2})

    def test_la_evaluacion_mas_prioritaria_obtiene_el_primer_bloque(self):
        urgente = ev(1, 2, pond=80, dif=5, nombre="Urgente")
        lejana = ev(2, 12, pond=10, dif=1, nombre="Lejana")
        res = generar_plan([lejana, urgente], [Bloque(0, 600, 720)], HOY)
        self.assertEqual(res.orden[0], 1)
        estudio = [s for s in res.sesiones if not s.es_pausa]
        self.assertEqual(estudio[0].asignatura, "Urgente")

    def test_no_planifica_el_dia_de_la_evaluacion(self):
        res = generar_plan([ev(1, 7)], [Bloque(0, 600, 720)], HOY)  # evaluación el lunes siguiente
        self.assertTrue(all(s.fecha < date.fromordinal(HOY.toordinal() + 7) for s in res.sesiones))


if __name__ == "__main__":
    unittest.main()
