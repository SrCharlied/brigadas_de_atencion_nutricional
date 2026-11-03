import math
from itertools import combinations

import numpy as np
import pytest

from brigadas.asignacion import (
    asignar_capacitado,
    calcular_indicadores,
    evaluar_bases,
    validar_bases,
    verificar_resultado,
)
from brigadas.contratos import PesosObjetivo, ResultadoAsignacion


def indicadores(res, demanda, dist, capacidad):
    return calcular_indicadores(res, demanda, dist, capacidad)


# --- 7.2 (1) demanda cero -------------------------------------------------

def test_demanda_cero_cobertura_definida_sin_division_invalida(caso_pequeno):
    d = np.zeros(5)
    res = evaluar_bases(d, caso_pequeno["distancias_km"], (0, 4), 100, 5)
    ind = indicadores(res, d, caso_pequeno["distancias_km"], 100)
    assert ind.cobertura == 1.0
    assert ind.demanda_no_cubierta == 0.0
    assert math.isnan(ind.distancia_media_km)
    assert math.isfinite(res.objetivo)
    assert res.asignaciones == (None,) * 5


# --- 7.2 (2) capacidad suficiente y sin límite de distancia ---------------

def test_capacidad_suficiente_y_distancia_infinita_cubre_todo(caso_pequeno):
    d = caso_pequeno["demanda"]
    res = evaluar_bases(d, caso_pequeno["distancias_km"], (2,), d.sum(), math.inf)
    ind = indicadores(res, d, caso_pequeno["distancias_km"], d.sum())
    assert ind.cobertura == 1.0
    assert all(a == 0 for a in res.asignaciones)


# --- 7.2 (3) capacidad cero -----------------------------------------------

def test_capacidad_cero_cobertura_cero(caso_pequeno):
    d = caso_pequeno["demanda"]
    res = evaluar_bases(d, caso_pequeno["distancias_km"], (0, 4), 0, math.inf)
    ind = indicadores(res, d, caso_pequeno["distancias_km"], 0)
    assert ind.cobertura == 0.0
    assert res.es_factible
    assert all(math.isnan(u) for u in ind.utilizacion_por_brigada)


def test_distancia_max_cero_solo_cubre_los_municipios_base(caso_pequeno):
    d = caso_pequeno["demanda"]
    res = evaluar_bases(d, caso_pequeno["distancias_km"], (0, 4), 100, 0.0)
    assert res.total_cubierto == d[0] + d[4]
    assert res.asignaciones == (0, None, None, None, 1)


# --- 7.2 (4) monotonía de la mejor cobertura respecto a la capacidad -------

@pytest.mark.parametrize("semilla", range(15))
def test_aumentar_capacidad_no_reduce_mejor_cobertura(instancia_aleatoria, semilla):
    demanda, dist = instancia_aleatoria(n=6, semilla=semilla)
    k, dmax = 2, 25.0

    def mejor_cobertura(capacidad):
        return max(
            evaluar_bases(demanda, dist, bases, capacidad, dmax).total_cubierto
            for bases in combinations(range(6), k)
        )

    capacidades = [0, 10, 25, 40, 60, 100, 1000]
    coberturas = [mejor_cobertura(c) for c in capacidades]
    assert all(b >= a - 1e-9 for a, b in zip(coberturas, coberturas[1:]))


# --- 7.2 (5) y (6) capacidad y asignación única ---------------------------

@pytest.mark.parametrize("semilla", range(20))
def test_ninguna_brigada_excede_capacidad_ni_se_crea_demanda(instancia_aleatoria, semilla):
    demanda, dist = instancia_aleatoria(n=8, semilla=semilla)
    rng = np.random.default_rng(semilla)
    bases = tuple(int(b) for b in rng.choice(8, size=3, replace=False))
    capacidad = float(rng.integers(0, 80))
    res = evaluar_bases(demanda, dist, bases, capacidad, 30.0)
    assert np.all(res.carga_por_brigada <= capacidad + 1e-9)
    assert np.all(res.demanda_cubierta <= demanda + 1e-9)
    assert np.all(res.demanda_cubierta >= 0)
    # Cada municipio aparece como máximo una vez: asignaciones es un único índice o None.
    assert len(res.asignaciones) == 8
    assert all(a is None or 0 <= a < 3 for a in res.asignaciones)
    assert res.es_factible
    assert verificar_resultado(res, demanda, dist, capacidad, 30.0) == []


def test_capacidad_vinculante_cobertura_parcial():
    # Dos municipios cerca de una única base con capacidad 15.
    dist = np.array([[0, 1], [1, 0]], dtype=float)
    d = np.array([10.0, 8.0])
    asign, cubierta, carga = asignar_capacitado(d, dist, (0,), 15, 5)
    # Se procesa primero la mayor demanda (10, completa) y luego 5 de 8.
    assert cubierta.tolist() == [10.0, 5.0]
    assert carga.tolist() == [15.0]
    assert asign == (0, 0)


def test_prefiere_base_cercana_con_capacidad_completa():
    # Municipio 2 equidistante? No: más cerca de base 0, pero base 0 sin capacidad suficiente.
    dist = np.array([[0, 10, 2], [10, 0, 3], [2, 3, 0]], dtype=float)
    d = np.array([8.0, 0.0, 5.0])
    asign, cubierta, _ = asignar_capacitado(d, dist, (0, 1), 10, 5)
    # Municipio 0 (demanda 8) toma la base 0 -> restante 2. Municipio 2 no cabe
    # completo en base 0, pero sí en base 1 (3 km): debe ir a la brigada 1.
    assert asign[2] == 1
    assert cubierta.tolist() == [8.0, 0.0, 5.0]


def test_respeta_distancia_maxima(caso_pequeno):
    res = evaluar_bases(caso_pequeno["demanda"], caso_pequeno["distancias_km"], (0, 4), 100, 5)
    for i, b in enumerate(res.asignaciones):
        if b is not None:
            assert caso_pequeno["distancias_km"][i, res.bases[b]] <= 5


# --- 7.2 (7) bases válidas -----------------------------------------------

@pytest.mark.parametrize(
    "bases, k, error",
    [
        ((0, 0), 2, ValueError),       # duplicadas
        ((0, 9), 2, ValueError),       # fuera de rango
        ((0,), 2, ValueError),         # cantidad incorrecta
        ((), 0, ValueError),           # K = 0
        (tuple(range(6)), 6, ValueError),  # K > municipios
        ((0.5, 1), 2, TypeError),      # no entero
    ],
)
def test_validar_bases_rechaza(bases, k, error):
    with pytest.raises(error):
        validar_bases(bases, 5, k)


def test_evaluar_bases_rechaza_duplicadas(caso_pequeno):
    with pytest.raises(ValueError, match="duplicados"):
        evaluar_bases(caso_pequeno["demanda"], caso_pequeno["distancias_km"], (1, 1), 100, 5)


# --- entradas inválidas ---------------------------------------------------

@pytest.mark.parametrize(
    "demanda",
    [np.array([1.0, -1.0, 0, 0, 0]), np.array([1.0, np.nan, 0, 0, 0]), np.array([1.0, 2.0])],
)
def test_demanda_invalida(caso_pequeno, demanda):
    with pytest.raises(ValueError):
        evaluar_bases(demanda, caso_pequeno["distancias_km"], (0, 1), 10, 5)


def test_capacidad_negativa_rechazada(caso_pequeno):
    with pytest.raises(ValueError):
        evaluar_bases(caso_pequeno["demanda"], caso_pequeno["distancias_km"], (0, 1), -1, 5)


# --- 7.2 (10) rangos y unidades -------------------------------------------

@pytest.mark.parametrize("semilla", range(10))
def test_metricas_en_rango(instancia_aleatoria, semilla):
    demanda, dist = instancia_aleatoria(n=7, semilla=semilla)
    res = evaluar_bases(demanda, dist, (0, 3, 5), 40, 20.0)
    ind = indicadores(res, demanda, dist, 40)
    assert 0.0 <= ind.cobertura <= 1.0
    assert 0.0 <= ind.peor_cobertura_municipal <= 1.0
    assert ind.demanda_no_cubierta == pytest.approx(demanda.sum() - res.total_cubierto)
    if not math.isnan(ind.distancia_media_km):
        assert 0.0 <= ind.distancia_media_km <= 20.0 + 1e-9
        assert 0.0 <= ind.distancia_p90_km <= 20.0 + 1e-9
    assert all(0.0 <= u <= 1.0 + 1e-9 for u in ind.utilizacion_por_brigada)
    # J tiene tres términos acotados en [0, 1] multiplicados por los pesos por defecto.
    assert 0.0 <= res.objetivo <= 1.0 + 0.1 + 0.1


def test_caso_pequeno_valores_manuales(caso_pequeno):
    esperado = caso_pequeno["solucion_esperada"]
    res = evaluar_bases(
        caso_pequeno["demanda"], caso_pequeno["distancias_km"], esperado["bases_optimas"],
        caso_pequeno["capacidad"], caso_pequeno["distancia_max_km"], caso_pequeno["pesos"],
    )
    ind = indicadores(res, caso_pequeno["demanda"], caso_pequeno["distancias_km"], caso_pequeno["capacidad"])
    assert res.total_cubierto == esperado["demanda_cubierta"]
    assert ind.cobertura == pytest.approx(esperado["cobertura"])
    assert ind.distancia_media_km == pytest.approx(esperado["distancia_media_km"])
    assert ind.peor_cobertura_municipal == 0.0
    assert res.objetivo == pytest.approx(esperado["objetivo"])


def test_pesos_cambian_el_objetivo(caso_pequeno):
    args = (caso_pequeno["demanda"], caso_pequeno["distancias_km"], (0, 4), 100, 5)
    j1 = evaluar_bases(*args, PesosObjetivo(1.0, 0.0, 0.0)).objetivo
    j2 = evaluar_bases(*args, PesosObjetivo(1.0, 1.0, 0.0)).objetivo
    assert j1 == pytest.approx(10 / 42)
    assert j2 > j1


# --- verificador independiente detecta violaciones ------------------------

def test_verificador_detecta_exceso_de_capacidad(caso_pequeno):
    d, dist = caso_pequeno["demanda"], caso_pequeno["distancias_km"]
    trampa = ResultadoAsignacion(
        bases=(0, 4),
        asignaciones=(0, 0, None, 1, 1),
        demanda_cubierta=np.array([10.0, 6.0, 0.0, 6.0, 10.0]),
        carga_por_brigada=np.array([16.0, 16.0]),
        objetivo=0.0,
        es_factible=True,
    )
    assert verificar_resultado(trampa, d, dist, 100, 5) == []
    assert any("capacidad" in e for e in verificar_resultado(trampa, d, dist, 10, 5))


def test_verificador_detecta_distancia_y_demanda_inventada(caso_pequeno):
    d, dist = caso_pequeno["demanda"], caso_pequeno["distancias_km"]
    trampa = ResultadoAsignacion(
        bases=(0, 4),
        asignaciones=(0, 0, 0, 1, 1),
        demanda_cubierta=np.array([10.0, 6.0, 10.0, 6.0, 99.0]),
        carga_por_brigada=np.array([26.0, 105.0]),
        objetivo=0.0,
        es_factible=True,
    )
    errores = verificar_resultado(trampa, d, dist, 1000, 5)
    assert any("D_max" in e for e in errores)
    assert any("más de su demanda" in e for e in errores)
