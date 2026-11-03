import pytest

from brigadas.config import ConfiguracionEscenario as ConfigDelEquipo
from brigadas.contratos import ConfiguracionEscenario, DemandaMunicipal, Municipio, PesosObjetivo


def test_contratos_reexporta_la_configuracion_del_equipo():
    assert ConfiguracionEscenario is ConfigDelEquipo


def test_pesos_por_defecto_y_validacion():
    p = PesosObjetivo()
    assert (p.w_c, p.w_d, p.w_e) == (1.0, 0.1, 0.1)
    with pytest.raises(ValueError):
        PesosObjetivo(w_c=0.0)
    with pytest.raises(ValueError):
        PesosObjetivo(w_d=-0.1)
    with pytest.raises(ValueError):
        PesosObjetivo(w_e=float("nan"))


def test_municipio_valida_coordenadas():
    Municipio("GT2001", "Chiquimula", "Chiquimula", 14.8, -89.54)
    with pytest.raises(ValueError):
        Municipio("GT2001", "Chiquimula", "Chiquimula", 95.0, -89.54)
    with pytest.raises(ValueError):
        Municipio("", "Chiquimula", "Chiquimula", 14.8, -89.54)


def test_demanda_municipal_rechaza_negativos_y_no_enteros():
    DemandaMunicipal("GT2001", 2020, 10, 5000)
    with pytest.raises(ValueError):
        DemandaMunicipal("GT2001", 2020, -1, 5000)
    with pytest.raises(TypeError):
        DemandaMunicipal("GT2001", 2020, 3.5, 5000)
    with pytest.raises(TypeError):
        DemandaMunicipal("GT2001", 2020, "10", 5000)
