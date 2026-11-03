import numpy as np
import pytest

from brigadas.asignacion import evaluar_bases
from brigadas.baseline import crear_politica_base, crear_politica_bases_fijas
from brigadas.config import ConfiguracionEscenario
from brigadas.contratos import ResultadoAsignacion
from brigadas.simulacion import (
    cargar_resultados_csv,
    derivar_semillas,
    ejecutar_replica,
    ejecutar_replicas,
    evaluar_demanda_fija,
    generador_binomial_negativa,
    generador_poisson,
    guardar_resultados_csv,
)


def config(**cambios):
    base = dict(
        departamento="GT20",
        anios_desarrollo=(2015, 2016),
        anios_validacion=(2023,),
        cantidad_brigadas=2,
        capacidad_por_brigada=100,
        distancia_max_km=5.0,
        replicas=30,
        semilla_raiz=123,
    )
    base.update(cambios)
    return ConfiguracionEscenario(**base)


def politicas(caso):
    return {
        "base": crear_politica_base(caso["demanda"], caso["pesos"]),
        "optima": crear_politica_bases_fijas((0, 4), caso["pesos"]),
    }


def test_semillas_reproducibles_y_distintas():
    a = derivar_semillas(7, 30)
    assert a == derivar_semillas(7, 30)
    assert len(set(a)) == 30
    assert a != derivar_semillas(8, 30)


def test_30_replicas_produce_filas_pareadas(caso_pequeno):
    res = ejecutar_replicas(config(), generador_poisson(caso_pequeno["demanda"]),
                            politicas(caso_pequeno), caso_pequeno["distancias_km"])
    assert len(res) == 60
    for r in range(30):
        filas = [x for x in res if x.replica == r]
        assert {f.politica for f in filas} == {"base", "optima"}
        assert len({f.semilla for f in filas}) == 1
    assert all(f.factible for f in res)


def test_misma_semilla_reproduce_resultados(caso_pequeno):
    args = (config(), generador_poisson(caso_pequeno["demanda"]), politicas(caso_pequeno),
            caso_pequeno["distancias_km"])
    a = [(r.porcentaje_cobertura, r.objetivo) for r in ejecutar_replicas(*args)]
    b = [(r.porcentaje_cobertura, r.objetivo) for r in ejecutar_replicas(*args)]
    assert a == b


def test_politicas_reciben_la_misma_demanda_y_no_pueden_mutarla(caso_pequeno):
    vistas = {}

    def espia(nombre):
        def politica(demanda, distancias, k, capacidad, dmax, rng):
            vistas[nombre] = demanda.copy()
            with pytest.raises(ValueError):
                demanda[0] = 1e6  # solo lectura
            return evaluar_bases(demanda, distancias, (0, 4), capacidad, dmax)
        return politica

    ejecutar_replica(0, 99, generador_poisson(caso_pequeno["demanda"]),
                     {"a": espia("a"), "b": espia("b")}, caso_pequeno["distancias_km"], 2, 100, 5)
    assert np.array_equal(vistas["a"], vistas["b"])


def test_politicas_reciben_rng_identico_independiente_del_orden(caso_pequeno):
    sorteos = {}

    def sorteadora(nombre):
        def politica(demanda, distancias, k, capacidad, dmax, rng):
            sorteos[nombre] = rng.random(3).tolist()
            return evaluar_bases(demanda, distancias, (0, 4), capacidad, dmax)
        return politica

    ejecutar_replica(0, 5, generador_poisson(caso_pequeno["demanda"]),
                     {"x": sorteadora("x"), "y": sorteadora("y")}, caso_pequeno["distancias_km"], 2, 100, 5)
    assert sorteos["x"] == sorteos["y"]


def test_politica_que_devuelve_solucion_invalida_se_marca_no_factible(caso_pequeno):
    def tramposa(demanda, distancias, k, capacidad, dmax, rng):
        return ResultadoAsignacion(
            bases=(0, 4), asignaciones=(0,) * 5,
            demanda_cubierta=np.asarray(demanda, dtype=float).copy(),
            carga_por_brigada=np.array([float(np.sum(demanda)), 0.0]),
            objetivo=0.0, es_factible=True,
        )

    filas, _ = ejecutar_replica(0, 1, generador_poisson(caso_pequeno["demanda"]), {"t": tramposa},
                                caso_pequeno["distancias_km"], 2, 100, 5)
    assert filas[0].factible is False


def test_generador_binomial_negativa_usa_el_modelo_del_equipo():
    mu = np.array([50.0, 120.0, 10.0])
    gen = generador_binomial_negativa(mu, a=0.116)
    a = gen(np.random.default_rng(3))
    b = gen(np.random.default_rng(3))
    assert np.array_equal(a, b) and a.shape == (3,) and np.all(a >= 0)
    muestras = np.array([gen(np.random.default_rng(s)) for s in range(4000)])
    assert np.allclose(muestras.mean(axis=0), mu, rtol=0.05)
    # Sobredispersión NB2: Var = mu + a·mu² (mucho mayor que Poisson).
    assert muestras[:, 1].var() == pytest.approx(120 + 0.116 * 120**2, rel=0.15)


def test_sensibilidad_con_escala_sobre_la_media():
    mu = np.array([40.0, 80.0])
    base = np.array([generador_binomial_negativa(mu, 0.116)(np.random.default_rng(s)) for s in range(3000)])
    mas20 = np.array([generador_binomial_negativa(mu, 0.116, escala=1.2)(np.random.default_rng(s))
                      for s in range(3000)])
    assert mas20.mean() / base.mean() == pytest.approx(1.2, rel=0.05)


def test_evaluar_demanda_fija_observada(caso_pequeno):
    observado = np.array([12.0, 3.0, 9.0, 7.0, 11.0])  # p. ej. casos reales de 2023
    filas = evaluar_demanda_fija(observado, politicas(caso_pequeno), caso_pequeno["distancias_km"],
                                 config(), escenario="observado_2023")
    assert {f.politica for f in filas} == {"base", "optima"}
    assert all(f.escenario == "observado_2023" and f.factible for f in filas)
    optima = next(f for f in filas if f.politica == "optima")
    assert optima.porcentaje_cobertura == pytest.approx(100 * (12 + 3 + 7 + 11) / 42)


def test_generador_con_forma_incorrecta(caso_pequeno):
    with pytest.raises(ValueError):
        ejecutar_replica(0, 1, lambda rng: np.ones(3), politicas(caso_pequeno),
                         caso_pequeno["distancias_km"], 2, 100, 5)


def test_k_mayor_que_municipios(caso_pequeno):
    with pytest.raises(ValueError):
        ejecutar_replicas(config(cantidad_brigadas=6), generador_poisson(caso_pequeno["demanda"]),
                          politicas(caso_pequeno), caso_pequeno["distancias_km"])


def test_exportar_y_recargar_resultados(tmp_path, caso_pequeno):
    res = ejecutar_replicas(config(replicas=3), generador_poisson(caso_pequeno["demanda"]),
                            politicas(caso_pequeno), caso_pequeno["distancias_km"])
    ruta = tmp_path / "resultados.csv"
    guardar_resultados_csv(res, ruta)
    recargados = cargar_resultados_csv(ruta)
    assert len(recargados) == len(res)
    for a, b in zip(res, recargados):
        assert a.semilla == b.semilla and a.politica == b.politica and a.factible == b.factible
        assert a.objetivo == pytest.approx(b.objetivo)
