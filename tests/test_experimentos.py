import numpy as np
import pandas as pd
import pytest

from brigadas.config import ConfiguracionEscenario
from brigadas.experimentos import CONDICIONES, configurar, ejecutar_experimentos, resumir_experimentos


def config_pequena(replicas=4):
    return ConfiguracionEscenario(
        departamento="GT20", anios_desarrollo=(2015, 2016), anios_validacion=(2023, 2024),
        cantidad_brigadas=2, capacidad_por_brigada=40, distancia_max_km=25.0, replicas=replicas, semilla_raiz=7,
    )


@pytest.fixture
def entradas(instancia_aleatoria):
    referencia, dist = instancia_aleatoria(n=7, semilla=2)
    referencia = referencia + 5.0
    mu = referencia * 1.1
    observados = {"observado_2023": referencia + 3.0, "observado_2024": referencia + 6.0}
    return referencia, mu, dist, observados


def test_condiciones_coinciden_con_el_diseno_congelado():
    resumen = [(c.nombre, c.escala, c.capacidad, c.distancia_max_km) for c in CONDICIONES]
    assert resumen == [
        ("nominal", 1.0, None, None),
        ("demanda_x1.2", 1.2, None, None),
        ("demanda_x1.6", 1.6, None, None),
        ("capacidad_177", 1.0, 177, None),
        ("dmax_40", 1.0, None, 40.0),
    ]


def test_configurar_solo_cambia_lo_indicado():
    base = config_pequena()
    assert configurar(base, CONDICIONES[0]) == base
    cap = configurar(base, CONDICIONES[3])
    assert cap.capacidad_por_brigada == 177 and cap.distancia_max_km == base.distancia_max_km
    dmax = configurar(base, CONDICIONES[4])
    assert dmax.distancia_max_km == 40.0 and dmax.capacidad_por_brigada == base.capacidad_por_brigada


def test_replicas_pareadas_entre_politicas_y_condiciones(entradas):
    referencia, mu, dist, observados = entradas
    r = ejecutar_experimentos(config_pequena(), referencia, mu, 0.116, dist, observados)
    tabla = pd.DataFrame([x.a_dict() for x in r.replicas])
    assert len(tabla) == len(CONDICIONES) * 4 * 2
    assert set(tabla["politica"]) == {"base", "genetico"}
    assert tabla["factible"].all()
    semillas = tabla.groupby(["escenario", "politica"])["semilla"].apply(tuple)
    assert semillas.nunique() == 1  # mismas semillas en todas las políticas y condiciones


def test_evalua_las_dos_politicas_con_los_casos_observados(entradas):
    referencia, mu, dist, observados = entradas
    r = ejecutar_experimentos(config_pequena(), referencia, mu, 0.116, dist, observados)
    pares = {(x.escenario, x.politica) for x in r.observado}
    assert pares == {(e, p) for e in observados for p in ("base", "genetico")}


def test_calidad_del_genetico_frente_al_optimo_exacto(entradas):
    referencia, mu, dist, observados = entradas
    r = ejecutar_experimentos(config_pequena(), referencia, mu, 0.116, dist, observados)
    assert len(r.calidad) == len(CONDICIONES) * 4
    assert (r.calidad["brecha"] >= -1e-9).all()  # nunca mejor que el óptimo
    assert r.calidad["alcanza_optimo"].dtype == bool
    assert set(r.convergencia.columns) == {"generacion", "mejor", "mediana"}


def test_es_reproducible_salvo_el_tiempo(entradas):
    referencia, mu, dist, observados = entradas
    a = ejecutar_experimentos(config_pequena(), referencia, mu, 0.116, dist, observados)
    b = ejecutar_experimentos(config_pequena(), referencia, mu, 0.116, dist, observados)
    ta = pd.DataFrame([x.a_dict() for x in a.replicas]).drop(columns="tiempo_ejecucion_ms")
    tb = pd.DataFrame([x.a_dict() for x in b.replicas]).drop(columns="tiempo_ejecucion_ms")
    pd.testing.assert_frame_equal(ta, tb)
    pd.testing.assert_frame_equal(a.calidad, b.calidad)


def test_resumen_por_condicion_con_diferencia_pareada(entradas):
    referencia, mu, dist, observados = entradas
    r = ejecutar_experimentos(config_pequena(), referencia, mu, 0.116, dist, observados)
    resumen = resumir_experimentos(r.replicas)
    assert list(resumen["condicion"]) == [c.nombre for c in CONDICIONES]
    for columna in ("cobertura_base_media", "cobertura_genetico_media", "diferencia_media_pp",
                    "ic95_inferior_pp", "ic95_superior_pp", "cambio_relativo_pct"):
        assert columna in resumen.columns
    fila = resumen.iloc[0]
    assert fila["ic95_inferior_pp"] <= fila["diferencia_media_pp"] <= fila["ic95_superior_pp"]
    assert np.isclose(fila["diferencia_media_pp"], fila["cobertura_genetico_media"] - fila["cobertura_base_media"])
