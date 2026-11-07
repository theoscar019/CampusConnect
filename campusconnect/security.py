"""Medidas de seguridad transversales (OWASP Top 10).

  A01 Control de acceso ........ ``login_requerido`` y ``rol_requerido``
  A02 Fallas criptográficas .... hash de contraseñas (scrypt) y cookies seguras
  A03 Inyección ................ consultas parametrizadas y neutralización de CSV
  A04 Diseño inseguro .......... token CSRF y bloqueo por intentos fallidos
  A05 Configuración insegura ... cabeceras HTTP de seguridad
  A07 Fallas de autenticación .. política de contraseñas, sesión con expiración
  A09 Registro y monitoreo ..... tabla de auditoría de eventos de seguridad
"""
import hmac
import logging
import secrets
from functools import wraps

from flask import abort, g, redirect, request, session, url_for
from markupsafe import Markup
from werkzeug.security import check_password_hash, generate_password_hash

from .db import ahora, get_db

log = logging.getLogger("campusconnect.seguridad")

# Hash falso para igualar el tiempo de respuesta cuando el usuario no existe.
_HASH_FALSO = generate_password_hash("contrasena-falsa-para-igualar-tiempos")


def hash_contrasena(contrasena: str) -> str:
    """Hash con sal (scrypt por defecto en Werkzeug). Nunca se guarda la contraseña."""
    return generate_password_hash(contrasena)


def verificar_contrasena(hash_guardado, contrasena: str) -> bool:
    """Compara contraseña y hash; si no hay usuario compara contra un hash falso."""
    if hash_guardado is None:
        check_password_hash(_HASH_FALSO, contrasena)
        return False
    return check_password_hash(hash_guardado, contrasena)


def registrar_evento(evento: str, detalle: str = "", usuario_id=None):
    """Guarda un evento de seguridad en la auditoría y en el log."""
    try:
        ip = request.remote_addr or ""
    except RuntimeError:
        ip = ""
    uid = usuario_id if usuario_id is not None else session.get("usuario_id")
    get_db().execute(
        "INSERT INTO auditoria (usuario_id, evento, detalle, ip, ts) VALUES (?, ?, ?, ?, ?)",
        (uid, evento, detalle[:300], ip, ahora()))
    get_db().commit()
    log.info("evento=%s usuario=%s ip=%s detalle=%s", evento, uid, ip, detalle[:120])


# ---- CSRF -----------------------------------------------------------------
def token_csrf() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def campo_csrf() -> Markup:
    return Markup('<input type="hidden" name="csrf_token" value="%s">') % token_csrf()


def _verificar_csrf():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        enviado = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
        esperado = session.get("csrf", "")
        if not esperado or not hmac.compare_digest(enviado, esperado):
            registrar_evento("csrf_invalido", request.path)
            abort(400)


# ---- Control de acceso ----------------------------------------------------
def login_requerido(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if g.usuario is None:
            return redirect(url_for("auth.login"))
        return vista(*args, **kwargs)
    return envoltura


def rol_requerido(*roles):
    """Permite el acceso solo a los roles indicados (principio de mínimo privilegio)."""
    def decorador(vista):
        @wraps(vista)
        @login_requerido
        def envoltura(*args, **kwargs):
            if g.usuario["rol"] not in roles:
                registrar_evento("acceso_denegado", f"{request.path} rol={g.usuario['rol']}")
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


def neutralizar_csv(valor) -> str:
    """Evita inyección de fórmulas al abrir un CSV en una planilla."""
    s = "" if valor is None else str(valor)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


# ---- Registro en la aplicación --------------------------------------------
def init_app(app):
    @app.before_request
    def cargar_usuario():
        g.usuario = None
        uid = session.get("usuario_id")
        if uid is not None:
            fila = get_db().execute(
                "SELECT * FROM usuarios WHERE id = ? AND activo = 1", (uid,)).fetchone()
            if fila is None:
                session.clear()
            g.usuario = fila
        _verificar_csrf()

    @app.after_request
    def cabeceras_seguridad(resp):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'none'; style-src 'self'; "
            "img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        if g.get("usuario") is not None:
            resp.headers["Cache-Control"] = "no-store"
        return resp

    app.jinja_env.globals["csrf_input"] = campo_csrf
