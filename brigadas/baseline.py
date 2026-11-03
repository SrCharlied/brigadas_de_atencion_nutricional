"""Política base (Escenario A) — Denis Rodríguez.

Heurística base: las ``K`` bases se ubican en los municipios con mayor
demanda media de **desarrollo** (empate: menor índice) y la asignación usa la
misma regla capacitada que la política optimizada.

Se denomina *heurística base*, no política actual del MSPAS.

Las bases dependen solo de la demanda de referencia (años de desarrollo), no
de la demanda de cada réplica: la política no "ve" el escenario antes de
decidir, igual que el GA entrenado con datos de desarrollo.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .asignacion import evaluar_bases, validar_bases
from .contratos import PesosObjetivo, Politica, ResultadoAsignacion

__all__ = [
    "demanda_media_desarrollo",
    "seleccionar_bases_base",
    "crear_politica_base",
    "crear_politica_bases_fijas",
]


def demanda_media_desarrollo(panel, anios_desarrollo, codigos: Sequence[str]) -> np.ndarray:
    """Casos registrados medios por municipio en los años de desarrollo.

    ``panel`` es ``data/processed/panel_<dep>.csv`` (Integrante 1). Los años sin
    registro (NA) se excluyen del promedio; **no** se cuentan como cero. Un
    municipio sin ningún registro en desarrollo produce un error explícito.
    El vector sigue el orden de ``codigos`` (usar el orden por código).
    """
    anios = set(int(a) for a in anios_desarrollo)
    datos = panel[panel["anio"].astype(int).isin(anios)]
    medias = datos.groupby(datos["codigo"].astype(str))["casos_registrados"].mean()
    faltantes = [c for c in codigos if c not in medias.index or medias.isna().get(c, True)]
    if faltantes:
        raise ValueError(f"Municipios sin registros en desarrollo: {faltantes}")
    return np.array([float(medias[c]) for c in codigos])


def seleccionar_bases_base(demanda_referencia: np.ndarray, cantidad_brigadas: int) -> tuple[int, ...]:
    """Índices de los ``K`` municipios con mayor demanda de referencia."""
    ref = np.asarray(demanda_referencia, dtype=float)
    if ref.ndim != 1 or ref.size == 0:
        raise ValueError("La demanda de referencia debe ser un vector 1D no vacío.")
    if not np.all(np.isfinite(ref)) or np.any(ref < 0):
        raise ValueError("La demanda de referencia debe ser finita y no negativa.")
    orden = sorted(range(ref.size), key=lambda i: (-ref[i], i))
    bases = tuple(orden[:cantidad_brigadas]) if cantidad_brigadas <= ref.size else tuple(orden)
    return validar_bases(bases, ref.size, cantidad_brigadas)


def crear_politica_bases_fijas(
    bases: Sequence[int],
    pesos: PesosObjetivo | None = None,
) -> Politica:
    """Política que siempre usa ``bases`` (p. ej. la mejor solución del GA)."""
    bases_t = tuple(int(b) for b in bases)

    def politica(
        demanda: np.ndarray,
        distancias: np.ndarray,
        cantidad_brigadas: int,
        capacidad: float,
        distancia_max: float,
        rng: np.random.Generator,
    ) -> ResultadoAsignacion:
        validar_bases(bases_t, len(demanda), cantidad_brigadas)
        return evaluar_bases(demanda, distancias, bases_t, capacidad, distancia_max, pesos)

    return politica


def crear_politica_base(
    demanda_referencia: np.ndarray,
    pesos: PesosObjetivo | None = None,
) -> Politica:
    """Crea la política base con el contrato ``resolver_politica``.

    ``demanda_referencia`` debe calcularse solo con años de desarrollo.
    El ``rng`` recibido se ignora (política determinista).
    """
    referencia = np.array(demanda_referencia, dtype=float, copy=True)
    referencia.setflags(write=False)

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
        bases = seleccionar_bases_base(referencia, cantidad_brigadas)
        return evaluar_bases(demanda, distancias, bases, capacidad, distancia_max, pesos)

    return politica
