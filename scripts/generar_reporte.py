"""Genera las figuras de los experimentos a partir de resultados/.

Requiere haber corrido antes ``python -m scripts.ejecutar_experimentos``.

Uso:
    python -m scripts.generar_reporte --config configs/piloto_chiquimula.json

Salidas (resultados/figuras/):
    mapa_asignacion.png          comportamiento del sistema
    comparacion_escenarios.png   comparación de escenarios y sensibilidad
    diferencias_pareadas.png     variabilidad
    convergencia_genetico.png    convergencia del algoritmo genético
    escalabilidad.png            análisis adicional (solo si existe resultados/escalabilidad_resultados.csv)
    dimensionamiento_*.png       curvas y mapas del estudio de dimensionamiento (si existe su salida)
    tamizaje_*.png               curvas y mapa del estudio de tamizaje (si existe su salida)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from brigadas import visualizacion as vis
from brigadas.asignacion import evaluar_bases
from brigadas.baseline import demanda_media_desarrollo
from brigadas.config import cargar_configuracion
from brigadas.dimensionamiento import asignar_divisible, matriz_tiempos
from brigadas.distancias import cargar_municipios_csv, matriz_distancias
from brigadas.tamizaje import ProblemaTamizaje

RAIZ = Path(__file__).resolve().parents[1]
LIMITES = RAIZ / "data" / "raw" / "hdx_gtm_admin_boundaries.geojson.zip"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="configs/piloto_chiquimula.json")
    args = parser.parse_args(argv)
    config = cargar_configuracion(RAIZ / args.config)
    dep = config.departamento
    resultados = RAIZ / "resultados"
    figuras = resultados / "figuras"

    municipios = cargar_municipios_csv(RAIZ / "data" / "processed" / "municipios.csv", dep)
    codigos = [m.codigo for m in municipios]
    distancias = matriz_distancias(municipios)
    panel = pd.read_csv(RAIZ / "data" / "processed" / f"panel_{dep}.csv", dtype={"codigo": str})
    referencia = demanda_media_desarrollo(panel, config.anios_desarrollo, codigos)
    tabla_municipios = pd.DataFrame({"codigo": codigos, "nombre": [m.nombre for m in municipios],
                                     "latitud": [m.latitud for m in municipios],
                                     "longitud": [m.longitud for m in municipios]})

    bases = pd.read_csv(resultados / "experimentos_bases.csv", dtype=str).set_index("condicion")
    a_tupla = lambda cadena: tuple(int(i) for i in cadena.split("-"))  # noqa: E731
    bases_base = a_tupla(bases.loc["nominal", "bases_base"])
    bases_ga = a_tupla(bases.loc["nominal", "bases_genetico_mas_frecuente"])
    asignacion = evaluar_bases(referencia, distancias, bases_ga, config.capacidad_por_brigada, config.distancia_max_km)
    poligonos = gpd.read_file(f"zip://{LIMITES}!gtm_admin2.geojson")
    poligonos = poligonos[poligonos["adm1_pcode"] == dep]
    vis.figura_mapa(poligonos, tabla_municipios, referencia, bases_base, bases_ga, asignacion.asignaciones,
                    figuras / "mapa_asignacion.png",
                    f"Chiquimula: demanda de referencia, bases y asignación (C = {config.capacidad_por_brigada}, "
                    f"D_max = {config.distancia_max_km:g} km)")

    resumen = pd.read_csv(resultados / "experimentos_resumen.csv")
    observado = pd.read_csv(resultados / "experimentos_observado.csv")
    replicas = pd.read_csv(resultados / "experimentos_replicas.csv")
    convergencia = pd.read_csv(resultados / "experimentos_convergencia.csv")
    vis.figura_comparacion(resumen, observado, figuras / "comparacion_escenarios.png")
    vis.figura_diferencias(replicas, figuras / "diferencias_pareadas.png")
    vis.figura_convergencia(convergencia, figuras / "convergencia_genetico.png")

    # Análisis adicional (docs/analisis_escalabilidad.md), si ya se ejecutó.
    ruta_escalabilidad = resultados / "escalabilidad_resultados.csv"
    if ruta_escalabilidad.exists():
        info = json.loads((resultados / "escalabilidad_resumen.json").read_text(encoding="utf-8"))
        titulos = {
            i["nombre"]: f"{'Huehuetenango' if i['nombre'].startswith('hue') else 'Nacional'}, K = {i['k']}\n"
                         f"{i['municipios']} municipios, {i['combinaciones']:.1e} combinaciones"
            for i in info["instancias"]
        }
        vis.figura_escalabilidad(pd.read_csv(ruta_escalabilidad), titulos, figuras / "escalabilidad.png")

    # Estudio de dimensionamiento (docs/estudio_dimensionamiento.md), si ya se ejecutó.
    ruta_dimensionamiento = resultados / "dimensionamiento_planes.csv"
    if ruta_dimensionamiento.exists():
        figuras_dimensionamiento(pd.read_csv(ruta_dimensionamiento, dtype={"bases": str}), municipios, tabla_municipios,
                                 panel, poligonos, figuras)

    # Estudio de tamizaje (docs/estudio_tamizaje.md), si ya se ejecutó.
    ruta_tamizaje = resultados / "tamizaje_planes.csv"
    if ruta_tamizaje.exists():
        figuras_tamizaje(pd.read_csv(ruta_tamizaje, dtype={"bases": str}), municipios, tabla_municipios, panel,
                         poligonos, figuras)
    print(f"Figuras guardadas en {figuras}")


def figuras_tamizaje(planes, municipios, tabla_municipios, panel, poligonos, figuras) -> None:
    vis.figura_tamizaje(planes, figuras / "tamizaje_curvas.png")
    info = json.loads((RAIZ / "resultados" / "tamizaje_resumen.json").read_text(encoding="utf-8"))["referencia"]
    k = info["k_minimo"]
    if k is None:
        return
    codigos = [m.codigo for m in municipios]
    tiempos = matriz_tiempos(RAIZ / "data" / "referencia" / "osrm_chiquimula.json", codigos)
    datos = panel[panel["anio"] == 2024].set_index("codigo").loc[codigos]
    ninos = datos["poblacion_0_4"].to_numpy(dtype=float)
    tasas = datos["casos_registrados"].to_numpy(dtype=float) / ninos
    sub = planes[planes["propuesto"] & (planes["k"] == k) & (planes["productividad"] == info["productividad"])
                 & (planes["umbral_min"] == info["umbral_min"])].set_index("objetivo")["bases"]
    bases = {o: tuple(int(i) for i in sub[o].split("-")) for o in ("casos", "ninos")}
    problema = ProblemaTamizaje(ninos, tasas, tiempos, 220 * info["productividad"], info["umbral_min"], "casos")
    r = problema.evaluar(bases["casos"])
    por_municipio = r.evaluados.sum(axis=1)
    posicion = {j: bases["casos"].index(j) for j in set(bases["casos"])}
    asignaciones = tuple(posicion[int(np.argmax(r.evaluados[i]))] if por_municipio[i] > 0 else None
                         for i in range(len(codigos)))
    vis.figura_mapa(poligonos, tabla_municipios, 1000 * tasas, bases["ninos"], bases["casos"], asignaciones,
                    figuras / "tamizaje_mapa.png",
                    f"Tamizaje con {k} brigadas ({info['productividad']:g} evaluaciones/día, viaje ≤ {info['umbral_min']:g} min)",
                    etiquetas=("Bases del plan para evaluar niños", "Bases del plan para identificar casos (×n)",
                               "Brigada que evalúa más niños del municipio"),
                    leyenda_color="Casos por cada 1,000 niños de 0 a 4 años (2024)", anotar_repetidas=True)


def figuras_dimensionamiento(planes, municipios, tabla_municipios, panel, poligonos, figuras) -> None:
    vis.figura_dimensionamiento(planes[planes["asignacion"] == "divisible"], figuras / "dimensionamiento_curvas.png")
    vis.figura_dimensionamiento(planes[planes["asignacion"] == "rigida"], figuras / "dimensionamiento_curvas_rigida.png")

    codigos = [m.codigo for m in municipios]
    tiempos = matriz_tiempos(RAIZ / "data" / "referencia" / "osrm_chiquimula.json", codigos)
    casos = panel[panel["anio"] == 2024].set_index("codigo").loc[codigos, "casos_registrados"].to_numpy(dtype=float)
    info = json.loads((RAIZ / "resultados" / "dimensionamiento_resumen.json").read_text(encoding="utf-8"))["referencia"]
    # Mapa de la configuración de referencia y mapa adicional con 3 brigadas (disyuntiva entre enfoques).
    for k, nombre in ((info["k_minimo"], "dimensionamiento_mapa.png"), (3, "dimensionamiento_mapa_k3.png")):
        if k is None:
            continue
        sub = planes[(planes["asignacion"] == "divisible") & (planes["k"] == k)
                     & (planes["capacidad"] == info["capacidad"]) & (planes["umbral_min"] == info["umbral_min"])]
        por_enfoque = sub.set_index("enfoque")["bases"].map(lambda c: tuple(int(i) for i in c.split("-")))
        resultado = asignar_divisible(casos, tiempos, por_enfoque["cobertura"], info["capacidad"], info["umbral_min"])
        vis.figura_mapa(
            poligonos, tabla_municipios, casos, por_enfoque["vulnerabilidad"], por_enfoque["cobertura"],
            resultado.asignaciones, figuras / nombre,
            f"Plan con {k} brigadas (C = {info['capacidad']}, viaje ≤ {info['umbral_min']} min, casos de 2024)",
            etiquetas=("Bases del enfoque de vulnerabilidad", "Bases del enfoque de cobertura",
                       "Asignación principal del enfoque de cobertura"),
            leyenda_color="Casos registrados en 2024")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
