"""Prueba de punta a punta del Hito 2 con archivos procesados SINTÉTICOS."""

import json

import numpy as np
import pandas as pd

from scripts.ejecutar_baseline import ejecutar


def preparar_archivos(tmp_path):
    rng = np.random.default_rng(0)
    codigos = [f"GT20{i:02d}" for i in range(1, 7)]
    lat = 14.6 + rng.uniform(0, 0.4, 6)
    lon = -89.7 + rng.uniform(0, 0.4, 6)
    municipios = pd.DataFrame({
        "codigo": codigos, "nombre": [f"Municipio {i}" for i in range(1, 7)],
        "codigo_departamento": "GT20", "departamento": "Chiquimula", "latitud": lat, "longitud": lon,
    })
    # Un municipio de otro departamento que debe ignorarse.
    municipios.loc[len(municipios)] = ["GT0101", "Otro", "GT01", "Guatemala", 14.6, -90.5]
    filas = []
    for c, tasa in zip(codigos, [5, 12, 8, 20, 3, 9]):
        for anio in range(2015, 2025):
            pob = 4000 + 100 * (anio - 2015)
            filas.append({"codigo": c, "anio": anio, "poblacion_0_4": pob,
                          "casos_registrados": int(rng.poisson(tasa * pob / 1000))})
    panel = pd.DataFrame(filas)
    config = {
        "_nota": "sintético", "departamento": "GT20",
        "anios_desarrollo": list(range(2015, 2023)), "anios_validacion": [2023, 2024],
        "cantidad_brigadas": 2, "capacidad_por_brigada": 150, "distancia_max_km": 40.0,
        "replicas": 30, "semilla_raiz": 1,
    }
    rutas = {k: tmp_path / v for k, v in {
        "config": "config.json", "municipios": "municipios.csv", "panel": "panel.csv",
        "dispersion": "dispersion.json"}.items()}
    rutas["config"].write_text(json.dumps(config), encoding="utf-8")
    municipios.to_csv(rutas["municipios"], index=False)
    panel.to_csv(rutas["panel"], index=False)
    rutas["dispersion"].write_text(json.dumps({"a": 0.116}), encoding="utf-8")
    return rutas


def test_baseline_de_punta_a_punta(tmp_path):
    rutas = preparar_archivos(tmp_path)
    (tmp_path / "res").mkdir()
    (tmp_path / "proc").mkdir()
    resumen = ejecutar(rutas["config"], rutas["municipios"], rutas["panel"], rutas["dispersion"],
                       tmp_path / "res", tmp_path / "proc", anio_objetivo=2024)
    # Bases = las 2 mayores demandas medias de desarrollo (tasas 20 y 12).
    assert [b["codigo"] for b in resumen["bases"]] == ["GT2004", "GT2002"]
    assert resumen["todas_factibles"]
    assert set(resumen["cobertura_media_pct"]) == {"escala_1", "escala_1.2"}
    assert resumen["cobertura_media_pct"]["escala_1.2"] <= resumen["cobertura_media_pct"]["escala_1"]
    assert set(resumen["cobertura_observada_pct"]) == {"observado_2023", "observado_2024"}
    replicas = pd.read_csv(tmp_path / "res" / "baseline_GT20_replicas.csv")
    assert len(replicas) == 60
    assert (tmp_path / "proc" / "distancias_GT20.csv").exists()


def test_baseline_es_reproducible(tmp_path):
    rutas = preparar_archivos(tmp_path)
    for carpeta in ("a", "b"):
        (tmp_path / carpeta).mkdir()
        ejecutar(rutas["config"], rutas["municipios"], rutas["panel"], rutas["dispersion"],
                 tmp_path / carpeta, tmp_path / carpeta, anio_objetivo=2024)
    a = pd.read_csv(tmp_path / "a" / "baseline_GT20_replicas.csv").drop(columns="tiempo_ejecucion_ms")
    b = pd.read_csv(tmp_path / "b" / "baseline_GT20_replicas.csv").drop(columns="tiempo_ejecucion_ms")
    pd.testing.assert_frame_equal(a, b)
