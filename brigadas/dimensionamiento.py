"""Estudio de dimensionamiento: cuántas brigadas y dónde (docs/estudio_dimensionamiento.md).

Usa tiempos de viaje por carretera (OSRM sobre OpenStreetMap) como distancia,
el objetivo J del modelo y enumeración exhaustiva para encontrar el plan óptimo
de cada configuración. Admite dos reglas de asignación:

- ``rigida``: la del modelo (``asignacion.evaluar_bases``); cada municipio lo
  atiende como máximo una brigada.
- ``divisible``: la demanda de un municipio puede repartirse entre varias
  brigadas a su alcance, empezando por la más cercana. Es una desviación
  registrada del diseño (§10 del documento) para que un municipio con más casos
  que la capacidad de una brigada pueda recibir más de una.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .asignacion import (
    IndicadoresAsignacion,
    _percentil_ponderado,
    calcular_objetivo,
    evaluar_bases,
    validar_bases,
    validar_entradas,
)
from .baseline import seleccionar_bases_base
from .contratos import PesosObjetivo
from .demanda import generar_demanda
from .distancias import validar_matriz_distancias
from .metricas import resumen_pareado
from .simulacion import derivar_semillas

__all__ = ["ResultadoDivisible", "matriz_tiempos", "asignar_divisible", "verificar_divisible",
           "cobertura_vulnerabilidad", "optimo_cobertura", "optimo_vulnerabilidad", "evaluar_plan", "estudio",
           "tabla_decision"]

_TOLERANCIA = 1e-9


def matriz_tiempos(ruta_osrm: str | Path, codigos: Sequence[str]) -> np.ndarray:
    """Minutos de manejo entre municipios, en el orden de ``codigos``, promediando ida y vuelta."""
    datos = json.loads(Path(ruta_osrm).read_text(encoding="utf-8"))
    if datos["respuesta"].get("code") != "Ok":
        raise ValueError("la respuesta de OSRM no es válida")
    origen = list(datos["codigos"])
    faltantes = [c for c in codigos if c not in origen]
    if faltantes:
        raise ValueError(f"códigos sin tiempos de viaje: {faltantes}")
    orden = [origen.index(c) for c in codigos]
    minutos = np.array(datos["respuesta"]["durations"], dtype=float)[np.ix_(orden, orden)] / 60.0
    minutos = (minutos + minutos.T) / 2
    np.fill_diagonal(minutos, 0.0)
    validar_matriz_distancias(minutos)
    return minutos


# --- asignación divisible -----------------------------------------------------------


@dataclass(frozen=True, eq=False)
class ResultadoDivisible:
    """``flujos[i, b]``: casos del municipio ``i`` que atiende la brigada ``b`` (con base en ``bases[b]``)."""

    bases: tuple[int, ...]
    flujos: np.ndarray
    demanda_cubierta: np.ndarray
    carga_por_brigada: np.ndarray
    objetivo: float
    es_factible: bool

    @property
    def total_cubierto(self) -> float:
        return float(np.sum(self.demanda_cubierta))

    @property
    def asignaciones(self) -> tuple[int | None, ...]:
        """Brigada que más atiende a cada municipio, o None si no lo atiende ninguna."""
        return tuple(int(np.argmax(f)) if f.sum() > _TOLERANCIA else None for f in self.flujos)


def verificar_divisible(resultado: ResultadoDivisible, demanda, tiempos, capacidad, umbral) -> list[str]:
    """Verificador independiente de la regla: capacidad, umbral y demanda."""
    demanda = np.asarray(demanda, dtype=float)
    errores = []
    if np.any(resultado.flujos < -_TOLERANCIA):
        errores.append("flujos negativos")
    if np.any(resultado.flujos.sum(axis=0) > capacidad + _TOLERANCIA):
        errores.append("una brigada excede su capacidad")
    if np.any(resultado.flujos.sum(axis=1) > demanda + _TOLERANCIA):
        errores.append("se cubre más demanda que la existente")
    lejos = np.asarray(tiempos)[:, list(resultado.bases)] > umbral + _TOLERANCIA
    if np.any(resultado.flujos[lejos] > _TOLERANCIA):
        errores.append("se atiende un municipio fuera del tiempo máximo")
    if len(set(resultado.bases)) != len(resultado.bases):
        errores.append("bases duplicadas")
    return errores


def asignar_divisible(demanda, tiempos, bases, capacidad, umbral, pesos: PesosObjetivo | None = None) -> ResultadoDivisible:
    """Municipios por demanda descendente; cada uno toma capacidad de las bases a su alcance, la más cercana primero."""
    demanda, tiempos = validar_entradas(demanda, tiempos, capacidad, umbral)
    bases = validar_bases(tuple(bases), demanda.size, len(tuple(bases)))
    restante = np.full(len(bases), float(capacidad))
    flujos = np.zeros((demanda.size, len(bases)))
    for i in sorted(range(demanda.size), key=lambda i: (-demanda[i], i)):
        pendiente = demanda[i]
        alcanzables = sorted((b for b in range(len(bases)) if tiempos[i, bases[b]] <= umbral),
                             key=lambda b: (tiempos[i, bases[b]], b))
        for b in alcanzables:
            if pendiente <= _TOLERANCIA:
                break
            atendido = min(pendiente, restante[b])
            if atendido > 0:
                flujos[i, b] += atendido
                restante[b] -= atendido
                pendiente -= atendido

    cubierta = flujos.sum(axis=1)
    total, cubierto = float(demanda.sum()), float(cubierta.sum())
    viajes = tiempos[:, list(bases)]
    positivos = flujos > _TOLERANCIA
    distancia_media = float(np.sum(flujos * viajes) / cubierto) if cubierto > _TOLERANCIA else math.nan
    distancia_p90 = _percentil_ponderado(viajes[positivos], flujos[positivos], 0.9) if positivos.any() else math.nan
    con_demanda = demanda > _TOLERANCIA
    indicadores = IndicadoresAsignacion(
        demanda_total=total,
        demanda_cubierta=cubierto,
        demanda_no_cubierta=max(0.0, total - cubierto),
        cobertura=1.0 if total <= _TOLERANCIA else min(1.0, cubierto / total),
        distancia_media_km=distancia_media,
        distancia_p90_km=distancia_p90,
        peor_cobertura_municipal=float(np.min(cubierta[con_demanda] / demanda[con_demanda])) if con_demanda.any() else 1.0,
        utilizacion_por_brigada=tuple(float(c / capacidad) if capacidad > 0 else math.nan for c in flujos.sum(axis=0)),
    )
    objetivo = calcular_objetivo(indicadores, tiempos, umbral, pesos or PesosObjetivo())
    resultado = ResultadoDivisible(bases, flujos, cubierta, flujos.sum(axis=0), objetivo, True)
    errores = verificar_divisible(resultado, demanda, tiempos, capacidad, umbral)
    return ResultadoDivisible(bases, flujos, cubierta, flujos.sum(axis=0), objetivo, not errores)


EVALUADORES = {"rigida": evaluar_bases, "divisible": asignar_divisible}


def _evaluador(asignacion: str):
    if asignacion not in EVALUADORES:
        raise ValueError(f"asignación desconocida: {asignacion}")
    return EVALUADORES[asignacion]


# --- criterios y optimización ----------------------------------------------------------


def cobertura_vulnerabilidad(resultado, demanda, tasas) -> float:
    """Fracción cubierta de cada municipio, ponderada por su tasa (en [0, 1])."""
    demanda = np.asarray(demanda, dtype=float)
    tasas = np.asarray(tasas, dtype=float)
    con_casos = demanda > 0
    fraccion = np.zeros_like(demanda)
    fraccion[con_casos] = resultado.demanda_cubierta[con_casos] / demanda[con_casos]
    return float(np.sum(tasas[con_casos] * fraccion[con_casos]) / np.sum(tasas[con_casos]))


def optimo_cobertura(demanda, tiempos, k, capacidad, umbral, pesos: PesosObjetivo | None = None,
                     asignacion: str = "rigida"):
    """Plan de menor J por enumeración exhaustiva (desempate: orden lexicográfico)."""
    evaluar = _evaluador(asignacion)
    mejor = None
    for bases in combinations(range(len(demanda)), k):
        resultado = evaluar(demanda, tiempos, bases, capacidad, umbral, pesos)
        if mejor is None or resultado.objetivo < mejor.objetivo - 1e-12:
            mejor = resultado
    return mejor


def optimo_vulnerabilidad(demanda, tiempos, k, capacidad, umbral, tasas, pesos: PesosObjetivo | None = None,
                          asignacion: str = "rigida"):
    """Plan que maximiza la cobertura ponderada por vulnerabilidad (desempate: menor J, luego lexicográfico)."""
    evaluar = _evaluador(asignacion)
    mejor, clave_mejor = None, None
    for bases in combinations(range(len(demanda)), k):
        resultado = evaluar(demanda, tiempos, bases, capacidad, umbral, pesos)
        clave = (-round(cobertura_vulnerabilidad(resultado, demanda, tasas), 12), round(resultado.objetivo, 12), bases)
        if clave_mejor is None or clave < clave_mejor:
            mejor, clave_mejor = resultado, clave
    return mejor


def _tiempo_medio(resultado, tiempos) -> float:
    if isinstance(resultado, ResultadoDivisible):
        cubierto = resultado.flujos.sum()
        return float(np.sum(resultado.flujos * tiempos[:, list(resultado.bases)]) / cubierto) if cubierto else math.nan
    cubierta = resultado.demanda_cubierta
    tiempo = np.array([tiempos[i, resultado.bases[b]] if b is not None else 0.0
                       for i, b in enumerate(resultado.asignaciones)])
    return float(np.sum(tiempo * cubierta) / np.sum(cubierta)) if np.sum(cubierta) else math.nan


def evaluar_plan(bases, escenarios: Mapping[str, np.ndarray], tiempos, capacidad, umbral, tasas, mu_simulacion, a,
                 semillas: Iterable[int], pesos: PesosObjetivo | None = None, asignacion: str = "rigida") -> dict:
    """Métricas de un plan con cada demanda fija y con réplicas simuladas."""
    evaluar = _evaluador(asignacion)
    bases = tuple(int(b) for b in bases)
    fila: dict = {}
    for nombre, demanda in escenarios.items():
        demanda = np.asarray(demanda, dtype=float)
        r = evaluar(demanda, tiempos, bases, capacidad, umbral, pesos)
        fila[f"cobertura_{nombre}_pct"] = 100.0 * r.total_cubierto / demanda.sum()
        fila[f"objetivo_{nombre.removeprefix('casos_')}"] = float(r.objetivo)
    principal = np.asarray(next(iter(escenarios.values())), dtype=float)
    r = evaluar(principal, tiempos, bases, capacidad, umbral, pesos)
    fila["vulnerabilidad_pct"] = 100.0 * cobertura_vulnerabilidad(r, principal, tasas)
    fila["tiempo_medio_min"] = _tiempo_medio(r, tiempos)
    fila["municipios_sin_cobertura"] = int(sum(b is None for b in r.asignaciones))

    simuladas = []
    for semilla in semillas:
        d = generar_demanda(mu_simulacion, np.random.default_rng(semilla), "binomial_negativa", a=a).astype(float)
        simuladas.append(100.0 * evaluar(d, tiempos, bases, capacidad, umbral, pesos).total_cubierto / d.sum())
    # Intervalo t de la media: diferencia pareada contra cero.
    resumen = resumen_pareado(np.zeros(len(simuladas)), np.array(simuladas))
    fila["sim_cobertura_media_pct"] = resumen["diferencia_media"]
    fila["sim_ic95_inferior_pct"] = resumen["ic95_inferior"]
    fila["sim_ic95_superior_pct"] = resumen["ic95_superior"]
    return fila


def estudio(casos_2024, casos_2023, tiempos, tasas, ks, capacidades, umbrales, a, semilla_raiz, replicas=30,
            pesos: PesosObjetivo | None = None, asignacion: str = "rigida") -> pd.DataFrame:
    """Los tres enfoques (regla, cobertura, vulnerabilidad) para cada K, C y umbral."""
    casos_2024 = np.asarray(casos_2024, dtype=float)
    escenarios = {"casos_2024": casos_2024, "casos_2023": np.asarray(casos_2023, dtype=float)}
    semillas = derivar_semillas(semilla_raiz, replicas)
    filas = []
    for k in ks:
        for capacidad in capacidades:
            for umbral in umbrales:
                planes = {
                    "regla": tuple(sorted(seleccionar_bases_base(casos_2024, k))),
                    "cobertura": optimo_cobertura(casos_2024, tiempos, k, capacidad, umbral, pesos, asignacion).bases,
                    "vulnerabilidad": optimo_vulnerabilidad(casos_2024, tiempos, k, capacidad, umbral, tasas, pesos,
                                                            asignacion).bases,
                }
                for enfoque, bases in planes.items():
                    fila = {"asignacion": asignacion, "k": k, "capacidad": float(capacidad), "umbral_min": float(umbral),
                            "enfoque": enfoque, "bases": "-".join(map(str, bases))}
                    fila.update(evaluar_plan(bases, escenarios, tiempos, capacidad, umbral, tasas, casos_2024, a,
                                             semillas, pesos, asignacion))
                    filas.append(fila)
    return pd.DataFrame(filas)


def tabla_decision(planes: pd.DataFrame, metas=(80, 90, 95), enfoque: str = "cobertura") -> pd.DataFrame:
    """Para cada capacidad, umbral y meta: el menor K cuyo plan cubre la meta de los casos de 2024."""
    filas = []
    sub = planes[planes["enfoque"] == enfoque]
    for (capacidad, umbral), grupo in sub.groupby(["capacidad", "umbral_min"], sort=True):
        grupo = grupo.sort_values("k")
        for meta in metas:
            alcanza = grupo[grupo["cobertura_casos_2024_pct"] >= meta]
            fila = {"capacidad": capacidad, "umbral_min": umbral, "meta_pct": meta}
            if alcanza.empty:
                fila.update({"k_minimo": np.nan, "bases": None, "cobertura_2024_pct": np.nan,
                             "cobertura_2023_pct": np.nan, "sim_cobertura_media_pct": np.nan})
            else:
                elegido = alcanza.iloc[0]
                fila.update({"k_minimo": int(elegido["k"]), "bases": elegido["bases"],
                             "cobertura_2024_pct": elegido["cobertura_casos_2024_pct"],
                             "cobertura_2023_pct": elegido["cobertura_casos_2023_pct"],
                             "sim_cobertura_media_pct": elegido["sim_cobertura_media_pct"]})
            filas.append(fila)
    return pd.DataFrame(filas)
