"""Estudio de tamizaje: cuántas brigadas para identificar cuántos casos (docs/estudio_tamizaje.md).

Las brigadas evalúan niños; los casos identificados se estiman como niños evaluados
por la tasa de casos de su municipio. Para una ubicación dada, el reparto de niños
entre brigadas es un programa lineal que se resuelve de forma óptima con
``scipy.optimize.linprog``. La ubicación (cuántas brigadas en cada municipio) se
busca por enumeración (K pequeño), con una heurística voraz y con el algoritmo
genético del proyecto en su modo con repetición.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations_with_replacement
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from .genetico import ParametrosGenetico, ejecutar_genetico

__all__ = ["ResultadoTamizaje", "ResultadoBusqueda", "ProblemaTamizaje", "buscar_exacto", "buscar_voraz",
           "buscar_genetico", "planificar", "estudio_tamizaje", "tabla_decision_tamizaje"]

OBJETIVOS = ("casos", "ninos")


@dataclass(frozen=True, eq=False)
class ResultadoTamizaje:
    bases: tuple[int, ...]
    evaluados: np.ndarray  # evaluados[i, j]: niños del municipio i evaluados por las brigadas con base en j
    valor: float  # valor del programa lineal (menor es mejor)
    ninos_evaluados: float
    casos_identificados: float
    tiempo_medio_min: float


@dataclass(frozen=True)
class ResultadoBusqueda:
    bases: tuple[int, ...]
    valor: float
    metodo: str
    evaluaciones: int


class ProblemaTamizaje:
    """Una configuración (capacidad por brigada, tiempo máximo y objetivo) con caché de evaluaciones."""

    def __init__(self, ninos, tasas, tiempos, capacidad: float, umbral: float, objetivo: str = "casos"):
        if objetivo not in OBJETIVOS:
            raise ValueError(f"objetivo desconocido: {objetivo}")
        self.ninos = np.asarray(ninos, dtype=float)
        self.tasas = np.asarray(tasas, dtype=float)
        self.tiempos = np.asarray(tiempos, dtype=float)
        self.capacidad = float(capacidad)
        self.umbral = float(umbral)
        self.objetivo = objetivo
        n = self.ninos.size
        self.pares = np.argwhere(self.tiempos <= self.umbral)  # (i, j) alcanzables
        peso = self.tasas if objetivo == "casos" else np.ones(n)
        positivos = peso[peso > 0]
        # Desempate lexicográfico por tiempo de viaje: nunca compensa perder un caso (o un niño).
        epsilon = 1e-6 * (positivos.min() if positivos.size else 1.0) / max(self.umbral, 1.0)
        i, j = self.pares[:, 0], self.pares[:, 1]
        self.costo = -peso[i] + epsilon * self.tiempos[i, j]
        self.restricciones = np.zeros((2 * n, len(self.pares)))
        self.restricciones[i, np.arange(len(self.pares))] = 1.0  # niños de cada municipio
        self.restricciones[n + j, np.arange(len(self.pares))] = 1.0  # capacidad de cada base
        self._cache: dict[tuple[int, ...], ResultadoTamizaje] = {}

    @property
    def evaluaciones(self) -> int:
        return len(self._cache)

    def evaluar(self, bases) -> ResultadoTamizaje:
        bases = tuple(sorted(int(b) for b in bases))
        if bases in self._cache:
            return self._cache[bases]
        n = self.ninos.size
        conteo = np.bincount(np.asarray(bases, dtype=int), minlength=n)
        limites = np.concatenate([self.ninos, conteo * self.capacidad])
        solucion = linprog(self.costo, A_ub=self.restricciones, b_ub=limites, bounds=(0, None), method="highs")
        if solucion.status != 0:
            raise RuntimeError(f"el programa lineal no se resolvió: {solucion.message}")
        evaluados = np.zeros((n, n))
        evaluados[self.pares[:, 0], self.pares[:, 1]] = solucion.x
        total = float(evaluados.sum())
        resultado = ResultadoTamizaje(
            bases=bases,
            evaluados=evaluados,
            valor=float(solucion.fun),
            ninos_evaluados=total,
            casos_identificados=float(self.tasas @ evaluados.sum(axis=1)),
            tiempo_medio_min=float((evaluados * self.tiempos).sum() / total) if total > 0 else float("nan"),
        )
        self._cache[bases] = resultado
        return resultado

    def aptitud(self, bases) -> float:
        return self.evaluar(bases).valor


def buscar_exacto(problema: ProblemaTamizaje, k: int) -> ResultadoBusqueda:
    """Todas las ubicaciones con repetición (desempate: orden lexicográfico)."""
    n = problema.ninos.size
    mejor = min(combinations_with_replacement(range(n), k), key=lambda b: (round(problema.aptitud(b), 12), b))
    return ResultadoBusqueda(mejor, problema.aptitud(mejor), "exacto", math.comb(n + k - 1, k))


def buscar_voraz(problema: ProblemaTamizaje, k: int) -> ResultadoBusqueda:
    """Agrega una brigada a la vez en el municipio que más mejora el valor (desempate: menor índice)."""
    bases: tuple[int, ...] = ()
    for _ in range(k):
        bases = min((tuple(sorted(bases + (j,))) for j in range(problema.ninos.size)),
                    key=lambda b: (round(problema.aptitud(b), 12), b))
    return ResultadoBusqueda(bases, problema.aptitud(bases), "voraz", k * problema.ninos.size)


def buscar_genetico(problema: ProblemaTamizaje, k: int, semilla: int,
                    parametros: ParametrosGenetico | None = None) -> ResultadoBusqueda:
    """Algoritmo genético del proyecto con genes repetidos y el valor del programa lineal como aptitud."""
    r = ejecutar_genetico(problema.ninos, problema.tiempos, k, problema.capacidad, problema.umbral,
                          np.random.default_rng(semilla), parametros, aptitud=problema.aptitud, con_repeticion=True)
    return ResultadoBusqueda(r.bases, r.objetivo, "genetico", r.evaluaciones)


def planificar(problema: ProblemaTamizaje, k: int, semillas: Iterable[int] = range(5), k_exacto: int = 5,
               parametros: ParametrosGenetico | None = None) -> ResultadoBusqueda:
    """Mejor plan para K brigadas: exacto si K ≤ ``k_exacto``; si no, el mejor entre voraz y genético."""
    if k <= k_exacto:
        return buscar_exacto(problema, k)
    busquedas = [buscar_voraz(problema, k)] + [buscar_genetico(problema, k, s, parametros) for s in semillas]
    return min(busquedas, key=lambda b: (round(b.valor, 12), b.bases))


def _metricas(problema: ProblemaTamizaje, bases, tasas_2023, casos_2024, casos_2023) -> dict:
    r = problema.evaluar(bases)
    por_municipio = r.evaluados.sum(axis=1)
    return {
        "casos_identificados": r.casos_identificados,
        "casos_pct": 100.0 * r.casos_identificados / float(np.sum(casos_2024)),
        "ninos_evaluados": r.ninos_evaluados,
        "ninos_pct": 100.0 * r.ninos_evaluados / float(problema.ninos.sum()),
        "casos_2023_pct": 100.0 * float(np.asarray(tasas_2023) @ por_municipio) / float(np.sum(casos_2023)),
        "tiempo_medio_min": r.tiempo_medio_min,
        "municipios_bajo_50_pct": int(np.sum(por_municipio < 0.5 * problema.ninos)),
    }


def estudio_tamizaje(ninos, tasas_2024, tasas_2023, casos_2024, casos_2023, tiempos, ks, productividades, umbrales,
                     dias: int = 220, objetivos=OBJETIVOS, semillas: Iterable[int] = range(5), k_exacto: int = 5,
                     parametros: ParametrosGenetico | None = None) -> pd.DataFrame:
    """Una fila por configuración y método; ``propuesto`` marca el mejor plan de cada configuración."""
    semillas = list(semillas)
    filas = []
    for objetivo in objetivos:
        for productividad in productividades:
            for umbral in umbrales:
                problema = ProblemaTamizaje(ninos, tasas_2024, tiempos, dias * productividad, umbral, objetivo)
                for k in ks:
                    busquedas = [buscar_voraz(problema, k)]
                    busquedas += [buscar_genetico(problema, k, s, parametros) for s in semillas]
                    if k <= k_exacto:
                        busquedas.append(buscar_exacto(problema, k))
                    if k <= k_exacto:
                        propuesta = busquedas[-1]
                    else:
                        propuesta = min(busquedas, key=lambda b: (round(b.valor, 12), b.bases))
                    for idx, b in enumerate(busquedas):
                        semilla = semillas[idx - 1] if b.metodo == "genetico" else -1
                        fila = {"objetivo": objetivo, "productividad": float(productividad), "umbral_min": float(umbral),
                                "capacidad": float(dias * productividad), "k": k, "metodo": b.metodo, "semilla": semilla,
                                "bases": "-".join(map(str, b.bases)), "valor": b.valor,
                                "evaluaciones": b.evaluaciones, "propuesto": b is propuesta}
                        fila.update(_metricas(problema, b.bases, tasas_2023, casos_2024, casos_2023))
                        filas.append(fila)
    return pd.DataFrame(filas)


def tabla_decision_tamizaje(planes: pd.DataFrame, metas=(50, 80, 90), objetivo: str = "casos") -> pd.DataFrame:
    """Para cada productividad, umbral y meta: el menor K cuyo plan propuesto identifica la meta de casos."""
    filas = []
    sub = planes[(planes["objetivo"] == objetivo) & planes["propuesto"]]
    for (productividad, umbral), grupo in sub.groupby(["productividad", "umbral_min"], sort=True):
        grupo = grupo.sort_values("k")
        for meta in metas:
            alcanza = grupo[grupo["casos_pct"] >= meta]
            fila = {"productividad": productividad, "umbral_min": umbral, "meta_pct": meta}
            if alcanza.empty:
                fila.update({"k_minimo": np.nan, "bases": None, "metodo": None, "casos_pct": np.nan,
                             "ninos_pct": np.nan, "casos_2023_pct": np.nan})
            else:
                e = alcanza.iloc[0]
                fila.update({"k_minimo": int(e["k"]), "bases": e["bases"], "metodo": e["metodo"],
                             "casos_pct": e["casos_pct"], "ninos_pct": e["ninos_pct"],
                             "casos_2023_pct": e["casos_2023_pct"]})
            filas.append(fila)
    return pd.DataFrame(filas)
