"""Estudio de dimensionamiento según docs/estudio_dimensionamiento.md.

Requiere haber corrido antes:
    python -m scripts.preparar_datos --config configs/piloto_chiquimula.json
    python -m scripts.validar_demanda --config configs/piloto_chiquimula.json

Uso:
    python -m scripts.ejecutar_dimensionamiento

Salidas (resultados/):
    dimensionamiento_planes.csv      una fila por configuración (K, C, umbral) y enfoque
    dimensionamiento_decision.csv    menor K que alcanza 80/90/95 % de los casos de 2024
    dimensionamiento_resumen.json    configuración de referencia y comparación recta frente a carretera
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from brigadas.dimensionamiento import estudio, matriz_tiempos, tabla_decision
from brigadas.distancias import cargar_municipios_csv, matriz_distancias

RAIZ = Path(__file__).resolve().parents[1]
DEPARTAMENTO = "GT20"
KS = range(1, 9)
CAPACIDADES = (150, 221, 300)
UMBRALES_MIN = (45, 60, 90)
REFERENCIA = {"capacidad": 221, "umbral_min": 60, "meta_pct": 90}
SEMILLA_RAIZ = 20261021


def main() -> int:
    resultados = RAIZ / "resultados"
    referencia_osrm = RAIZ / "data" / "referencia" / "osrm_chiquimula.json"
    municipios = cargar_municipios_csv(RAIZ / "data" / "processed" / "municipios.csv", DEPARTAMENTO)
    codigos = [m.codigo for m in municipios]
    nombres = {i: m.nombre for i, m in enumerate(municipios)}
    tiempos = matriz_tiempos(referencia_osrm, codigos)

    panel = pd.read_csv(RAIZ / "data" / "processed" / f"panel_{DEPARTAMENTO}.csv", dtype={"codigo": str})
    por_anio = {a: panel[panel["anio"] == a].set_index("codigo").loc[codigos] for a in (2023, 2024)}
    for anio, tabla in por_anio.items():
        if tabla["casos_registrados"].isna().any():
            raise ValueError(f"Hay municipios sin registro en {anio}; no se imputan como cero.")
    casos_2024 = por_anio[2024]["casos_registrados"].to_numpy(dtype=float)
    casos_2023 = por_anio[2023]["casos_registrados"].to_numpy(dtype=float)
    tasas_2024 = por_anio[2024]["tasa_por_1000"].to_numpy(dtype=float)
    a = json.loads((resultados / "demanda_dispersion.json").read_text(encoding="utf-8"))["a"]

    planes = pd.concat(
        [estudio(casos_2024, casos_2023, tiempos, tasas_2024, KS, CAPACIDADES, UMBRALES_MIN, a, SEMILLA_RAIZ,
                 asignacion=regla) for regla in ("rigida", "divisible")],
        ignore_index=True)
    planes["nombres"] = planes["bases"].map(lambda c: ", ".join(nombres[int(i)] for i in c.split("-")))
    decision = pd.concat(
        [tabla_decision(planes[planes["asignacion"] == regla], enfoque=e).assign(asignacion=regla, enfoque=e)
         for regla in ("rigida", "divisible") for e in ("cobertura", "vulnerabilidad")],
        ignore_index=True)
    decision["nombres"] = decision["bases"].map(
        lambda c: ", ".join(nombres[int(i)] for i in c.split("-")) if isinstance(c, str) else None)

    # Configuración de referencia con la variante divisible (desviación registrada en el diseño, §10).
    elegida = decision[(decision["asignacion"] == "divisible") & (decision["enfoque"] == "cobertura")
                       & (decision["capacidad"] == REFERENCIA["capacidad"])
                       & (decision["umbral_min"] == REFERENCIA["umbral_min"])
                       & (decision["meta_pct"] == REFERENCIA["meta_pct"])].iloc[0]
    k_ref = None if pd.isna(elegida["k_minimo"]) else int(elegida["k_minimo"])
    planes_ref = planes[(planes["asignacion"] == "divisible") & (planes["k"] == k_ref)
                        & (planes["capacidad"] == REFERENCIA["capacidad"])
                        & (planes["umbral_min"] == REFERENCIA["umbral_min"])] if k_ref else planes.iloc[0:0]

    recta = matriz_distancias(municipios)
    datos_osrm = json.loads(referencia_osrm.read_text(encoding="utf-8"))
    orden = [datos_osrm["codigos"].index(c) for c in codigos]
    vial_km = np.array(datos_osrm["respuesta"]["distances"], dtype=float)[np.ix_(orden, orden)] / 1000
    vial_km = (vial_km + vial_km.T) / 2
    iu = np.triu_indices(len(codigos), 1)

    planes.to_csv(resultados / "dimensionamiento_planes.csv", index=False, lineterminator="\n")
    decision.to_csv(resultados / "dimensionamiento_decision.csv", index=False, lineterminator="\n")
    contenido = {
        "diseno": "docs/estudio_dimensionamiento.md",
        "fuente_tiempos": {k: datos_osrm[k] for k in ("fuente", "datos_viales", "consultado_utc")},
        "casos_2024": float(casos_2024.sum()),
        "casos_2023": float(casos_2023.sum()),
        "referencia": {**REFERENCIA, "asignacion": "divisible", "k_minimo": k_ref,
                       "planes": planes_ref.drop(columns=["capacidad", "umbral_min"]).to_dict("records")},
        "techo_rigido_pct": {str(c): float(100 * np.minimum(casos_2024, c).sum() / casos_2024.sum())
                             for c in CAPACIDADES},
        "recta_frente_a_carretera": {
            "razon_mediana_km_vial_sobre_recta": float(np.median(vial_km[iu] / recta[iu])),
            "km_recta_mediana": float(np.median(recta[iu])),
            "km_vial_mediana": float(np.median(vial_km[iu])),
            "minutos_mediana": float(np.median(tiempos[iu])),
            "spearman_minutos_frente_a_recta": float(stats.spearmanr(tiempos[iu], recta[iu]).statistic),
        },
    }
    (resultados / "dimensionamiento_resumen.json").write_text(
        json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    columnas = ["capacidad", "umbral_min", "meta_pct", "k_minimo", "cobertura_2024_pct", "cobertura_2023_pct",
                "sim_cobertura_media_pct", "nombres"]
    for regla in ("rigida", "divisible"):
        print(f"\n=== asignación {regla}, enfoque cobertura")
        sub = decision[(decision["asignacion"] == regla) & (decision["enfoque"] == "cobertura")]
        print(sub[columnas].round(1).to_string(index=False))
    print(f"\nReferencia (C={REFERENCIA['capacidad']}, T={REFERENCIA['umbral_min']} min, meta {REFERENCIA['meta_pct']} %): K = {k_ref}")
    if k_ref:
        print(planes_ref[["enfoque", "nombres", "cobertura_casos_2024_pct", "cobertura_casos_2023_pct",
                          "sim_cobertura_media_pct", "vulnerabilidad_pct", "tiempo_medio_min",
                          "municipios_sin_cobertura"]].round(1).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
