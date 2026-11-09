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


def test_secuencia_aleatoria_del_modo_por_defecto_no_cambia(instancia_aleatoria):
    """Regresión: los resultados publicados dependen del orden exacto de los sorteos."""
    demanda, dist = instancia_aleatoria(n=10, semilla=0)
    r = ejecutar_genetico(demanda, dist, 3, 40.0, 25.0, rng(11))
    assert (r.bases, r.generaciones, r.evaluaciones) == ((5, 8, 9), 21, 72)
    assert r.objetivo == pytest.approx(0.19860243424222232, rel=1e-12)


# --- modo con repetición y aptitud externa (estudio de tamizaje) ----------------------


def test_cruce_con_repeticion_conserva_k_genes_de_los_padres():
    g = rng(3)
    for _ in range(200):
        hijo = cruzar((0, 0, 4), (0, 2, 2), 3, g, con_repeticion=True)
        assert len(hijo) == 3 and list(hijo) == sorted(hijo)
        # Cada gen aparece como máximo tantas veces como entre los dos padres juntos.
        assert all(hijo.count(v) <= (0, 0, 4, 0, 2, 2).count(v) for v in set(hijo))


def test_mutacion_con_repeticion_cambia_un_gen_y_permite_repetidos():
    g = rng(4)
    vistos_repetidos = False
    for _ in range(300):
        hijo = mutar((1, 1, 3), 4, g, con_repeticion=True)
        assert len(hijo) == 3 and list(hijo) == sorted(hijo)
        assert sum(abs(hijo.count(v) - (1, 1, 3).count(v)) for v in range(4)) == 2  # un gen cambió
        vistos_repetidos |= len(set(hijo)) < 3
    assert vistos_repetidos


def aptitud_rendimientos_decrecientes(demanda, capacidad):
    """Aptitud a minimizar: −Σ min(brigadas_i · capacidad, demanda_i)."""
    def aptitud(individuo):
        conteo = np.bincount(np.asarray(individuo, dtype=int), minlength=len(demanda))
        return -float(np.minimum(conteo * capacidad, demanda).sum())
    return aptitud


def test_con_repeticion_y_aptitud_externa_alcanza_el_optimo_por_fuerza_bruta():
    import itertools
    demanda = np.array([30.0, 12.0, 25.0, 5.0, 18.0])
    aptitud = aptitud_rendimientos_decrecientes(demanda, 10.0)
    optimo = min(aptitud(b) for b in itertools.combinations_with_replacement(range(5), 6))
    dist = np.zeros((5, 5))
    resultado = ejecutar_genetico(demanda, dist, 6, 10.0, 1.0, rng(0), aptitud=aptitud, con_repeticion=True)
    assert resultado.objetivo == pytest.approx(optimo)
    assert len(resultado.bases) == 6 and len(set(resultado.bases)) < 6  # varias brigadas comparten municipio


def test_con_repeticion_permite_mas_brigadas_que_municipios():
    demanda = np.array([30.0, 12.0])
    resultado = ejecutar_genetico(demanda, np.zeros((2, 2)), 4, 10.0, 1.0, rng(1),
                                  aptitud=aptitud_rendimientos_decrecientes(demanda, 10.0), con_repeticion=True)
    assert resultado.objetivo == pytest.approx(-40.0)  # 3 brigadas en el municipio 0 (30) y 1 en el 1 (10)
    assert resultado.bases == (0, 0, 0, 1)


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
