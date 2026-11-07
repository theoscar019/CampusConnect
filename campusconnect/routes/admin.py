"""Funciones del administrador académico: asignaturas, tutores y reportes (RF09, RF10)."""
import csv
import io

from flask import (Blueprint, Response, abort, flash, g, redirect, render_template,
                   request, url_for, current_app)

from .. import validators as v
from ..db import ahora, get_db
from ..security import hash_contrasena, neutralizar_csv, registrar_evento, rol_requerido

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/asignaturas", methods=("GET", "POST"))
@rol_requerido("admin")
def asignaturas():
    db = get_db()
    if request.method == "POST":
        try:
            codigo = v.texto(request.form.get("codigo"), "Código", 3, 20).upper()
            nombre = v.texto(request.form.get("nombre"), "Nombre", 3, 80)
            carrera = v.texto(request.form.get("carrera"), "Carrera", 3, 80)
            if db.execute("SELECT 1 FROM asignaturas WHERE codigo = ?", (codigo,)).fetchone():
                raise v.ErrorValidacion("Ya existe una asignatura con ese código.")
        except v.ErrorValidacion as e:
            flash(str(e), "error")
            return redirect(url_for("admin.asignaturas"))
        db.execute("INSERT INTO asignaturas (codigo, nombre, carrera) VALUES (?, ?, ?)",
                   (codigo, nombre, carrera))
        db.commit()
        registrar_evento("asignatura_creada", codigo)
        flash("Asignatura creada.", "ok")
        return redirect(url_for("admin.asignaturas"))
    filas = db.execute("SELECT * FROM asignaturas ORDER BY activa DESC, nombre").fetchall()
    return render_template("admin_asignaturas.html", asignaturas=filas)


@bp.route("/asignaturas/<int:asig_id>/alternar", methods=("POST",))
@rol_requerido("admin")
def asignatura_alternar(asig_id):
    db = get_db()
    n = db.execute("UPDATE asignaturas SET activa = 1 - activa WHERE id = ?", (asig_id,)).rowcount
    db.commit()
    if n == 0:
        abort(404)
    registrar_evento("asignatura_alternada", str(asig_id))
    return redirect(url_for("admin.asignaturas"))


@bp.route("/tutores", methods=("GET", "POST"))
@rol_requerido("admin")
def tutores():
    db = get_db()
    asig = db.execute("SELECT * FROM asignaturas WHERE activa = 1 ORDER BY nombre").fetchall()
    if request.method == "POST":
        try:
            nombre = v.texto(request.form.get("nombre"), "Nombre", 2, 80)
            correo = v.correo(request.form.get("correo"), current_app.config["DOMINIOS_PERMITIDOS"])
            contrasena = request.form.get("contrasena", "")
            faltas = v.validar_contrasena(contrasena, correo)
            if faltas:
                raise v.ErrorValidacion("La contraseña temporal debe tener: " + ", ".join(faltas) + ".")
            ids = [v.entero(x, "Asignatura", 1, 10**9) for x in request.form.getlist("asignaturas")]
            if not ids:
                raise v.ErrorValidacion("Seleccione al menos una asignatura.")
            if db.execute("SELECT 1 FROM usuarios WHERE correo = ?", (correo,)).fetchone():
                raise v.ErrorValidacion("No fue posible crear el tutor con esos datos.")
        except v.ErrorValidacion as e:
            flash(str(e), "error")
            return redirect(url_for("admin.tutores"))
        tid = db.execute("INSERT INTO usuarios (nombre, correo, hash, rol, creado) "
                         "VALUES (?, ?, ?, 'tutor', ?)",
                         (nombre, correo, hash_contrasena(contrasena), ahora())).lastrowid
        for a in ids:
            if db.execute("SELECT 1 FROM asignaturas WHERE id = ?", (a,)).fetchone():
                db.execute("INSERT OR IGNORE INTO tutor_asignaturas VALUES (?, ?)", (tid, a))
        db.commit()
        registrar_evento("tutor_creado", correo)
        flash("Tutor creado.", "ok")
        return redirect(url_for("admin.tutores"))
    filas = db.execute(
        "SELECT u.id, u.nombre, u.correo, u.activo, "
        "(SELECT group_concat(a.nombre, ', ') FROM tutor_asignaturas ta "
        " JOIN asignaturas a ON a.id = ta.asignatura_id WHERE ta.tutor_id = u.id) AS asignaturas "
        "FROM usuarios u WHERE u.rol = 'tutor' ORDER BY u.nombre").fetchall()
    return render_template("admin_tutores.html", tutores=filas, asignaturas=asig)


@bp.route("/tutores/<int:tutor_id>/alternar", methods=("POST",))
@rol_requerido("admin")
def tutor_alternar(tutor_id):
    db = get_db()
    n = db.execute("UPDATE usuarios SET activo = 1 - activo WHERE id = ? AND rol = 'tutor'",
                   (tutor_id,)).rowcount
    db.commit()
    if n == 0:
        abort(404)
    registrar_evento("tutor_alternado", str(tutor_id))
    return redirect(url_for("admin.tutores"))


def _metricas(db):
    def uno(sql):
        return db.execute(sql).fetchone()[0]
    return [
        ("Estudiantes registrados", uno("SELECT COUNT(*) FROM usuarios WHERE rol = 'estudiante'")),
        ("Tutores activos", uno("SELECT COUNT(*) FROM usuarios WHERE rol = 'tutor' AND activo = 1")),
        ("Planes de estudio generados", uno("SELECT COUNT(*) FROM planes")),
        ("Grupos de estudio", uno("SELECT COUNT(*) FROM grupos")),
        ("Tutorías pendientes", uno("SELECT COUNT(*) FROM solicitudes_tutoria WHERE estado = 'pendiente'")),
        ("Tutorías aceptadas", uno("SELECT COUNT(*) FROM solicitudes_tutoria WHERE estado = 'aceptada'")),
        ("Tutorías rechazadas", uno("SELECT COUNT(*) FROM solicitudes_tutoria WHERE estado = 'rechazada'")),
    ]


@bp.route("/reportes")
@rol_requerido("admin")
def reportes():
    db = get_db()
    eventos = db.execute("SELECT evento, COUNT(*) AS n FROM auditoria GROUP BY evento "
                         "ORDER BY n DESC LIMIT 8").fetchall()
    return render_template("admin_reportes.html", metricas=_metricas(db), eventos=eventos)


@bp.route("/reportes.csv")
@rol_requerido("admin")
def reportes_csv():
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(["Indicador", "Valor"])
    for nombre, valor in _metricas(get_db()):
        escritor.writerow([neutralizar_csv(nombre), valor])
    registrar_evento("reporte_exportado")
    return Response(salida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=reporte_campusconnect.csv"})
