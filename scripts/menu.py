"""Menú interactivo para la demostración: brigadas de atención nutricional en Chiquimula.

Uso (o doble clic en demo.bat):
    python -m scripts.menu

Cada pregunta muestra su valor por defecto entre corchetes; Enter lo acepta.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

from scripts import planificar

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = RAIZ / "resultados"
FIGURAS = RESULTADOS / "figuras"
LINEA = "=" * 64


def pedir_numero(texto: str, defecto: float, minimo: float, maximo: float, entero: bool = False):
    while True:
        respuesta = input(f"{texto} [{defecto:g}]: ").strip().lstrip("﻿").replace(",", ".")
        if not respuesta:
            return defecto
        try:
            valor = int(respuesta) if entero else float(respuesta)
        except ValueError:
            print(f"  Escriba un número{' entero' if entero else ''}.")
            continue
        if minimo <= valor <= maximo:
            return valor
        print(f"  Debe estar entre {minimo:g} y {maximo:g}.")


def pedir_opcion(texto: str, opciones: dict[str, str], defecto: str) -> str:
    while True:
        respuesta = input(f"{texto} [{defecto}]: ").strip().lstrip("﻿") or defecto
        if respuesta in opciones:
            return opciones[respuesta]
        print(f"  Elija una de: {', '.join(opciones)}.")


def abrir(ruta: Path) -> None:
    if hasattr(os, "startfile"):
        os.startfile(ruta)  # Windows: abre con el visor predeterminado
    else:
        print(f"  Abra el archivo: {ruta}")


def tabla_rapida(planes: pd.DataFrame, productividad: float, umbral: float, objetivo: str) -> pd.DataFrame:
    sub = planes[planes["propuesto"] & (planes["objetivo"] == objetivo) & (planes["productividad"] == productividad)
                 & (planes["umbral_min"] == umbral)].sort_values("k")
    # Después del primer 100 % las brigadas extra no aportan y hay muchos planes empatados.
    completos = sub.index[sub["casos_pct"] >= 99.95]
    if len(completos):
        sub = sub.loc[: completos[0]]
    return pd.DataFrame({
        "brigadas": sub["k"].astype(int).to_numpy(),
        "casos %": sub["casos_pct"].round(1).to_numpy(),
        "niños %": sub["ninos_pct"].round(1).to_numpy(),
        "ubicación": sub["ubicacion"].to_numpy(),
    })


def opcion_planificar() -> None:
    print("\nPlanificar brigadas: ¿dónde ubicarlas y cuántos casos identificarían?")
    brigadas = pedir_numero("Número de brigadas", 6, 1, 30, entero=True)
    productividad = pedir_numero("Evaluaciones por brigada y día (PMA: 20 a 35)", 27.5, 5, 60)
    tiempo = pedir_numero("Viaje máximo en minutos, solo ida", 60, 15, 180)
    objetivo = pedir_opcion("Objetivo: 1 = identificar casos, 2 = evaluar a más niños", {"1": "casos", "2": "ninos"}, "1")
    mapa = pedir_opcion("¿Guardar y abrir el mapa? s/n", {"s": "s", "n": "n"}, "s") == "s"
    argumentos = ["--brigadas", str(brigadas), "--productividad", f"{productividad:g}", "--tiempo", f"{tiempo:g}",
                  "--objetivo", objetivo] + (["--mapa"] if mapa else [])
    print("\nCalculando…")
    planificar.main(argumentos)
    if mapa:
        abrir(FIGURAS / f"plan_{brigadas}.png")


def opcion_tabla() -> None:
    ruta = RESULTADOS / "tamizaje_planes.csv"
    if not ruta.exists():
        print("  Falta resultados/tamizaje_planes.csv; ejecute python -m scripts.ejecutar_tamizaje.")
        return
    print("\nComparar números de brigadas (resultados del estudio de tamizaje)")
    productividad = pedir_opcion("Evaluaciones por día: 1 = 20, 2 = 27.5, 3 = 35", {"1": 20.0, "2": 27.5, "3": 35.0}, "2")
    umbral = pedir_opcion("Viaje máximo: 1 = 45 min, 2 = 60 min, 3 = 90 min", {"1": 45.0, "2": 60.0, "3": 90.0}, "2")
    objetivo = pedir_opcion("Objetivo: 1 = identificar casos, 2 = evaluar a más niños", {"1": "casos", "2": "ninos"}, "1")
    tabla = tabla_rapida(pd.read_csv(ruta), productividad, umbral, objetivo)
    print(f"\n{productividad:g} evaluaciones/día, viaje ≤ {umbral:g} min, objetivo: "
          f"{'identificar casos' if objetivo == 'casos' else 'evaluar niños'}\n")
    print(tabla.to_string(index=False))
    if len(tabla) and tabla["casos %"].iloc[-1] >= 99.95:
        print(f"\nCon {tabla['brigadas'].iloc[-1]} brigadas ya se cubre todo; más brigadas no aumentan los casos identificados.")


def opcion_resumen() -> None:
    try:
        validacion = json.loads((RESULTADOS / "demanda_validacion.json").read_text(encoding="utf-8"))
        experimentos = json.loads((RESULTADOS / "experimentos_resumen.json").read_text(encoding="utf-8"))
        decision = pd.read_csv(RESULTADOS / "tamizaje_decision.csv")
    except FileNotFoundError as error:
        print(f"  Falta un archivo de resultados: {error.filename}")
        return
    m = validacion["metricas"][validacion["modelo_elegido"]]
    print(f"\n1) Demanda (modelo {validacion['modelo_elegido']}) frente a los casos reales de 2023-2024")
    print(f"   Ordena bien los municipios (Spearman {m['spearman_ranking']:.2f}; acierta {m['coincidencia_top3']} de los "
          f"3 con más casos), pero subestima el nivel ({100 * m['sesgo_relativo']:+.1f} %).")
    print("\n2) Política base frente al algoritmo genético (3 brigadas, 30 réplicas pareadas)")
    for fila in experimentos["resumen"]:
        print(f"   {fila['condicion']:<14} base {fila['cobertura_base_media']:5.1f} %  genético "
              f"{fila['cobertura_genetico_media']:5.1f} %  diferencia {fila['diferencia_media_pp']:+5.1f} pp "
              f"[{fila['ic95_inferior_pp']:+.1f}, {fila['ic95_superior_pp']:+.1f}]")
    for nombre, real in experimentos["comparacion_real"].items():
        print(f"   {nombre:<14} base {real['cobertura_base_pct']:5.1f} %  genético {real['cobertura_genetico_pct']:5.1f} %")
    print("\n3) Propuesta de tamizaje: brigadas necesarias (viaje ≤ 60 min)")
    sub = decision[decision["umbral_min"] == 60.0]
    for productividad, grupo in sub.groupby("productividad"):
        metas = ", ".join(f"{int(f.meta_pct)} %: {'—' if pd.isna(f.k_minimo) else int(f.k_minimo)}"
                          for f in grupo.itertuples())
        print(f"   {productividad:g} evaluaciones/día → {metas}")


def opcion_figuras() -> None:
    figuras = sorted(FIGURAS.glob("*.png"))
    if not figuras:
        print("  No hay figuras; ejecute python -m scripts.generar_reporte.")
        return
    print()
    for i, ruta in enumerate(figuras, start=1):
        print(f"  {i:>2}. {ruta.stem}")
    eleccion = pedir_numero("Número de la figura (0 = volver)", 0, 0, len(figuras), entero=True)
    if eleccion:
        abrir(figuras[eleccion - 1])


OPCIONES = {
    "1": ("Planificar brigadas (¿dónde y cuántos casos?)", opcion_planificar),
    "2": ("Comparar números de brigadas", opcion_tabla),
    "3": ("Ver resultados principales", opcion_resumen),
    "4": ("Abrir una figura", opcion_figuras),
}


def main() -> int:
    while True:
        print(f"\n{LINEA}\n  Brigadas de atención nutricional — Chiquimula\n{LINEA}")
        for clave, (texto, _) in OPCIONES.items():
            print(f"  {clave}. {texto}")
        print("  0. Salir")
        eleccion = input("\nOpción: ").strip().lstrip("﻿")
        if eleccion == "0":
            return 0
        if eleccion not in OPCIONES:
            print("  Opción no válida.")
            continue
        try:
            OPCIONES[eleccion][1]()
        except KeyboardInterrupt:
            print("\n  Cancelado.")
        input("\nEnter para volver al menú…")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyboardInterrupt, EOFError):
        sys.exit(0)
