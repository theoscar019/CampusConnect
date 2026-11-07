"""Algoritmo planificador del plan de estudio (RF03, RF04, RF05).

El módulo no depende de Flask ni de la base de datos: recibe evaluaciones y
bloques libres y devuelve un plan. Eso permite probarlo de forma unitaria.

Reglas de negocio:
  * Cada evaluación recibe una prioridad según su ponderación, su dificultad y
    lo cerca que está la fecha.
  * Las sesiones se ubican solo en los bloques libres del estudiante y siempre
    antes de la fecha de la evaluación.
  * Tras ``estudio_max`` minutos de estudio continuo se inserta una pausa activa.
  * Si las horas libres no alcanzan, se informa el déficit (sobrecarga).
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

ESTUDIO_MAX = 50   # minutos de estudio continuo antes de una pausa
PAUSA = 10         # minutos de pausa activa
TROZO_MIN = 10     # no se agendan sesiones de estudio más cortas que esto


@dataclass(frozen=True)
class Evaluacion:
    """Una evaluación registrada por el estudiante."""
    id: int
    asignatura_id: int
    asignatura: str
    fecha: date
    ponderacion: int   # 1 a 100
    dificultad: int    # 1 a 5


@dataclass(frozen=True)
class Bloque:
    """Bloque horario libre semanal. ``dia``: 0 = lunes ... 6 = domingo."""
    dia: int
    inicio: int  # minutos desde las 00:00
    fin: int


@dataclass
class Sesion:
    """Sesión de estudio o pausa activa dentro del plan."""
    fecha: date
    inicio: int
    fin: int
    asignatura: str = ""
    es_pausa: bool = False


@dataclass
class ResultadoPlan:
    """Resultado de ``generar_plan``."""
    sesiones: list = field(default_factory=list)
    deficit: dict = field(default_factory=dict)   # id evaluación -> minutos sin cubrir
    orden: list = field(default_factory=list)     # ids de evaluaciones por prioridad

    @property
    def sobrecarga(self) -> bool:
        """True si alguna evaluación quedó sin cubrir por falta de tiempo libre."""
        return bool(self.deficit)


def minutos_requeridos(ev: Evaluacion) -> int:
    """Minutos de estudio sugeridos para una evaluación (múltiplos de 10, mínimo 30)."""
    base = ev.dificultad * 60 * (0.5 + ev.ponderacion / 100)
    return max(30, int(round(base / 10.0)) * 10)


def prioridad(ev: Evaluacion, hoy: date) -> float:
    """Puntaje de prioridad entre 0 y 1: pondera peso, dificultad y urgencia."""
    dias = max((ev.fecha - hoy).days, 0)
    urgencia = max(0.0, 1.0 - dias / 14.0)
    return 0.4 * ev.ponderacion / 100.0 + 0.3 * ev.dificultad / 5.0 + 0.3 * urgencia


def fusionar_bloques(bloques):
    """Une bloques que se superponen o se tocan dentro del mismo día."""
    por_dia = {}
    for b in sorted(bloques, key=lambda x: (x.dia, x.inicio)):
        lista = por_dia.setdefault(b.dia, [])
        if lista and b.inicio <= lista[-1].fin:
            lista[-1] = Bloque(b.dia, lista[-1].inicio, max(lista[-1].fin, b.fin))
        else:
            lista.append(b)
    return por_dia


class _Hueco:
    """Intervalo libre de una fecha concreta, con cursor de ocupación."""
    __slots__ = ("fecha", "cursor", "fin", "continuo")

    def __init__(self, fecha, inicio, fin):
        self.fecha, self.cursor, self.fin, self.continuo = fecha, inicio, fin, 0


def generar_plan(evaluaciones, bloques, hoy, dias=7,
                 estudio_max=ESTUDIO_MAX, pausa=PAUSA) -> ResultadoPlan:
    """Genera el plan de estudio de los próximos ``dias`` días.

    Args:
        evaluaciones: lista de ``Evaluacion`` pendientes.
        bloques: lista de ``Bloque`` libres semanales.
        hoy: fecha desde la cual se planifica.
        dias: horizonte del plan en días.
        estudio_max: minutos máximos de estudio continuo.
        pausa: minutos de la pausa activa.

    Returns:
        ``ResultadoPlan`` con las sesiones ordenadas por fecha y hora.
    """
    resultado = ResultadoPlan()
    por_dia = fusionar_bloques(bloques)

    huecos = []
    for desplazamiento in range(dias):
        fecha = hoy + timedelta(days=desplazamiento)
        for b in por_dia.get(fecha.weekday(), []):
            huecos.append(_Hueco(fecha, b.inicio, b.fin))

    ordenadas = sorted(evaluaciones, key=lambda e: prioridad(e, hoy), reverse=True)
    resultado.orden = [e.id for e in ordenadas]

    for ev in ordenadas:
        pendiente = minutos_requeridos(ev)
        for h in huecos:
            if pendiente <= 0:
                break
            if h.fecha >= ev.fecha:
                continue
            while pendiente > 0 and (h.fin - h.cursor) >= TROZO_MIN:
                trozo = min(estudio_max - h.continuo, pendiente, h.fin - h.cursor)
                resultado.sesiones.append(
                    Sesion(h.fecha, h.cursor, h.cursor + trozo, ev.asignatura))
                h.cursor += trozo
                h.continuo += trozo
                pendiente -= trozo
                if h.continuo >= estudio_max and h.cursor < h.fin:
                    largo = min(pausa, h.fin - h.cursor)
                    resultado.sesiones.append(
                        Sesion(h.fecha, h.cursor, h.cursor + largo, "Pausa activa", True))
                    h.cursor += largo
                    h.continuo = 0
        if pendiente > 0:
            resultado.deficit[ev.id] = pendiente

    resultado.sesiones.sort(key=lambda s: (s.fecha, s.inicio))
    return resultado
