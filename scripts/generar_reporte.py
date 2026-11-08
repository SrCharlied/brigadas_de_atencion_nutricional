"""Genera las figuras de los experimentos a partir de resultados/.

Requiere haber corrido antes ``python -m scripts.ejecutar_experimentos``.

Uso:
    python -m scripts.generar_reporte --config configs/piloto_chiquimula.json

Salidas (resultados/figuras/):
    mapa_asignacion.png          comportamiento del sistema
    comparacion_escenarios.png   comparación de escenarios y sensibilidad
    diferencias_pareadas.png     variabilidad
    convergencia_genetico.png    convergencia del algoritmo genético
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

from brigadas import visualizacion as vis
from brigadas.asignacion import evaluar_bases
from brigadas.baseline import demanda_media_desarrollo
from brigadas.config import cargar_configuracion
from brigadas.distancias import cargar_municipios_csv, matriz_distancias

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
    print(f"Figuras guardadas en {figuras}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
