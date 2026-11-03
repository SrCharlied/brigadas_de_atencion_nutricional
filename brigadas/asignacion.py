"""Asignación capacitada determinista y evaluador de soluciones (Denis Rodríguez).

Dado un conjunto de ``K`` bases, este módulo decide qué brigada atiende a cada
municipio y cuánta demanda queda cubierta, respetando capacidad y ``D_max``.
Es el evaluador común que usan la política base, el algoritmo genético
(Integrante 3) y el enumerador exacto.

Regla de asignación (determinista, sin aleatoriedad):

1. Los municipios se procesan por demanda descendente; empates por índice.
2. Solo son elegibles las bases con ``dist <= D_max`` y capacidad restante > 0.
3. Si alguna base elegible puede cubrir toda la demanda del municipio, se
   elige la más cercana (empate: menor posición de brigada).
4. Si ninguna puede cubrirla completa, se asigna a la base elegible con mayor
   capacidad restante (empate: más cercana, luego menor posición) y se cubre
   parcialmente ``min(demanda, restante)``.
5. Si no hay base elegible, el municipio queda explícitamente no cubierto
   (``asignaciones[i] = None``).

Cada municipio se asigna como máximo a una brigada (no se divide su demanda
entre brigadas). Es una heurística: no garantiza la asignación óptima para
unas bases dadas, pero es reproducible y fácil de auditar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .contratos import PesosObjetivo, ResultadoAsignacion

__all__ = [
    "TOLERANCIA",
    "IndicadoresAsignacion",
    "validar_entradas",
    "validar_bases",
    "asignar_capacitado",
    "calcular_indicadores",
    "calcular_objetivo",
    "evaluar_bases",
    "verificar_resultado",
]

TOLERANCIA = 1e-9


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

def validar_entradas(
    demanda: np.ndarray,
    distancias: np.ndarray,
    capacidad: float,
    distancia_max: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Valida y normaliza demanda (1D, >=0, finita) y distancias (n×n)."""
    demanda = np.asarray(demanda, dtype=float)
    distancias = np.asarray(distancias, dtype=float)
    if demanda.ndim != 1 or demanda.size == 0:
        raise ValueError("La demanda debe ser un vector 1D no vacío.")
    if not np.all(np.isfinite(demanda)):
        raise ValueError("La demanda contiene valores no finitos.")
    if np.any(demanda < 0):
        raise ValueError("La demanda no puede ser negativa.")
    n = demanda.size
    if distancias.shape != (n, n):
        raise ValueError(f"Las distancias deben tener forma ({n}, {n}); se recibió {distancias.shape}.")
    if not np.all(np.isfinite(distancias)) or np.any(distancias < 0):
        raise ValueError("Las distancias deben ser finitas y no negativas.")
    if isinstance(capacidad, bool) or not isinstance(capacidad, (int, float, np.integer, np.floating)):
        raise TypeError("La capacidad debe ser numérica.")
    if not math.isfinite(capacidad) or capacidad < 0:
        raise ValueError("La capacidad debe ser finita y >= 0.")
    if isinstance(distancia_max, bool) or not isinstance(distancia_max, (int, float, np.integer, np.floating)):
        raise TypeError("distancia_max debe ser numérica.")
    if math.isnan(distancia_max) or distancia_max < 0:
        raise ValueError("distancia_max debe ser >= 0 (se permite inf).")
    return demanda, distancias


def validar_bases(bases: Sequence[int], n_municipios: int, cantidad_brigadas: int) -> tuple[int, ...]:
    """Exige exactamente ``K`` bases enteras, distintas y dentro de rango."""
    if isinstance(cantidad_brigadas, bool) or not isinstance(cantidad_brigadas, (int, np.integer)):
        raise TypeError("cantidad_brigadas debe ser entero.")
    if cantidad_brigadas < 1:
        raise ValueError("cantidad_brigadas debe ser >= 1.")
    if cantidad_brigadas > n_municipios:
        raise ValueError(
            f"cantidad_brigadas ({cantidad_brigadas}) excede los municipios candidatos ({n_municipios})."
        )
    bases_t = tuple(bases)
    for b in bases_t:
        if isinstance(b, bool) or not isinstance(b, (int, np.integer)):
            raise TypeError(f"Índice de base no entero: {b!r}")
        if not 0 <= b < n_municipios:
            raise ValueError(f"Índice de base fuera de rango: {b}")
    if len(bases_t) != cantidad_brigadas:
        raise ValueError(f"Se esperaban {cantidad_brigadas} bases y se recibieron {len(bases_t)}.")
    if len(set(bases_t)) != len(bases_t):
        raise ValueError(f"Las bases contienen duplicados: {bases_t}")
    return tuple(int(b) for b in bases_t)


# ---------------------------------------------------------------------------
# Asignación
# ---------------------------------------------------------------------------

def asignar_capacitado(
    demanda: np.ndarray,
    distancias: np.ndarray,
    bases: Sequence[int],
    capacidad: float,
    distancia_max: float,
) -> tuple[tuple[int | None, ...], np.ndarray, np.ndarray]:
    """Aplica la regla determinista. Devuelve (asignaciones, cubierta, carga)."""
    demanda, distancias = validar_entradas(demanda, distancias, capacidad, distancia_max)
    n = demanda.size
    bases_t = validar_bases(bases, n, len(tuple(bases)))
    k = len(bases_t)

    restante = np.full(k, float(capacidad))
    asignaciones: list[int | None] = [None] * n
    cubierta = np.zeros(n)

    # Orden: demanda descendente, empate por índice ascendente (orden estable).
    orden = sorted(range(n), key=lambda i: (-demanda[i], i))
    for i in orden:
        d_i = demanda[i]
        if d_i <= 0:
            continue
        dist_i = distancias[i, list(bases_t)]
        elegibles = [b for b in range(k)
                     if dist_i[b] <= distancia_max + TOLERANCIA and restante[b] > TOLERANCIA]
        if not elegibles:
            continue
        completas = [b for b in elegibles if restante[b] + TOLERANCIA >= d_i]
        if completas:
            elegida = min(completas, key=lambda b: (dist_i[b], b))
        else:
            elegida = min(elegibles, key=lambda b: (-restante[b], dist_i[b], b))
        atendida = min(d_i, restante[elegida])
        restante[elegida] = max(0.0, restante[elegida] - atendida)
        asignaciones[i] = elegida
        cubierta[i] = atendida

    carga = float(capacidad) - restante
    carga = np.where(np.abs(carga) < TOLERANCIA, 0.0, carga)
    return tuple(asignaciones), cubierta, carga


# ---------------------------------------------------------------------------
# Indicadores y objetivo
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndicadoresAsignacion:
    """Métricas de una asignación. Distancias en km geodésicos entre centroides."""

    demanda_total: float
    demanda_cubierta: float
    demanda_no_cubierta: float
    cobertura: float                 # proporción [0, 1]
    distancia_media_km: float        # ponderada por demanda cubierta; NaN si nada cubierto
    distancia_p90_km: float          # percentil 90 ponderado; NaN si nada cubierto
    peor_cobertura_municipal: float  # mínimo de cubierta_i / d_i entre municipios con demanda
    utilizacion_por_brigada: tuple[float, ...]  # carga / capacidad; NaN si capacidad 0


def _percentil_ponderado(valores: np.ndarray, pesos: np.ndarray, q: float) -> float:
    orden = np.argsort(valores, kind="stable")
    valores, pesos = valores[orden], pesos[orden]
    acumulado = np.cumsum(pesos)
    objetivo = q * acumulado[-1]
    idx = int(np.searchsorted(acumulado, objetivo - TOLERANCIA, side="left"))
    return float(valores[min(idx, len(valores) - 1)])


def calcular_indicadores(
    resultado: ResultadoAsignacion,
    demanda: np.ndarray,
    distancias: np.ndarray,
    capacidad: float,
) -> IndicadoresAsignacion:
    demanda = np.asarray(demanda, dtype=float)
    total = float(demanda.sum())
    cubierto = float(resultado.demanda_cubierta.sum())
    no_cubierto = max(0.0, total - cubierto)
    # Convención: sin demanda no hay nada que cubrir -> cobertura 1.0.
    cobertura = 1.0 if total <= TOLERANCIA else min(1.0, cubierto / total)

    atendidos = [i for i, b in enumerate(resultado.asignaciones)
                 if b is not None and resultado.demanda_cubierta[i] > 0]
    if atendidos:
        d = np.array([distancias[i, resultado.bases[resultado.asignaciones[i]]] for i in atendidos])
        w = resultado.demanda_cubierta[atendidos]
        dist_media = float(np.average(d, weights=w))
        dist_p90 = _percentil_ponderado(d, w, 0.9)
    else:
        dist_media = math.nan
        dist_p90 = math.nan

    con_demanda = demanda > TOLERANCIA
    if np.any(con_demanda):
        peor = float(np.min(resultado.demanda_cubierta[con_demanda] / demanda[con_demanda]))
    else:
        peor = 1.0

    if capacidad > 0:
        utilizacion = tuple(float(c / capacidad) for c in resultado.carga_por_brigada)
    else:
        utilizacion = tuple(math.nan for _ in resultado.carga_por_brigada)

    return IndicadoresAsignacion(
        demanda_total=total,
        demanda_cubierta=cubierto,
        demanda_no_cubierta=no_cubierto,
        cobertura=cobertura,
        distancia_media_km=dist_media,
        distancia_p90_km=dist_p90,
        peor_cobertura_municipal=peor,
        utilizacion_por_brigada=utilizacion,
    )


def calcular_objetivo(
    indicadores: IndicadoresAsignacion,
    distancias: np.ndarray,
    distancia_max: float,
    pesos: PesosObjetivo,
) -> float:
    """J = w_c·(1−cobertura) + w_d·dist_normalizada + w_e·(1−peor_cobertura). Minimizar.

    La distancia se normaliza por ``D_max`` (o por la mayor distancia de la
    matriz si ``D_max`` es infinito), así cada término queda en [0, 1].
    """
    fraccion_no_cubierta = 1.0 - indicadores.cobertura
    if math.isnan(indicadores.distancia_media_km):
        dist_norm = 0.0
    else:
        escala = distancia_max if math.isfinite(distancia_max) else float(np.max(distancias))
        dist_norm = indicadores.distancia_media_km / escala if escala > 0 else 0.0
        dist_norm = min(1.0, max(0.0, dist_norm))
    inequidad = 1.0 - indicadores.peor_cobertura_municipal
    return float(pesos.w_c * fraccion_no_cubierta + pesos.w_d * dist_norm + pesos.w_e * inequidad)


def evaluar_bases(
    demanda: np.ndarray,
    distancias: np.ndarray,
    bases: Sequence[int],
    capacidad: float,
    distancia_max: float,
    pesos: PesosObjetivo | None = None,
) -> ResultadoAsignacion:
    """Evaluador común: asigna, calcula objetivo y verifica restricciones.

    Lanza ``ValueError`` si las bases son inválidas (duplicadas, fuera de
    rango). El GA debe reparar sus cromosomas antes de evaluar.
    """
    pesos = pesos or PesosObjetivo()
    demanda_arr, distancias_arr = validar_entradas(demanda, distancias, capacidad, distancia_max)
    bases_t = validar_bases(bases, demanda_arr.size, len(tuple(bases)))
    asignaciones, cubierta, carga = asignar_capacitado(
        demanda_arr, distancias_arr, bases_t, capacidad, distancia_max
    )
    provisional = ResultadoAsignacion(
        bases=bases_t,
        asignaciones=asignaciones,
        demanda_cubierta=cubierta,
        carga_por_brigada=carga,
        objetivo=math.nan,
        es_factible=False,
    )
    errores = verificar_resultado(provisional, demanda_arr, distancias_arr, capacidad, distancia_max)
    indicadores = calcular_indicadores(provisional, demanda_arr, distancias_arr, capacidad)
    objetivo = calcular_objetivo(indicadores, distancias_arr, distancia_max, pesos)
    return ResultadoAsignacion(
        bases=bases_t,
        asignaciones=asignaciones,
        demanda_cubierta=cubierta,
        carga_por_brigada=carga,
        objetivo=objetivo,
        es_factible=not errores,
    )


# ---------------------------------------------------------------------------
# Verificador independiente
# ---------------------------------------------------------------------------

def verificar_resultado(
    resultado: ResultadoAsignacion,
    demanda: np.ndarray,
    distancias: np.ndarray,
    capacidad: float,
    distancia_max: float,
) -> list[str]:
    """Revisa restricciones sin reutilizar la lógica de asignación.

    Devuelve la lista de violaciones encontradas (vacía si es factible).
    Sirve para verificar soluciones producidas por cualquier política.
    """
    errores: list[str] = []
    demanda = np.asarray(demanda, dtype=float)
    n = demanda.size
    k = len(resultado.bases)

    if len(set(resultado.bases)) != k:
        errores.append("Bases duplicadas.")
    if any(not 0 <= b < n for b in resultado.bases):
        errores.append("Base fuera de rango.")
    if len(resultado.asignaciones) != n:
        errores.append("La cantidad de asignaciones no coincide con los municipios.")
        return errores
    if resultado.demanda_cubierta.shape != (n,):
        errores.append("demanda_cubierta tiene forma incorrecta.")
        return errores
    if resultado.carga_por_brigada.shape != (k,):
        errores.append("carga_por_brigada tiene forma incorrecta.")
        return errores

    carga_recalculada = np.zeros(k)
    for i, b in enumerate(resultado.asignaciones):
        cubierta = resultado.demanda_cubierta[i]
        if cubierta < -TOLERANCIA:
            errores.append(f"Municipio {i}: demanda cubierta negativa.")
        if cubierta > demanda[i] + TOLERANCIA:
            errores.append(f"Municipio {i}: cubre más de su demanda (se creó demanda).")
        if b is None:
            if cubierta > TOLERANCIA:
                errores.append(f"Municipio {i}: no asignado pero con demanda cubierta.")
            continue
        if not 0 <= b < k:
            errores.append(f"Municipio {i}: brigada {b} inexistente.")
            continue
        if distancias[i, resultado.bases[b]] > distancia_max + TOLERANCIA:
            errores.append(f"Municipio {i}: asignado fuera de D_max.")
        carga_recalculada[b] += cubierta

    if np.any(carga_recalculada > capacidad + 1e-6):
        errores.append("Alguna brigada excede su capacidad.")
    if not np.allclose(carga_recalculada, resultado.carga_por_brigada, atol=1e-6):
        errores.append("carga_por_brigada no coincide con la demanda asignada.")
    return errores
