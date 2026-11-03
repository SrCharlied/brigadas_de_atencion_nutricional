import json
from pathlib import Path

import numpy as np
import pytest

from brigadas.contratos import PesosObjetivo

RUTA_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def caso_pequeno():
    with open(RUTA_FIXTURES / "caso_pequeno.json", encoding="utf-8") as f:
        datos = json.load(f)
    datos["demanda"] = np.array(datos["demanda"], dtype=float)
    datos["distancias_km"] = np.array(datos["distancias_km"], dtype=float)
    datos["pesos"] = PesosObjetivo(**datos["pesos"])
    return datos


@pytest.fixture
def instancia_aleatoria():
    """Fábrica de instancias sintéticas reproducibles (puntos en un plano, km)."""

    def crear(n=7, semilla=0, escala_km=60.0):
        rng = np.random.default_rng(semilla)
        puntos = rng.uniform(0, escala_km, size=(n, 2))
        dist = np.sqrt(((puntos[:, None, :] - puntos[None, :, :]) ** 2).sum(-1))
        dist = (dist + dist.T) / 2
        np.fill_diagonal(dist, 0.0)
        demanda = rng.integers(0, 40, size=n).astype(float)
        return demanda, dist

    return crear
