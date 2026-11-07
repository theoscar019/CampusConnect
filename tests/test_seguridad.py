"""Pruebas de seguridad (OWASP Top 10) sobre el prototipo."""
from campusconnect.security import neutralizar_csv, verificar_contrasena
from tests.helpers import CLAVE, BaseTest


class TestControlDeAcceso(BaseTest):  # A01
    def test_rutas_privadas_redirigen_al_login(self):
        for url in ("/panel", "/horario", "/plan", "/tutor/solicitudes", "/admin/reportes"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/login", r.headers["Location"])

    def test_estudiante_no_accede_a_rutas_de_admin_ni_tutor(self):
        c, _ = self.sesion("est@inacapmail.cl")
        for url in ("/admin/reportes", "/admin/tutores", "/admin/reportes.csv", "/tutor/solicitudes"):
            self.assertEqual(c.get(url).status_code, 403, url)
        r = self.enviar(c, "/admin/asignaturas", {"codigo": "X1X", "nombre": "Hack", "carrera": "Hack"})
        self.assertEqual(r.status_code, 403)

    def test_tutor_no_accede_a_funciones_de_estudiante(self):
        c, _ = self.sesion("tut@inacap.cl", rol="tutor")
        for url in ("/plan", "/horario", "/grupos", "/tutorias"):
            self.assertEqual(c.get(url).status_code, 403, url)

    def test_no_se_puede_borrar_el_horario_de_otra_persona(self):
        a, _ = self.sesion("a@inacapmail.cl")
        b, _ = self.sesion("b@inacapmail.cl")
        self.agregar_bloque(a)
        bloque_id = self.sql("SELECT id FROM bloques")[0]["id"]
        r = self.enviar(b, f"/horario/{bloque_id}/eliminar")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(len(self.sql("SELECT id FROM bloques")), 1)

    def test_no_se_puede_responder_la_solicitud_de_otro_tutor(self):
        asig = self.crear_asignatura()
        t1, t1id = self.sesion("t1@inacap.cl", rol="tutor")
        t2, _ = self.sesion("t2@inacap.cl", rol="tutor")
        est, eid = self.sesion("e@inacapmail.cl")
        disp = self.sql("INSERT INTO disponibilidad_tutor (tutor_id, dia, inicio, fin) VALUES (?,?,?,?)",
                        (t1id, 0, 960, 1020))
        sol = self.sql("INSERT INTO solicitudes_tutoria (estudiante_id, tutor_id, asignatura_id, "
                       "disponibilidad_id, creada) VALUES (?,?,?,?, 'x')", (eid, t1id, asig, disp))
        r = self.enviar(t2, f"/tutor/solicitudes/{sol}/responder", {"accion": "aceptar"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.sql("SELECT estado FROM solicitudes_tutoria")[0]["estado"], "pendiente")

    def test_el_registro_no_permite_elegir_rol(self):
        c = self.app.test_client()
        c.post("/registro", data={"nombre": "Intruso", "correo": "intruso@inacapmail.cl",
                                  "carrera": "Otra", "contrasena": CLAVE, "contrasena2": CLAVE,
                                  "rol": "admin", "csrf_token": self.token(c, "/registro")})
        self.assertEqual(self.sql("SELECT rol FROM usuarios WHERE correo = 'intruso@inacapmail.cl'")[0]["rol"],
                         "estudiante")


class TestCriptografiaYSesion(BaseTest):  # A02, A07
    def test_la_contrasena_se_guarda_con_hash(self):
        self.crear_usuario("h@inacapmail.cl")
        h = self.sql("SELECT hash FROM usuarios")[0]["hash"]
        self.assertNotIn(CLAVE, h)
        self.assertTrue(h.startswith(("scrypt:", "pbkdf2:")))
        self.assertTrue(verificar_contrasena(h, CLAVE))
        self.assertFalse(verificar_contrasena(h, "otra"))

    def test_cookie_de_sesion_httponly_y_samesite(self):
        self.crear_usuario("c@inacapmail.cl")
        r = self.login(self.app.test_client(), "c@inacapmail.cl")
        cookie = r.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_mensaje_de_login_no_revela_si_el_usuario_existe(self):
        self.crear_usuario("existe@inacapmail.cl")
        c = self.app.test_client()
        r1 = self.login(c, "existe@inacapmail.cl", "ClaveIncorrecta1")
        r2 = self.login(c, "noexiste@inacapmail.cl", "ClaveIncorrecta1")
        self.assertEqual(r1.status_code, 401)
        self.assertEqual(r2.status_code, 401)
        self.assertIn("Correo o contraseña incorrectos", r1.get_data(as_text=True))
        self.assertIn("Correo o contraseña incorrectos", r2.get_data(as_text=True))

    def test_bloqueo_tras_intentos_fallidos(self):
        self.crear_usuario("b@inacapmail.cl")
        c = self.app.test_client()
        for _ in range(self.app.config["MAX_INTENTOS"]):
            self.assertEqual(self.login(c, "b@inacapmail.cl", "Mala1234567").status_code, 401)
        r = self.login(c, "b@inacapmail.cl", CLAVE)       # incluso con la clave correcta
        self.assertEqual(r.status_code, 429)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM auditoria WHERE evento = 'cuenta_bloqueada'")[0]["n"], 1)

    def test_logout_cierra_la_sesion(self):
        c, _ = self.sesion("l@inacapmail.cl")
        self.assertEqual(c.get("/panel").status_code, 200)
        self.enviar(c, "/logout")
        self.assertEqual(c.get("/panel").status_code, 302)

    def test_registro_rechaza_dominio_externo_y_clave_debil(self):
        c = self.app.test_client()
        base = {"nombre": "Ana", "carrera": "Otra", "csrf_token": self.token(c, "/registro")}
        r = c.post("/registro", data={**base, "correo": "ana@gmail.com",
                                       "contrasena": CLAVE, "contrasena2": CLAVE})
        self.assertEqual(r.status_code, 400)
        r = c.post("/registro", data={**base, "correo": "ana@inacapmail.cl",
                                       "contrasena": "123", "contrasena2": "123"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM usuarios")[0]["n"], 0)


class TestInyeccionYXSS(BaseTest):  # A03
    def test_inyeccion_sql_en_login_no_autentica(self):
        self.crear_usuario("v@inacapmail.cl")
        c = self.app.test_client()
        for carga in ("' OR '1'='1", "v@inacapmail.cl' --", "'; DROP TABLE usuarios; --"):
            r = self.login(c, carga, carga)
            self.assertEqual(r.status_code, 401, carga)
        self.assertEqual(c.get("/panel").status_code, 302)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM usuarios")[0]["n"], 1)

    def test_inyeccion_sql_en_formularios_se_rechaza(self):
        c, _ = self.sesion("i@inacapmail.cl")
        self.crear_asignatura()
        r = self.agregar_evaluacion(c, "1 OR 1=1", fecha="2026-11-13'; DROP TABLE evaluaciones;--")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM evaluaciones")[0]["n"], 0)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM usuarios")[0]["n"], 1)

    def test_xss_se_escapa_al_mostrar_datos(self):
        carga = "<script>alert(1)</script>"
        c, _ = self.sesion("x@inacapmail.cl", nombre=carga)
        html = c.get("/panel").get_data(as_text=True)
        self.assertNotIn(carga, html)
        self.assertIn("&lt;script&gt;", html)

    def test_csv_neutraliza_formulas(self):
        for peligro in ("=HYPERLINK(\"x\")", "+1+1", "-2+3", "@SUM(A1)"):
            self.assertTrue(neutralizar_csv(peligro).startswith("'"))
        self.assertEqual(neutralizar_csv("Normal"), "Normal")


class TestConfiguracionYCSRF(BaseTest):  # A04, A05, A09
    def test_cabeceras_de_seguridad(self):
        h = self.client.get("/login").headers
        self.assertIn("default-src 'self'", h["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"])
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertIn("Referrer-Policy", h)

    def test_post_sin_token_csrf_se_rechaza(self):
        c, _ = self.sesion("t@inacapmail.cl")
        r = c.post("/horario", data={"dia": 0, "inicio": "16:00", "fin": "18:00"})
        self.assertEqual(r.status_code, 400)
        r = c.post("/horario", data={"dia": 0, "inicio": "16:00", "fin": "18:00", "csrf_token": "falso"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM bloques")[0]["n"], 0)

    def test_modo_debug_desactivado_y_errores_sin_detalle_tecnico(self):
        self.assertFalse(self.app.debug)
        r = self.client.get("/ruta-inexistente")
        self.assertEqual(r.status_code, 404)
        self.assertNotIn("Traceback", r.get_data(as_text=True))

    def test_se_auditan_eventos_de_seguridad(self):
        self.crear_usuario("a@inacapmail.cl")
        c = self.app.test_client()
        self.login(c, "a@inacapmail.cl", "Incorrecta123")
        self.login(c, "a@inacapmail.cl")
        eventos = {f["evento"] for f in self.sql("SELECT evento FROM auditoria")}
        self.assertTrue({"login_fallido", "login_ok"} <= eventos)

    def test_cuerpo_demasiado_grande_se_rechaza(self):
        c, _ = self.sesion("g@inacapmail.cl")
        r = c.post("/horario", data={"dia": 0, "inicio": "16:00", "fin": "18:00",
                                     "csrf_token": "x" * 70000})
        self.assertIn(r.status_code, (400, 413))


if __name__ == "__main__":
    import unittest
    unittest.main()
