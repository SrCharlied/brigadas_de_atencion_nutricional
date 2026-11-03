"""Hito 2: ejecuta la política base con los datos reales, sin el algoritmo genético.

Requiere haber corrido antes (Integrante 1):
    python -m scripts.descargar_datos
    python -m scripts.preparar_datos --config configs/piloto_chiquimula.json
    python -m scripts.validar_demanda --config configs/piloto_chiquimula.json

Uso:
    python -m scripts.ejecutar_baseline --config configs/piloto_chiquimula.json

Salidas:
    data/processed/distancias_<dep>.csv       matriz congelada (km geodésicos)
    resultados/baseline_<dep>_replicas.csv    réplicas simuladas (escala 1.0, 1.2 y 1.6)
    resultados/baseline_<dep>_observado.csv   cobertura con los casos reales 2023–2024
    resultados/baseline_<dep>_resumen.json    bases elegidas y resumen
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import numpy as np
import pandas as pd

from brigadas import demanda
from brigadas.baseline import crear_politica_base, demanda_media_desarrollo, seleccionar_bases_base
from brigadas.config import cargar_configuracion
from brigadas.contratos import PesosObjetivo
from brigadas.distancias import cargar_municipios_csv, guardar_matriz_csv, matriz_distancias
from brigadas.simulacion import (
    ejecutar_replicas,
    evaluar_demanda_fija,
    generador_binomial_negativa,
    guardar_resultados_csv,
)

RAIZ = Path(__file__).resolve().parents[1]


def ejecutar(
    ruta_config: Path,
    ruta_municipios: Path,
    ruta_panel: Path,
    ruta_dispersion: Path,
    carpeta_resultados: Path,
    carpeta_procesados: Path,
    anio_objetivo: int,
    escalas: tuple[float, ...] = (1.0, 1.2, 1.6),  # docs/protocolo_parametros.md §3
) -> dict:
    config = cargar_configuracion(ruta_config)
    dep = config.departamento
    pesos = PesosObjetivo()

    municipios = cargar_municipios_csv(ruta_municipios, dep)
    codigos = [m.codigo for m in municipios]
    distancias = matriz_distancias(municipios)
    guardar_matriz_csv(distancias, codigos, carpeta_procesados / f"distancias_{dep}.csv")

    panel = pd.read_csv(ruta_panel, dtype={"codigo": str})
    panel = panel[panel["codigo"].isin(codigos)]

    # Referencia de la política base: solo años de desarrollo.
    referencia = demanda_media_desarrollo(panel, config.anios_desarrollo, codigos)
    politicas = {"base": crear_politica_base(referencia, pesos)}

    # Media del modelo M0 (ajustado con desarrollo) para la población del año objetivo.
    desarrollo = panel[panel["anio"].isin(config.anios_desarrollo)]
    modelo = demanda.ajustar(desarrollo, "M0", config.anios_desarrollo)
    objetivo = panel[panel["anio"] == anio_objetivo].sort_values("codigo")
    if objetivo["codigo"].tolist() != codigos:
        raise ValueError(f"El panel no tiene todos los municipios de {dep} en {anio_objetivo}.")
    mu = modelo.media(objetivo)["mu"].to_numpy(dtype=float)
    a = json.loads(ruta_dispersion.read_text(encoding="utf-8"))["a"]

    replicas = []
    for escala in escalas:
        gen = generador_binomial_negativa(mu, a, escala=escala)
        replicas += ejecutar_replicas(config, gen, politicas, distancias, escenario=f"escala_{escala:g}")
    guardar_resultados_csv(replicas, carpeta_resultados / f"baseline_{dep}_replicas.csv")

    observado = []
    for anio in config.anios_validacion:
        filas = panel[panel["anio"] == anio].sort_values("codigo")
        if filas["casos_registrados"].isna().any():
            raise ValueError(f"Hay municipios sin registro en {anio}; no se imputan como cero.")
        observado += evaluar_demanda_fija(filas["casos_registrados"].to_numpy(dtype=float), politicas,
                                          distancias, config, escenario=f"observado_{anio}")
    guardar_resultados_csv(observado, carpeta_resultados / f"baseline_{dep}_observado.csv")

    bases = seleccionar_bases_base(referencia, config.cantidad_brigadas)
    resumen = {
        "departamento": dep,
        "anio_objetivo_media": anio_objetivo,
        "supuestos": {"cantidad_brigadas": config.cantidad_brigadas,
                      "capacidad_por_brigada_casos_anio": config.capacidad_por_brigada,
                      "distancia_max_km_geodesica": config.distancia_max_km,
                      "pesos": vars(pesos)},
        "bases": [{"indice": b, "codigo": codigos[b], "nombre": municipios[b].nombre} for b in bases],
        "replicas_por_escala": config.replicas,
        "cobertura_media_pct": {
            esc: statistics.mean(r.porcentaje_cobertura for r in replicas if r.escenario == esc)
            for esc in sorted({r.escenario for r in replicas})
        },
        "cobertura_observada_pct": {r.escenario: r.porcentaje_cobertura for r in observado},
        "todas_factibles": all(r.factible for r in replicas + observado),
        "nota": "Resultados simulados; km geodésicos entre centroides; casos registrados, no prevalencia.",
    }
    ruta = carpeta_resultados / f"baseline_{dep}_resumen.json"
    ruta.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumen


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="configs/piloto_chiquimula.json")
    p.add_argument("--anio-objetivo", type=int, default=2024,
                   help="Año cuya población proyectada multiplica las tasas M0 (no usa casos de ese año).")
    args = p.parse_args()
    resumen = ejecutar(
        ruta_config=RAIZ / args.config,
        ruta_municipios=RAIZ / "data" / "processed" / "municipios.csv",
        ruta_panel=RAIZ / "data" / "processed" / f"panel_{cargar_configuracion(RAIZ / args.config).departamento}.csv",
        ruta_dispersion=RAIZ / "resultados" / "demanda_dispersion.json",
        carpeta_resultados=RAIZ / "resultados",
        carpeta_procesados=RAIZ / "data" / "processed",
        anio_objetivo=args.anio_objetivo,
    )
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
