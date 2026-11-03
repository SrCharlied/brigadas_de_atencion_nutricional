import json

import pytest

from brigadas.config import ConfiguracionEscenario, ErrorConfiguracion, cargar_configuracion

VALIDA = {
    "departamento": "GT20",
    "anios_desarrollo": [2015, 2016, 2017],
    "anios_validacion": [2023, 2024],
    "cantidad_brigadas": 3,
    "capacidad_por_brigada": 150,
    "distancia_max_km": 40.0,
    "replicas": 30,
    "semilla_raiz": 123,
}


def escribir(tmp_path, datos):
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return ruta


def test_cargar_configuracion_valida(tmp_path):
    config = cargar_configuracion(escribir(tmp_path, VALIDA))
    assert isinstance(config, ConfiguracionEscenario)
    assert config.anios_desarrollo == (2015, 2016, 2017)
    assert config.anios_validacion == (2023, 2024)


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("cantidad_brigadas", 0),
        ("capacidad_por_brigada", -1),
        ("distancia_max_km", -5.0),
        ("replicas", 0),
        ("departamento", ""),
        ("anios_validacion", []),
    ],
)
def test_configuracion_rechaza_valores_fuera_de_dominio(tmp_path, campo, valor):
    with pytest.raises(ErrorConfiguracion, match=campo):
        cargar_configuracion(escribir(tmp_path, {**VALIDA, campo: valor}))


def test_configuracion_rechaza_traslape_temporal(tmp_path):
    with pytest.raises(ErrorConfiguracion, match="traslap"):
        cargar_configuracion(escribir(tmp_path, {**VALIDA, "anios_validacion": [2017, 2023]}))


def test_configuracion_rechaza_validacion_anterior_a_desarrollo(tmp_path):
    with pytest.raises(ErrorConfiguracion, match="posterior"):
        cargar_configuracion(
            escribir(tmp_path, {**VALIDA, "anios_desarrollo": [2023, 2024], "anios_validacion": [2020]})
        )


def test_configuracion_rechaza_campos_desconocidos(tmp_path):
    with pytest.raises(ErrorConfiguracion, match="desconocid"):
        cargar_configuracion(escribir(tmp_path, {**VALIDA, "brigadaz": 3}))


def test_configuracion_ignora_claves_de_documentacion(tmp_path):
    documentada = {**VALIDA, "_supuestos": {"cantidad_brigadas": {"valor": 99}}, "_nota": "texto"}
    config = cargar_configuracion(escribir(tmp_path, documentada))
    assert config.cantidad_brigadas == 3


def test_configuracion_rechaza_campos_faltantes(tmp_path):
    incompleta = {k: v for k, v in VALIDA.items() if k != "semilla_raiz"}
    with pytest.raises(ErrorConfiguracion, match="semilla_raiz"):
        cargar_configuracion(escribir(tmp_path, incompleta))
