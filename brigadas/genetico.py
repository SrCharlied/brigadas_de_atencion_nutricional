"""Algoritmo genético con restricciones para seleccionar las bases de las brigadas.

Implementa el diseño congelado en docs/diseno_experimental.md §3. El cromosoma es
una tupla ordenada de K municipios distintos; la asignación de municipios a bases
la calcula el evaluador común (``asignacion.evaluar_bases``), igual que para la
política base y el enumerador exacto. Los operadores preservan la unicidad por
construcción, así que nunca se evalúan soluciones inválidas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .asignacion import evaluar_bases, validar_entradas
from .contratos import PesosObjetivo, Politica, ResultadoAsignacion

__all__ = [
    "ParametrosGenetico",
    "ResultadoGenetico",
    "cruzar",
    "mutar",
    "ejecutar_genetico",
    "crear_politica_genetica",
]

_TOLERANCIA = 1e-12


@dataclass(frozen=True)
class ParametrosGenetico:
    poblacion: int = 40
    generaciones_max: int = 100
    generaciones_sin_mejora: int = 20
    torneo: int = 3
    prob_cruce: float = 0.9
    prob_mutacion: float = 0.3
    elitismo: int = 2

    def __post_init__(self) -> None:
        if self.poblacion < 2:
            raise ValueError("poblacion debe ser al menos 2")
        if not 0 <= self.elitismo < self.poblacion:
            raise ValueError("elitismo debe estar entre 0 y poblacion - 1")
        if not 1 <= self.torneo <= self.poblacion:
            raise ValueError("torneo debe estar entre 1 y poblacion")
        for nombre in ("prob_cruce", "prob_mutacion"):
            if not 0.0 <= getattr(self, nombre) <= 1.0:
                raise ValueError(f"{nombre} debe estar en [0, 1]")
        if self.generaciones_max < 1 or self.generaciones_sin_mejora < 1:
            raise ValueError("generaciones_max y generaciones_sin_mejora deben ser al menos 1")


@dataclass(frozen=True)
class ResultadoGenetico:
    bases: tuple[int, ...]
    objetivo: float
    generaciones: int
    evaluaciones: int
    historial_mejor: tuple[float, ...]
    historial_mediana: tuple[float, ...]


def cruzar(padre: Sequence[int], madre: Sequence[int], k: int, rng: np.random.Generator) -> tuple[int, ...]:
    """Hijo con K genes distintos elegidos al azar de la unión de los padres."""
    union = sorted(set(padre) | set(madre))
    elegidos = rng.choice(len(union), size=k, replace=False)
    return tuple(sorted(union[i] for i in elegidos))


def mutar(individuo: Sequence[int], n: int, rng: np.random.Generator) -> tuple[int, ...]:
    """Reemplaza una base al azar por un municipio que no sea base."""
    candidatos = [m for m in range(n) if m not in individuo]
    if not candidatos:
        return tuple(individuo)
    genes = list(individuo)
    genes[int(rng.integers(len(genes)))] = candidatos[int(rng.integers(len(candidatos)))]
    return tuple(sorted(genes))


def ejecutar_genetico(
    demanda: np.ndarray,
    distancias: np.ndarray,
    cantidad_brigadas: int,
    capacidad: float,
    distancia_max: float,
    rng: np.random.Generator,
    parametros: ParametrosGenetico | None = None,
    pesos: PesosObjetivo | None = None,
) -> ResultadoGenetico:
    """Busca las K bases que minimizan el objetivo J sobre ``demanda``."""
    p = parametros or ParametrosGenetico()
    demanda, distancias = validar_entradas(demanda, distancias, capacidad, distancia_max)
    n, k = demanda.size, int(cantidad_brigadas)
    if not 1 <= k <= n:
        raise ValueError(f"cantidad_brigadas debe estar entre 1 y {n}")

    cache: dict[tuple[int, ...], float] = {}

    def aptitud(individuo: tuple[int, ...]) -> float:
        if individuo not in cache:
            cache[individuo] = float(evaluar_bases(demanda, distancias, individuo, capacidad, distancia_max, pesos).objetivo)
        return cache[individuo]

    def ordenar(poblacion: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
        return sorted(poblacion, key=lambda ind: (aptitud(ind), ind))

    def torneo(poblacion: list[tuple[int, ...]]) -> tuple[int, ...]:
        indices = rng.choice(len(poblacion), size=p.torneo, replace=False)
        return min((poblacion[i] for i in indices), key=lambda ind: (aptitud(ind), ind))

    poblacion = ordenar([tuple(sorted(int(x) for x in rng.choice(n, size=k, replace=False))) for _ in range(p.poblacion)])
    historial_mejor = [aptitud(poblacion[0])]
    historial_mediana = [float(np.median([aptitud(ind) for ind in poblacion]))]
    sin_mejora = 0
    generaciones = 0

    while generaciones < p.generaciones_max and sin_mejora < p.generaciones_sin_mejora:
        nueva = poblacion[: p.elitismo]
        while len(nueva) < p.poblacion:
            padre, madre = torneo(poblacion), torneo(poblacion)
            hijo = cruzar(padre, madre, k, rng) if rng.random() < p.prob_cruce else padre
            if rng.random() < p.prob_mutacion:
                hijo = mutar(hijo, n, rng)
            nueva.append(hijo)
        poblacion = ordenar(nueva)
        generaciones += 1
        mejor = aptitud(poblacion[0])
        sin_mejora = 0 if mejor < historial_mejor[-1] - _TOLERANCIA else sin_mejora + 1
        historial_mejor.append(mejor)
        historial_mediana.append(float(np.median([aptitud(ind) for ind in poblacion])))

    return ResultadoGenetico(
        bases=poblacion[0],
        objetivo=aptitud(poblacion[0]),
        generaciones=generaciones,
        evaluaciones=len(cache),
        historial_mejor=tuple(historial_mejor),
        historial_mediana=tuple(historial_mediana),
    )


def crear_politica_genetica(
    demanda_referencia: np.ndarray,
    parametros: ParametrosGenetico | None = None,
    pesos: PesosObjetivo | None = None,
) -> Politica:
    """Política que elige las bases con el algoritmo genético sobre ``demanda_referencia``.

    Igual que la política base, decide solo con la demanda de referencia (años de
    desarrollo) y evalúa esas bases con la demanda de la réplica. Usa el ``rng``
    de la réplica, así la variabilidad del algoritmo queda en los resultados.
    Cada ejecución se guarda en ``politica.ejecuciones`` para analizar su calidad.
    """
    referencia = np.array(demanda_referencia, dtype=float, copy=True)
    referencia.setflags(write=False)
    ejecuciones: list[ResultadoGenetico] = []

    def politica(
        demanda: np.ndarray,
        distancias: np.ndarray,
        cantidad_brigadas: int,
        capacidad: float,
        distancia_max: float,
        rng: np.random.Generator,
    ) -> ResultadoAsignacion:
        if len(demanda) != referencia.size:
            raise ValueError("La demanda de la réplica y la de referencia tienen tamaños distintos.")
        busqueda = ejecutar_genetico(referencia, distancias, cantidad_brigadas, capacidad, distancia_max, rng,
                                     parametros, pesos)
        ejecuciones.append(busqueda)
        return evaluar_bases(demanda, distancias, busqueda.bases, capacidad, distancia_max, pesos)

    politica.ejecuciones = ejecuciones  # type: ignore[attr-defined]
    return politica
