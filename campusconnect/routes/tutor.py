"""Funciones del tutor: publicar disponibilidad y responder solicitudes (RF07, RF08)."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .. import validators as v
from ..db import ahora, get_db
from ..security import registrar_evento, rol_requerido

bp = Blueprint("tutor", __name__, url_prefix="/tutor")


@bp.route("/disponibilidad", methods=("GET", "POST"))
@rol_requerido("tutor")
def disponibilidad():
    db = get_db()
    if request.method == "POST":
        try:
            dia, ini, fin = v.tramo(request.form.get("dia"), request.form.get("inicio"),
                                    request.form.get("fin"), duracion_minima=30)
            existentes = [(f["dia"], f["inicio"], f["fin"]) for f in db.execute(
                "SELECT dia, inicio, fin FROM disponibilidad_tutor WHERE tutor_id = ?",
                (g.usuario["id"],))]
            if v.hay_solape(existentes, dia, ini, fin):
                raise v.ErrorValidacion("Ese tramo se superpone con otro ya publicado.")
        except v.ErrorValidacion as e:
            flash(str(e), "error")
            return redirect(url_for("tutor.disponibilidad"))
        db.execute("INSERT INTO disponibilidad_tutor (tutor_id, dia, inicio, fin) VALUES (?, ?, ?, ?)",
                   (g.usuario["id"], dia, ini, fin))
        db.commit()
        flash("Disponibilidad publicada.", "ok")
        return redirect(url_for("tutor.disponibilidad"))
    filas = db.execute("SELECT * FROM disponibilidad_tutor WHERE tutor_id = ? ORDER BY dia, inicio",
                       (g.usuario["id"],)).fetchall()
    return render_template("tutor_disponibilidad.html", tramos=filas)


@bp.route("/disponibilidad/<int:tramo_id>/eliminar", methods=("POST",))
@rol_requerido("tutor")
def disponibilidad_eliminar(tramo_id):
    db = get_db()
    n = db.execute("DELETE FROM disponibilidad_tutor WHERE id = ? AND tutor_id = ?",
                   (tramo_id, g.usuario["id"])).rowcount
    db.commit()
    if n == 0:
        abort(404)
    flash("Tramo eliminado.", "ok")
    return redirect(url_for("tutor.disponibilidad"))


@bp.route("/solicitudes")
@rol_requerido("tutor")
def solicitudes():
    filas = get_db().execute(
        "SELECT s.id, s.estado, s.motivo, a.nombre AS asignatura, u.nombre AS estudiante, "
        "d.dia, d.inicio, d.fin FROM solicitudes_tutoria s "
        "JOIN asignaturas a ON a.id = s.asignatura_id JOIN usuarios u ON u.id = s.estudiante_id "
        "JOIN disponibilidad_tutor d ON d.id = s.disponibilidad_id "
        "WHERE s.tutor_id = ? ORDER BY s.id DESC", (g.usuario["id"],)).fetchall()
    return render_template("tutor_solicitudes.html", solicitudes=filas)


@bp.route("/solicitudes/<int:sol_id>/responder", methods=("POST",))
@rol_requerido("tutor")
def responder(sol_id):
    db = get_db()
    accion = request.form.get("accion")
    if accion not in ("aceptar", "rechazar"):
        abort(400)
    sol = db.execute("SELECT * FROM solicitudes_tutoria WHERE id = ? AND tutor_id = ? "
                     "AND estado = 'pendiente'", (sol_id, g.usuario["id"])).fetchone()
    if sol is None:
        abort(404)
    motivo = ""
    if accion == "rechazar":
        try:
            motivo = v.texto(request.form.get("motivo"), "Motivo", 3, 200)
        except v.ErrorValidacion as e:
            flash(str(e), "error")
            return redirect(url_for("tutor.solicitudes"))
    estado = "aceptada" if accion == "aceptar" else "rechazada"
    db.execute("UPDATE solicitudes_tutoria SET estado = ?, motivo = ? WHERE id = ?",
               (estado, motivo, sol_id))
    texto = ("Tu tutoría fue confirmada." if estado == "aceptada"
             else f"Tu solicitud de tutoría fue rechazada: {motivo}")
    db.execute("INSERT INTO notificaciones (usuario_id, mensaje, creada) VALUES (?, ?, ?)",
               (sol["estudiante_id"], texto, ahora()))
    db.commit()
    registrar_evento("tutoria_" + estado, f"solicitud={sol_id}")
    flash("Respuesta registrada.", "ok")
    return redirect(url_for("tutor.solicitudes"))
