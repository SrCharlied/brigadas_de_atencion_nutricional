"""Experimentos base vs. algoritmo genético con réplicas pareadas.

Implementa docs/diseno_experimental.md §2-§5 sobre la infraestructura de
``simulacion.py``: misma demanda por réplica para ambas políticas, mismas
semillas en todas las condiciones y verificador independiente de restricciones.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

import numpy as np
import pandas as pd

from .baseline import crear_politica_base, seleccionar_bases_base
from .config import ConfiguracionEscenario
from .contratos import PesosObjetivo, ResultadoReplica
from .exacto import calcular_gap, enumerar_optimo
from .genetico import ParametrosGenetico, crear_politica_genetica, ejecutar_genetico
from .metricas import resumen_pareado, resumir
from .simulacion import ejecutar_replicas, evaluar_demanda_fija, generador_binomial_negativa

__all__ = ["Condicion", "CONDICIONES", "ResultadosExperimentos", "configurar", "ejecutar_experimentos",
           "resumir_experimentos"]


@dataclass(frozen=True)
class Condicion:
    nombre: str
    escala: float = 1.0
    capacidad: int | None = None
    distancia_max_km: float | None = None


CONDICIONES = (
    Condicion("nominal"),
    Condicion("demanda_x1.2", escala=1.2),
    Condicion("demanda_x1.6", escala=1.6),
    Condicion("capacidad_177", capacidad=177),
    Condicion("dmax_40", distancia_max_km=40.0),
)


@dataclass
class ResultadosExperimentos:
    replicas: list[ResultadoReplica]
    observado: list[ResultadoReplica]
    calidad: pd.DataFrame
    convergencia: pd.DataFrame
    bases: pd.DataFrame


def configurar(config: ConfiguracionEscenario, condicion: Condicion) -> ConfiguracionEscenario:
    cambios = {}
    if condicion.capacidad is not None:
        cambios["capacidad_por_brigada"] = condicion.capacidad
    if condicion.distancia_max_km is not None:
        cambios["distancia_max_km"] = condicion.distancia_max_km
    return replace(config, **cambios)


def _politicas(referencia, parametros, pesos):
    return {"base": crear_politica_base(referencia, pesos), "genetico": crear_politica_genetica(referencia, parametros, pesos)}


def ejecutar_experimentos(
    config: ConfiguracionEscenario,
    referencia: np.ndarray,
    mu: np.ndarray,
    a: float,
    distancias: np.ndarray,
    observados: Mapping[str, np.ndarray],
    condiciones=CONDICIONES,
    parametros: ParametrosGenetico | None = None,
    pesos: PesosObjetivo | None = None,
) -> ResultadosExperimentos:
    """Ejecuta todas las condiciones, la referencia real y el análisis de calidad del algoritmo."""
    replicas: list[ResultadoReplica] = []
    calidad = []
    bases = []
    k = config.cantidad_brigadas
    for condicion in condiciones:
        cfg = configurar(config, condicion)
        politicas = _politicas(referencia, parametros, pesos)
        generador = generador_binomial_negativa(mu, a, escala=condicion.escala)
        replicas += ejecutar_replicas(cfg, generador, politicas, distancias, escenario=condicion.nombre)

        optimo = enumerar_optimo(referencia, distancias, k, cfg.capacidad_por_brigada, cfg.distancia_max_km, pesos)
        for r, busqueda in enumerate(politicas["genetico"].ejecuciones):
            brecha = calcular_gap(busqueda.objetivo, optimo.objetivo)
            calidad.append({
                "condicion": condicion.nombre,
                "replica": r,
                "bases_genetico": "-".join(map(str, busqueda.bases)),
                "objetivo_genetico": busqueda.objetivo,
                "objetivo_optimo": optimo.objetivo,
                "brecha": brecha,
                "alcanza_optimo": bool(abs(busqueda.objetivo - optimo.objetivo) <= 1e-9),
                "generaciones": busqueda.generaciones,
                "evaluaciones": busqueda.evaluaciones,
            })
        frecuentes = pd.Series([c["bases_genetico"] for c in calidad if c["condicion"] == condicion.nombre]).mode()
        bases.append({
            "condicion": condicion.nombre,
            "bases_base": "-".join(map(str, sorted(seleccionar_bases_base(referencia, k)))),
            "bases_genetico_mas_frecuente": frecuentes.iloc[0],
            "bases_optimo_exacto": "-".join(map(str, optimo.bases)),
        })

    nominal = configurar(config, condiciones[0])
    observado: list[ResultadoReplica] = []
    for escenario, demanda in observados.items():
        observado += evaluar_demanda_fija(np.asarray(demanda, dtype=float), _politicas(referencia, parametros, pesos),
                                          distancias, nominal, escenario=escenario)

    corrida = ejecutar_genetico(referencia, distancias, k, nominal.capacidad_por_brigada, nominal.distancia_max_km,
                                np.random.default_rng(config.semilla_raiz), parametros, pesos)
    convergencia = pd.DataFrame({
        "generacion": range(len(corrida.historial_mejor)),
        "mejor": corrida.historial_mejor,
        "mediana": corrida.historial_mediana,
    })
    return ResultadosExperimentos(replicas, observado, pd.DataFrame(calidad), convergencia, pd.DataFrame(bases))


def resumir_experimentos(replicas: list[ResultadoReplica]) -> pd.DataFrame:
    """Una fila por condición: métricas por política y diferencia pareada de cobertura."""
    tabla = pd.DataFrame([r.a_dict() for r in replicas])
    filas = []
    for condicion in dict.fromkeys(tabla["escenario"]):
        sub = tabla[tabla["escenario"] == condicion]
        base = sub[sub["politica"] == "base"].sort_values("replica")
        ga = sub[sub["politica"] == "genetico"].sort_values("replica")
        if not np.array_equal(base["semilla"].to_numpy(), ga["semilla"].to_numpy()):
            raise ValueError(f"réplicas no pareadas en {condicion}")
        pareado = resumen_pareado(base["porcentaje_cobertura"], ga["porcentaje_cobertura"])
        fila = {"condicion": condicion, "replicas": pareado["n"]}
        for politica, datos in (("base", base), ("genetico", ga)):
            for metrica, columna in (("cobertura", "porcentaje_cobertura"), ("distancia_km", "distancia_media_km"),
                                     ("peor_cobertura", "peor_cobertura_municipal"),
                                     ("tiempo_ms", "tiempo_ejecucion_ms")):
                r = resumir(datos[columna])
                fila[f"{metrica}_{politica}_media"] = r["media"]
                fila[f"{metrica}_{politica}_desviacion"] = r["desviacion"]
                if metrica == "cobertura":
                    fila[f"{metrica}_{politica}_mediana"] = r["mediana"]
        fila.update({
            "diferencia_media_pp": pareado["diferencia_media"],
            "diferencia_desviacion_pp": pareado["diferencia_desviacion"],
            "ic95_inferior_pp": pareado["ic95_inferior"],
            "ic95_superior_pp": pareado["ic95_superior"],
            "cambio_relativo_pct": pareado["cambio_relativo_pct"],
            "todas_factibles": bool(sub["factible"].all()),
        })
        filas.append(fila)
    return pd.DataFrame(filas)
