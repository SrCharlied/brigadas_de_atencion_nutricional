"""Modelo de demanda municipal: media esperada, dispersión y generación de escenarios.

Implementa el protocolo congelado en docs/protocolo_demanda.md. La demanda son casos
registrados por municipio y año (MSPAS), no prevalencia ni necesidad clínica.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize, special, stats

from brigadas.datos import ErrorDatos

MODELOS = ("M0", "M1", "M2")
VENTANA_RECIENTE = 3
UMBRAL_MEJORA = 0.90
UMBRAL_PHI = 1.5
NIVEL_SIGNIFICANCIA = 0.05
PLIEGUES = (
    ((2015, 2016, 2017, 2018), (2019, 2020)),
    ((2015, 2016, 2017, 2018, 2019), (2020, 2021)),
    ((2015, 2016, 2017, 2018, 2019, 2020), (2021, 2022)),
)
_TOLERANCIA = 1e-12


# --- modelos de media ---------------------------------------------------------


@dataclass(frozen=True)
class ModeloDemanda:
    """Media ajustada. M0/M1 guardan una tasa por municipio; M2, interceptos y pendiente común."""

    nombre: str
    codigos: tuple[str, ...]
    tasas: tuple[float, ...] | None = None
    interceptos: tuple[float, ...] | None = None
    beta: float | None = None
    anio_centro: float | None = None

    @property
    def parametros(self) -> int:
        return len(self.codigos) + (1 if self.nombre == "M2" else 0)

    def media(self, poblacion: pd.DataFrame) -> pd.DataFrame:
        """Casos esperados ``mu`` para cada fila (codigo, anio, poblacion_0_4)."""
        desconocidos = sorted(set(poblacion["codigo"]) - set(self.codigos))
        if desconocidos:
            raise ErrorDatos(f"municipios sin ajuste: {', '.join(desconocidos)}")
        posicion = poblacion["codigo"].map({c: i for i, c in enumerate(self.codigos)}).to_numpy()
        pob = poblacion["poblacion_0_4"].to_numpy(dtype=float)
        if self.nombre == "M2":
            tendencia = self.beta * (poblacion["anio"].to_numpy(dtype=float) - self.anio_centro)
            mu = np.exp(np.asarray(self.interceptos)[posicion] + tendencia) * pob
        else:
            mu = np.asarray(self.tasas)[posicion] * pob
        return pd.DataFrame({"codigo": poblacion["codigo"].to_numpy(), "anio": poblacion["anio"].to_numpy(), "mu": mu})


def _observadas(datos: pd.DataFrame, anios) -> pd.DataFrame:
    seleccion = datos[datos["anio"].isin(list(anios)) & datos["casos_registrados"].notna()]
    if seleccion.empty:
        raise ErrorDatos("no hay observaciones en los años de entrenamiento")
    return seleccion.astype({"casos_registrados": float, "poblacion_0_4": float})


def _tasas(datos: pd.DataFrame) -> pd.Series:
    sumas = datos.groupby("codigo")[["casos_registrados", "poblacion_0_4"]].sum()
    return sumas["casos_registrados"] / sumas["poblacion_0_4"]


def _ajustar_tendencia(datos: pd.DataFrame) -> ModeloDemanda:
    """Poisson log-lineal con intercepto por municipio y pendiente común (IRLS)."""
    codigos = tuple(sorted(datos["codigo"].unique()))
    sumas = datos.groupby("codigo")["casos_registrados"].sum()
    if (sumas <= 0).any():
        raise ErrorDatos(f"M2 no es estimable con municipios sin casos: {list(sumas[sumas <= 0].index)}")
    centro = float(np.mean(sorted(datos["anio"].unique())))
    indice = datos["codigo"].map({c: i for i, c in enumerate(codigos)}).to_numpy()
    x = np.zeros((len(datos), len(codigos) + 1))
    x[np.arange(len(datos)), indice] = 1.0
    x[:, -1] = datos["anio"].to_numpy(dtype=float) - centro
    y = datos["casos_registrados"].to_numpy(dtype=float)
    desplazamiento = np.log(datos["poblacion_0_4"].to_numpy(dtype=float))

    coef = np.append(np.log(_tasas(datos).loc[list(codigos)].to_numpy()), 0.0)
    for _ in range(100):
        mu = np.exp(x @ coef + desplazamiento)
        z = x @ coef + (y - mu) / mu
        nuevo = np.linalg.solve(x.T @ (mu[:, None] * x), x.T @ (mu * z))
        if np.max(np.abs(nuevo - coef)) < 1e-12:
            coef = nuevo
            break
        coef = nuevo
    else:
        raise ErrorDatos("M2 no convergió en 100 iteraciones")
    return ModeloDemanda("M2", codigos, interceptos=tuple(coef[:-1]), beta=float(coef[-1]), anio_centro=centro)


def ajustar(datos: pd.DataFrame, nombre: str, anios_entrenamiento) -> ModeloDemanda:
    """Ajusta el modelo ``nombre`` usando solo ``anios_entrenamiento`` y celdas con registro."""
    if nombre not in MODELOS:
        raise ErrorDatos(f"modelo desconocido: {nombre}")
    anios = sorted(int(a) for a in anios_entrenamiento)
    if nombre == "M1":
        anios = anios[-VENTANA_RECIENTE:]
    observadas = _observadas(datos, anios)
    if nombre == "M2":
        return _ajustar_tendencia(observadas)
    tasas = _tasas(observadas)
    return ModeloDemanda(nombre, tuple(tasas.index), tasas=tuple(float(t) for t in tasas))


# --- métricas -----------------------------------------------------------------


def _total_observado(y: np.ndarray) -> float:
    total = float(np.sum(y))
    if total == 0:
        raise ErrorDatos("el total observado es cero; el error relativo no está definido")
    return total


def wape(y, mu) -> float:
    y, mu = np.asarray(y, dtype=float), np.asarray(mu, dtype=float)
    return float(np.sum(np.abs(y - mu)) / _total_observado(y))


def mae(y, mu) -> float:
    return float(np.mean(np.abs(np.asarray(y, dtype=float) - np.asarray(mu, dtype=float))))


def sesgo_relativo(y, mu) -> float:
    y, mu = np.asarray(y, dtype=float), np.asarray(mu, dtype=float)
    return float(np.sum(mu - y) / _total_observado(y))


# --- backtest y regla de decisión --------------------------------------------


def backtest(datos: pd.DataFrame, anios_permitidos, pliegues=PLIEGUES, modelos=MODELOS) -> pd.DataFrame:
    """Error de cada modelo en cada pliegue. Rechaza datos fuera de ``anios_permitidos``."""
    ajenos = sorted(set(datos["anio"]) - set(int(a) for a in anios_permitidos))
    if ajenos:
        raise ErrorDatos(f"el backtest recibió años fuera del periodo de desarrollo: {ajenos}")
    filas = []
    for numero, (entrenamiento, prueba) in enumerate(pliegues, start=1):
        evaluacion = _observadas(datos, prueba)
        for nombre in modelos:
            modelo = ajustar(datos, nombre, entrenamiento)
            mu = evaluacion[["codigo", "anio"]].merge(modelo.media(evaluacion), on=["codigo", "anio"])["mu"]
            y = evaluacion["casos_registrados"].to_numpy()
            filas.append(
                {
                    "modelo": nombre,
                    "pliegue": numero,
                    "entrenamiento": f"{entrenamiento[0]}-{entrenamiento[-1]}",
                    "prueba": f"{prueba[0]}-{prueba[-1]}",
                    "wape": wape(y, mu),
                    "mae": mae(y, mu),
                    "sesgo": sesgo_relativo(y, mu),
                }
            )
    return pd.DataFrame(filas)


def elegir_modelo(wape_promedio: dict[str, float], umbral: float = UMBRAL_MEJORA) -> str:
    """Regla del protocolo §4: un modelo complejo debe mejorar a M0 en al menos (1 - umbral)."""
    limite = umbral * wape_promedio["M0"] + _TOLERANCIA
    calificados = [m for m in ("M1", "M2") if wape_promedio[m] <= limite]
    if not calificados:
        return "M0"
    mejor = min(wape_promedio[m] for m in calificados)
    # El orden M1 antes que M2 resuelve los empates a favor del más simple.
    return next(m for m in calificados if wape_promedio[m] <= mejor + _TOLERANCIA)


# --- dispersión ---------------------------------------------------------------


def dispersion_pearson(y, mu, parametros: int) -> float:
    y, mu = np.asarray(y, dtype=float), np.asarray(mu, dtype=float)
    grados = len(y) - parametros
    if grados <= 0:
        raise ErrorDatos("no hay grados de libertad para estimar la dispersión")
    return float(np.sum((y - mu) ** 2 / mu) / grados)


def _logver_poisson(y: np.ndarray, mu: np.ndarray) -> float:
    return float(np.sum(stats.poisson.logpmf(y, mu)))


def _logver_nb(y: np.ndarray, mu: np.ndarray, a: float) -> float:
    n = 1.0 / a
    return float(
        np.sum(
            special.gammaln(y + n)
            - special.gammaln(n)
            - special.gammaln(y + 1)
            + n * np.log(n / (n + mu))
            + y * np.log(mu / (n + mu))
        )
    )


def elegir_distribucion(phi: float, valor_p: float) -> str:
    return "binomial_negativa" if phi > UMBRAL_PHI and valor_p < NIVEL_SIGNIFICANCIA else "poisson"


def evaluar_dispersion(y, mu, parametros: int) -> dict:
    """Protocolo §5: φ de Pearson y razón de verosimilitudes NB2 frente a Poisson con μ fijo."""
    y, mu = np.asarray(y, dtype=float), np.asarray(mu, dtype=float)
    phi = dispersion_pearson(y, mu, parametros)
    logver_poisson = _logver_poisson(y, mu)
    optimo = optimize.minimize_scalar(
        lambda log_a: -_logver_nb(y, mu, float(np.exp(log_a))), bounds=(-20.0, 5.0), method="bounded"
    )
    a = float(np.exp(optimo.x))
    logver_nb = -float(optimo.fun)
    if logver_nb <= logver_poisson:
        a, logver_nb = 0.0, logver_poisson
    razon = max(0.0, 2.0 * (logver_nb - logver_poisson))
    # a = 0 está en la frontera del espacio de parámetros: mezcla 50:50 de χ²₀ y χ²₁.
    valor_p = 0.5 * float(stats.chi2.sf(razon, df=1))
    return {
        "phi": phi,
        "a": a,
        "logver_poisson": logver_poisson,
        "logver_nb": logver_nb,
        "razon_verosimilitud": razon,
        "valor_p": valor_p,
        "distribucion": elegir_distribucion(phi, valor_p),
    }


# --- generación de escenarios -------------------------------------------------


def generar_demanda(
    mu,
    rng: np.random.Generator,
    distribucion: str,
    a: float | None = None,
    escala: float = 1.0,
    replicas: int | None = None,
) -> np.ndarray:
    """Demanda simulada por municipio. ``escala`` multiplica la media (p. ej. 1.2 para +20 %)."""
    media = np.asarray(mu, dtype=float) * escala
    if (media < 0).any() or not np.isfinite(media).all():
        raise ErrorDatos("las medias de demanda no pueden ser negativas ni infinitas")
    forma = media.shape if replicas is None else (replicas, *media.shape)
    if distribucion == "poisson":
        return rng.poisson(media, size=forma)
    if distribucion == "binomial_negativa":
        if a is None or a <= 0:
            raise ErrorDatos("la binomial negativa requiere un parámetro a > 0")
        n = 1.0 / a
        return rng.negative_binomial(n, n / (n + media), size=forma)
    raise ErrorDatos(f"distribución desconocida: {distribucion}")


# --- validación final ---------------------------------------------------------


def metricas_validacion(observado: pd.DataFrame, previsto: pd.DataFrame, top: int = 3) -> dict:
    """Protocolo §6: errores y concordancia de ranking contra los registros reservados."""
    union = observado[observado["casos_registrados"].notna()][["codigo", "anio", "casos_registrados"]].merge(
        previsto[["codigo", "anio", "mu"]], on=["codigo", "anio"], validate="one_to_one"
    )
    y = union["casos_registrados"].to_numpy(dtype=float)
    mu = union["mu"].to_numpy(dtype=float)
    por_anio = {
        str(int(anio)): {
            "observado": int(grupo["casos_registrados"].sum()),
            "previsto": float(grupo["mu"].sum()),
            "error": float(grupo["mu"].sum() - grupo["casos_registrados"].sum()),
        }
        for anio, grupo in union.groupby("anio")
    }
    carga = union.groupby("codigo")[["casos_registrados", "mu"]].sum()
    top_observado = set(carga["casos_registrados"].nlargest(top).index)
    top_previsto = set(carga["mu"].nlargest(top).index)
    return {
        "observaciones": int(len(union)),
        "casos_observados": int(y.sum()),
        "casos_previstos": float(mu.sum()),
        "mae": mae(y, mu),
        "wape": wape(y, mu),
        "sesgo_casos": float(mu.sum() - y.sum()),
        "sesgo_relativo": sesgo_relativo(y, mu),
        "por_anio": por_anio,
        "spearman_ranking": float(stats.spearmanr(carga["casos_registrados"], carga["mu"]).statistic),
        "coincidencia_top3": len(top_observado & top_previsto),
        "top3_observado": sorted(top_observado),
        "top3_previsto": sorted(top_previsto),
    }
