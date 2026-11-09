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
from dataclasses import dataclass
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
NOMBRES_METODO = {"exacto": "óptimo exacto (enumeración de todas las ubicaciones)", "voraz": "heurística voraz",
                  "genetico": "algoritmo genético"}


@dataclass(frozen=True, eq=False)
class Contexto:
    """Datos de Chiquimula que usan el planificador por comando y la interfaz web."""

    municipios: list
    codigos: list[str]
    nombres: list[str]
    tiempos: np.ndarray
    ninos: np.ndarray
    casos: np.ndarray
    tasas: np.ndarray


@dataclass(frozen=True, eq=False)
class PlanCalculado:
    brigadas: int
    productividad: float
    dias: int
    tiempo: float
    objetivo: str
    capacidad: float
    metodo: str
    segundos: float
    bases: tuple[int, ...]
    conteo: dict[int, int]
    resultado: object  # ResultadoTamizaje
    tabla: pd.DataFrame


def cargar_contexto() -> Contexto:
    municipios = cargar_municipios_csv(RAIZ / "data" / "processed" / "municipios.csv", DEPARTAMENTO)
    codigos = [m.codigo for m in municipios]
    tiempos = matriz_tiempos(RAIZ / "data" / "referencia" / "osrm_chiquimula.json", codigos)
    panel = pd.read_csv(RAIZ / "data" / "processed" / f"panel_{DEPARTAMENTO}.csv", dtype={"codigo": str})
    datos = panel[panel["anio"] == 2024].set_index("codigo").loc[codigos]
    ninos = datos["poblacion_0_4"].to_numpy(dtype=float)
    casos = datos["casos_registrados"].to_numpy(dtype=float)
    return Contexto(municipios, codigos, [m.nombre for m in municipios], tiempos, ninos, casos, casos / ninos)


def calcular_plan(ctx: Contexto, brigadas: int, productividad: float = 27.5, tiempo: float = 60.0,
                  objetivo: str = "casos", dias: int = 220) -> PlanCalculado:
    capacidad = dias * productividad
    problema = ProblemaTamizaje(ctx.ninos, ctx.tasas, ctx.tiempos, capacidad, tiempo, objetivo)
    inicio = time.perf_counter()
    plan = planificar(problema, brigadas)
    segundos = time.perf_counter() - inicio
    r = problema.evaluar(plan.bases)
    por_municipio = r.evaluados.sum(axis=1)
    tabla = pd.DataFrame({
        "municipio": ctx.nombres,
        "niños 0-4": ctx.ninos.astype(int),
        "evaluados %": np.round(100 * por_municipio / ctx.ninos, 1),
        "tasa ‰": np.round(1000 * ctx.tasas, 1),
        "casos esperados": np.round(ctx.tasas * por_municipio, 1),
    }).sort_values("tasa ‰", ascending=False)
    return PlanCalculado(brigadas, productividad, dias, tiempo, objetivo, capacidad, plan.metodo, segundos, plan.bases,
                         dict(Counter(plan.bases)), r, tabla)


def guardar_mapa(ctx: Contexto, calculado: PlanCalculado, ruta: Path) -> Path:
    r = calculado.resultado
    por_municipio = r.evaluados.sum(axis=1)
    principal = tuple(int(np.argmax(r.evaluados[i])) if por_municipio[i] > 0 else None for i in range(len(ctx.codigos)))
    posicion = {j: calculado.bases.index(j) for j in set(calculado.bases)}
    asignaciones = tuple(posicion[j] if j is not None else None for j in principal)
    poligonos = gpd.read_file(f"zip://{RAIZ / 'data' / 'raw' / 'hdx_gtm_admin_boundaries.geojson.zip'}!gtm_admin2.geojson")
    poligonos = poligonos[poligonos["adm1_pcode"] == DEPARTAMENTO]
    tabla_municipios = pd.DataFrame({"codigo": ctx.codigos, "nombre": ctx.nombres,
                                     "latitud": [m.latitud for m in ctx.municipios],
                                     "longitud": [m.longitud for m in ctx.municipios]})
    vis.figura_mapa(poligonos, tabla_municipios, 1000 * ctx.tasas, (), calculado.bases, asignaciones, ruta,
                    f"Plan con {calculado.brigadas} brigadas ({calculado.productividad:g}/día, viaje ≤ {calculado.tiempo:g} min)",
                    etiquetas=("_", "Bases (×n: brigadas en el municipio)", "Brigada que evalúa más niños del municipio"),
                    leyenda_color="Casos por cada 1,000 niños de 0 a 4 años (2024)", anotar_repetidas=True)
    return Path(ruta)


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

    ctx = cargar_contexto()
    c = calcular_plan(ctx, args.brigadas, args.productividad, args.tiempo, args.objetivo, args.dias)
    r = c.resultado

    print(f"\nPlan para {c.brigadas} brigada(s) en Chiquimula "
          f"({c.productividad:g} evaluaciones/día × {c.dias} días = {c.capacidad:,.0f} evaluaciones/año por brigada; "
          f"viaje ≤ {c.tiempo:g} min; objetivo: {'identificar casos' if c.objetivo == 'casos' else 'evaluar niños'})")
    print(f"Método: {NOMBRES_METODO[c.metodo]} ({c.segundos:.1f} s)\n")
    print("Bases:")
    for j, n_brigadas in sorted(c.conteo.items(), key=lambda par: ctx.nombres[par[0]]):
        print(f"  {ctx.nombres[j]:<22} {n_brigadas} brigada(s)")
    print(f"\nCasos identificados (esperados): {r.casos_identificados:,.0f} de {ctx.casos.sum():,.0f} "
          f"({100 * r.casos_identificados / ctx.casos.sum():.1f} %)")
    print(f"Niños evaluados:                 {r.ninos_evaluados:,.0f} de {ctx.ninos.sum():,.0f} "
          f"({100 * r.ninos_evaluados / ctx.ninos.sum():.1f} %)")
    print(f"Tiempo medio de viaje:           {r.tiempo_medio_min:.1f} min\n")
    print(c.tabla.to_string(index=False))
    print("\nResultados simulados con supuestos declarados (docs/estudio_tamizaje.md); casos registrados, no prevalencia.")

    if args.mapa:
        ruta = guardar_mapa(ctx, c, RAIZ / "resultados" / "figuras" / f"plan_{c.brigadas}.png")
        print(f"Mapa guardado en {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
