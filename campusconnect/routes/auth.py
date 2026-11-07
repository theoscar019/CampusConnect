"""Registro, inicio y cierre de sesión (RF01) y panel principal."""
from datetime import datetime, timedelta, timezone

from flask import (Blueprint, current_app, flash, g, redirect, render_template,
                   request, session, url_for)

from .. import validators as v
from ..db import ahora, get_db
from ..security import (hash_contrasena, login_requerido, registrar_evento,
                        token_csrf, verificar_contrasena)

bp = Blueprint("auth", __name__)

CARRERAS = ("Ingeniería en Informática", "Ingeniería en Conectividad y Redes",
            "Analista Programador", "Otra")


def _hora_utc(texto):
    return datetime.fromisoformat(texto) if texto else None


@bp.route("/")
def index():
    return redirect(url_for("auth.panel" if g.usuario else "auth.login"))


@bp.route("/registro", methods=("GET", "POST"))
def registro():
    """Registro de estudiantes. Los tutores los crea el administrador."""
    if request.method == "POST":
        errores = []
        try:
            nombre = v.texto(request.form.get("nombre"), "Nombre", 2, 80)
        except v.ErrorValidacion as e:
            errores.append(str(e))
        try:
            correo = v.correo(request.form.get("correo"), current_app.config["DOMINIOS_PERMITIDOS"])
        except v.ErrorValidacion as e:
            errores.append(str(e))
            correo = ""
        carrera = request.form.get("carrera", "")
        if carrera not in CARRERAS:
            errores.append("Seleccione una carrera de la lista.")
        contrasena = request.form.get("contrasena", "")
        if contrasena != request.form.get("contrasena2", ""):
            errores.append("Las contraseñas no coinciden.")
        faltas = v.validar_contrasena(contrasena, correo)
        if faltas:
            errores.append("La contraseña debe tener: " + ", ".join(faltas) + ".")
        if not errores and get_db().execute(
                "SELECT 1 FROM usuarios WHERE correo = ?", (correo,)).fetchone():
            # Mensaje genérico para no revelar qué correos están registrados.
            errores.append("No fue posible completar el registro con esos datos.")
        if errores:
            for e in errores:
                flash(e, "error")
            return render_template("registro.html", carreras=CARRERAS, form=request.form), 400
        db = get_db()
        db.execute(
            "INSERT INTO usuarios (nombre, correo, hash, rol, carrera, creado) "
            "VALUES (?, ?, ?, 'estudiante', ?, ?)",
            (nombre, correo, hash_contrasena(contrasena), carrera, ahora()))
        db.commit()
        registrar_evento("registro", correo)
        flash("Cuenta creada. Ya puede iniciar sesión.", "ok")
        return redirect(url_for("auth.login"))
    return render_template("registro.html", carreras=CARRERAS, form={})


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        db = get_db()
        correo = (request.form.get("correo") or "").strip().lower()
        contrasena = request.form.get("contrasena") or ""
        usuario = db.execute(
            "SELECT * FROM usuarios WHERE correo = ? AND activo = 1", (correo,)).fetchone()
        ahora_utc = datetime.now(timezone.utc)

        if usuario and _hora_utc(usuario["bloqueado_hasta"]) and \
                _hora_utc(usuario["bloqueado_hasta"]) > ahora_utc:
            registrar_evento("login_bloqueado", correo, usuario["id"])
            flash("Demasiados intentos fallidos. Intente de nuevo en unos minutos.", "error")
            return render_template("login.html"), 429

        if verificar_contrasena(usuario["hash"] if usuario else None, contrasena) and usuario:
            db.execute("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL "
                       "WHERE id = ?", (usuario["id"],))
            db.commit()
            session.clear()           # evita fijación de sesión
            session["usuario_id"] = usuario["id"]
            session.permanent = True
            token_csrf()
            registrar_evento("login_ok", correo, usuario["id"])
            return redirect(url_for("auth.panel"))

        if usuario:
            intentos = usuario["intentos_fallidos"] + 1
            bloqueo = None
            if intentos >= current_app.config["MAX_INTENTOS"]:
                bloqueo = (ahora_utc + timedelta(minutes=current_app.config["BLOQUEO_MINUTOS"])
                           ).isoformat(timespec="seconds")
                intentos = 0
                registrar_evento("cuenta_bloqueada", correo, usuario["id"])
            db.execute("UPDATE usuarios SET intentos_fallidos = ?, bloqueado_hasta = ? "
                       "WHERE id = ?", (intentos, bloqueo, usuario["id"]))
            db.commit()
        registrar_evento("login_fallido", correo)
        flash("Correo o contraseña incorrectos.", "error")   # mensaje genérico
        return render_template("login.html"), 401
    return render_template("login.html")


@bp.route("/logout", methods=("POST",))
@login_requerido
def logout():
    registrar_evento("logout")
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/panel")
@login_requerido
def panel():
    db = get_db()
    notificaciones = db.execute(
        "SELECT * FROM notificaciones WHERE usuario_id = ? ORDER BY id DESC LIMIT 8",
        (g.usuario["id"],)).fetchall()
    db.execute("UPDATE notificaciones SET leida = 1 WHERE usuario_id = ?", (g.usuario["id"],))
    db.commit()
    return render_template("panel.html", notificaciones=notificaciones)
