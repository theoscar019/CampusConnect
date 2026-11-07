"""Emparejamiento de estudiantes con grupos de estudio (RF06).

Aplica el patrón Strategy: el criterio con que se puntúa la compatibilidad se
puede cambiar sin tocar el servicio que lo usa.
"""
from abc import ABC, abstractmethod


def minutos_en_comun(a, b) -> int:
    """Minutos de coincidencia entre dos listas de ``Bloque`` semanales."""
    total = 0
    for x in a:
        for y in b:
            if x.dia == y.dia:
                total += max(0, min(x.fin, y.fin) - max(x.inicio, y.inicio))
    return total


class EstrategiaEmparejamiento(ABC):
    """Interfaz de las estrategias de compatibilidad."""

    @abstractmethod
    def puntuar(self, bloques_solicitante, bloques_miembros) -> float:
        """Devuelve un puntaje de compatibilidad (0 si no hay compatibilidad)."""


class EmparejamientoPorHorario(EstrategiaEmparejamiento):
    """Puntúa por minutos libres en común con cada miembro del grupo."""

    def __init__(self, minimo_minutos: int = 120):
        self.minimo = minimo_minutos

    def puntuar(self, bloques_solicitante, bloques_miembros) -> float:
        if not bloques_miembros:
            return 0.0
        comunes = [minutos_en_comun(bloques_solicitante, m) for m in bloques_miembros]
        promedio = sum(comunes) / len(comunes)
        return promedio if promedio >= self.minimo else 0.0


class ServicioEmparejamiento:
    """Busca el grupo más compatible usando la estrategia configurada."""

    def __init__(self, estrategia: EstrategiaEmparejamiento):
        self.estrategia = estrategia

    def mejor_grupo(self, bloques_solicitante, grupos):
        """``grupos``: dict id_grupo -> lista de bloques de cada miembro.

        Returns:
            ``(id_grupo, puntaje)`` o ``None`` si ningún grupo es compatible.
        """
        mejor = None
        for gid, miembros in grupos.items():
            puntaje = self.estrategia.puntuar(bloques_solicitante, miembros)
            if puntaje > 0 and (mejor is None or puntaje > mejor[1]):
                mejor = (gid, puntaje)
        return mejor
