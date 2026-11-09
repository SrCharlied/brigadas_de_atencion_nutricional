"""Pruebas de humo: cada figura se genera sin errores con datos SINTÉTICOS."""

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from brigadas import visualizacion as vis


def test_mapa(tmp_path):
    poligonos = gpd.GeoDataFrame(
        {"adm2_pcode": ["A", "B", "C"]}, geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)], crs="EPSG:4326"
    )
    municipios = pd.DataFrame({"codigo": ["A", "B", "C"], "nombre": ["Uno", "Dos", "Tres"],
                               "latitud": [0.5] * 3, "longitud": [0.5, 1.5, 2.5]})
    ruta = tmp_path / "mapa.png"
    vis.figura_mapa(poligonos, municipios, np.array([10.0, 5.0, 2.0]), (0,), (1,), (0, 0, None), ruta, "Prueba")
    assert ruta.stat().st_size > 0


def test_dimensionamiento(tmp_path):
    filas = []
    for umbral in (45.0, 60.0):
        for capacidad in (150.0, 221.0):
            for k in (1, 2, 3):
                for enfoque, cob in (("cobertura", 40.0 * k), ("regla", 30.0 * k)):
                    filas.append({"umbral_min": umbral, "capacidad": capacidad, "k": k, "enfoque": enfoque,
                                  "cobertura_casos_2024_pct": cob, "sim_ic95_inferior_pct": cob - 3,
                                  "sim_ic95_superior_pct": cob + 3})
    ruta = tmp_path / "dim.png"
    vis.figura_dimensionamiento(pd.DataFrame(filas), ruta)
    assert ruta.stat().st_size > 0


def test_tamizaje(tmp_path):
    filas = [{"objetivo": o, "propuesto": True, "umbral_min": t, "productividad": p, "k": k,
              "casos_pct": min(100.0, k * (12.0 if o == "casos" else 9.0)), "ninos_pct": min(100.0, k * 8.0)}
             for o in ("casos", "ninos") for t in (45.0, 60.0) for p in (20.0, 27.5) for k in range(1, 6)]
    ruta = tmp_path / "tam.png"
    vis.figura_tamizaje(pd.DataFrame(filas), ruta)
    assert ruta.stat().st_size > 0


def test_escalabilidad(tmp_path):
    filas = []
    for instancia, optimo in (("chica", 0.1), ("grande", float("nan"))):
        filas += [{"instancia": instancia, "metodo": m, "semilla": -1, "objetivo": j, "optimo": optimo}
                  for m, j in (("base", 0.5), ("voraz", 0.2))]
        filas += [{"instancia": instancia, "metodo": m, "semilla": s, "objetivo": j + 0.01 * s, "optimo": optimo}
                  for s in range(3) for m, j in (("aleatoria", 0.3), ("genetico", 0.15))]
    ruta = tmp_path / "esc.png"
    vis.figura_escalabilidad(pd.DataFrame(filas), {"chica": "Chica", "grande": "Grande"}, ruta)
    assert ruta.stat().st_size > 0


def test_comparacion_diferencias_y_convergencia(tmp_path):
    resumen = pd.DataFrame({
        "condicion": ["nominal", "dmax_40"], "replicas": [30, 30],
        "cobertura_base_media": [70.0, 80.0], "cobertura_base_desviacion": [3.0, 2.0],
        "cobertura_genetico_media": [75.0, 81.0], "cobertura_genetico_desviacion": [3.0, 2.0],
    })
    observado = pd.DataFrame({"escenario": ["observado_2023"] * 2, "politica": ["base", "genetico"],
                              "porcentaje_cobertura": [60.0, 65.0]})
    replicas = pd.DataFrame({
        "escenario": ["nominal"] * 4, "replica": [0, 0, 1, 1], "politica": ["base", "genetico"] * 2,
        "porcentaje_cobertura": [70.0, 74.0, 71.0, 76.0],
    })
    convergencia = pd.DataFrame({"generacion": [0, 1, 2], "mejor": [0.5, 0.4, 0.4], "mediana": [0.7, 0.5, 0.45]})
    rutas = [tmp_path / n for n in ("comp.png", "dif.png", "conv.png")]
    vis.figura_comparacion(resumen, observado, rutas[0])
    vis.figura_diferencias(replicas, rutas[1])
    vis.figura_convergencia(convergencia, rutas[2])
    assert all(r.stat().st_size > 0 for r in rutas)
