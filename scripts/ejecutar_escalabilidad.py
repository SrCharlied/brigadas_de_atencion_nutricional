"""Análisis adicional de escalabilidad según docs/analisis_escalabilidad.md.

Requiere haber corrido antes ``python -m scripts.preparar_datos``.

Uso:
    python -m scripts.ejecutar_escalabilidad

Salidas (resultados/):
    escalabilidad_resultados.csv   una fila por instancia, método y semilla
    escalabilidad_resumen.csv      resumen por instancia y método
    escalabilidad_pareado.csv      diferencia pareada genético − aleatoria
    escalabilidad_resumen.json
Tarda unos 25 minutos. La columna tiempo_s cambia en cada ejecución.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from brigadas.baseline import demanda_media_desarrollo
from brigadas.distancias import cargar_municipios_csv, matriz_distancias
from brigadas.escalabilidad import Instancia, comparar_metodos, resumir_escalabilidad
from brigadas.exacto import enumerar_optimo

RAIZ = Path(__file__).resolve().parents[1]
DESARROLLO = range(2015, 2023)
SEMILLAS = range(30)
# Valores congelados en docs/analisis_escalabilidad.md §2: el script se detiene si los datos producen otros.
CONGELADO = {"huehuetenango_k4": (337, 35.0), "nacional_k10": (1744, 22.0), "nacional_k20": (872, 22.0),
             "nacional_k40": (436, 22.0)}


def _instancia(nombre, municipios, panel, k, distancia_max=None, con_optimo=False) -> Instancia:
    codigos = [m.codigo for m in municipios]
    demanda = demanda_media_desarrollo(panel, DESARROLLO, codigos)
    distancias = matriz_distancias(municipios)
    if distancia_max is None:
        distancia_max = float(round(np.median(distancias[np.triu_indices(len(codigos), 1)])))
    capacidad = round(float(demanda.sum()) / k)
    if (capacidad, distancia_max) != CONGELADO[nombre]:
        raise ValueError(f"{nombre}: C={capacidad}, D_max={distancia_max} no coincide con lo congelado {CONGELADO[nombre]}")
    optimo = None
    if con_optimo:
        optimo = float(enumerar_optimo(demanda, distancias, k, capacidad, distancia_max).objetivo)
    return Instancia(nombre, demanda, distancias, k, float(capacidad), distancia_max, optimo)


def main() -> int:
    ruta_municipios = RAIZ / "data" / "processed" / "municipios.csv"
    panel = pd.read_csv(RAIZ / "data" / "processed" / "panel_municipal.csv", dtype={"codigo": str})
    departamentos = sorted(pd.read_csv(ruta_municipios, dtype=str)["codigo_departamento"].unique())

    desarrollo = panel[panel["anio"].isin(DESARROLLO)]
    con_registro = set(desarrollo.loc[desarrollo["casos_registrados"].notna(), "codigo"])
    nacional = sorted((m for d in departamentos for m in cargar_municipios_csv(ruta_municipios, d)), key=lambda m: m.codigo)
    excluidos = [m.codigo for m in nacional if m.codigo not in con_registro]
    nacional = [m for m in nacional if m.codigo in con_registro]

    instancias = [_instancia("huehuetenango_k4", cargar_municipios_csv(ruta_municipios, "GT13"), panel, 4, con_optimo=True)]
    instancias += [_instancia(f"nacional_k{k}", nacional, panel, k, distancia_max=22.0) for k in (10, 20, 40)]

    tablas = []
    for instancia in instancias:
        inicio = time.perf_counter()
        tablas.append(comparar_metodos(instancia, SEMILLAS))
        print(f"{instancia.nombre}: {time.perf_counter() - inicio:.0f} s", flush=True)
    tabla = pd.concat(tablas, ignore_index=True)
    metodos, pareado = resumir_escalabilidad(tabla)

    resultados = RAIZ / "resultados"
    tabla.to_csv(resultados / "escalabilidad_resultados.csv", index=False, lineterminator="\n")
    metodos.to_csv(resultados / "escalabilidad_resumen.csv", index=False, lineterminator="\n")
    pareado.to_csv(resultados / "escalabilidad_pareado.csv", index=False, lineterminator="\n")
    contenido = {
        "diseno": "docs/analisis_escalabilidad.md",
        "instancias": [{"nombre": i.nombre, "municipios": len(i.demanda), "k": i.k, "capacidad": i.capacidad,
                        "distancia_max_km": i.distancia_max, "combinaciones": float(math.comb(len(i.demanda), i.k)),
                        "optimo_exacto": i.optimo} for i in instancias],
        "excluidos_nacional_sin_registro": excluidos,
        "resumen": metodos.to_dict("records"),
        "pareado_genetico_menos_aleatoria": pareado.to_dict("records"),
    }
    (resultados / "escalabilidad_resumen.json").write_text(
        json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    columnas = ["instancia", "metodo", "objetivo_media", "objetivo_min", "cobertura_media_pct", "evaluaciones_media",
                "brecha_media", "proporcion_alcanza_referencia", "tiempo_medio_s"]
    print(metodos[columnas].round(4).to_string(index=False))
    print(pareado.round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
