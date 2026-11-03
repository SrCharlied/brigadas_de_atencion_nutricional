"""Contratos compartidos del proyecto (Denis Rodríguez).

Define las estructuras de datos que intercambian los módulos de datos,
simulación, política base, algoritmo genético y experimentación.

Reglas:
- Las entradas públicas se validan explícitamente con ``ValueError``/``TypeError``
  (nunca con ``assert``).
- Las dataclasses son inmutables (``frozen=True``).
- Unidades: demanda y capacidad en *casos registrados por municipio y año*;
  distancias en *kilómetros geodésicos* entre centroides.
- ``ConfiguracionEscenario`` vive en :mod:`brigadas.config` (Integrante 1) y se
  reexporta aquí para que todos importen los contratos desde un solo lugar.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any, Protocol

import numpy as np

from .config import ConfiguracionEscenario  # definida por el Integrante 1; se reexporta

__all__ = [
    "ConfiguracionEscenario",
    "PesosObjetivo",
    "Municipio",
    "DemandaMunicipal",
    "ResultadoAsignacion",
    "ResultadoReplica",
    "Politica",
    "CAMPOS_RESULTADO_REPLICA",
]


# ---------------------------------------------------------------------------
# Utilidades de validación
# ---------------------------------------------------------------------------

def _entero_no_bool(valor: Any) -> bool:
    return isinstance(valor, (int, np.integer)) and not isinstance(valor, bool)


def _numero_no_bool(valor: Any) -> bool:
    return isinstance(valor, (int, float, np.integer, np.floating)) and not isinstance(valor, bool)


# ---------------------------------------------------------------------------
# Pesos de la función objetivo
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PesosObjetivo:
    """Pesos de la función objetivo (supuestos de escenario, sección 4.7).

    J = w_c·fracción_no_cubierta + w_d·distancia_normalizada + w_e·inequidad

    Deben declararse antes de observar resultados finales.
    """

    w_c: float = 1.0
    w_d: float = 0.1
    w_e: float = 0.1

    def __post_init__(self) -> None:
        for f in fields(self):
            valor = getattr(self, f.name)
            if not _numero_no_bool(valor) or not math.isfinite(valor):
                raise ValueError(f"El peso {f.name} debe ser un número finito.")
            if valor < 0:
                raise ValueError(f"El peso {f.name} no puede ser negativo.")
        if self.w_c == 0:
            raise ValueError("w_c debe ser positivo: la cobertura es la métrica principal.")


# ---------------------------------------------------------------------------
# Datos municipales
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Municipio:
    codigo: str
    nombre: str
    departamento: str
    latitud: float
    longitud: float

    def __post_init__(self) -> None:
        for nombre in ("codigo", "nombre", "departamento"):
            valor = getattr(self, nombre)
            if not isinstance(valor, str) or not valor.strip():
                raise ValueError(f"{nombre} debe ser un texto no vacío.")
        if not _numero_no_bool(self.latitud) or not -90 <= self.latitud <= 90:
            raise ValueError(f"Latitud fuera de rango en {self.codigo}: {self.latitud!r}")
        if not _numero_no_bool(self.longitud) or not -180 <= self.longitud <= 180:
            raise ValueError(f"Longitud fuera de rango en {self.codigo}: {self.longitud!r}")


@dataclass(frozen=True)
class DemandaMunicipal:
    codigo_municipio: str
    anio: int
    casos_registrados: int
    poblacion_0_4: int

    def __post_init__(self) -> None:
        if not isinstance(self.codigo_municipio, str) or not self.codigo_municipio.strip():
            raise ValueError("codigo_municipio debe ser un texto no vacío.")
        for nombre in ("anio", "casos_registrados", "poblacion_0_4"):
            valor = getattr(self, nombre)
            if not _entero_no_bool(valor):
                raise TypeError(f"{nombre} debe ser entero, se recibió {valor!r}.")
            if valor < 0:
                raise ValueError(f"{nombre} no puede ser negativo.")


# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class ResultadoAsignacion:
    """Resultado de evaluar un conjunto de bases sobre una demanda.

    - ``bases``: índices de municipios usados como base; la brigada ``b``
      opera desde ``bases[b]``.
    - ``asignaciones[i]``: índice de brigada (posición en ``bases``) que atiende
      al municipio ``i``, o ``None`` si queda explícitamente no cubierto.
    - ``demanda_cubierta[i]``: demanda del municipio ``i`` atendida (<= demanda).
    - ``carga_por_brigada[b]``: demanda total atendida por la brigada ``b``.
    """

    bases: tuple[int, ...]
    asignaciones: tuple[int | None, ...]
    demanda_cubierta: np.ndarray
    carga_por_brigada: np.ndarray
    objetivo: float
    es_factible: bool

    @property
    def total_cubierto(self) -> float:
        return float(np.sum(self.demanda_cubierta))


CAMPOS_RESULTADO_REPLICA: tuple[str, ...] = (
    "escenario",
    "replica",
    "semilla",
    "politica",
    "cantidad_brigadas",
    "capacidad",
    "porcentaje_cobertura",
    "demanda_no_cubierta",
    "distancia_media_km",
    "distancia_p90_km",
    "peor_cobertura_municipal",
    "objetivo",
    "tiempo_ejecucion_ms",
    "factible",
)


@dataclass(frozen=True)
class ResultadoReplica:
    escenario: str
    replica: int
    semilla: int
    politica: str
    cantidad_brigadas: int
    capacidad: float
    porcentaje_cobertura: float
    demanda_no_cubierta: float
    distancia_media_km: float
    distancia_p90_km: float
    peor_cobertura_municipal: float
    objetivo: float
    tiempo_ejecucion_ms: float
    factible: bool

    def a_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Política
# ---------------------------------------------------------------------------

class Politica(Protocol):
    """Contrato de toda política (base, GA, enumeración exacta).

    La política base puede ignorar ``rng``; el GA debe usarlo explícitamente.
    Nunca usar estado aleatorio global.
    """

    def __call__(
        self,
        demanda: np.ndarray,
        distancias: np.ndarray,
        cantidad_brigadas: int,
        capacidad: float,
        distancia_max: float,
        rng: np.random.Generator,
    ) -> ResultadoAsignacion: ...
