import itertools

import numpy as np
import pandas as pd
import pytest

from brigadas.genetico import ParametrosGenetico
from brigadas.tamizaje import (
    ProblemaTamizaje,
    buscar_exacto,
    buscar_genetico,
    buscar_voraz,
    estudio_tamizaje,
    tabla_decision_tamizaje,
)


def dos_municipios(objetivo="casos", capacidad=100.0):
    """Base posible en 0; el municipio 0 tiene tasa baja y el 1 tasa alta, ambos a 20 min."""
    ninos = np.array([100.0, 100.0])
    tasas = np.array([0.01, 0.05])
    tiempos = np.array([[0.0, 20.0], [20.0, 0.0]])
    return ProblemaTamizaje(ninos, tasas, tiempos, capacidad, 60.0, objetivo)


def test_capacidad_limita_los_ninos_evaluados():
    r = dos_municipios(capacidad=30.0).evaluar((0,))
    assert r.ninos_evaluados == pytest.approx(30.0)


def test_objetivo_casos_prioriza_la_tasa_alta():
    r = dos_municipios("casos").evaluar((0,))
    assert r.evaluados[1].sum() == pytest.approx(100.0)  # todo al municipio de tasa alta
    assert r.casos_identificados == pytest.approx(5.0)


def test_objetivo_ninos_desempata_por_cercania():
    r = dos_municipios("ninos").evaluar((0,))
    assert r.ninos_evaluados == pytest.approx(100.0)
    assert r.evaluados[0].sum() == pytest.approx(100.0)  # mismo número de niños; gana el municipio sin viaje


def test_respeta_el_tiempo_maximo():
    ninos = np.array([100.0, 100.0])
    p = ProblemaTamizaje(ninos, np.array([0.01, 0.05]), np.array([[0.0, 90.0], [90.0, 0.0]]), 500.0, 60.0, "casos")
    r = p.evaluar((0,))
    assert r.evaluados[1].sum() == pytest.approx(0.0)
    assert r.ninos_evaluados == pytest.approx(100.0)


def test_varias_brigadas_en_el_mismo_municipio_suman_capacidad():
    p = dos_municipios(capacidad=60.0)
    assert p.evaluar((0, 0)).ninos_evaluados == pytest.approx(120.0)
    assert p.evaluar((0,)).ninos_evaluados == pytest.approx(60.0)


def instancia(n=6, semilla=0):
    g = np.random.default_rng(semilla)
    puntos = g.uniform(0, 80, size=(n, 2))
    tiempos = np.sqrt(((puntos[:, None] - puntos[None]) ** 2).sum(-1))
    tiempos = (tiempos + tiempos.T) / 2
    np.fill_diagonal(tiempos, 0)
    return g.integers(500, 3000, size=n).astype(float), g.uniform(0.005, 0.05, size=n), tiempos


def test_exacto_coincide_con_fuerza_bruta_y_genetico_lo_alcanza():
    ninos, tasas, tiempos = instancia()
    p = ProblemaTamizaje(ninos, tasas, tiempos, 1500.0, 45.0, "casos")
    exacto = buscar_exacto(p, 3)
    bruto = min(itertools.combinations_with_replacement(range(6), 3), key=lambda b: (p.aptitud(b), b))
    assert exacto.bases == bruto
    ga = buscar_genetico(p, 3, semilla=0)
    assert ga.valor == pytest.approx(exacto.valor)


def test_voraz_devuelve_k_brigadas_y_nunca_supera_al_exacto():
    ninos, tasas, tiempos = instancia(semilla=1)
    p = ProblemaTamizaje(ninos, tasas, tiempos, 1200.0, 45.0, "casos")
    voraz = buscar_voraz(p, 4)
    assert len(voraz.bases) == 4
    assert voraz.valor >= buscar_exacto(p, 4).valor - 1e-9


def test_estudio_propone_el_mejor_plan_de_cada_configuracion():
    ninos, tasas, tiempos = instancia(semilla=2)
    casos = ninos * tasas
    planes = estudio_tamizaje(ninos, tasas, tasas * 0.9, casos, casos * 0.9, tiempos, ks=(1, 2, 3),
                              productividades=(10.0,), umbrales=(45.0,), dias=100, semillas=range(2), k_exacto=2,
                              parametros=ParametrosGenetico(generaciones_max=10))
    assert set(planes["metodo"]) == {"exacto", "voraz", "genetico"}
    assert planes[planes["k"] == 3]["metodo"].ne("exacto").all()  # sin exacto por encima de k_exacto
    for _, grupo in planes.groupby(["objetivo", "k", "productividad", "umbral_min"]):
        propuesto = grupo[grupo["propuesto"]]
        assert len(propuesto) == 1
        assert propuesto["valor"].iloc[0] <= grupo["valor"].min() + 1e-12
    assert planes["casos_pct"].between(0, 100).all() and planes["ninos_pct"].between(0, 100).all()


def test_planificar_usa_exacto_si_k_es_pequeno_y_el_mejor_metodo_si_no():
    from brigadas.tamizaje import planificar
    ninos, tasas, tiempos = instancia(semilla=3)
    p = ProblemaTamizaje(ninos, tasas, tiempos, 1000.0, 45.0, "casos")
    chico = planificar(p, 2, semillas=range(2), k_exacto=3)
    assert chico.metodo == "exacto" and chico.valor == pytest.approx(buscar_exacto(p, 2).valor)
    grande = planificar(p, 5, semillas=range(2), k_exacto=3, parametros=ParametrosGenetico(generaciones_max=10))
    assert grande.metodo in {"voraz", "genetico"}
    assert grande.valor <= buscar_voraz(p, 5).valor + 1e-12


def test_tabla_decision_menor_k_para_cada_meta():
    planes = pd.DataFrame({
        "objetivo": ["casos"] * 3, "propuesto": [True] * 3, "productividad": [27.5] * 3, "umbral_min": [60.0] * 3,
        "k": [1, 2, 3], "casos_pct": [30.0, 60.0, 85.0], "ninos_pct": [20.0, 45.0, 70.0],
        "casos_2023_pct": [32.0, 62.0, 86.0], "bases": ["0", "0-1", "0-1-2"], "metodo": ["exacto"] * 3,
    })
    decision = tabla_decision_tamizaje(planes, metas=(50, 80, 90)).set_index("meta_pct")
    assert decision.loc[50, "k_minimo"] == 2
    assert decision.loc[80, "k_minimo"] == 3
    assert pd.isna(decision.loc[90, "k_minimo"])
