import numpy as np
import pandas as pd
import pytest

from brigadas import demanda
from brigadas.datos import ErrorDatos


def panel_sintetico(alfas, beta, anios, poblacion=10_000, rng=None, centro=None):
    """Panel con casos esperados exactos (sin ruido) o simulados con Poisson si se da rng."""
    centro = np.mean(anios) if centro is None else centro
    filas = []
    for i, alfa in enumerate(alfas):
        for anio in anios:
            mu = np.exp(alfa + beta * (anio - centro)) * poblacion
            casos = rng.poisson(mu) if rng is not None else mu
            filas.append({"codigo": f"M{i}", "anio": anio, "casos_registrados": casos, "poblacion_0_4": poblacion})
    return pd.DataFrame(filas)


def tabla(filas):
    return pd.DataFrame(filas, columns=["codigo", "anio", "casos_registrados", "poblacion_0_4"])


# --- modelos de media ---------------------------------------------------------


def test_m0_usa_tasa_agregada_no_promedio_de_tasas():
    datos = tabla([("A", 2015, 10, 1000), ("A", 2016, 30, 3000), ("B", 2015, 5, 500), ("B", 2016, 5, 500)])
    modelo = demanda.ajustar(datos, "M0", [2015, 2016])
    # A: 40 / 4000 = 0.01 (el promedio simple de tasas también da 0.01; B confirma el cálculo)
    pob = tabla([("A", 2017, None, 2000), ("B", 2017, None, 1000)])
    mu = modelo.media(pob).set_index("codigo")["mu"]
    assert mu["A"] == pytest.approx(20.0)
    assert mu["B"] == pytest.approx(10.0)


def test_m0_pondera_por_poblacion():
    datos = tabla([("A", 2015, 10, 1000), ("A", 2016, 90, 3000)])
    modelo = demanda.ajustar(datos, "M0", [2015, 2016])
    # tasa agregada 100/4000 = 0.025, no (0.01 + 0.03)/2 = 0.02
    mu = modelo.media(tabla([("A", 2017, None, 1000)]))["mu"].iloc[0]
    assert mu == pytest.approx(25.0)


def test_m1_usa_solo_los_tres_ultimos_anios_de_entrenamiento():
    datos = tabla([("A", a, c, 1000) for a, c in [(2015, 100), (2016, 10), (2017, 20), (2018, 30)]])
    modelo = demanda.ajustar(datos, "M1", [2015, 2016, 2017, 2018])
    mu = modelo.media(tabla([("A", 2019, None, 1000)]))["mu"].iloc[0]
    assert mu == pytest.approx(20.0)  # (10 + 20 + 30) / 3000 * 1000


def test_m2_recupera_tendencia_sin_ruido():
    anios = list(range(2015, 2023))
    datos = panel_sintetico(alfas=[np.log(0.01), np.log(0.02)], beta=0.1, anios=anios)
    modelo = demanda.ajustar(datos, "M2", anios)
    assert modelo.beta == pytest.approx(0.1, abs=1e-8)
    futuro = panel_sintetico(alfas=[np.log(0.01), np.log(0.02)], beta=0.1, anios=[2024], centro=np.mean(anios))
    mu = modelo.media(futuro.drop(columns="casos_registrados"))
    assert mu["mu"].to_numpy() == pytest.approx(futuro["casos_registrados"].to_numpy(), rel=1e-8)


def test_m2_cumple_ecuaciones_de_score_poisson():
    rng = np.random.default_rng(7)
    anios = list(range(2015, 2023))
    datos = panel_sintetico(alfas=[np.log(0.012), np.log(0.03), np.log(0.008)], beta=-0.05, anios=anios, rng=rng)
    modelo = demanda.ajustar(datos, "M2", anios)
    ajuste = datos.merge(modelo.media(datos.drop(columns="casos_registrados")), on=["codigo", "anio"])
    residuo = ajuste["casos_registrados"] - ajuste["mu"]
    # En el máximo de verosimilitud Poisson: Σ residuos = 0 por municipio y Σ (t - t̄)·residuo = 0.
    assert residuo.groupby(ajuste["codigo"]).sum().abs().max() < 1e-6
    assert abs(((ajuste["anio"] - np.mean(anios)) * residuo).sum()) < 1e-6


def test_ajustar_ignora_anios_fuera_del_entrenamiento():
    datos = tabla([("A", 2015, 10, 1000), ("A", 2023, 999, 1000)])
    modelo = demanda.ajustar(datos, "M0", [2015])
    assert modelo.media(tabla([("A", 2024, None, 1000)]))["mu"].iloc[0] == pytest.approx(10.0)


def test_ajustar_excluye_celdas_sin_registro():
    datos = tabla([("A", 2015, 10, 1000), ("A", 2016, None, 1000)])
    modelo = demanda.ajustar(datos, "M0", [2015, 2016])
    assert modelo.media(tabla([("A", 2017, None, 1000)]))["mu"].iloc[0] == pytest.approx(10.0)


def test_ajustar_rechaza_modelo_desconocido():
    with pytest.raises(ErrorDatos, match="M9"):
        demanda.ajustar(tabla([("A", 2015, 1, 10)]), "M9", [2015])


def test_media_rechaza_municipio_no_ajustado():
    modelo = demanda.ajustar(tabla([("A", 2015, 1, 10)]), "M0", [2015])
    with pytest.raises(ErrorDatos, match="B"):
        modelo.media(tabla([("B", 2016, None, 10)]))


# --- métricas -----------------------------------------------------------------


def test_metricas_de_error():
    y = np.array([10.0, 20.0, 30.0])
    mu = np.array([12.0, 18.0, 33.0])
    assert demanda.wape(y, mu) == pytest.approx(7 / 60)
    assert demanda.mae(y, mu) == pytest.approx(7 / 3)
    assert demanda.sesgo_relativo(y, mu) == pytest.approx(3 / 60)


def test_wape_rechaza_total_observado_cero():
    with pytest.raises(ErrorDatos, match="cero"):
        demanda.wape(np.array([0.0]), np.array([1.0]))


# --- backtest y regla de decisión --------------------------------------------


def test_pliegues_del_protocolo():
    assert demanda.PLIEGUES == (
        ((2015, 2016, 2017, 2018), (2019, 2020)),
        ((2015, 2016, 2017, 2018, 2019), (2020, 2021)),
        ((2015, 2016, 2017, 2018, 2019, 2020), (2021, 2022)),
    )


def test_backtest_rechaza_datos_de_validacion():
    datos = tabla([("A", 2015, 1, 10), ("A", 2023, 1, 10)])
    with pytest.raises(ErrorDatos, match="2023"):
        demanda.backtest(datos, anios_permitidos=range(2015, 2023))


def test_backtest_entrena_y_evalua_en_los_anios_de_cada_pliegue():
    anios = list(range(2015, 2023))
    datos = panel_sintetico(alfas=[np.log(0.01)], beta=0.2, anios=anios)
    resultado = demanda.backtest(datos, anios_permitidos=anios)
    assert set(resultado["modelo"]) == {"M0", "M1", "M2"}
    assert sorted(resultado["pliegue"].unique()) == [1, 2, 3]
    # Con tendencia exacta y sin ruido, M2 predice perfecto.
    assert resultado.loc[resultado["modelo"] == "M2", "wape"].max() == pytest.approx(0.0, abs=1e-8)


@pytest.mark.parametrize(
    "wapes, esperado",
    [
        ({"M0": 0.30, "M1": 0.28, "M2": 0.275}, "M0"),  # ninguno mejora 10 %
        ({"M0": 0.30, "M1": 0.27, "M2": 0.29}, "M1"),  # M1 justo en el umbral (0.27 = 0.9 × 0.30)
        ({"M0": 0.30, "M1": 0.29, "M2": 0.20}, "M2"),
        ({"M0": 0.30, "M1": 0.25, "M2": 0.20}, "M2"),  # ambos califican: gana el menor
        ({"M0": 0.30, "M1": 0.20, "M2": 0.20}, "M1"),  # empate: gana el más simple
    ],
)
def test_elegir_modelo_aplica_regla_del_protocolo(wapes, esperado):
    assert demanda.elegir_modelo(wapes) == esperado


# --- dispersión ---------------------------------------------------------------


def test_dispersion_pearson():
    y = np.array([0.0, 4.0])
    mu = np.array([2.0, 2.0])
    assert demanda.dispersion_pearson(y, mu, parametros=1) == pytest.approx(4.0)  # (2 + 2) / (2 - 1)


def test_datos_poisson_no_eligen_binomial_negativa():
    rng = np.random.default_rng(1)
    mu = np.full(400, 30.0)
    resultado = demanda.evaluar_dispersion(rng.poisson(mu), mu, parametros=1)
    assert resultado["phi"] == pytest.approx(1.0, abs=0.25)
    assert resultado["distribucion"] == "poisson"


def test_datos_sobredispersos_eligen_binomial_negativa():
    rng = np.random.default_rng(2)
    mu = np.full(400, 30.0)
    a = 0.3
    y = rng.negative_binomial(1 / a, 1 / (1 + a * mu))
    resultado = demanda.evaluar_dispersion(y, mu, parametros=1)
    assert resultado["distribucion"] == "binomial_negativa"
    assert resultado["a"] == pytest.approx(a, rel=0.3)
    assert resultado["valor_p"] < 0.05


@pytest.mark.parametrize("phi, p, esperado", [(1.6, 0.01, "binomial_negativa"), (1.4, 0.01, "poisson"), (2.0, 0.2, "poisson")])
def test_elegir_distribucion_requiere_ambas_condiciones(phi, p, esperado):
    assert demanda.elegir_distribucion(phi, p) == esperado


# --- generación de escenarios -------------------------------------------------


def test_generar_demanda_es_reproducible_con_la_misma_semilla():
    mu = np.array([10.0, 50.0, 100.0])
    a = demanda.generar_demanda(mu, np.random.default_rng(42), "poisson")
    b = demanda.generar_demanda(mu, np.random.default_rng(42), "poisson")
    assert np.array_equal(a, b)
    assert a.dtype.kind == "i"


@pytest.mark.parametrize("distribucion, a", [("poisson", None), ("binomial_negativa", 0.2)])
def test_generar_demanda_respeta_media_y_escala(distribucion, a):
    mu = np.array([20.0, 80.0])
    muestras = demanda.generar_demanda(mu, np.random.default_rng(3), distribucion, a=a, escala=1.2, replicas=20_000)
    assert muestras.shape == (20_000, 2)
    assert muestras.mean(axis=0) == pytest.approx(mu * 1.2, rel=0.02)
    if distribucion == "binomial_negativa":
        esperada = mu * 1.2 + a * (mu * 1.2) ** 2
        assert muestras.var(axis=0) == pytest.approx(esperada, rel=0.08)


def test_generar_demanda_binomial_negativa_requiere_parametro():
    with pytest.raises(ErrorDatos, match="a"):
        demanda.generar_demanda(np.array([1.0]), np.random.default_rng(0), "binomial_negativa")


def test_generar_demanda_rechaza_medias_negativas():
    with pytest.raises(ErrorDatos, match="negativ"):
        demanda.generar_demanda(np.array([-1.0]), np.random.default_rng(0), "poisson")


# --- validación final ---------------------------------------------------------


def test_metricas_validacion():
    observado = tabla(
        [("A", 2023, 10, 0), ("B", 2023, 20, 0), ("C", 2023, 5, 0), ("A", 2024, 12, 0), ("B", 2024, 18, 0), ("C", 2024, 7, 0)]
    )
    previsto = observado[["codigo", "anio"]].assign(mu=[11.0, 18.0, 6.0, 12.0, 20.0, 5.0])
    m = demanda.metricas_validacion(observado, previsto)
    assert m["mae"] == pytest.approx((1 + 2 + 1 + 0 + 2 + 2) / 6)
    assert m["wape"] == pytest.approx(8 / 72)
    assert m["sesgo_casos"] == pytest.approx(0.0)
    assert m["por_anio"]["2023"] == {"observado": 35, "previsto": 35.0, "error": 0.0}
    assert m["spearman_ranking"] == pytest.approx(1.0)
    assert m["coincidencia_top3"] == 3
