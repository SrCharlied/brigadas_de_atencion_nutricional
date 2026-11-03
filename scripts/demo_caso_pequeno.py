"""Demostración del Hito 2: el baseline se ejecuta sin el algoritmo genético.

Usa la red SINTÉTICA de tests/fixtures/caso_pequeno.json (no son datos MSPAS):
compara la política base contra el óptimo exacto en 30 réplicas pareadas y
guarda los resultados en resultados/demo_caso_pequeno.csv.

Uso (desde la raíz del repositorio):
    python -m scripts.demo_caso_pequeno
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import numpy as np

from brigadas.baseline import crear_politica_base
from brigadas.config import ConfiguracionEscenario
from brigadas.contratos import PesosObjetivo
from brigadas.exacto import crear_politica_exacta
from brigadas.simulacion import ejecutar_replicas, generador_poisson, guardar_resultados_csv

RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    with open(RAIZ / "tests" / "fixtures" / "caso_pequeno.json", encoding="utf-8") as f:
        caso = json.load(f)
    demanda_ref = np.array(caso["demanda"], dtype=float)
    distancias = np.array(caso["distancias_km"], dtype=float)
    pesos = PesosObjetivo(**caso["pesos"])

    config = ConfiguracionEscenario(
        departamento="Sintético",
        anios_desarrollo=(2015, 2022),
        anios_validacion=(2023, 2024),
        cantidad_brigadas=caso["cantidad_brigadas"],
        capacidad_por_brigada=caso["capacidad"],
        distancia_max_km=caso["distancia_max_km"],
        replicas=30,
        semilla_raiz=2026,
    )
    politicas = {
        "base": crear_politica_base(demanda_ref, pesos),
        "exacta": crear_politica_exacta(demanda_ref, pesos),
    }
    resultados = ejecutar_replicas(config, generador_poisson(demanda_ref), politicas, distancias,
                                    escenario="demo_caso_pequeno")

    salida = RAIZ / "resultados" / "demo_caso_pequeno.csv"
    guardar_resultados_csv(resultados, salida)

    print("Red sintética de 5 municipios, 30 réplicas pareadas (datos NO reales)\n")
    for nombre in politicas:
        filas = [r for r in resultados if r.politica == nombre]
        cob = [r.porcentaje_cobertura for r in filas]
        print(f"{nombre:>7}: cobertura media {statistics.mean(cob):5.1f} % "
              f"(DE {statistics.stdev(cob):4.1f}); factibles {sum(r.factible for r in filas)}/{len(filas)}")
    diferencias = [
        e.porcentaje_cobertura - b.porcentaje_cobertura
        for b, e in zip(
            (r for r in resultados if r.politica == "base"),
            (r for r in resultados if r.politica == "exacta"),
        )
    ]
    print(f"\nDiferencia pareada media (exacta − base): {statistics.mean(diferencias):+.1f} puntos")
    print(f"Resultados guardados en {salida.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
