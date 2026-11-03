"""Flujo de réplicas con demanda inyectada (Denis Rodríguez).

Flujo de una réplica (sección 5.4)::

    semilla de la réplica
    → generar demanda municipal del escenario (una sola vez)
    → ejecutar cada política con la MISMA demanda (copia de solo lectura)
    → verificar restricciones con el verificador independiente
    → calcular métricas
    → guardar parámetros, semilla y resultados

Semillas: se derivan de ``semilla_raiz`` con ``numpy.random.SeedSequence``.
Cada réplica tiene una semilla entera registrada; de ella salen dos flujos
independientes: uno para la demanda y otro para las políticas. Todas las
políticas reciben un generador *recién creado* del mismo flujo, así el orden
en que se ejecutan no altera los resultados (diferencias pareadas).

El modelo de demanda lo provee ``demanda.py`` (Integrante 1): media M0 y
binomial negativa NB2. ``generador_binomial_negativa`` lo envuelve con el
contrato ``GeneradorDemanda``; la sensibilidad (+20 %, ×1.6) se aplica con
``escala`` sobre la media, no multiplicando conteos ya generados.
``generador_poisson`` queda solo para pruebas (los datos reales están
sobredispersos, φ ≈ 7.4).

``evaluar_demanda_fija`` evalúa las políticas con un vector dado, por ejemplo
los casos observados de 2023 o 2024, para la comparación con la referencia real.
"""

from __future__ import annotations

import csv
import math
import time
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

from .asignacion import calcular_indicadores, validar_entradas, verificar_resultado
from .contratos import (
    CAMPOS_RESULTADO_REPLICA,
    ConfiguracionEscenario,
    Politica,
    ResultadoReplica,
)

__all__ = [
    "GeneradorDemanda",
    "derivar_semillas",
    "generadores_replica",
    "generador_poisson",
    "generador_binomial_negativa",
    "ejecutar_replica",
    "evaluar_demanda_fija",
    "ejecutar_replicas",
    "guardar_resultados_csv",
    "cargar_resultados_csv",
]

GeneradorDemanda = Callable[[np.random.Generator], np.ndarray]


def derivar_semillas(semilla_raiz: int, replicas: int) -> tuple[int, ...]:
    """Semillas enteras (uint32) reproducibles, una por réplica."""
    if isinstance(semilla_raiz, bool) or not isinstance(semilla_raiz, (int, np.integer)) or semilla_raiz < 0:
        raise ValueError("semilla_raiz debe ser un entero >= 0.")
    if isinstance(replicas, bool) or not isinstance(replicas, (int, np.integer)) or replicas < 1:
        raise ValueError("replicas debe ser un entero >= 1.")
    estado = np.random.SeedSequence(int(semilla_raiz)).generate_state(int(replicas), dtype=np.uint32)
    return tuple(int(s) for s in estado)


def generadores_replica(semilla: int) -> tuple[np.random.Generator, np.random.SeedSequence]:
    """Devuelve (rng_demanda, semilla_politicas) para una réplica."""
    ss_demanda, ss_politicas = np.random.SeedSequence(int(semilla)).spawn(2)
    return np.random.Generator(np.random.PCG64(ss_demanda)), ss_politicas


def generador_poisson(tasas: np.ndarray, factor: float = 1.0) -> GeneradorDemanda:
    """Generador simple ``d_i ~ Poisson(factor · tasa_i)``. Solo para pruebas."""
    lam = np.asarray(tasas, dtype=float) * float(factor)
    if lam.ndim != 1 or lam.size == 0 or not np.all(np.isfinite(lam)) or np.any(lam < 0):
        raise ValueError("Las tasas deben ser un vector 1D finito y no negativo.")

    def generar(rng: np.random.Generator) -> np.ndarray:
        return rng.poisson(lam).astype(float)

    return generar


def generador_binomial_negativa(mu: np.ndarray, a: float, escala: float = 1.0) -> GeneradorDemanda:
    """Generador del modelo elegido por el Integrante 1 (NB2, ``Var = μ + a·μ²``).

    ``mu`` debe venir de ``demanda.ajustar(...).media(objetivo)`` ordenado por código
    y ``a`` de ``resultados/demanda_dispersion.json``.
    """
    from . import demanda  # importación diferida: requiere pandas/scipy

    media = np.array(mu, dtype=float, copy=True)
    if media.ndim != 1 or media.size == 0:
        raise ValueError("mu debe ser un vector 1D no vacío.")

    def generar(rng: np.random.Generator) -> np.ndarray:
        return demanda.generar_demanda(media, rng, "binomial_negativa", a=a, escala=escala).astype(float)

    return generar


def _validar_demanda_generada(demanda: np.ndarray, n: int) -> np.ndarray:
    demanda = np.array(demanda, dtype=float, copy=True)
    if demanda.shape != (n,):
        raise ValueError(f"El generador devolvió forma {demanda.shape}; se esperaba ({n},).")
    if not np.all(np.isfinite(demanda)) or np.any(demanda < 0):
        raise ValueError("El generador devolvió demanda no finita o negativa.")
    demanda.setflags(write=False)  # ninguna política puede modificarla
    return demanda


def ejecutar_replica(
    replica: int,
    semilla: int,
    generar_demanda: GeneradorDemanda,
    politicas: Mapping[str, Politica],
    distancias: np.ndarray,
    cantidad_brigadas: int,
    capacidad: float,
    distancia_max: float,
    escenario: str = "base",
) -> tuple[list[ResultadoReplica], np.ndarray]:
    """Ejecuta una réplica. Devuelve (resultados por política, demanda usada)."""
    if not politicas:
        raise ValueError("Se requiere al menos una política.")
    distancias = np.asarray(distancias, dtype=float)
    n = distancias.shape[0]

    rng_demanda, ss_politicas = generadores_replica(semilla)
    demanda = _validar_demanda_generada(generar_demanda(rng_demanda), n)
    validar_entradas(demanda, distancias, capacidad, distancia_max)

    resultados: list[ResultadoReplica] = []
    for nombre, politica in politicas.items():
        rng_politica = np.random.Generator(np.random.PCG64(ss_politicas))
        inicio = time.perf_counter()
        asignacion = politica(demanda, distancias, cantidad_brigadas, capacidad, distancia_max, rng_politica)
        tiempo_ms = (time.perf_counter() - inicio) * 1000.0

        errores = verificar_resultado(asignacion, demanda, distancias, capacidad, distancia_max)
        if len(asignacion.bases) != cantidad_brigadas:
            errores.append("La política no devolvió exactamente K bases.")
        ind = calcular_indicadores(asignacion, demanda, distancias, capacidad)
        resultados.append(
            ResultadoReplica(
                escenario=escenario,
                replica=replica,
                semilla=int(semilla),
                politica=nombre,
                cantidad_brigadas=cantidad_brigadas,
                capacidad=float(capacidad),
                porcentaje_cobertura=100.0 * ind.cobertura,
                demanda_no_cubierta=ind.demanda_no_cubierta,
                distancia_media_km=ind.distancia_media_km,
                distancia_p90_km=ind.distancia_p90_km,
                peor_cobertura_municipal=ind.peor_cobertura_municipal,
                objetivo=float(asignacion.objetivo),
                tiempo_ejecucion_ms=tiempo_ms,
                factible=bool(asignacion.es_factible and not errores),
            )
        )
    return resultados, demanda


def ejecutar_replicas(
    config: ConfiguracionEscenario,
    generar_demanda: GeneradorDemanda,
    politicas: Mapping[str, Politica],
    distancias: np.ndarray,
    escenario: str = "base",
) -> list[ResultadoReplica]:
    """Ejecuta ``config.replicas`` réplicas pareadas para todas las políticas.

    Para la sensibilidad, usar las mismas semillas (misma ``config``) con un
    generador de otra ``escala`` y otro nombre de ``escenario``.
    """
    if config.cantidad_brigadas > np.asarray(distancias).shape[0]:
        raise ValueError("cantidad_brigadas excede la cantidad de municipios.")
    resultados: list[ResultadoReplica] = []
    for r, semilla in enumerate(derivar_semillas(config.semilla_raiz, config.replicas)):
        filas, _ = ejecutar_replica(
            replica=r,
            semilla=semilla,
            generar_demanda=generar_demanda,
            politicas=politicas,
            distancias=distancias,
            cantidad_brigadas=config.cantidad_brigadas,
            capacidad=config.capacidad_por_brigada,
            distancia_max=config.distancia_max_km,
            escenario=escenario,
        )
        resultados.extend(filas)
    return resultados


def evaluar_demanda_fija(
    demanda: np.ndarray,
    politicas: Mapping[str, Politica],
    distancias: np.ndarray,
    config: ConfiguracionEscenario,
    escenario: str,
    semilla: int | None = None,
) -> list[ResultadoReplica]:
    """Evalúa las políticas sobre un vector de demanda dado (sin aleatoriedad).

    Pensado para la comparación con la referencia real: pasar los casos
    observados del MSPAS de 2023 o 2024 (ordenados por código). Las políticas
    deben haber decidido sus bases **solo** con años de desarrollo.
    """
    fija = np.array(demanda, dtype=float, copy=True)
    filas, _ = ejecutar_replica(
        replica=0,
        semilla=config.semilla_raiz if semilla is None else semilla,
        generar_demanda=lambda rng: fija,
        politicas=politicas,
        distancias=distancias,
        cantidad_brigadas=config.cantidad_brigadas,
        capacidad=config.capacidad_por_brigada,
        distancia_max=config.distancia_max_km,
        escenario=escenario,
    )
    return filas


# ---------------------------------------------------------------------------
# Exportación / recarga
# ---------------------------------------------------------------------------

_TIPOS = {
    "escenario": str, "replica": int, "semilla": int, "politica": str,
    "cantidad_brigadas": int, "capacidad": float, "porcentaje_cobertura": float,
    "demanda_no_cubierta": float, "distancia_media_km": float, "distancia_p90_km": float,
    "peor_cobertura_municipal": float, "objetivo": float, "tiempo_ejecucion_ms": float,
    "factible": lambda v: v == "True",
}


def guardar_resultados_csv(resultados: Sequence[ResultadoReplica], ruta: str | Path) -> None:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(CAMPOS_RESULTADO_REPLICA))
        escritor.writeheader()
        for r in resultados:
            fila = r.a_dict()
            for clave, valor in fila.items():
                if isinstance(valor, float):
                    fila[clave] = "nan" if math.isnan(valor) else repr(valor)
            escritor.writerow(fila)


def cargar_resultados_csv(ruta: str | Path) -> list[ResultadoReplica]:
    with open(ruta, newline="", encoding="utf-8") as archivo:
        lector = csv.DictReader(archivo)
        if tuple(lector.fieldnames or ()) != CAMPOS_RESULTADO_REPLICA:
            raise ValueError("Encabezados del CSV de resultados no coinciden con el contrato.")
        return [ResultadoReplica(**{k: _TIPOS[k](v) for k, v in fila.items()}) for fila in lector]
