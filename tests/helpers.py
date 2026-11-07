"""Utilidades compartidas por las pruebas."""
import os
import re
import tempfile
import unittest
from datetime import date

from campusconnect import create_app
from campusconnect.db import ahora, get_db
from campusconnect.security import hash_contrasena

CLAVE = "ClaveSegura123"
HOY = date(2026, 11, 9)  # lunes


class BaseTest(unittest.TestCase):
    """Crea una aplicación y una base de datos temporal para cada prueba."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"DATABASE": os.path.join(self.tmp.name, "t.db"),
                               "TESTING": True, "HOY": HOY})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    # ---- datos --------------------------------------------------------
    def sql(self, consulta, params=()):
        with self.app.app_context():
            cur = get_db().execute(consulta, params)
            get_db().commit()
            return [dict(f) for f in cur.fetchall()] if cur.description else cur.lastrowid

    def crear_usuario(self, correo, rol="estudiante", nombre="Usuario Prueba", clave=CLAVE):
        return self.sql(
            "INSERT INTO usuarios (nombre, correo, hash, rol, carrera, creado) VALUES (?,?,?,?,?,?)",
            (nombre, correo, hash_contrasena(clave), rol, "Ingeniería en Informática", ahora()))

    def crear_asignatura(self, codigo="TI3043", nombre="Ingeniería de Software"):
        return self.sql("INSERT INTO asignaturas (codigo, nombre, carrera) VALUES (?,?,?)",
                        (codigo, nombre, "Ingeniería en Informática"))

    # ---- navegación ---------------------------------------------------
    def token(self, client, url="/login"):
        html = client.get(url).get_data(as_text=True)
        m = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(m, "la página no incluye token CSRF")
        return m.group(1)

    def login(self, client, correo, clave=CLAVE):
        return client.post("/login", data={"correo": correo, "contrasena": clave,
                                           "csrf_token": self.token(client)})

    def sesion(self, correo, rol="estudiante", nombre="Usuario Prueba"):
        """Crea un usuario, inicia sesión y devuelve (cliente, id)."""
        uid = self.crear_usuario(correo, rol, nombre)
        cliente = self.app.test_client()
        self.assertEqual(self.login(cliente, correo).status_code, 302)
        return cliente, uid

    def enviar(self, client, url, datos=None, **kw):
        datos = dict(datos or {})
        datos["csrf_token"] = self.token(client, "/panel")
        return client.post(url, data=datos, **kw)

    def agregar_bloque(self, client, dia=0, ini="16:00", fin="20:00"):
        return self.enviar(client, "/horario", {"dia": dia, "inicio": ini, "fin": fin})

    def agregar_evaluacion(self, client, asig_id, fecha="2026-11-13", pond=40, dif=4, tipo="Prueba"):
        return self.enviar(client, "/evaluaciones", {
            "asignatura_id": asig_id, "fecha": fecha, "ponderacion": pond,
            "dificultad": dif, "tipo": tipo})
