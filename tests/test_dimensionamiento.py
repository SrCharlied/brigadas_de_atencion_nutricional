import itertools
import json

import numpy as np
import pandas as pd
import pytest

from brigadas.asignacion import evaluar_bases
from brigadas.dimensionamiento import (
    asignar_divisible,
    cobertura_vulnerabilidad,
    estudio,
    evaluar_plan,
    matriz_tiempos,
    optimo_cobertura,
    optimo_vulnerabilidad,
    tabla_decision,
    verificar_divisible,
)
from brigadas.exacto import enumerar_optimo


def escribir_osrm(tmp_path, codigos, segundos):
    ruta = tmp_path / "osrm.json"
    ruta.write_text(json.dumps({"codigos": codigos, "respuesta": {"code": "Ok", "durations": segundos}}), encoding="utf-8")
    return ruta


def test_matriz_tiempos_en_minutos_simetrica_y_ordenada(tmp_path):
    ruta = escribir_osrm(tmp_path, ["B", "A"], [[0, 600], [660, 0]])
    m = matriz_tiempos(ruta, ["A", "B"])
    assert m.shape == (2, 2)
    assert m[0, 1] == m[1, 0] == pytest.approx(10.5)  # promedio de 10 y 11 minutos
    assert m[0, 0] == m[1, 1] == 0


def test_matriz_tiempos_rechaza_codigos_faltantes(tmp_path):
    ruta = escribir_osrm(tmp_path, ["A", "B"], [[0, 60], [60, 0]])
    with pytest.raises(ValueError, match="C"):
        matriz_tiempos(ruta, ["A", "C"])


def test_cobertura_vulnerabilidad_a_mano():
    demanda = np.array([10.0, 10.0])
    dist = np.array([[0.0, 100.0], [100.0, 0.0]])
    resultado = evaluar_bases(demanda, dist, (0,), 15.0, 5.0)  # cubre 10 del municipio 0 y nada del 1
    assert cobertura_vulnerabilidad(resultado, demanda, np.array([1.0, 3.0])) == pytest.approx(1 / 4)


def caso_conflicto():
    """Municipio 0: muchos casos y tasa baja. Municipio 2: pocos casos y tasa muy alta."""
    demanda = np.array([50.0, 5.0, 8.0, 6.0])
    dist = np.array([[0, 10, 80, 80], [10, 0, 80, 80], [80, 80, 0, 10], [80, 80, 10, 0]], dtype=float)
    tasas = np.array([5.0, 6.0, 60.0, 40.0])
    return demanda, dist, tasas


def test_optimo_vulnerabilidad_coincide_con_fuerza_bruta_y_prioriza_tasa_alta():
    demanda, dist, tasas = caso_conflicto()
    resultado = optimo_vulnerabilidad(demanda, dist, 1, 60.0, 20.0, tasas)
    mejor = max(itertools.combinations(range(4), 1),
                key=lambda b: cobertura_vulnerabilidad(evaluar_bases(demanda, dist, b, 60.0, 20.0), demanda, tasas))
    assert resultado.bases in {(2,), (3,)} and set(mejor) <= {2, 3}
    assert cobertura_vulnerabilidad(resultado, demanda, tasas) == pytest.approx(
        cobertura_vulnerabilidad(evaluar_bases(demanda, dist, mejor, 60.0, 20.0), demanda, tasas))


def test_evaluar_plan_coberturas_e_intervalo():
    demanda, dist, tasas = caso_conflicto()
    escenarios = {"casos_2024": demanda, "casos_2023": demanda * 0.8}
    r = evaluar_plan((0, 2), escenarios, dist, 30.0, 20.0, tasas, demanda, 0.116, range(10))
    esperado = evaluar_bases(demanda, dist, (0, 2), 30.0, 20.0).demanda_cubierta.sum() / demanda.sum() * 100
    assert r["cobertura_casos_2024_pct"] == pytest.approx(esperado)
    assert r["sim_ic95_inferior_pct"] <= r["sim_cobertura_media_pct"] <= r["sim_ic95_superior_pct"]
    assert 0 <= r["vulnerabilidad_pct"] <= 100
    assert r == evaluar_plan((0, 2), escenarios, dist, 30.0, 20.0, tasas, demanda, 0.116, range(10))


def test_estudio_tres_enfoques_y_garantias_de_optimalidad():
    demanda, dist, tasas = caso_conflicto()
    planes = estudio(demanda, demanda * 0.8, dist, tasas, ks=(1, 2), capacidades=(30.0, 60.0), umbrales=(20.0,),
                     a=0.116, semilla_raiz=1, replicas=5)
    assert len(planes) == 2 * 2 * 1 * 3
    for _, grupo in planes.groupby(["k", "capacidad", "umbral_min"]):
        por_enfoque = grupo.set_index("enfoque")
        assert por_enfoque.loc["cobertura", "objetivo_2024"] <= por_enfoque["objetivo_2024"].min() + 1e-12
        assert por_enfoque.loc["vulnerabilidad", "vulnerabilidad_pct"] >= por_enfoque["vulnerabilidad_pct"].max() - 1e-9


# --- variante divisible (desviación registrada en docs/estudio_dimensionamiento.md) ------------


def municipio_grande():
    """Municipio 0 con 338 casos y dos bases posibles a su alcance (0 y 1) de 221 cada una."""
    demanda = np.array([338.0, 10.0, 20.0])
    tiempos = np.array([[0, 30, 100], [30, 0, 100], [100, 100, 0]], dtype=float)
    return demanda, tiempos


def test_divisible_reparte_un_municipio_grande_entre_brigadas():
    demanda, tiempos = municipio_grande()
    rigida = evaluar_bases(demanda, tiempos, (0, 1), 221.0, 60.0)
    divisible = asignar_divisible(demanda, tiempos, (0, 1), 221.0, 60.0)
    assert rigida.demanda_cubierta[0] == pytest.approx(221.0)
    assert divisible.demanda_cubierta[0] == pytest.approx(338.0)
    assert divisible.flujos[0].tolist() == pytest.approx([221.0, 117.0])  # primero la base más cercana
    assert divisible.demanda_cubierta[1] == pytest.approx(10.0)  # usa lo que queda de la segunda brigada
    assert divisible.es_factible


def test_divisible_respeta_capacidad_umbral_y_demanda(instancia_aleatoria):
    for semilla in range(6):
        demanda, tiempos = instancia_aleatoria(n=9, semilla=semilla)
        r = asignar_divisible(demanda, tiempos, (0, 3, 6), 25.0, 22.0)
        assert verificar_divisible(r, demanda, tiempos, 25.0, 22.0) == []
        assert np.all(r.carga_por_brigada <= 25.0 + 1e-9)
        assert np.all(r.demanda_cubierta <= demanda + 1e-9)
        lejos = tiempos[:, list(r.bases)] > 22.0
        assert np.all(r.flujos[lejos] == 0)


def test_verificador_divisible_detecta_violaciones():
    demanda, tiempos = municipio_grande()
    r = asignar_divisible(demanda, tiempos, (0, 1), 221.0, 60.0)
    assert verificar_divisible(r, demanda, tiempos, 200.0, 60.0)  # capacidad menor a la usada


def test_divisible_objetivo_con_la_formula_del_modelo():
    demanda, tiempos = municipio_grande()
    r = asignar_divisible(demanda, tiempos, (0, 1), 221.0, 60.0)
    cubierto = 338 + 10
    cobertura = cubierto / 368
    distancia = (221 * 0 + 117 * 30 + 10 * 0) / cubierto
    esperado = 1.0 * (1 - cobertura) + 0.1 * (distancia / 60.0) + 0.1 * (1 - 0.0)  # municipio 2 sin cubrir
    assert r.objetivo == pytest.approx(esperado)


def test_optimo_cobertura_rigido_coincide_con_el_enumerador_del_modelo(instancia_aleatoria):
    demanda, tiempos = instancia_aleatoria(n=8, semilla=2)
    propio = optimo_cobertura(demanda, tiempos, 3, 40.0, 25.0, asignacion="rigida")
    assert propio.bases == enumerar_optimo(demanda, tiempos, 3, 40.0, 25.0).bases


def test_estudio_divisible_supera_el_techo_rigido():
    demanda, tiempos = municipio_grande()
    tasas = np.array([10.0, 10.0, 10.0])
    kwargs = dict(ks=(2,), capacidades=(221.0,), umbrales=(60.0,), a=0.116, semilla_raiz=1, replicas=5)
    rigida = estudio(demanda, demanda, tiempos, tasas, asignacion="rigida", **kwargs)
    divisible = estudio(demanda, demanda, tiempos, tasas, asignacion="divisible", **kwargs)
    mejor = lambda t: t[t["enfoque"] == "cobertura"]["cobertura_casos_2024_pct"].iloc[0]  # noqa: E731
    assert mejor(divisible) > mejor(rigida)
    assert set(divisible["asignacion"]) == {"divisible"}


def test_tabla_decision_menor_k_que_alcanza_la_meta():
    planes = pd.DataFrame({
        "enfoque": ["cobertura"] * 3, "capacidad": [221.0] * 3, "umbral_min": [60.0] * 3, "k": [1, 2, 3],
        "cobertura_casos_2024_pct": [50.0, 85.0, 96.0], "cobertura_casos_2023_pct": [55.0, 90.0, 99.0],
        "sim_cobertura_media_pct": [52.0, 86.0, 95.0], "bases": ["0", "0-1", "0-1-2"],
    })
    decision = tabla_decision(planes, metas=(80, 90, 99)).set_index("meta_pct")
    assert decision.loc[80, "k_minimo"] == 2
    assert decision.loc[90, "k_minimo"] == 3
    assert pd.isna(decision.loc[99, "k_minimo"])
