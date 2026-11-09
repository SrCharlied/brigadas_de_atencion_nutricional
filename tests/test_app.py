"""Pruebas de la interfaz web (app.py), sin navegador."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"
DATOS = Path(__file__).resolve().parents[1] / "data" / "processed" / "panel_GT20.csv"


@pytest.mark.skipif(not DATOS.exists(), reason="requiere data/processed (python -m scripts.preparar_datos)")
def test_app_carga_sin_errores_y_muestra_el_plan_de_referencia():
    app = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not app.exception
    metricas = {m.label: m.value for m in app.metric}
    assert metricas["Casos identificados"] == "83.1 %"
    assert metricas["Niños evaluados"] == "71.3 %"


@pytest.mark.skipif(not DATOS.exists(), reason="requiere data/processed (python -m scripts.preparar_datos)")
def test_app_responde_al_cambiar_el_numero_de_brigadas():
    app = AppTest.from_file(str(APP), default_timeout=120).run()
    app.sidebar.slider[0].set_value(3).run()
    assert not app.exception
    metricas = {m.label: m.value for m in app.metric}
    assert metricas["Casos identificados"] == "50.1 %"


@pytest.mark.skipif(not DATOS.exists(), reason="requiere data/processed (python -m scripts.preparar_datos)")
def test_la_propuesta_se_lee_de_los_resultados_y_no_esta_fija():
    referencia = json.loads((APP.parent / "resultados" / "tamizaje_resumen.json").read_text(encoding="utf-8"))["referencia"]
    app = AppTest.from_file(str(APP), default_timeout=120).run()
    propuesta = next(m for m in app.metric if m.label.startswith("Propuesta"))
    assert propuesta.value == f"{referencia['k_minimo']} brigadas"
    assert f"{referencia['meta_pct']} %" in propuesta.label
