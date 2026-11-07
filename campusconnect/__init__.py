"""CampusConnect: plataforma para organizar el estudio, formar grupos y pedir tutorías."""
import os
import secrets
from datetime import date, timedelta

from flask import Flask, render_template

from . import db, security

DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def minutos_a_hora(m) -> str:
    """Convierte minutos desde las 00:00 en 'HH:MM'."""
    m = int(m)
    return f"{m // 60:02d}:{m % 60:02d}"


def create_app(test_config=None):
    """Fábrica de la aplicación Flask."""
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("CAMPUSCONNECT_SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get("CAMPUSCONNECT_DB", os.path.join(os.getcwd(), "campusconnect.db")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("CAMPUSCONNECT_HTTPS", "0") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
        MAX_CONTENT_LENGTH=64 * 1024,
        DOMINIOS_PERMITIDOS=("inacapmail.cl", "inacap.cl"),
        MAX_INTENTOS=5,
        BLOQUEO_MINUTOS=15,
        HOY=None,  # solo para pruebas: fija la fecha actual
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    security.init_app(app)
    app.jinja_env.filters["hora"] = minutos_a_hora
    app.jinja_env.globals["DIAS"] = DIAS

    from .routes import admin, auth, estudiante, tutor
    for modulo in (auth, estudiante, tutor, admin):
        app.register_blueprint(modulo.bp)

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_controlado(e):
        mensajes = {400: "La solicitud no es válida o la sesión del formulario expiró.",
                    403: "No tiene permiso para ver esta página.",
                    404: "No encontramos lo que busca.",
                    413: "El envío es demasiado grande."}
        return render_template("error.html", codigo=e.code, mensaje=mensajes.get(e.code, "Error.")), e.code

    @app.errorhandler(500)
    def error_interno(_e):
        # No se expone el detalle técnico al usuario (OWASP A05).
        return render_template("error.html", codigo=500,
                               mensaje="Ocurrió un error inesperado. Intente nuevamente."), 500

    with app.app_context():
        db.init_db()
    return app


def hoy(app_config) -> date:
    """Fecha actual (o la fijada por configuración en las pruebas)."""
    return app_config.get("HOY") or date.today()
