"""Datos de demostración. Las contraseñas se generan al azar y se muestran una sola vez."""
import secrets

from . import db as basedatos
from .db import ahora
from .security import hash_contrasena


def _clave():
    return "Cc" + secrets.token_urlsafe(9) + "7!"


def cargar_datos_demo():
    """Crea un administrador, un tutor, dos estudiantes y asignaturas. Devuelve credenciales."""
    conexion = basedatos.get_db()
    if conexion.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
        raise RuntimeError("La base de datos ya tiene usuarios; no se cargan datos de demostración.")
    asignaturas = [("TI3043", "Ingeniería de Software", "Ingeniería en Informática"),
                   ("TI2010", "Bases de Datos", "Ingeniería en Informática"),
                   ("MA1010", "Cálculo", "Ingeniería en Informática")]
    for cod, nom, car in asignaturas:
        conexion.execute("INSERT INTO asignaturas (codigo, nombre, carrera) VALUES (?, ?, ?)",
                         (cod, nom, car))
    cuentas = [("Admin Académico", "admin@inacap.cl", "admin", ""),
               ("Tutora Demo", "tutor.demo@inacap.cl", "tutor", ""),
               ("Estudiante Uno", "estudiante1@inacapmail.cl", "estudiante", "Ingeniería en Informática"),
               ("Estudiante Dos", "estudiante2@inacapmail.cl", "estudiante", "Ingeniería en Informática")]
    credenciales = []
    for nombre, correo, rol, carrera in cuentas:
        clave = _clave()
        uid = conexion.execute(
            "INSERT INTO usuarios (nombre, correo, hash, rol, carrera, creado) VALUES (?, ?, ?, ?, ?, ?)",
            (nombre, correo, hash_contrasena(clave), rol, carrera, ahora())).lastrowid
        credenciales.append((rol, correo, clave))
        if rol == "tutor":
            conexion.execute("INSERT INTO tutor_asignaturas VALUES (?, 1)", (uid,))
            conexion.execute("INSERT INTO tutor_asignaturas VALUES (?, 2)", (uid,))
            conexion.execute("INSERT INTO disponibilidad_tutor (tutor_id, dia, inicio, fin) "
                             "VALUES (?, 2, 1020, 1080)", (uid,))
    conexion.commit()
    return credenciales
