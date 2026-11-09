"""Planificador interactivo: dónde ubicar N brigadas en Chiquimula y cuántos casos identificarían.

Usa la formulación de docs/estudio_tamizaje.md: las brigadas evalúan niños de 0 a 4 años
(población INE 2024) y los casos identificados se estiman con la tasa de casos de 2024
de cada municipio. Con K ≤ 5 el plan es el óptimo exacto; con más brigadas, el mejor entre
la heurística voraz y 5 ejecuciones del algoritmo genético.

Uso:
    python -m scripts.planificar --brigadas 9
    python -m scripts.planificar --brigadas 4 --productividad 20 --tiempo 45 --objetivo ninos --mapa
"""

from __future__ import annotations

import argparse
import time
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from brigadas import visualizacion as vis
from brigadas.dimensionamiento import matriz_tiempos
from brigadas.distancias import cargar_municipios_csv
from brigadas.tamizaje import ProblemaTamizaje, planificar

RAIZ = Path(__file__).resolve().parents[1]
DEPARTAMENTO = "GT20"
RANGOS = {"productividad": (20.0, 35.0), "tiempo": (45.0, 90.0), "brigadas": (1, 15), "dias": (220, 220)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--brigadas", type=int, required=True, help="número de brigadas (estudiado: 1 a 15)")
    parser.add_argument("--productividad", type=float, default=27.5, help="evaluaciones por brigada y día (PMA: 20 a 35)")
    parser.add_argument("--dias", type=int, default=220, help="días de campo al año (supuesto: 220)")
    parser.add_argument("--tiempo", type=float, default=60.0, help="viaje máximo en minutos, solo ida (estudiado: 45 a 90)")
    parser.add_argument("--objetivo", choices=("casos", "ninos"), default="casos",
                        help="casos: identificar más casos; ninos: evaluar a más niños")
    parser.add_argument("--mapa", action="store_true", help="guardar resultados/figuras/plan_<brigadas>.png")
    args = parser.parse_args(argv)
    if args.brigadas < 1:
        parser.error("--brigadas debe ser al menos 1")
    for nombre, valor in (("brigadas", args.brigadas), ("productividad", args.productividad),
                          ("tiempo", args.tiempo), ("dias", args.dias)):
        bajo, alto = RANGOS[nombre]
        if not bajo <= valor <= alto:
            # Por la salida normal: en PowerShell, stderr se muestra como si fuera un error.
            print(f"AVISO: {nombre} = {valor:g} está fuera del rango estudiado ({bajo:g} a {alto:g}); "
                  "el resultado es una extrapolación.")

    municipios = cargar_municipios_csv(RAIZ / "data" / "processed" / "municipios.csv", DEPARTAMENTO)
    codigos = [m.codigo for m in municipios]
    nombres = [m.nombre for m in municipios]
    tiempos = matriz_tiempos(RAIZ / "data" / "referencia" / "osrm_chiquimula.json", codigos)
    panel = pd.read_csv(RAIZ / "data" / "processed" / f"panel_{DEPARTAMENTO}.csv", dtype={"codigo": str})
    datos = panel[panel["anio"] == 2024].set_index("codigo").loc[codigos]
    ninos = datos["poblacion_0_4"].to_numpy(dtype=float)
    casos = datos["casos_registrados"].to_numpy(dtype=float)
    tasas = casos / ninos

    capacidad = args.dias * args.productividad
    problema = ProblemaTamizaje(ninos, tasas, tiempos, capacidad, args.tiempo, args.objetivo)
    inicio = time.perf_counter()
    plan = planificar(problema, args.brigadas)
    segundos = time.perf_counter() - inicio
    r = problema.evaluar(plan.bases)
    por_municipio = r.evaluados.sum(axis=1)
    conteo = Counter(plan.bases)

    print(f"\nPlan para {args.brigadas} brigada(s) en Chiquimula "
          f"({args.productividad:g} evaluaciones/día × {args.dias} días = {capacidad:,.0f} evaluaciones/año por brigada; "
          f"viaje ≤ {args.tiempo:g} min; objetivo: {'identificar casos' if args.objetivo == 'casos' else 'evaluar niños'})")
    print(f"Método: {plan.metodo} ({segundos:.1f} s)\n")
    print("Bases:")
    for j, n_brigadas in sorted(conteo.items(), key=lambda par: nombres[par[0]]):
        print(f"  {nombres[j]:<22} {n_brigadas} brigada(s)")
    print(f"\nCasos identificados (esperados): {r.casos_identificados:,.0f} de {casos.sum():,.0f} "
          f"({100 * r.casos_identificados / casos.sum():.1f} %)")
    print(f"Niños evaluados:                 {r.ninos_evaluados:,.0f} de {ninos.sum():,.0f} "
          f"({100 * r.ninos_evaluados / ninos.sum():.1f} %)")
    print(f"Tiempo medio de viaje:           {r.tiempo_medio_min:.1f} min\n")
    tabla = pd.DataFrame({
        "municipio": nombres,
        "niños 0-4": ninos.astype(int),
        "evaluados %": np.round(100 * por_municipio / ninos, 1),
        "tasa ‰": np.round(1000 * tasas, 1),
        "casos esperados": np.round(tasas * por_municipio, 1),
    }).sort_values("tasa ‰", ascending=False)
    print(tabla.to_string(index=False))
    print("\nResultados simulados con supuestos declarados (docs/estudio_tamizaje.md); casos registrados, no prevalencia.")

    if args.mapa:
        principal = tuple(int(np.argmax(r.evaluados[i])) if por_municipio[i] > 0 else None for i in range(len(codigos)))
        posicion = {j: plan.bases.index(j) for j in set(plan.bases)}
        asignaciones = tuple(posicion[j] if j is not None else None for j in principal)
        poligonos = gpd.read_file(f"zip://{RAIZ / 'data' / 'raw' / 'hdx_gtm_admin_boundaries.geojson.zip'}!gtm_admin2.geojson")
        poligonos = poligonos[poligonos["adm1_pcode"] == DEPARTAMENTO]
        tabla_municipios = pd.DataFrame({"codigo": codigos, "nombre": nombres,
                                         "latitud": [m.latitud for m in municipios],
                                         "longitud": [m.longitud for m in municipios]})
        ruta = RAIZ / "resultados" / "figuras" / f"plan_{args.brigadas}.png"
        vis.figura_mapa(poligonos, tabla_municipios, 1000 * tasas, (), plan.bases, asignaciones, ruta,
                        f"Plan con {args.brigadas} brigadas ({args.productividad:g}/día, viaje ≤ {args.tiempo:g} min)",
                        etiquetas=("_", "Bases (×n: brigadas en el municipio)", "Brigada que evalúa más niños del municipio"),
                        leyenda_color="Casos por cada 1,000 niños de 0 a 4 años (2024)", anotar_repetidas=True)
        print(f"Mapa guardado en {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
