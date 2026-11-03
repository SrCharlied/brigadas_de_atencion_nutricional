"""Matriz de distancias del MVP (Denis Rodríguez).

Distancia geodésica (fórmula de haversine) entre centroides municipales, en km.

LIMITACIÓN: no equivale a distancia vial ni a tiempo real de viaje. Todo
resultado derivado debe etiquetarse como "km geodésicos entre centroides".
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Sequence

import numpy as np

from .contratos import Municipio

RADIO_TIERRA_KM = 6371.0088  # radio medio (IUGG)

__all__ = [
    "RADIO_TIERRA_KM",
    "haversine_km",
    "matriz_distancias",
    "validar_matriz_distancias",
    "guardar_matriz_csv",
    "cargar_matriz_csv",
    "cargar_municipios_csv",
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia de gran círculo en kilómetros entre dos puntos (grados)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(min(1.0, math.sqrt(a)))


def matriz_distancias(municipios: Sequence[Municipio]) -> np.ndarray:
    """Construye la matriz simétrica n×n de distancias en km.

    El orden de filas/columnas es el orden de ``municipios``; los códigos deben
    ser únicos para que el orden sea auditable.
    """
    if len(municipios) == 0:
        raise ValueError("Se requiere al menos un municipio.")
    codigos = [m.codigo for m in municipios]
    if len(set(codigos)) != len(codigos):
        duplicados = sorted({c for c in codigos if codigos.count(c) > 1})
        raise ValueError(f"Códigos de municipio duplicados: {duplicados}")

    lat = np.radians([m.latitud for m in municipios])
    lon = np.radians([m.longitud for m in municipios])
    dphi = lat[:, None] - lat[None, :]
    dlambda = lon[:, None] - lon[None, :]
    a = np.sin(dphi / 2) ** 2 + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin(dlambda / 2) ** 2
    matriz = 2 * RADIO_TIERRA_KM * np.arcsin(np.minimum(1.0, np.sqrt(a)))
    matriz = (matriz + matriz.T) / 2  # simetría exacta
    np.fill_diagonal(matriz, 0.0)
    validar_matriz_distancias(matriz)
    return matriz


def validar_matriz_distancias(matriz: np.ndarray, tolerancia: float = 1e-9) -> None:
    """Verifica forma cuadrada, valores finitos no negativos, diagonal cero y simetría."""
    if not isinstance(matriz, np.ndarray):
        raise TypeError("La matriz de distancias debe ser un numpy.ndarray.")
    if matriz.ndim != 2 or matriz.shape[0] != matriz.shape[1] or matriz.shape[0] == 0:
        raise ValueError(f"La matriz debe ser cuadrada y no vacía; forma recibida {matriz.shape}.")
    if not np.issubdtype(matriz.dtype, np.number):
        raise TypeError("La matriz de distancias debe ser numérica.")
    if not np.all(np.isfinite(matriz)):
        raise ValueError("La matriz contiene valores no finitos.")
    if np.any(matriz < 0):
        raise ValueError("La matriz contiene distancias negativas.")
    if np.any(np.abs(np.diag(matriz)) > tolerancia):
        raise ValueError("La diagonal de la matriz debe ser cero.")
    if not np.allclose(matriz, matriz.T, atol=tolerancia, rtol=0):
        raise ValueError("La matriz de distancias no es simétrica.")


def guardar_matriz_csv(matriz: np.ndarray, codigos: Sequence[str], ruta: str | Path) -> None:
    """Congela la matriz en CSV con los códigos como encabezado y primera columna."""
    validar_matriz_distancias(matriz)
    if len(codigos) != matriz.shape[0]:
        raise ValueError("La cantidad de códigos no coincide con la matriz.")
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["codigo", *codigos])
        for codigo, fila in zip(codigos, matriz):
            escritor.writerow([codigo, *(f"{v:.6f}" for v in fila)])


def cargar_matriz_csv(ruta: str | Path) -> tuple[np.ndarray, list[str]]:
    """Carga una matriz guardada con :func:`guardar_matriz_csv` y la valida."""
    with open(ruta, newline="", encoding="utf-8") as archivo:
        filas = list(csv.reader(archivo))
    if not filas or filas[0][0] != "codigo":
        raise ValueError("Formato de matriz inválido: falta encabezado 'codigo'.")
    codigos = filas[0][1:]
    codigos_filas = [f[0] for f in filas[1:]]
    if codigos != codigos_filas:
        raise ValueError("Los códigos de filas y columnas no coinciden.")
    matriz = np.array([[float(v) for v in f[1:]] for f in filas[1:]], dtype=float)
    validar_matriz_distancias(matriz, tolerancia=1e-5)
    return matriz, codigos


def cargar_municipios_csv(ruta: str | Path, codigo_departamento: str) -> list[Municipio]:
    """Lee ``data/processed/municipios.csv`` (Integrante 1) para un departamento.

    Devuelve los municipios **ordenados por código**, el mismo orden que usa
    ``demanda.ajustar(...).media(...)``; así los índices de la demanda y de la
    matriz de distancias coinciden.
    """
    with open(ruta, newline="", encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo))
    requeridas = {"codigo", "nombre", "codigo_departamento", "latitud", "longitud"}
    if not filas or not requeridas <= set(filas[0]):
        raise ValueError(f"{ruta} debe tener las columnas {sorted(requeridas)}.")
    seleccion = [f for f in filas if f["codigo_departamento"] == codigo_departamento]
    if not seleccion:
        raise ValueError(f"No hay municipios con codigo_departamento == {codigo_departamento!r}.")
    municipios = [
        Municipio(
            codigo=f["codigo"],
            nombre=f["nombre"],
            departamento=f.get("departamento") or f["codigo_departamento"],
            latitud=float(f["latitud"]),
            longitud=float(f["longitud"]),
        )
        for f in seleccion
    ]
    return sorted(municipios, key=lambda m: m.codigo)
