"""Análisis adicional de escalabilidad del algoritmo genético (docs/analisis_escalabilidad.md).

Compara, sobre la demanda de referencia y con el mismo evaluador del modelo, el
algoritmo genético con la heurística base, una búsqueda voraz y una búsqueda
aleatoria con el mismo presupuesto de evaluaciones únicas.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from .asignacion import evaluar_bases
from .baseline import seleccionar_bases_base
from .contratos import PesosObjetivo
from .genetico import ParametrosGenetico, ejecutar_genetico
from .metricas import resumen_pareado

__all__ = ["Instancia", "ResultadoBusqueda", "busqueda_aleatoria", "busqueda_voraz", "comparar_metodos",
           "resumir_escalabilidad"]

_TOLERANCIA = 1e-9


@dataclass(frozen=True)
class Instancia:
    nombre: str
    demanda: np.ndarray
    distancias: np.ndarray
    k: int
    capacidad: float
    distancia_max: float
    optimo: float | None = None


@dataclass(frozen=True)
class ResultadoBusqueda:
    bases: tuple[int, ...]
    objetivo: float
    evaluaciones: int


def busqueda_aleatoria(demanda, distancias, k, capacidad, distancia_max, rng: np.random.Generator,
                       evaluaciones: int, pesos: PesosObjetivo | None = None) -> ResultadoBusqueda:
    """Mejor de ``evaluaciones`` K-subconjuntos aleatorios distintos (o de todos, si hay menos)."""
    n = len(demanda)
    presupuesto = min(int(evaluaciones), math.comb(n, k))
    vistos: dict[tuple[int, ...], float] = {}
    while len(vistos) < presupuesto:
        bases = tuple(sorted(int(x) for x in rng.choice(n, size=k, replace=False)))
        if bases not in vistos:
            vistos[bases] = float(evaluar_bases(demanda, distancias, bases, capacidad, distancia_max, pesos).objetivo)
    mejor = min(vistos, key=lambda b: (vistos[b], b))
    return ResultadoBusqueda(mejor, vistos[mejor], len(vistos))


def busqueda_voraz(demanda, distancias, k, capacidad, distancia_max,
                   pesos: PesosObjetivo | None = None) -> ResultadoBusqueda:
    """Agrega una base a la vez, la que más reduce J (empate: menor índice)."""
    actuales: list[int] = []
    evaluaciones = 0
    objetivo = math.inf
    for _ in range(k):
        mejor = None
        for j in range(len(demanda)):
            if j in actuales:
                continue
            candidato = tuple(sorted(actuales + [j]))
            valor = float(evaluar_bases(demanda, distancias, candidato, capacidad, distancia_max, pesos).objetivo)
            evaluaciones += 1
            if mejor is None or valor < mejor[0] - 1e-12:
                mejor = (valor, j)
        objetivo = mejor[0]
        actuales.append(mejor[1])
    return ResultadoBusqueda(tuple(sorted(actuales)), objetivo, evaluaciones)


def _fila(instancia: Instancia, metodo: str, semilla: int, resultado: ResultadoBusqueda, segundos: float) -> dict:
    cubierta = evaluar_bases(instancia.demanda, instancia.distancias, resultado.bases, instancia.capacidad,
                             instancia.distancia_max).demanda_cubierta.sum()
    return {
        "instancia": instancia.nombre,
        "metodo": metodo,
        "semilla": semilla,
        "objetivo": resultado.objetivo,
        "cobertura_pct": 100.0 * float(cubierta) / float(np.sum(instancia.demanda)),
        "evaluaciones": resultado.evaluaciones,
        "tiempo_s": segundos,
        "bases": "-".join(map(str, resultado.bases)),
        "optimo": math.nan if instancia.optimo is None else instancia.optimo,
    }


def comparar_metodos(instancia: Instancia, semillas: Iterable[int], parametros: ParametrosGenetico | None = None,
                     pesos: PesosObjetivo | None = None) -> pd.DataFrame:
    """Una fila por método y semilla; los deterministas usan semilla -1."""
    i = instancia
    argumentos = (i.demanda, i.distancias, i.k, i.capacidad, i.distancia_max)
    filas = []

    inicio = time.perf_counter()
    bases = tuple(sorted(seleccionar_bases_base(i.demanda, i.k)))
    base = ResultadoBusqueda(bases, float(evaluar_bases(i.demanda, i.distancias, bases, i.capacidad,
                                                        i.distancia_max, pesos).objetivo), 1)
    filas.append(_fila(i, "base", -1, base, time.perf_counter() - inicio))

    inicio = time.perf_counter()
    voraz = busqueda_voraz(*argumentos, pesos)
    filas.append(_fila(i, "voraz", -1, voraz, time.perf_counter() - inicio))

    for semilla in semillas:
        inicio = time.perf_counter()
        ga = ejecutar_genetico(*argumentos, np.random.default_rng(semilla), parametros, pesos)
        tiempo_ga = time.perf_counter() - inicio
        filas.append(_fila(i, "genetico", semilla, ResultadoBusqueda(ga.bases, ga.objetivo, ga.evaluaciones), tiempo_ga))

        inicio = time.perf_counter()
        # Flujo aleatorio distinto del genético, con su mismo presupuesto de evaluaciones únicas.
        aleatoria = busqueda_aleatoria(*argumentos, np.random.default_rng([semilla, 1]), ga.evaluaciones, pesos)
        filas.append(_fila(i, "aleatoria", semilla, aleatoria, time.perf_counter() - inicio))
    return pd.DataFrame(filas)


def resumir_escalabilidad(tabla: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Resumen por instancia y método, y diferencia pareada genético − aleatoria."""
    metodos, pareados = [], []
    for instancia in dict.fromkeys(tabla["instancia"]):
        sub = tabla[tabla["instancia"] == instancia]
        optimo = sub["optimo"].iloc[0]
        referencia = float(optimo) if pd.notna(optimo) else float(sub["objetivo"].min())
        for metodo in ("base", "voraz", "aleatoria", "genetico"):
            m = sub[sub["metodo"] == metodo]
            if m.empty:
                continue
            brecha = (m["objetivo"] - referencia) / abs(referencia) if referencia else m["objetivo"] - referencia
            metodos.append({
                "instancia": instancia,
                "metodo": metodo,
                "ejecuciones": len(m),
                "referencia": referencia,
                "referencia_es_optimo": bool(pd.notna(optimo)),
                "objetivo_media": float(m["objetivo"].mean()),
                "objetivo_desviacion": float(m["objetivo"].std(ddof=1)) if len(m) > 1 else math.nan,
                "objetivo_min": float(m["objetivo"].min()),
                "cobertura_media_pct": float(m["cobertura_pct"].mean()),
                "evaluaciones_media": float(m["evaluaciones"].mean()),
                "tiempo_medio_s": float(m["tiempo_s"].mean()),
                "brecha_media": float(brecha.mean()),
                "brecha_maxima": float(brecha.max()),
                "proporcion_alcanza_referencia": float((abs(m["objetivo"] - referencia) <= _TOLERANCIA).mean()),
            })
        ga = sub[sub["metodo"] == "genetico"].sort_values("semilla")
        al = sub[sub["metodo"] == "aleatoria"].sort_values("semilla")
        if len(ga) >= 2:
            obj = resumen_pareado(al["objetivo"], ga["objetivo"])
            cob = resumen_pareado(al["cobertura_pct"], ga["cobertura_pct"])
            pareados.append({
                "instancia": instancia,
                "pares": obj["n"],
                "diferencia_media_objetivo": obj["diferencia_media"],
                "ic95_inferior_objetivo": obj["ic95_inferior"],
                "ic95_superior_objetivo": obj["ic95_superior"],
                "diferencia_media_cobertura_pp": cob["diferencia_media"],
                "ic95_inferior_cobertura_pp": cob["ic95_inferior"],
                "ic95_superior_cobertura_pp": cob["ic95_superior"],
                "genetico_mejor_en": int((ga["objetivo"].to_numpy() < al["objetivo"].to_numpy() - _TOLERANCIA).sum()),
                "empates": int((abs(ga["objetivo"].to_numpy() - al["objetivo"].to_numpy()) <= _TOLERANCIA).sum()),
            })
    return pd.DataFrame(metodos), pd.DataFrame(pareados)
