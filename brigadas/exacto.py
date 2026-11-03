"""Enumerador exacto para instancias pequeñas (Denis Rodríguez).

Evalúa todas las combinaciones de ``K`` bases con el mismo evaluador que la
política base y el GA. Es el óptimo *bajo la regla de asignación capacitada*
(sección 7.4). Solo debe usarse en tests y en el análisis de calidad del GA.
"""

from __future__ import annotations

import math
from itertools import combinations

import numpy as np

from .asignacion import evaluar_bases, validar_bases, validar_entradas
from .contratos import PesosObjetivo, Politica, ResultadoAsignacion

__all__ = ["MAX_COMBINACIONES", "enumerar_optimo", "calcular_gap", "crear_politica_exacta"]

MAX_COMBINACIONES = 200_000


def enumerar_optimo(
    demanda: np.ndarray,
    distancias: np.ndarray,
    cantidad_brigadas: int,
    capacidad: float,
    distancia_max: float,
    pesos: PesosObjetivo | None = None,
    max_combinaciones: int = MAX_COMBINACIONES,
) -> ResultadoAsignacion:
    """Devuelve la combinación de menor objetivo (empate: orden lexicográfico)."""
    demanda, distancias = validar_entradas(demanda, distancias, capacidad, distancia_max)
    n = demanda.size
    validar_bases(tuple(range(cantidad_brigadas)) if cantidad_brigadas <= n else (), n, cantidad_brigadas)
    total = math.comb(n, cantidad_brigadas)
    if total > max_combinaciones:
        raise ValueError(
            f"C({n},{cantidad_brigadas}) = {total} combinaciones excede el límite de "
            f"{max_combinaciones}; el enumerador es solo para instancias pequeñas."
        )

    mejor: ResultadoAsignacion | None = None
    for bases in combinations(range(n), cantidad_brigadas):
        resultado = evaluar_bases(demanda, distancias, bases, capacidad, distancia_max, pesos)
        if not resultado.es_factible:
            continue
        if mejor is None or resultado.objetivo < mejor.objetivo - 1e-12:
            mejor = resultado
    if mejor is None:  # pragma: no cover - el evaluador siempre produce factibles
        raise RuntimeError("No se encontró ninguna combinación factible.")
    return mejor


def calcular_gap(objetivo_heuristico: float, objetivo_optimo: float, tolerancia: float = 1e-12) -> float:
    """gap = (J_h − J_opt) / |J_opt|.

    Si ``J_opt`` es cero: devuelve 0.0 cuando ``J_h`` también es cero (dentro de
    la tolerancia) y ``inf`` en otro caso, porque un gap relativo no está
    definido. En ese caso reportar también la diferencia absoluta.
    """
    for valor in (objetivo_heuristico, objetivo_optimo):
        if not math.isfinite(valor):
            raise ValueError("Los objetivos deben ser finitos.")
    if abs(objetivo_optimo) <= tolerancia:
        return 0.0 if abs(objetivo_heuristico) <= tolerancia else math.inf
    return (objetivo_heuristico - objetivo_optimo) / abs(objetivo_optimo)


def crear_politica_exacta(
    demanda_referencia: np.ndarray | None = None,
    pesos: PesosObjetivo | None = None,
) -> Politica:
    """Política que elige el óptimo exacto.

    Con ``demanda_referencia`` optimiza sobre esa demanda (como haría el GA con
    datos de desarrollo); sin ella, optimiza sobre la demanda de la réplica
    (oráculo con información perfecta, solo para análisis).
    """
    referencia = None if demanda_referencia is None else np.array(demanda_referencia, dtype=float)

    def politica(
        demanda: np.ndarray,
        distancias: np.ndarray,
        cantidad_brigadas: int,
        capacidad: float,
        distancia_max: float,
        rng: np.random.Generator,
    ) -> ResultadoAsignacion:
        objetivo_demanda = demanda if referencia is None else referencia
        optimo = enumerar_optimo(objetivo_demanda, distancias, cantidad_brigadas, capacidad,
                                 distancia_max, pesos)
        return evaluar_bases(demanda, distancias, optimo.bases, capacidad, distancia_max, pesos)

    return politica
