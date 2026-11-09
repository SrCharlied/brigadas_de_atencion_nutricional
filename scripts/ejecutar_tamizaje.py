"""Estudio de tamizaje según docs/estudio_tamizaje.md.

Requiere haber corrido antes ``python -m scripts.preparar_datos --config configs/piloto_chiquimula.json``.

Uso:
    python -m scripts.ejecutar_tamizaje

Salidas (resultados/):
    tamizaje_planes.csv      una fila por configuración (objetivo, productividad, umbral, K) y método
    tamizaje_decision.csv    menor K que identifica 50/80/90 % de los casos esperados
    tamizaje_resumen.json    configuración de referencia y calidad del algoritmo genético
Tarda entre 20 y 40 minutos.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from brigadas.dimensionamiento import matriz_tiempos
from brigadas.distancias import cargar_municipios_csv
from brigadas.tamizaje import estudio_tamizaje, tabla_decision_tamizaje

RAIZ = Path(__file__).resolve().parents[1]
DEPARTAMENTO = "GT20"
KS = range(1, 16)
PRODUCTIVIDADES = (20.0, 27.5, 35.0)  # evaluaciones por brigada y día (PMA, 2020)
UMBRALES_MIN = (45.0, 60.0, 90.0)
DIAS = 220  # supuesto declarado
SEMILLAS = range(5)
K_EXACTO = 5
REFERENCIA = {"productividad": 27.5, "umbral_min": 60.0, "meta_pct": 80}


def describir(bases: str, nombres: list[str]) -> str:
    conteo = Counter(int(i) for i in bases.split("-"))
    return ", ".join(f"{nombres[i]}{' ×' + str(c) if c > 1 else ''}" for i, c in sorted(conteo.items()))


def main() -> int:
    resultados = RAIZ / "resultados"
    municipios = cargar_municipios_csv(RAIZ / "data" / "processed" / "municipios.csv", DEPARTAMENTO)
    codigos = [m.codigo for m in municipios]
    nombres = [m.nombre for m in municipios]
    tiempos = matriz_tiempos(RAIZ / "data" / "referencia" / "osrm_chiquimula.json", codigos)

    panel = pd.read_csv(RAIZ / "data" / "processed" / f"panel_{DEPARTAMENTO}.csv", dtype={"codigo": str})
    anio = {a: panel[panel["anio"] == a].set_index("codigo").loc[codigos] for a in (2023, 2024)}
    for a, tabla in anio.items():
        if tabla[["casos_registrados", "poblacion_0_4"]].isna().any().any():
            raise ValueError(f"Faltan casos o población en {a}; no se imputan.")
    ninos = anio[2024]["poblacion_0_4"].to_numpy(dtype=float)
    casos_2024 = anio[2024]["casos_registrados"].to_numpy(dtype=float)
    casos_2023 = anio[2023]["casos_registrados"].to_numpy(dtype=float)
    tasas_2024 = casos_2024 / ninos
    tasas_2023 = casos_2023 / anio[2023]["poblacion_0_4"].to_numpy(dtype=float)

    planes = estudio_tamizaje(ninos, tasas_2024, tasas_2023, casos_2024, casos_2023, tiempos, KS, PRODUCTIVIDADES,
                              UMBRALES_MIN, dias=DIAS, semillas=SEMILLAS, k_exacto=K_EXACTO)
    planes["ubicacion"] = planes["bases"].map(lambda b: describir(b, nombres))
    decision = tabla_decision_tamizaje(planes)
    decision["ubicacion"] = decision["bases"].map(lambda b: describir(b, nombres) if isinstance(b, str) else None)

    # Calidad del algoritmo genético: brecha frente al exacto (K ≤ 5) y frente al plan propuesto (todas las K).
    clave = ["objetivo", "productividad", "umbral_min", "k"]
    propuestos = planes[planes["propuesto"]].set_index(clave)["valor"]
    ga = planes[planes["metodo"] == "genetico"].join(propuestos.rename("valor_propuesto"), on=clave)
    ga["alcanza_propuesto"] = (ga["valor"] - ga["valor_propuesto"]).abs() <= 1e-9
    calidad = ga.groupby(ga["k"] <= K_EXACTO).agg(ejecuciones=("valor", "size"),
                                                   proporcion_alcanza=("alcanza_propuesto", "mean"))
    voraz = planes[planes["metodo"] == "voraz"].join(propuestos.rename("valor_propuesto"), on=clave)
    voraz_alcanza = float(((voraz["valor"] - voraz["valor_propuesto"]).abs() <= 1e-9).mean())
    metodo_propuesto = planes[planes["propuesto"] & (planes["k"] > K_EXACTO)]["metodo"].value_counts().to_dict()

    elegida = decision[(decision["productividad"] == REFERENCIA["productividad"])
                       & (decision["umbral_min"] == REFERENCIA["umbral_min"])
                       & (decision["meta_pct"] == REFERENCIA["meta_pct"])].iloc[0]
    k_ref = None if pd.isna(elegida["k_minimo"]) else int(elegida["k_minimo"])
    referencia = planes[planes["propuesto"] & (planes["k"] == k_ref)
                        & (planes["productividad"] == REFERENCIA["productividad"])
                        & (planes["umbral_min"] == REFERENCIA["umbral_min"])] if k_ref else planes.iloc[0:0]

    planes.to_csv(resultados / "tamizaje_planes.csv", index=False, lineterminator="\n")
    decision.to_csv(resultados / "tamizaje_decision.csv", index=False, lineterminator="\n")
    contenido = {
        "diseno": "docs/estudio_tamizaje.md",
        "ninos_0_4_2024": float(ninos.sum()),
        "casos_2024": float(casos_2024.sum()),
        "casos_2023": float(casos_2023.sum()),
        "dias_de_campo": DIAS,
        "referencia": {**REFERENCIA, "k_minimo": k_ref, "planes": referencia.to_dict("records")},
        "calidad_genetico": {
            "por_rango_k": {("k<=5" if k else "k>5"): fila for k, fila in calidad.to_dict("index").items()},
            "voraz_alcanza_propuesto": voraz_alcanza,
            "metodo_del_plan_propuesto_k>5": metodo_propuesto,
        },
    }
    (resultados / "tamizaje_resumen.json").write_text(
        json.dumps(contenido, ensure_ascii=False, indent=2, default=float) + "\n", encoding="utf-8", newline="\n")

    columnas = ["productividad", "umbral_min", "meta_pct", "k_minimo", "casos_pct", "ninos_pct", "casos_2023_pct",
                "metodo", "ubicacion"]
    print(decision[columnas].round(1).to_string(index=False))
    print(f"\nReferencia: K = {k_ref}")
    print(referencia[["objetivo", "metodo", "ubicacion", "casos_pct", "ninos_pct", "casos_2023_pct",
                      "tiempo_medio_min", "municipios_bajo_50_pct"]].round(1).to_string(index=False))
    print("\nCalidad del genético:", contenido["calidad_genetico"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
