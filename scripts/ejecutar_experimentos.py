"""Experimentos base vs. algoritmo genético según docs/diseno_experimental.md.

Requiere haber corrido antes:
    python -m scripts.preparar_datos --config configs/piloto_chiquimula.json
    python -m scripts.validar_demanda --config configs/piloto_chiquimula.json

Uso:
    python -m scripts.ejecutar_experimentos --config configs/piloto_chiquimula.json

Salidas (resultados/):
    experimentos_replicas.csv       5 condiciones × 30 réplicas × 2 políticas
    experimentos_observado.csv      ambas políticas con los casos reales 2023 y 2024
    experimentos_resumen.csv        métricas por condición y diferencia pareada con IC 95 %
    experimentos_calidad.csv        brecha del algoritmo genético frente al óptimo exacto
    experimentos_convergencia.csv   mejor y mediana de J por generación
    experimentos_bases.csv          bases elegidas por cada política
    experimentos_resumen.json       resumen para el informe
La columna tiempo_ejecucion_ms cambia en cada ejecución; el resto es reproducible.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from brigadas import demanda
from brigadas.baseline import demanda_media_desarrollo
from brigadas.config import cargar_configuracion
from brigadas.contratos import PesosObjetivo
from brigadas.distancias import cargar_municipios_csv, matriz_distancias
from brigadas.experimentos import CONDICIONES, ejecutar_experimentos, resumir_experimentos
from brigadas.genetico import ParametrosGenetico
from brigadas.simulacion import guardar_resultados_csv

RAIZ = Path(__file__).resolve().parents[1]


def _nombres(cadena: str, municipios) -> list[str]:
    return [municipios[int(i)].nombre for i in cadena.split("-")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="configs/piloto_chiquimula.json")
    parser.add_argument("--anio-objetivo", type=int, default=2024,
                        help="Año cuya población proyectada multiplica las tasas M0 (no usa casos de ese año).")
    args = parser.parse_args(argv)
    config = cargar_configuracion(RAIZ / args.config)
    dep = config.departamento
    resultados = RAIZ / "resultados"
    parametros, pesos = ParametrosGenetico(), PesosObjetivo()

    municipios = cargar_municipios_csv(RAIZ / "data" / "processed" / "municipios.csv", dep)
    codigos = [m.codigo for m in municipios]
    distancias = matriz_distancias(municipios)
    panel = pd.read_csv(RAIZ / "data" / "processed" / f"panel_{dep}.csv", dtype={"codigo": str})
    panel = panel[panel["codigo"].isin(codigos)]

    referencia = demanda_media_desarrollo(panel, config.anios_desarrollo, codigos)
    desarrollo = panel[panel["anio"].isin(config.anios_desarrollo)]
    modelo = demanda.ajustar(desarrollo, "M0", config.anios_desarrollo)
    objetivo = panel[panel["anio"] == args.anio_objetivo].sort_values("codigo")
    mu = modelo.media(objetivo)["mu"].to_numpy(dtype=float)
    a = json.loads((resultados / "demanda_dispersion.json").read_text(encoding="utf-8"))["a"]
    observados = {}
    for anio in config.anios_validacion:
        filas = panel[panel["anio"] == anio].sort_values("codigo")
        if filas["casos_registrados"].isna().any():
            raise ValueError(f"Hay municipios sin registro en {anio}; no se imputan como cero.")
        observados[f"observado_{anio}"] = filas["casos_registrados"].to_numpy(dtype=float)

    r = ejecutar_experimentos(config, referencia, mu, a, distancias, observados, CONDICIONES, parametros, pesos)
    resumen = resumir_experimentos(r.replicas)

    guardar_resultados_csv(r.replicas, resultados / "experimentos_replicas.csv")
    guardar_resultados_csv(r.observado, resultados / "experimentos_observado.csv")
    resumen.to_csv(resultados / "experimentos_resumen.csv", index=False, lineterminator="\n")
    r.calidad.to_csv(resultados / "experimentos_calidad.csv", index=False, lineterminator="\n")
    r.convergencia.to_csv(resultados / "experimentos_convergencia.csv", index=False, lineterminator="\n")
    bases = r.bases.copy()
    for columna in ("bases_base", "bases_genetico_mas_frecuente", "bases_optimo_exacto"):
        bases[columna.replace("bases_", "nombres_")] = bases[columna].map(lambda c: ", ".join(_nombres(c, municipios)))
    bases.to_csv(resultados / "experimentos_bases.csv", index=False, lineterminator="\n")

    observado = pd.DataFrame([x.a_dict() for x in r.observado])
    real = {}
    for escenario, sub in observado.groupby("escenario"):
        base = float(sub.loc[sub["politica"] == "base", "porcentaje_cobertura"].iloc[0])
        ga = float(sub.loc[sub["politica"] == "genetico", "porcentaje_cobertura"].iloc[0])
        real[escenario] = {"casos": float(observados[escenario].sum()), "cobertura_base_pct": base,
                           "cobertura_genetico_pct": ga, "diferencia_pp": ga - base,
                           "cambio_relativo_pct": (ga - base) / base * 100 if base else None}
    calidad = r.calidad.groupby("condicion", sort=False).agg(
        proporcion_alcanza_optimo=("alcanza_optimo", "mean"), brecha_media=("brecha", "mean"),
        brecha_maxima=("brecha", "max"), generaciones_media=("generaciones", "mean"),
        evaluaciones_media=("evaluaciones", "mean"))
    contenido = {
        "diseno": "docs/diseno_experimental.md",
        "departamento": dep,
        "anio_objetivo_media": args.anio_objetivo,
        "parametros_genetico": asdict(parametros),
        "pesos": asdict(pesos),
        "condiciones": [asdict(c) for c in CONDICIONES],
        "resumen": resumen.to_dict("records"),
        "comparacion_real": real,
        "calidad_genetico": calidad.reset_index().to_dict("records"),
        "bases": bases.to_dict("records"),
        "nota": "Resultados simulados; km geodésicos entre centroides; casos registrados, no prevalencia.",
    }
    (resultados / "experimentos_resumen.json").write_text(
        json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    columnas = ["condicion", "cobertura_base_media", "cobertura_genetico_media", "diferencia_media_pp",
                "ic95_inferior_pp", "ic95_superior_pp"]
    print(resumen[columnas].round(2).to_string(index=False))
    for escenario, valores in real.items():
        print(f"{escenario}: base {valores['cobertura_base_pct']:.1f} % | genético {valores['cobertura_genetico_pct']:.1f} %"
              f" | diferencia {valores['diferencia_pp']:+.2f} pp")
    print(calidad.round(4).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
