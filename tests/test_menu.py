import pandas as pd
import pytest

from scripts import menu


def respuestas(monkeypatch, *valores):
    entradas = iter(valores)
    monkeypatch.setattr("builtins.input", lambda _="": next(entradas))


def test_pedir_numero_usa_el_valor_por_defecto_con_enter(monkeypatch):
    respuestas(monkeypatch, "")
    assert menu.pedir_numero("Brigadas", 6, 1, 15, entero=True) == 6


def test_pedir_numero_reintenta_hasta_un_valor_valido(monkeypatch, capsys):
    respuestas(monkeypatch, "abc", "0", "4")
    assert menu.pedir_numero("Brigadas", 6, 1, 15, entero=True) == 4
    salida = capsys.readouterr().out
    assert "número" in salida and "entre 1 y 15" in salida


def test_pedir_numero_acepta_coma_decimal(monkeypatch):
    respuestas(monkeypatch, "27,5")
    assert menu.pedir_numero("Productividad", 20.0, 20.0, 35.0) == pytest.approx(27.5)


def test_pedir_opcion(monkeypatch):
    respuestas(monkeypatch, "x", "2")
    assert menu.pedir_opcion("Objetivo", {"1": "casos", "2": "ninos"}, "1") == "ninos"


def test_tabla_rapida_filtra_el_estudio_y_ordena_por_brigadas():
    planes = pd.DataFrame({
        "objetivo": ["casos"] * 3 + ["ninos"], "propuesto": [True, True, False, True],
        "productividad": [27.5] * 4, "umbral_min": [60.0] * 4, "k": [2, 1, 2, 1],
        "casos_pct": [35.0, 18.0, 30.0, 10.0], "ninos_pct": [24.0, 12.0, 24.0, 12.0],
        "ubicacion": ["Jocotán ×2", "Jocotán", "Camotán ×2", "Chiquimula"],
    })
    tabla = menu.tabla_rapida(planes, 27.5, 60.0, "casos")
    assert tabla["brigadas"].tolist() == [1, 2]
    assert tabla["ubicación"].tolist() == ["Jocotán", "Jocotán ×2"]


def test_tabla_rapida_se_detiene_al_llegar_al_100_por_ciento():
    planes = pd.DataFrame({
        "objetivo": ["casos"] * 4, "propuesto": [True] * 4, "productividad": [27.5] * 4, "umbral_min": [60.0] * 4,
        "k": [1, 2, 3, 4], "casos_pct": [60.0, 100.0, 100.0, 100.0], "ninos_pct": [50.0, 100.0, 100.0, 100.0],
        "ubicacion": ["A", "A ×2", "A ×3", "A ×4"],
    })
    assert menu.tabla_rapida(planes, 27.5, 60.0, "casos")["brigadas"].tolist() == [1, 2]


def test_menu_ignora_la_marca_bom_de_entradas_por_tuberia(monkeypatch, capsys):
    respuestas(monkeypatch, "﻿0")
    assert menu.main() == 0
