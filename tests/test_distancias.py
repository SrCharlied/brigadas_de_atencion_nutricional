import numpy as np
import pytest

from brigadas.contratos import Municipio
from brigadas.distancias import (
    cargar_matriz_csv,
    guardar_matriz_csv,
    haversine_km,
    matriz_distancias,
    validar_matriz_distancias,
)


def municipios_ejemplo():
    return [
        Municipio("A", "Alfa", "Sintético", 14.0, -89.0),
        Municipio("B", "Beta", "Sintético", 15.0, -89.0),
        Municipio("C", "Gamma", "Sintético", 14.0, -90.0),
    ]


def test_un_grado_de_latitud_mide_unos_111_km():
    assert haversine_km(14.0, -89.0, 15.0, -89.0) == pytest.approx(111.195, abs=0.01)


def test_mismo_punto_distancia_cero():
    assert haversine_km(14.8, -89.5, 14.8, -89.5) == 0.0


def test_matriz_simetrica_diagonal_cero_y_coherente():
    m = matriz_distancias(municipios_ejemplo())
    assert m.shape == (3, 3)
    assert np.allclose(m, m.T)
    assert np.all(np.diag(m) == 0)
    assert m[0, 1] == pytest.approx(haversine_km(14.0, -89.0, 15.0, -89.0))
    # Un grado de longitud mide menos que uno de latitud fuera del ecuador.
    assert m[0, 2] < m[0, 1]


def test_codigos_duplicados_se_rechazan():
    ms = municipios_ejemplo() + [Municipio("A", "Otro", "Sintético", 14.5, -89.5)]
    with pytest.raises(ValueError, match="duplicados"):
        matriz_distancias(ms)


def test_lista_vacia_se_rechaza():
    with pytest.raises(ValueError):
        matriz_distancias([])


@pytest.mark.parametrize(
    "matriz",
    [
        np.array([[0.0, 1.0], [2.0, 0.0]]),        # no simétrica
        np.array([[1.0, 1.0], [1.0, 0.0]]),        # diagonal no cero
        np.array([[0.0, -1.0], [-1.0, 0.0]]),      # negativa
        np.array([[0.0, np.inf], [np.inf, 0.0]]),  # no finita
        np.zeros((2, 3)),                           # no cuadrada
    ],
)
def test_validar_matriz_rechaza_invalidas(matriz):
    with pytest.raises(ValueError):
        validar_matriz_distancias(matriz)


def test_guardar_y_cargar_matriz(tmp_path):
    m = matriz_distancias(municipios_ejemplo())
    ruta = tmp_path / "distancias.csv"
    guardar_matriz_csv(m, ["A", "B", "C"], ruta)
    recargada, codigos = cargar_matriz_csv(ruta)
    assert codigos == ["A", "B", "C"]
    assert np.allclose(recargada, m, atol=1e-5)


def test_cargar_municipios_csv_filtra_y_ordena_por_codigo(tmp_path):
    from brigadas.distancias import cargar_municipios_csv

    ruta = tmp_path / "municipios.csv"
    ruta.write_text(
        "codigo,nombre,codigo_departamento,departamento,latitud,longitud\n"
        "GT2003,Jocotán,GT20,Chiquimula,14.82,-89.39\n"
        "GT2001,Chiquimula,GT20,Chiquimula,14.80,-89.54\n"
        "GT0101,Guatemala,GT01,Guatemala,14.62,-90.52\n",
        encoding="utf-8",
    )
    ms = cargar_municipios_csv(ruta, "GT20")
    assert [m.codigo for m in ms] == ["GT2001", "GT2003"]
    assert ms[1].nombre == "Jocotán"
    with pytest.raises(ValueError):
        cargar_municipios_csv(ruta, "GT99")
