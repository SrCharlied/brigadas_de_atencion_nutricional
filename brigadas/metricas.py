"""Resúmenes estadísticos de los experimentos (docs/diseno_experimental.md §5)."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

__all__ = ["resumir", "resumen_pareado"]


def resumir(valores) -> dict:
    """Media, desviación estándar muestral y mediana, ignorando NaN."""
    x = np.asarray(valores, dtype=float)
    x = x[~np.isnan(x)]
    return {
        "n": int(x.size),
        "media": float(np.mean(x)) if x.size else math.nan,
        "desviacion": float(np.std(x, ddof=1)) if x.size > 1 else math.nan,
        "mediana": float(np.median(x)) if x.size else math.nan,
    }


def resumen_pareado(base, mejora, nivel: float = 0.95) -> dict:
    """Diferencia pareada (mejora − base) con intervalo t de Student."""
    base = np.asarray(base, dtype=float)
    mejora = np.asarray(mejora, dtype=float)
    if base.shape != mejora.shape or base.ndim != 1:
        raise ValueError("base y mejora deben ser vectores de la misma longitud")
    if base.size < 2:
        raise ValueError("se necesitan al menos 2 pares")
    diferencias = mejora - base
    media = float(np.mean(diferencias))
    desviacion = float(np.std(diferencias, ddof=1))
    margen = float(stats.t.ppf(0.5 + nivel / 2, df=base.size - 1)) * desviacion / math.sqrt(base.size)
    media_base = float(np.mean(base))
    return {
        "n": int(base.size),
        "media_base": media_base,
        "media_mejora": float(np.mean(mejora)),
        "diferencia_media": media,
        "diferencia_desviacion": desviacion,
        "ic95_inferior": media - margen,
        "ic95_superior": media + margen,
        "cambio_relativo_pct": media / media_base * 100 if media_base != 0 else math.nan,
    }
