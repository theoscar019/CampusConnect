"""Validación de entradas del usuario (OWASP A03: nunca confiar en la entrada)."""
import re
from datetime import date, datetime

MAX_FUTURO_DIAS = 365
TIPOS_EVALUACION = ("Prueba", "Examen", "Trabajo", "Control")
_CORREO = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,120}\.[A-Za-z]{2,}$")


class ErrorValidacion(ValueError):
    """Error de validación con un mensaje apto para mostrar al usuario."""


def texto(valor, campo, minimo=1, maximo=100):
    """Texto sin espacios sobrantes y con largo acotado."""
    v = (valor or "").strip()
    if not (minimo <= len(v) <= maximo):
        raise ErrorValidacion(f"{campo}: debe tener entre {minimo} y {maximo} caracteres.")
    return v


def correo(valor, dominios):
    """Correo con formato válido y de un dominio institucional permitido."""
    v = (valor or "").strip().lower()
    if not _CORREO.match(v):
        raise ErrorValidacion("Ingrese un correo válido.")
    if v.rsplit("@", 1)[1] not in dominios:
        raise ErrorValidacion("Use su correo institucional (" + ", ".join("@" + d for d in dominios) + ").")
    return v


def entero(valor, campo, minimo, maximo):
    """Entero dentro de un rango."""
    try:
        n = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ErrorValidacion(f"{campo}: ingrese un número entero.")
    if not (minimo <= n <= maximo):
        raise ErrorValidacion(f"{campo}: debe estar entre {minimo} y {maximo}.")
    return n


def hora_a_minutos(valor, campo="Hora"):
    """Convierte 'HH:MM' a minutos desde las 00:00."""
    m = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", (valor or "").strip())
    if not m:
        raise ErrorValidacion(f"{campo}: use el formato HH:MM.")
    return int(m.group(1)) * 60 + int(m.group(2))


def tramo(dia, inicio, fin, duracion_minima=30):
    """Valida un tramo horario semanal y devuelve (dia, inicio, fin) en minutos."""
    d = entero(dia, "Día", 0, 6)
    i = hora_a_minutos(inicio, "Hora de inicio")
    f = hora_a_minutos(fin, "Hora de término")
    if f - i < duracion_minima:
        raise ErrorValidacion(f"El tramo debe durar al menos {duracion_minima} minutos y terminar después de iniciar.")
    return d, i, f


def fecha_futura(valor, hoy):
    """Fecha ISO (AAAA-MM-DD) posterior a hoy y a menos de un año."""
    try:
        f = datetime.strptime((valor or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ErrorValidacion("Fecha: use el formato AAAA-MM-DD.")
    if f <= hoy:
        raise ErrorValidacion("La fecha de la evaluación debe ser posterior a hoy.")
    if (f - hoy).days > MAX_FUTURO_DIAS:
        raise ErrorValidacion("La fecha no puede superar un año desde hoy.")
    return f


def hay_solape(existentes, dia, inicio, fin):
    """True si el tramo se superpone con alguno de ``existentes`` [(dia, ini, fin)]."""
    return any(d == dia and inicio < f and i < fin for d, i, f in existentes)


def validar_contrasena(contrasena, correo_usuario=""):
    """Política de contraseñas. Devuelve la lista de problemas encontrados."""
    problemas = []
    c = contrasena or ""
    if len(c) < 10:
        problemas.append("al menos 10 caracteres")
    if not re.search(r"[a-z]", c):
        problemas.append("una minúscula")
    if not re.search(r"[A-Z]", c):
        problemas.append("una mayúscula")
    if not re.search(r"\d", c):
        problemas.append("un número")
    local = (correo_usuario or "").split("@")[0].lower()
    if local and len(local) >= 4 and local in c.lower():
        problemas.append("no contener su correo")
    return problemas
