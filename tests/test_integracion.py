"""Pruebas de integración: flujos completos por rol."""
from tests.helpers import CLAVE, BaseTest


class TestFlujoEstudiante(BaseTest):
    def test_registro_login_y_plan_completo(self):
        asig = self.crear_asignatura()
        c = self.app.test_client()
        r = c.post("/registro", data={"nombre": "Ana Pérez", "correo": "ana@inacapmail.cl",
                                      "carrera": "Ingeniería en Informática", "contrasena": CLAVE,
                                      "contrasena2": CLAVE, "csrf_token": self.token(c, "/registro")})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.login(c, "ana@inacapmail.cl").status_code, 302)
        self.agregar_bloque(c, dia=0, ini="08:00", fin="13:00")
        self.agregar_evaluacion(c, asig, fecha="2026-11-13", pond=60, dif=5)
        r = self.enviar(c, "/plan/generar", follow_redirects=True)
        html = r.get_data(as_text=True)
        self.assertIn("Lunes 09/11", html)
        self.assertIn("Ingeniería de Software", html)
        self.assertIn("Pausa activa", html)
        self.assertIn("Reorganizar plan", html)

    def test_plan_requiere_horario_y_evaluaciones(self):
        c, _ = self.sesion("e@inacapmail.cl")
        r = self.enviar(c, "/plan/generar", follow_redirects=True)
        self.assertIn("registre al menos una evaluación", r.get_data(as_text=True))
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM planes")[0]["n"], 0)

    def test_alerta_de_sobrecarga(self):
        asig = self.crear_asignatura()
        c, _ = self.sesion("e@inacapmail.cl")
        self.agregar_bloque(c, dia=0, ini="10:00", fin="10:40")
        self.agregar_evaluacion(c, asig, fecha="2026-11-12", pond=90, dif=5)
        r = self.enviar(c, "/plan/generar", follow_redirects=True)
        self.assertIn("Alerta de sobrecarga", r.get_data(as_text=True))

    def test_reorganizar_reemplaza_el_plan_anterior(self):
        asig = self.crear_asignatura()
        c, _ = self.sesion("e@inacapmail.cl")
        self.agregar_bloque(c, dia=0, ini="08:00", fin="12:00")
        self.agregar_evaluacion(c, asig)
        self.enviar(c, "/plan/generar")
        self.agregar_bloque(c, dia=1, ini="08:00", fin="12:00")
        self.enviar(c, "/plan/generar")
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM planes")[0]["n"], 1)

    def test_validaciones_de_horario_y_evaluaciones(self):
        asig = self.crear_asignatura()
        c, _ = self.sesion("e@inacapmail.cl")
        self.agregar_bloque(c, dia=0, ini="16:00", fin="18:00")
        self.agregar_bloque(c, dia=0, ini="17:00", fin="19:00")      # se superpone
        self.agregar_bloque(c, dia=0, ini="19:00", fin="18:00")      # fin antes del inicio
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM bloques")[0]["n"], 1)
        self.agregar_evaluacion(c, asig, fecha="2026-11-01")         # fecha pasada
        self.agregar_evaluacion(c, asig, pond=150)                   # peso fuera de rango
        self.agregar_evaluacion(c, asig, dif=9)                      # dificultad fuera de rango
        self.agregar_evaluacion(c, asig, tipo="Hackeo")              # tipo inválido
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM evaluaciones")[0]["n"], 0)
        self.agregar_evaluacion(c, asig)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM evaluaciones")[0]["n"], 1)


class TestGrupos(BaseTest):
    def test_union_a_grupo_compatible_y_aviso_a_miembros(self):
        asig = self.crear_asignatura()
        a, _ = self.sesion("a@inacapmail.cl", nombre="Ana")
        b, _ = self.sesion("b@inacapmail.cl", nombre="Beto")
        for c in (a, b):
            self.agregar_bloque(c, dia=0, ini="16:00", fin="19:00")
        self.enviar(a, "/grupos/crear", {"nombre": "Los de Software", "asignatura_id": asig})
        r = self.enviar(b, "/grupos/solicitar", {"asignatura_id": asig}, follow_redirects=True)
        self.assertIn("Te uniste a un grupo", r.get_data(as_text=True))
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM grupo_miembros")[0]["n"], 2)
        self.assertIn("Beto se unió", a.get("/panel").get_data(as_text=True))

    def test_sin_horarios_compatibles_no_se_une(self):
        asig = self.crear_asignatura()
        a, _ = self.sesion("a@inacapmail.cl")
        b, _ = self.sesion("b@inacapmail.cl")
        self.agregar_bloque(a, dia=0, ini="16:00", fin="19:00")
        self.agregar_bloque(b, dia=3, ini="09:00", fin="12:00")
        self.enviar(a, "/grupos/crear", {"nombre": "Grupo A", "asignatura_id": asig})
        r = self.enviar(b, "/grupos/solicitar", {"asignatura_id": asig}, follow_redirects=True)
        self.assertIn("No hay un grupo con horarios compatibles", r.get_data(as_text=True))
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM grupo_miembros")[0]["n"], 1)

    def test_grupo_lleno_no_acepta_mas_miembros(self):
        asig = self.crear_asignatura()
        a, _ = self.sesion("a@inacapmail.cl")
        self.agregar_bloque(a, dia=0, ini="16:00", fin="19:00")
        self.enviar(a, "/grupos/crear", {"nombre": "Grupo A", "asignatura_id": asig})
        self.sql("UPDATE grupos SET capacidad = 1")
        b, _ = self.sesion("b@inacapmail.cl")
        self.agregar_bloque(b, dia=0, ini="16:00", fin="19:00")
        self.enviar(b, "/grupos/solicitar", {"asignatura_id": asig})
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM grupo_miembros")[0]["n"], 1)


class TestTutorias(BaseTest):
    def preparar(self):
        asig = self.crear_asignatura()
        admin, _ = self.sesion("admin@inacap.cl", rol="admin")
        self.enviar(admin, "/admin/tutores", {"nombre": "Tutora Ruiz", "correo": "ruiz@inacap.cl",
                                              "contrasena": CLAVE, "asignaturas": [asig]})
        tutor = self.app.test_client()
        self.assertEqual(self.login(tutor, "ruiz@inacap.cl").status_code, 302)
        self.enviar(tutor, "/tutor/disponibilidad", {"dia": 2, "inicio": "17:00", "fin": "18:00"})
        return asig, tutor

    def test_flujo_completo_solicitar_y_aceptar(self):
        asig, tutor = self.preparar()
        est, _ = self.sesion("e@inacapmail.cl")
        self.agregar_bloque(est, dia=2, ini="16:00", fin="19:00")
        disp = self.sql("SELECT id FROM disponibilidad_tutor")[0]["id"]
        self.enviar(est, "/tutorias/solicitar", {"disponibilidad_id": disp, "asignatura_id": asig})
        self.assertEqual(self.sql("SELECT estado FROM solicitudes_tutoria")[0]["estado"], "pendiente")
        self.assertIn("Nueva solicitud", tutor.get("/panel").get_data(as_text=True))
        sol = self.sql("SELECT id FROM solicitudes_tutoria")[0]["id"]
        self.enviar(tutor, f"/tutor/solicitudes/{sol}/responder", {"accion": "aceptar"})
        self.assertEqual(self.sql("SELECT estado FROM solicitudes_tutoria")[0]["estado"], "aceptada")
        self.assertIn("confirmada", est.get("/panel").get_data(as_text=True))

    def test_rechazo_exige_motivo(self):
        asig, tutor = self.preparar()
        est, eid = self.sesion("e@inacapmail.cl")
        self.agregar_bloque(est, dia=2, ini="16:00", fin="19:00")
        disp = self.sql("SELECT id FROM disponibilidad_tutor")[0]["id"]
        self.enviar(est, "/tutorias/solicitar", {"disponibilidad_id": disp, "asignatura_id": asig})
        sol = self.sql("SELECT id FROM solicitudes_tutoria")[0]["id"]
        self.enviar(tutor, f"/tutor/solicitudes/{sol}/responder", {"accion": "rechazar", "motivo": ""})
        self.assertEqual(self.sql("SELECT estado FROM solicitudes_tutoria")[0]["estado"], "pendiente")
        self.enviar(tutor, f"/tutor/solicitudes/{sol}/responder", {"accion": "rechazar", "motivo": "Cruce de horario"})
        self.assertEqual(self.sql("SELECT estado FROM solicitudes_tutoria")[0]["estado"], "rechazada")

    def test_horario_incompatible_se_rechaza(self):
        asig, _ = self.preparar()
        est, _ = self.sesion("e@inacapmail.cl")
        self.agregar_bloque(est, dia=4, ini="09:00", fin="12:00")       # el tutor atiende el miércoles
        disp = self.sql("SELECT id FROM disponibilidad_tutor")[0]["id"]
        self.enviar(est, "/tutorias/solicitar", {"disponibilidad_id": disp, "asignatura_id": asig})
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM solicitudes_tutoria")[0]["n"], 0)

    def test_horario_ya_tomado_no_se_puede_reservar_dos_veces(self):
        asig, _ = self.preparar()
        disp = self.sql("SELECT id FROM disponibilidad_tutor")[0]["id"]
        for correo in ("e1@inacapmail.cl", "e2@inacapmail.cl"):
            est, _ = self.sesion(correo)
            self.agregar_bloque(est, dia=2, ini="16:00", fin="19:00")
            self.enviar(est, "/tutorias/solicitar", {"disponibilidad_id": disp, "asignatura_id": asig})
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM solicitudes_tutoria")[0]["n"], 1)

    def test_cancelar_libera_el_horario(self):
        asig, _ = self.preparar()
        est, _ = self.sesion("e@inacapmail.cl")
        self.agregar_bloque(est, dia=2, ini="16:00", fin="19:00")
        disp = self.sql("SELECT id FROM disponibilidad_tutor")[0]["id"]
        self.enviar(est, "/tutorias/solicitar", {"disponibilidad_id": disp, "asignatura_id": asig})
        sol = self.sql("SELECT id FROM solicitudes_tutoria")[0]["id"]
        self.enviar(est, f"/tutorias/{sol}/cancelar")
        self.assertEqual(self.sql("SELECT estado FROM solicitudes_tutoria")[0]["estado"], "cancelada")
        html = est.get(f"/tutorias?asignatura_id={asig}").get_data(as_text=True)
        self.assertIn("Solicitar", html)


class TestAdministrador(BaseTest):
    def test_crear_asignatura_y_ver_reportes(self):
        admin, _ = self.sesion("admin@inacap.cl", rol="admin")
        self.enviar(admin, "/admin/asignaturas", {"codigo": "bd101", "nombre": "Bases de Datos",
                                                  "carrera": "Informática"})
        self.assertEqual(self.sql("SELECT codigo FROM asignaturas")[0]["codigo"], "BD101")
        self.enviar(admin, "/admin/asignaturas", {"codigo": "BD101", "nombre": "Duplicada", "carrera": "X"})
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM asignaturas")[0]["n"], 1)
        self.assertIn("Estudiantes registrados", admin.get("/admin/reportes").get_data(as_text=True))
        r = admin.get("/admin/reportes.csv")
        self.assertEqual(r.mimetype, "text/csv")
        self.assertIn("Indicador,Valor", r.get_data(as_text=True))

    def test_desactivar_tutor_le_impide_iniciar_sesion(self):
        admin, _ = self.sesion("admin@inacap.cl", rol="admin")
        tid = self.crear_usuario("t@inacap.cl", rol="tutor")
        self.enviar(admin, f"/admin/tutores/{tid}/alternar")
        self.assertEqual(self.login(self.app.test_client(), "t@inacap.cl").status_code, 401)


if __name__ == "__main__":
    import unittest
    unittest.main()
