import numpy as np
import pytest

from brigadas.asignacion import evaluar_bases
from brigadas.exacto import enumerar_optimo
from brigadas.genetico import (
    ParametrosGenetico,
    crear_politica_genetica,
    cruzar,
    ejecutar_genetico,
    mutar,
)


def rng(semilla=0):
    return np.random.default_rng(semilla)


# --- operadores ---------------------------------------------------------------


def test_cruce_produce_k_genes_distintos_de_la_union_de_los_padres():
    g = rng(1)
    for _ in range(200):
        hijo = cruzar((0, 2, 5), (1, 2, 7), 3, g)
        assert len(hijo) == 3
        assert len(set(hijo)) == 3
        assert set(hijo) <= {0, 1, 2, 5, 7}
        assert list(hijo) == sorted(hijo)


def test_mutacion_cambia_exactamente_un_gen_por_uno_que_no_era_base():
    g = rng(2)
    for _ in range(200):
        hijo = mutar((0, 3, 6), 10, g)
        assert len(set(hijo)) == 3
        assert len(set(hijo) - {0, 3, 6}) == 1
        assert all(0 <= b < 10 for b in hijo)
        assert list(hijo) == sorted(hijo)


def test_mutacion_sin_candidatos_devuelve_el_mismo_individuo():
    assert mutar((0, 1, 2), 3, rng()) == (0, 1, 2)


# --- búsqueda -----------------------------------------------------------------


def test_encuentra_el_optimo_del_caso_conocido(caso_pequeno):
    c = caso_pequeno
    resultado = ejecutar_genetico(c["demanda"], c["distancias_km"], c["cantidad_brigadas"], c["capacidad"],
                                  c["distancia_max_km"], rng(0), pesos=c["pesos"])
    assert resultado.bases == tuple(c["solucion_esperada"]["bases_optimas"])
    assert resultado.objetivo == pytest.approx(c["solucion_esperada"]["objetivo"])


@pytest.mark.parametrize("semilla", range(5))
def test_alcanza_el_optimo_exacto_en_instancias_pequenas(instancia_aleatoria, semilla):
    demanda, dist = instancia_aleatoria(n=9, semilla=semilla)
    optimo = enumerar_optimo(demanda, dist, 3, 40.0, 25.0)
    resultado = ejecutar_genetico(demanda, dist, 3, 40.0, 25.0, rng(semilla))
    assert resultado.objetivo == pytest.approx(optimo.objetivo)


def test_es_reproducible_con_la_misma_semilla(instancia_aleatoria):
    demanda, dist = instancia_aleatoria(n=10, semilla=3)
    a = ejecutar_genetico(demanda, dist, 3, 40.0, 25.0, rng(11))
    b = ejecutar_genetico(demanda, dist, 3, 40.0, 25.0, rng(11))
    assert a == b


def test_historial_del_mejor_nunca_empeora_gracias_al_elitismo(instancia_aleatoria):
    demanda, dist = instancia_aleatoria(n=12, semilla=4)
    resultado = ejecutar_genetico(demanda, dist, 4, 30.0, 25.0, rng(5))
    mejores = np.array(resultado.historial_mejor)
    assert np.all(np.diff(mejores) <= 1e-12)
    assert len(resultado.historial_mejor) == len(resultado.historial_mediana) == resultado.generaciones + 1
    assert resultado.objetivo == pytest.approx(mejores[-1])


def test_se_detiene_por_estancamiento_antes_del_maximo(caso_pequeno):
    c = caso_pequeno
    parametros = ParametrosGenetico(generaciones_max=500, generaciones_sin_mejora=5)
    resultado = ejecutar_genetico(c["demanda"], c["distancias_km"], 2, 100.0, 5.0, rng(0), parametros)
    assert resultado.generaciones < 500


def test_devuelve_k_bases_validas_y_distintas(instancia_aleatoria):
    demanda, dist = instancia_aleatoria(n=11, semilla=6)
    resultado = ejecutar_genetico(demanda, dist, 3, 40.0, 22.0, rng(7))
    assert len(resultado.bases) == len(set(resultado.bases)) == 3
    assert all(0 <= b < 11 for b in resultado.bases)


def test_k_igual_al_numero_de_municipios():
    demanda = np.array([5.0, 3.0, 2.0])
    dist = np.array([[0, 1, 2], [1, 0, 1], [2, 1, 0]], dtype=float)
    assert ejecutar_genetico(demanda, dist, 3, 10.0, 5.0, rng()).bases == (0, 1, 2)


def test_rechaza_k_mayor_que_municipios():
    demanda = np.array([5.0, 3.0])
    dist = np.array([[0, 1], [1, 0]], dtype=float)
    with pytest.raises(ValueError):
        ejecutar_genetico(demanda, dist, 3, 10.0, 5.0, rng())


@pytest.mark.parametrize(
    "cambios",
    [{"poblacion": 1}, {"elitismo": 40}, {"torneo": 0}, {"prob_cruce": 1.5}, {"prob_mutacion": -0.1},
     {"generaciones_max": 0}, {"generaciones_sin_mejora": 0}],
)
def test_parametros_invalidos(cambios):
    with pytest.raises(ValueError):
        ParametrosGenetico(**cambios)


def test_parametros_por_defecto_coinciden_con_el_diseno_congelado():
    p = ParametrosGenetico()
    assert (p.poblacion, p.generaciones_max, p.generaciones_sin_mejora, p.torneo, p.prob_cruce,
            p.prob_mutacion, p.elitismo) == (40, 100, 20, 3, 0.9, 0.3, 2)


# --- política -----------------------------------------------------------------


def test_politica_decide_con_la_referencia_y_evalua_con_la_demanda_de_la_replica(instancia_aleatoria):
    referencia, dist = instancia_aleatoria(n=9, semilla=8)
    replica = referencia[::-1].copy()  # demanda distinta a la de referencia
    politica = crear_politica_genetica(referencia)
    resultado = politica(replica, dist, 3, 40.0, 25.0, rng(9))

    esperado = ejecutar_genetico(referencia, dist, 3, 40.0, 25.0, rng(9))
    assert resultado.bases == esperado.bases
    evaluado = evaluar_bases(replica, dist, esperado.bases, 40.0, 25.0)
    assert resultado.objetivo == pytest.approx(evaluado.objetivo)
    assert resultado.es_factible


def test_politica_rechaza_tamanos_distintos():
    politica = crear_politica_genetica(np.array([1.0, 2.0, 3.0]))
    dist = np.zeros((2, 2))
    with pytest.raises(ValueError):
        politica(np.array([1.0, 2.0]), dist, 1, 10.0, 5.0, rng())
