import math
from itertools import combinations

import numpy as np
import pytest

from brigadas.asignacion import evaluar_bases
from brigadas.baseline import crear_politica_base
from brigadas.exacto import calcular_gap, crear_politica_exacta, enumerar_optimo


def test_enumerador_encuentra_optimo_manual(caso_pequeno):
    esperado = caso_pequeno["solucion_esperada"]
    opt = enumerar_optimo(caso_pequeno["demanda"], caso_pequeno["distancias_km"], 2,
                          caso_pequeno["capacidad"], caso_pequeno["distancia_max_km"],
                          caso_pequeno["pesos"])
    assert opt.bases == tuple(esperado["bases_optimas"])
    assert opt.objetivo == pytest.approx(esperado["objetivo"])


@pytest.mark.parametrize("semilla", range(8))
def test_enumerador_es_minimo_de_todas_las_combinaciones(instancia_aleatoria, semilla):
    demanda, dist = instancia_aleatoria(n=6, semilla=semilla)
    opt = enumerar_optimo(demanda, dist, 2, 50, 20.0)
    todos = [evaluar_bases(demanda, dist, b, 50, 20.0).objetivo for b in combinations(range(6), 2)]
    assert opt.objetivo == pytest.approx(min(todos))


def test_optimo_no_es_peor_que_la_base(caso_pequeno):
    d, dist = caso_pequeno["demanda"], caso_pequeno["distancias_km"]
    base = crear_politica_base(d)(d, dist, 2, 100, 5, np.random.default_rng(0))
    opt = enumerar_optimo(d, dist, 2, 100, 5)
    assert opt.objetivo <= base.objetivo


def test_limite_de_combinaciones():
    n = 30
    dist = np.zeros((n, n))
    with pytest.raises(ValueError, match="instancias pequeñas"):
        enumerar_optimo(np.ones(n), dist, 10, 5, 1.0, max_combinaciones=1000)


def test_k_invalido(caso_pequeno):
    with pytest.raises(ValueError):
        enumerar_optimo(caso_pequeno["demanda"], caso_pequeno["distancias_km"], 0, 10, 5)
    with pytest.raises(ValueError):
        enumerar_optimo(caso_pequeno["demanda"], caso_pequeno["distancias_km"], 6, 10, 5)


def test_gap():
    assert calcular_gap(1.1, 1.0) == pytest.approx(0.1)
    assert calcular_gap(1.0, 1.0) == 0.0
    assert calcular_gap(0.0, 0.0) == 0.0
    assert math.isinf(calcular_gap(0.2, 0.0))
    with pytest.raises(ValueError):
        calcular_gap(math.nan, 1.0)


def test_politica_exacta_con_referencia(caso_pequeno):
    politica = crear_politica_exacta(caso_pequeno["demanda"], caso_pequeno["pesos"])
    res = politica(caso_pequeno["demanda"], caso_pequeno["distancias_km"], 2, 100, 5, np.random.default_rng(0))
    assert res.bases == (0, 4)
