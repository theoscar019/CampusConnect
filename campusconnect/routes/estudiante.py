"""Funciones del estudiante: horario, evaluaciones, plan, grupos y tutorías."""
from datetime import date

from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, url_for)

from .. import hoy as obtener_hoy
from .. import validators as v
from ..db import ahora, get_db
from ..matching import EmparejamientoPorHorario, ServicioEmparejamiento
from ..planner import Bloque, Evaluacion, generar_plan
from ..security import registrar_evento, rol_requerido

bp = Blueprint("estudiante", __name__)

PAUSAS = ("Estiramiento de cuello y hombros", "Caminata corta", "Respiración profunda",
          "Mirar a lo lejos y parpadear", "Hidratarse y moverse")


def _hoy():
    return obtener_hoy(current_app.config)


def _bloques(db, usuario_id):
    filas = db.execute("SELECT dia, inicio, fin FROM bloques WHERE usuario_id = ?",
                       (usuario_id,)).fetchall()
    return [Bloque(f["dia"], f["inicio"], f["fin"]) for f in filas]


def _notificar(db, usuario_id, mensaje):
    db.execute("INSERT INTO notificaciones (usuario_id, mensaje, creada) VALUES (?, ?, ?)",
               (usuario_id, mensaje, ahora()))


# ---- Horario (RF02) --------------------------------------------------------
@bp.route("/horario", methods=("GET", "POST"))
@rol_requerido("estudiante")
def horario():
    db = get_db()
    if request.method == "POST":
        try:
            dia, ini, fin = v.tramo(request.form.get("dia"), request.form.get("inicio"),
                                    request.form.get("fin"))
            existentes = [(b.dia, b.inicio, b.fin) for b in _bloques(db, g.usuario["id"])]
            if v.hay_solape(existentes, dia, ini, fin):
                raise v.ErrorValidacion("Ese tramo se superpone con otro ya registrado.")
        except v.ErrorValidacion as e:
            flash(str(e), "error")
            return redirect(url_for("estudiante.horario"))
        db.execute("INSERT INTO bloques (usuario_id, dia, inicio, fin) VALUES (?, ?, ?, ?)",
                   (g.usuario["id"], dia, ini, fin))
        db.commit()
        flash("Tramo libre guardado.", "ok")
        return redirect(url_for("estudiante.horario"))
    filas = db.execute("SELECT * FROM bloques WHERE usuario_id = ? ORDER BY dia, inicio",
                       (g.usuario["id"],)).fetchall()
    return render_template("horario.html", bloques=filas)


@bp.route("/horario/<int:bloque_id>/eliminar", methods=("POST",))
@rol_requerido("estudiante")
def horario_eliminar(bloque_id):
    db = get_db()
    # La condición usuario_id impide borrar tramos de otra persona (OWASP A01).
    n = db.execute("DELETE FROM bloques WHERE id = ? AND usuario_id = ?",
                   (bloque_id, g.usuario["id"])).rowcount
    db.commit()
    if n == 0:
        abort(404)
    flash("Tramo eliminado.", "ok")
    return redirect(url_for("estudiante.horario"))


# ---- Evaluaciones (RF02) ---------------------------------------------------
@bp.route("/evaluaciones", methods=("GET", "POST"))
@rol_requerido("estudiante")
def evaluaciones():
    db = get_db()
    asignaturas = db.execute(
        "SELECT * FROM asignaturas WHERE activa = 1 ORDER BY nombre").fetchall()
    if request.method == "POST":
        try:
            asig_id = v.entero(request.form.get("asignatura_id"), "Asignatura", 1, 10**9)
            if not db.execute("SELECT 1 FROM asignaturas WHERE id = ? AND activa = 1",
                              (asig_id,)).fetchone():
                raise v.ErrorValidacion("La asignatura seleccionada no existe.")
            fecha = v.fecha_futura(request.form.get("fecha"), _hoy())
            pond = v.entero(request.form.get("ponderacion"), "Ponderación (%)", 1, 100)
            dif = v.entero(request.form.get("dificultad"), "Dificultad", 1, 5)
            tipo = request.form.get("tipo", "")
            if tipo not in v.TIPOS_EVALUACION:
                raise v.ErrorValidacion("Seleccione un tipo de evaluación válido.")
        except v.ErrorValidacion as e:
            flash(str(e), "error")
            return redirect(url_for("estudiante.evaluaciones"))
        db.execute("INSERT INTO evaluaciones (usuario_id, asignatura_id, fecha, ponderacion, "
                   "dificultad, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                   (g.usuario["id"], asig_id, fecha.isoformat(), pond, dif, tipo))
        db.commit()
        flash("Evaluación registrada.", "ok")
        return redirect(url_for("estudiante.evaluaciones"))
    filas = db.execute(
        "SELECT e.*, a.nombre AS asignatura FROM evaluaciones e "
        "JOIN asignaturas a ON a.id = e.asignatura_id "
        "WHERE e.usuario_id = ? ORDER BY e.fecha", (g.usuario["id"],)).fetchall()
    return render_template("evaluaciones.html", evaluaciones=filas, asignaturas=asignaturas,
                           tipos=v.TIPOS_EVALUACION, hoy=_hoy().isoformat())


@bp.route("/evaluaciones/<int:eval_id>/eliminar", methods=("POST",))
@rol_requerido("estudiante")
def evaluacion_eliminar(eval_id):
    db = get_db()
    n = db.execute("DELETE FROM evaluaciones WHERE id = ? AND usuario_id = ?",
                   (eval_id, g.usuario["id"])).rowcount
    db.commit()
    if n == 0:
        abort(404)
    flash("Evaluación eliminada.", "ok")
    return redirect(url_for("estudiante.evaluaciones"))


# ---- Plan de estudio (RF03, RF04, RF05) ------------------------------------
@bp.route("/plan/generar", methods=("POST",))
@rol_requerido("estudiante")
def plan_generar():
    db = get_db()
    hoy = _hoy()
    filas = db.execute(
        "SELECT e.id, e.asignatura_id, a.nombre, e.fecha, e.ponderacion, e.dificultad "
        "FROM evaluaciones e JOIN asignaturas a ON a.id = e.asignatura_id "
        "WHERE e.usuario_id = ? AND e.fecha > ?", (g.usuario["id"], hoy.isoformat())).fetchall()
    evaluaciones_ = [Evaluacion(f["id"], f["asignatura_id"], f["nombre"],
                                date.fromisoformat(f["fecha"]), f["ponderacion"], f["dificultad"])
                     for f in filas]
    bloques = _bloques(db, g.usuario["id"])
    if not evaluaciones_ or not bloques:
        flash("Para generar el plan registre al menos una evaluación y un tramo libre.", "error")
        return redirect(url_for("estudiante.plan"))

    resultado = generar_plan(evaluaciones_, bloques, hoy)
    alerta = ""
    if resultado.sobrecarga:
        faltan = sum(resultado.deficit.values())
        alerta = (f"Alerta de sobrecarga: faltan {faltan} minutos de estudio. "
                  "Amplíe su disponibilidad o solicite una tutoría.")

    db.execute("DELETE FROM planes WHERE usuario_id = ?", (g.usuario["id"],))  # reorganiza
    plan_id = db.execute("INSERT INTO planes (usuario_id, creado, alerta) VALUES (?, ?, ?)",
                         (g.usuario["id"], ahora(), alerta)).lastrowid
    n_pausa = 0
    for s in resultado.sesiones:
        etiqueta = s.asignatura
        if s.es_pausa:
            etiqueta = "Pausa activa: " + PAUSAS[n_pausa % len(PAUSAS)]
            n_pausa += 1
        db.execute("INSERT INTO sesiones_estudio (plan_id, fecha, inicio, fin, asignatura, es_pausa) "
                   "VALUES (?, ?, ?, ?, ?, ?)",
                   (plan_id, s.fecha.isoformat(), s.inicio, s.fin, etiqueta, int(s.es_pausa)))
    db.commit()
    registrar_evento("plan_generado", f"sesiones={len(resultado.sesiones)}")
    flash(alerta or "Plan generado.", "error" if alerta else "ok")
    return redirect(url_for("estudiante.plan"))


@bp.route("/plan")
@rol_requerido("estudiante")
def plan():
    db = get_db()
    p = db.execute("SELECT * FROM planes WHERE usuario_id = ? ORDER BY id DESC LIMIT 1",
                   (g.usuario["id"],)).fetchone()
    por_fecha = {}
    if p:
        for s in db.execute("SELECT * FROM sesiones_estudio WHERE plan_id = ? "
                            "ORDER BY fecha, inicio", (p["id"],)):
            por_fecha.setdefault(s["fecha"], []).append(s)
    dias = [(date.fromisoformat(f), sesiones) for f, sesiones in por_fecha.items()]
    return render_template("plan.html", plan=p, dias=dias)


# ---- Grupos de estudio (RF06) ----------------------------------------------
@bp.route("/grupos", methods=("GET",))
@rol_requerido("estudiante")
def grupos():
    db = get_db()
    mis = db.execute(
        "SELECT g.id, g.nombre, a.nombre AS asignatura, "
        "(SELECT COUNT(*) FROM grupo_miembros m WHERE m.grupo_id = g.id) AS miembros, g.capacidad "
        "FROM grupos g JOIN grupo_miembros gm ON gm.grupo_id = g.id AND gm.usuario_id = ? "
        "JOIN asignaturas a ON a.id = g.asignatura_id", (g.usuario["id"],)).fetchall()
    asignaturas = db.execute("SELECT * FROM asignaturas WHERE activa = 1 ORDER BY nombre").fetchall()
    return render_template("grupos.html", mis_grupos=mis, asignaturas=asignaturas)


@bp.route("/grupos/crear", methods=("POST",))
@rol_requerido("estudiante")
def grupo_crear():
    db = get_db()
    try:
        nombre = v.texto(request.form.get("nombre"), "Nombre del grupo", 3, 60)
        asig_id = v.entero(request.form.get("asignatura_id"), "Asignatura", 1, 10**9)
        if not db.execute("SELECT 1 FROM asignaturas WHERE id = ? AND activa = 1",
                          (asig_id,)).fetchone():
            raise v.ErrorValidacion("La asignatura seleccionada no existe.")
    except v.ErrorValidacion as e:
        flash(str(e), "error")
        return redirect(url_for("estudiante.grupos"))
    gid = db.execute("INSERT INTO grupos (nombre, asignatura_id) VALUES (?, ?)",
                     (nombre, asig_id)).lastrowid
    db.execute("INSERT INTO grupo_miembros (grupo_id, usuario_id) VALUES (?, ?)",
               (gid, g.usuario["id"]))
    db.commit()
    flash("Grupo creado. Otros estudiantes compatibles podrán unirse.", "ok")
    return redirect(url_for("estudiante.grupos"))


@bp.route("/grupos/solicitar", methods=("POST",))
@rol_requerido("estudiante")
def grupo_solicitar():
    """Busca el grupo abierto más compatible y agrega al estudiante (RF06)."""
    db = get_db()
    try:
        asig_id = v.entero(request.form.get("asignatura_id"), "Asignatura", 1, 10**9)
    except v.ErrorValidacion as e:
        flash(str(e), "error")
        return redirect(url_for("estudiante.grupos"))
    candidatos = db.execute(
        "SELECT g.id FROM grupos g WHERE g.asignatura_id = ? AND g.estado = 'abierto' "
        "AND (SELECT COUNT(*) FROM grupo_miembros m WHERE m.grupo_id = g.id) < g.capacidad "
        "AND g.id NOT IN (SELECT grupo_id FROM grupo_miembros WHERE usuario_id = ?)",
        (asig_id, g.usuario["id"])).fetchall()
    grupos_bloques = {}
    for c in candidatos:
        miembros = db.execute("SELECT usuario_id FROM grupo_miembros WHERE grupo_id = ?",
                              (c["id"],)).fetchall()
        grupos_bloques[c["id"]] = [_bloques(db, m["usuario_id"]) for m in miembros]
    servicio = ServicioEmparejamiento(EmparejamientoPorHorario())
    mejor = servicio.mejor_grupo(_bloques(db, g.usuario["id"]), grupos_bloques)
    if mejor is None:
        flash("No hay un grupo con horarios compatibles. Puede crear uno o solicitar una tutoría.",
              "error")
        return redirect(url_for("estudiante.grupos"))
    gid = mejor[0]
    db.execute("INSERT INTO grupo_miembros (grupo_id, usuario_id) VALUES (?, ?)",
               (gid, g.usuario["id"]))
    for m in db.execute("SELECT usuario_id FROM grupo_miembros WHERE grupo_id = ? "
                        "AND usuario_id != ?", (gid, g.usuario["id"])):
        _notificar(db, m["usuario_id"], f"{g.usuario['nombre']} se unió a tu grupo de estudio.")
    db.commit()
    registrar_evento("grupo_unido", f"grupo={gid}")
    flash("Te uniste a un grupo compatible con tus horarios.", "ok")
    return redirect(url_for("estudiante.grupos"))


# ---- Tutorías (RF07) -------------------------------------------------------
@bp.route("/tutorias", methods=("GET",))
@rol_requerido("estudiante")
def tutorias():
    db = get_db()
    asig_id = request.args.get("asignatura_id", type=int)
    asignaturas = db.execute("SELECT * FROM asignaturas WHERE activa = 1 ORDER BY nombre").fetchall()
    oferta = []
    if asig_id:
        oferta = db.execute(
            "SELECT d.id, d.dia, d.inicio, d.fin, u.nombre AS tutor "
            "FROM disponibilidad_tutor d JOIN usuarios u ON u.id = d.tutor_id AND u.activo = 1 "
            "JOIN tutor_asignaturas ta ON ta.tutor_id = d.tutor_id AND ta.asignatura_id = ? "
            "WHERE d.id NOT IN (SELECT disponibilidad_id FROM solicitudes_tutoria "
            "WHERE estado IN ('pendiente', 'aceptada')) ORDER BY d.dia, d.inicio",
            (asig_id,)).fetchall()
    mias = db.execute(
        "SELECT s.id, s.estado, s.motivo, a.nombre AS asignatura, u.nombre AS tutor, "
        "d.dia, d.inicio, d.fin FROM solicitudes_tutoria s "
        "JOIN asignaturas a ON a.id = s.asignatura_id JOIN usuarios u ON u.id = s.tutor_id "
        "JOIN disponibilidad_tutor d ON d.id = s.disponibilidad_id "
        "WHERE s.estudiante_id = ? ORDER BY s.id DESC", (g.usuario["id"],)).fetchall()
    return render_template("tutorias.html", asignaturas=asignaturas, oferta=oferta,
                           asig_id=asig_id, mias=mias)


@bp.route("/tutorias/solicitar", methods=("POST",))
@rol_requerido("estudiante")
def tutoria_solicitar():
    db = get_db()
    try:
        disp_id = v.entero(request.form.get("disponibilidad_id"), "Horario", 1, 10**9)
        asig_id = v.entero(request.form.get("asignatura_id"), "Asignatura", 1, 10**9)
        d = db.execute(
            "SELECT d.* FROM disponibilidad_tutor d "
            "JOIN tutor_asignaturas ta ON ta.tutor_id = d.tutor_id AND ta.asignatura_id = ? "
            "JOIN usuarios u ON u.id = d.tutor_id AND u.activo = 1 WHERE d.id = ?",
            (asig_id, disp_id)).fetchone()
        if d is None:
            raise v.ErrorValidacion("El horario seleccionado no está disponible para esa asignatura.")
        if db.execute("SELECT 1 FROM solicitudes_tutoria WHERE disponibilidad_id = ? "
                      "AND estado IN ('pendiente', 'aceptada')", (disp_id,)).fetchone():
            raise v.ErrorValidacion("Ese horario ya fue tomado por otra persona.")
        # Validar compatibilidad horaria: el tramo del tutor debe caber en un tramo libre del estudiante.
        libres = _bloques(db, g.usuario["id"])
        if not any(b.dia == d["dia"] and b.inicio <= d["inicio"] and d["fin"] <= b.fin for b in libres):
            raise v.ErrorValidacion("Ese horario no coincide con sus tramos libres. "
                                    "Revise su horario o elija otro.")
    except v.ErrorValidacion as e:
        flash(str(e), "error")
        return redirect(url_for("estudiante.tutorias", asignatura_id=request.form.get("asignatura_id")))
    db.execute("INSERT INTO solicitudes_tutoria (estudiante_id, tutor_id, asignatura_id, "
               "disponibilidad_id, creada) VALUES (?, ?, ?, ?, ?)",
               (g.usuario["id"], d["tutor_id"], asig_id, disp_id, ahora()))
    _notificar(db, d["tutor_id"], f"Nueva solicitud de tutoría de {g.usuario['nombre']}.")
    db.commit()
    registrar_evento("tutoria_solicitada", f"disponibilidad={disp_id}")
    flash("Solicitud enviada. Te avisaremos cuando el tutor responda.", "ok")
    return redirect(url_for("estudiante.tutorias"))


@bp.route("/tutorias/<int:sol_id>/cancelar", methods=("POST",))
@rol_requerido("estudiante")
def tutoria_cancelar(sol_id):
    db = get_db()
    n = db.execute("UPDATE solicitudes_tutoria SET estado = 'cancelada' WHERE id = ? "
                   "AND estudiante_id = ? AND estado IN ('pendiente', 'aceptada')",
                   (sol_id, g.usuario["id"])).rowcount
    db.commit()
    if n == 0:
        abort(404)
    flash("Solicitud cancelada.", "ok")
    return redirect(url_for("estudiante.tutorias"))
