import math

import numpy as np
import pytest

from brigadas.asignacion import evaluar_bases
from brigadas.escalabilidad import (
    Instancia,
    busqueda_aleatoria,
    busqueda_voraz,
    comparar_metodos,
    resumir_escalabilidad,
)
from brigadas.exacto import enumerar_optimo
from brigadas.genetico import ParametrosGenetico


def rng(s=0):
    return np.random.default_rng(s)


def test_aleatoria_respeta_el_presupuesto_y_devuelve_su_mejor_solucion(instancia_aleatoria):
    demanda, dist = instancia_aleatoria(n=15, semilla=1)
    r = busqueda_aleatoria(demanda, dist, 4, 30.0, 25.0, rng(2), evaluaciones=60)
    assert r.evaluaciones == 60
    assert len(set(r.bases)) == 4 and list(r.bases) == sorted(r.bases)
    assert r.objetivo == pytest.approx(evaluar_bases(demanda, dist, r.bases, 30.0, 25.0).objetivo)


def test_aleatoria_es_reproducible(instancia_aleatoria):
    demanda, dist = instancia_aleatoria(n=12, semilla=3)
    assert busqueda_aleatoria(demanda, dist, 3, 30.0, 25.0, rng(5), 40) == busqueda_aleatoria(
        demanda, dist, 3, 30.0, 25.0, rng(5), 40)


def test_aleatoria_con_presupuesto_mayor_al_espacio_lo_recorre_completo(instancia_aleatoria):
    demanda, dist = instancia_aleatoria(n=5, semilla=4)
    r = busqueda_aleatoria(demanda, dist, 2, 30.0, 25.0, rng(0), evaluaciones=50)
    assert r.evaluaciones == math.comb(5, 2)
    assert r.objetivo == pytest.approx(enumerar_optimo(demanda, dist, 2, 30.0, 25.0).objetivo)


def test_voraz_determinista_valido_y_nunca_mejor_que_el_optimo(instancia_aleatoria):
    for semilla in range(4):
        demanda, dist = instancia_aleatoria(n=9, semilla=semilla)
        a = busqueda_voraz(demanda, dist, 3, 30.0, 25.0)
        assert a == busqueda_voraz(demanda, dist, 3, 30.0, 25.0)
        assert len(set(a.bases)) == 3
        assert a.objetivo == pytest.approx(evaluar_bases(demanda, dist, a.bases, 30.0, 25.0).objetivo)
        assert a.objetivo >= enumerar_optimo(demanda, dist, 3, 30.0, 25.0).objetivo - 1e-12
        assert a.evaluaciones == 9 + 8 + 7


def test_comparar_metodos_parea_el_presupuesto_aleatorio_con_el_genetico(instancia_aleatoria):
    demanda, dist = instancia_aleatoria(n=12, semilla=6)
    optimo = enumerar_optimo(demanda, dist, 3, 30.0, 25.0).objetivo
    tabla = comparar_metodos(Instancia("prueba", demanda, dist, 3, 30.0, 25.0, optimo), semillas=range(3),
                             parametros=ParametrosGenetico(generaciones_max=15))
    assert len(tabla) == 2 + 2 * 3
    assert set(tabla["metodo"]) == {"base", "voraz", "aleatoria", "genetico"}
    ga = tabla[tabla["metodo"] == "genetico"].set_index("semilla")["evaluaciones"]
    al = tabla[tabla["metodo"] == "aleatoria"].set_index("semilla")["evaluaciones"]
    assert (ga == al).all()
    assert (tabla["objetivo"] >= optimo - 1e-12).all()
    assert tabla["cobertura_pct"].between(0, 100).all()


def test_resumen_usa_el_optimo_o_la_mejor_solucion_conocida(instancia_aleatoria):
    demanda, dist = instancia_aleatoria(n=12, semilla=7)
    sin_optimo = comparar_metodos(Instancia("x", demanda, dist, 3, 30.0, 25.0), semillas=range(4),
                                  parametros=ParametrosGenetico(generaciones_max=10))
    metodos, pareado = resumir_escalabilidad(sin_optimo)
    mejor = sin_optimo["objetivo"].min()
    assert metodos["referencia"].iloc[0] == pytest.approx(mejor)
    assert (metodos["brecha_media"] >= -1e-12).all()
    fila = pareado.iloc[0]
    assert fila["ic95_inferior_objetivo"] <= fila["diferencia_media_objetivo"] <= fila["ic95_superior_objetivo"]
