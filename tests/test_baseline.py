import numpy as np
import pytest

from brigadas.baseline import crear_politica_base, crear_politica_bases_fijas, seleccionar_bases_base


def test_bases_mayor_demanda_con_desempate_por_indice(caso_pequeno):
    esperado = caso_pequeno["politica_base_esperada"]
    assert seleccionar_bases_base(caso_pequeno["demanda"], 2) == tuple(esperado["bases"])


def test_politica_base_caso_pequeno(caso_pequeno):
    politica = crear_politica_base(caso_pequeno["demanda"], caso_pequeno["pesos"])
    res = politica(caso_pequeno["demanda"], caso_pequeno["distancias_km"], 2,
                   caso_pequeno["capacidad"], caso_pequeno["distancia_max_km"],
                   np.random.default_rng(0))
    assert res.bases == (0, 2)
    assert res.total_cubierto == caso_pequeno["politica_base_esperada"]["demanda_cubierta"]
    assert res.es_factible


def test_bases_dependen_de_la_referencia_no_de_la_replica(caso_pequeno):
    referencia = caso_pequeno["demanda"]
    politica = crear_politica_base(referencia)
    demanda_replica = np.array([0.0, 0.0, 0.0, 50.0, 50.0])
    res = politica(demanda_replica, caso_pequeno["distancias_km"], 2, 100, 5, np.random.default_rng(1))
    assert res.bases == (0, 2)


def test_politica_base_ignora_rng(caso_pequeno):
    politica = crear_politica_base(caso_pequeno["demanda"])
    args = (caso_pequeno["demanda"], caso_pequeno["distancias_km"], 2, 100, 5)
    a = politica(*args, np.random.default_rng(1))
    b = politica(*args, np.random.default_rng(999))
    assert a.bases == b.bases and a.objetivo == b.objetivo


def test_referencia_no_se_puede_mutar_desde_fuera(caso_pequeno):
    referencia = caso_pequeno["demanda"].copy()
    politica = crear_politica_base(referencia)
    referencia[:] = 0  # el llamador modifica su arreglo
    res = politica(caso_pequeno["demanda"], caso_pequeno["distancias_km"], 2, 100, 5, np.random.default_rng(0))
    assert res.bases == (0, 2)


@pytest.mark.parametrize("k", [0, 6])
def test_k_invalido(caso_pequeno, k):
    with pytest.raises(ValueError):
        seleccionar_bases_base(caso_pequeno["demanda"], k)


def test_tamanos_distintos_se_rechazan(caso_pequeno):
    politica = crear_politica_base(np.ones(3))
    with pytest.raises(ValueError):
        politica(caso_pequeno["demanda"], caso_pequeno["distancias_km"], 2, 100, 5, np.random.default_rng(0))


def test_politica_bases_fijas(caso_pequeno):
    politica = crear_politica_bases_fijas((0, 4))
    res = politica(caso_pequeno["demanda"], caso_pequeno["distancias_km"], 2, 100, 5, np.random.default_rng(0))
    assert res.bases == (0, 4)
    with pytest.raises(ValueError):
        politica(caso_pequeno["demanda"], caso_pequeno["distancias_km"], 3, 100, 5, np.random.default_rng(0))


def test_demanda_media_desarrollo_ignora_ausencias_y_anios_de_validacion():
    import pandas as pd

    from brigadas.baseline import demanda_media_desarrollo

    panel = pd.DataFrame({
        "codigo": ["GT2001"] * 3 + ["GT2002"] * 3,
        "anio": [2015, 2016, 2023] * 2,
        "casos_registrados": pd.array([10, 20, 999, 4, None, 999], dtype="Int64"),
    })
    media = demanda_media_desarrollo(panel, (2015, 2016), ["GT2001", "GT2002"])
    # GT2002 tiene 2016 sin registro: se promedia solo 2015 (no se toma como cero).
    assert media.tolist() == [15.0, 4.0]
    with pytest.raises(ValueError, match="sin registros"):
        demanda_media_desarrollo(panel, (2015, 2016), ["GT2001", "GT2099"])
