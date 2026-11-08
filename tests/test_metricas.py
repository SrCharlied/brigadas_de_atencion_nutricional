import math

import numpy as np
import pytest
from scipy import stats

from brigadas.metricas import resumen_pareado, resumir


def test_resumir_media_desviacion_y_mediana():
    r = resumir([1.0, 2.0, 3.0, 10.0])
    assert r["media"] == pytest.approx(4.0)
    assert r["desviacion"] == pytest.approx(np.std([1, 2, 3, 10], ddof=1))
    assert r["mediana"] == pytest.approx(2.5)
    assert r["n"] == 4


def test_resumir_ignora_nan():
    r = resumir([1.0, float("nan"), 3.0])
    assert r["media"] == pytest.approx(2.0)
    assert r["n"] == 2


def test_resumen_pareado_con_intervalo_t():
    base = np.array([10.0, 20.0, 30.0])
    mejora = np.array([11.0, 22.0, 33.0])  # diferencias 1, 2, 3
    r = resumen_pareado(base, mejora)
    t = stats.t.ppf(0.975, df=2)
    assert r["diferencia_media"] == pytest.approx(2.0)
    assert r["diferencia_desviacion"] == pytest.approx(1.0)
    assert r["ic95_inferior"] == pytest.approx(2.0 - t / math.sqrt(3))
    assert r["ic95_superior"] == pytest.approx(2.0 + t / math.sqrt(3))
    assert r["cambio_relativo_pct"] == pytest.approx(2.0 / 20.0 * 100)
    assert r["media_base"] == pytest.approx(20.0)
    assert r["media_mejora"] == pytest.approx(22.0)
    assert r["n"] == 3


def test_resumen_pareado_sin_variacion_da_intervalo_degenerado():
    r = resumen_pareado(np.array([5.0, 5.0]), np.array([6.0, 6.0]))
    assert r["ic95_inferior"] == pytest.approx(1.0)
    assert r["ic95_superior"] == pytest.approx(1.0)


def test_resumen_pareado_rechaza_longitudes_distintas_o_muy_cortas():
    with pytest.raises(ValueError):
        resumen_pareado(np.array([1.0, 2.0]), np.array([1.0]))
    with pytest.raises(ValueError):
        resumen_pareado(np.array([1.0]), np.array([2.0]))


def test_resumen_pareado_con_base_cero_no_divide():
    r = resumen_pareado(np.array([0.0, 0.0]), np.array([1.0, 1.0]))
    assert math.isnan(r["cambio_relativo_pct"])
