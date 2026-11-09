"""Figuras de los experimentos (docs/diseno_experimental.md §6).

Cada figura lleva título, ejes con unidades y leyenda. La explicación va en el
informe. Se guardan sin metadatos de fecha para que sean reproducibles.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

__all__ = ["NOMBRES_CONDICION", "figura_mapa", "figura_comparacion", "figura_diferencias", "figura_convergencia",
           "figura_escalabilidad", "figura_dimensionamiento", "figura_tamizaje"]

NOMBRES_CONDICION = {
    "nominal": "Nominal",
    "demanda_x1.2": "Demanda ×1.2",
    "demanda_x1.6": "Demanda ×1.6",
    "capacidad_177": "Capacidad 177",
    "dmax_40": "D_max 40 km",
    "observado_2023": "Real 2023",
    "observado_2024": "Real 2024",
}
COLORES = {"base": "#7f7f7f", "genetico": "#1f77b4"}
ETIQUETAS = {"base": "Política base", "genetico": "Algoritmo genético"}


def _guardar(fig, ruta: Path) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(ruta, dpi=150, metadata={"Software": None})
    plt.close(fig)


ETIQUETAS_MAPA = ("Bases de la política base", "Bases del algoritmo genético", "Asignación del algoritmo genético")


def figura_mapa(poligonos, municipios: pd.DataFrame, demanda_referencia, bases_base, bases_genetico,
                asignaciones_genetico, ruta, titulo: str, etiquetas=ETIQUETAS_MAPA,
                leyenda_color: str = "Casos registrados medios 2015–2022 (casos/año)",
                anotar_repetidas: bool = False) -> None:
    """Demanda por municipio, dos conjuntos de bases (círculos y estrellas) y las asignaciones del segundo."""
    municipios = municipios.reset_index(drop=True)
    datos = poligonos.merge(
        pd.DataFrame({"adm2_pcode": municipios["codigo"], "demanda": demanda_referencia}), on="adm2_pcode"
    )
    fig, eje = plt.subplots(figsize=(8, 7))
    datos.plot(column="demanda", cmap="Oranges", edgecolor="0.4", linewidth=0.6, legend=True, ax=eje,
               legend_kwds={"label": leyenda_color, "shrink": 0.7})
    x, y = municipios["longitud"].to_numpy(), municipios["latitud"].to_numpy()
    for i, brigada in enumerate(asignaciones_genetico):
        if brigada is not None:
            b = bases_genetico[brigada]
            eje.plot([x[i], x[b]], [y[i], y[b]], color=COLORES["genetico"], linewidth=1.2, alpha=0.8, zorder=2)
    eje.scatter(x[list(bases_base)], y[list(bases_base)], s=260, facecolors="none", edgecolors="black",
                linewidths=2, label=etiquetas[0], zorder=3)
    eje.scatter(x[list(bases_genetico)], y[list(bases_genetico)], s=140, marker="*", color=COLORES["genetico"],
                edgecolors="white", linewidths=0.8, label=etiquetas[1], zorder=4)
    eje.plot([], [], color=COLORES["genetico"], linewidth=1.2, label=etiquetas[2])
    if anotar_repetidas:
        for j in set(bases_genetico):
            veces = list(bases_genetico).count(j)
            if veces > 1:
                eje.annotate(f"×{veces}", (x[j], y[j]), fontsize=10, fontweight="bold", color=COLORES["genetico"],
                             xytext=(8, 6), textcoords="offset points", zorder=5)
    for i, nombre in enumerate(municipios["nombre"]):
        eje.annotate(nombre, (x[i], y[i]), fontsize=7, xytext=(4, -9), textcoords="offset points")
    sin_cubrir = [i for i, b in enumerate(asignaciones_genetico) if b is None]
    if sin_cubrir:
        eje.scatter(x[sin_cubrir], y[sin_cubrir], marker="x", color="red", s=50,
                    label="Sin cobertura con el plan de estrellas", zorder=4)
    eje.set_xlabel("Longitud (grados)")
    eje.set_ylabel("Latitud (grados)")
    eje.set_title(titulo)
    eje.legend(loc="lower left", fontsize=8)
    _guardar(fig, ruta)


def _margen_ic(desviacion, n):
    return stats.t.ppf(0.975, df=n - 1) * desviacion / np.sqrt(n)


def figura_comparacion(resumen: pd.DataFrame, observado: pd.DataFrame, ruta) -> None:
    """Cobertura media por condición y política (IC 95 %), más la evaluación con casos reales."""
    etiquetas = [NOMBRES_CONDICION.get(c, c) for c in resumen["condicion"]]
    reales = list(dict.fromkeys(observado["escenario"]))
    etiquetas += [NOMBRES_CONDICION.get(e, e) for e in reales]
    posiciones = np.arange(len(etiquetas))
    ancho = 0.38
    fig, eje = plt.subplots(figsize=(10, 5.5))
    for desplazamiento, politica in ((-ancho / 2, "base"), (ancho / 2, "genetico")):
        medias = list(resumen[f"cobertura_{politica}_media"])
        errores = list(_margen_ic(resumen[f"cobertura_{politica}_desviacion"], resumen["replicas"]))
        for e in reales:
            fila = observado[(observado["escenario"] == e) & (observado["politica"] == politica)]
            medias.append(float(fila["porcentaje_cobertura"].iloc[0]))
            errores.append(0.0)
        barras = eje.bar(posiciones + desplazamiento, medias, ancho, yerr=errores, capsize=3,
                         color=COLORES[politica], label=ETIQUETAS[politica])
        eje.bar_label(barras, fmt="%.1f", fontsize=7, padding=2)
    eje.axvline(len(resumen) - 0.5, color="0.5", linestyle="--", linewidth=1)
    eje.set_xticks(posiciones, etiquetas, rotation=15)
    eje.set_ylabel("Cobertura de la demanda (%)")
    eje.set_ylim(0, 105)
    eje.set_title("Cobertura por condición: simulación (media e IC 95 %, 30 réplicas) y casos reales")
    eje.legend(loc="lower left")
    _guardar(fig, ruta)


def figura_diferencias(replicas: pd.DataFrame, ruta) -> None:
    """Distribución de la diferencia pareada de cobertura (genético − base) por condición."""
    tabla = replicas.pivot_table(index=["escenario", "replica"], columns="politica", values="porcentaje_cobertura")
    tabla["diferencia"] = tabla["genetico"] - tabla["base"]
    condiciones = list(dict.fromkeys(replicas["escenario"]))
    datos = [tabla.loc[c, "diferencia"].to_numpy() for c in condiciones]
    fig, eje = plt.subplots(figsize=(9, 5))
    # Sin atípicos del boxplot: todos los puntos ya se dibujan encima.
    eje.boxplot(datos, widths=0.5, showmeans=True, showfliers=False,
                meanprops={"marker": "D", "markerfacecolor": "white", "markeredgecolor": "black"})
    rng = np.random.default_rng(0)  # solo para separar visualmente los puntos
    for i, valores in enumerate(datos, start=1):
        eje.scatter(i + rng.uniform(-0.12, 0.12, len(valores)), valores, s=12, alpha=0.6, color=COLORES["genetico"])
    eje.axhline(0, color="black", linewidth=1, linestyle="--", label="Sin diferencia")
    eje.set_xticks(range(1, len(condiciones) + 1), [NOMBRES_CONDICION.get(c, c) for c in condiciones])
    eje.set_ylabel("Diferencia de cobertura, genético − base (puntos porcentuales)")
    eje.set_title("Variabilidad de la diferencia pareada por réplica (30 réplicas por condición)")
    eje.plot([], [], marker="D", color="white", markeredgecolor="black", linestyle="", label="Media")
    eje.legend(loc="upper right")
    _guardar(fig, ruta)


def figura_escalabilidad(resultados: pd.DataFrame, titulos: dict[str, str], ruta) -> None:
    """Objetivo J por método en cada instancia: cajas para los métodos estocásticos y líneas para los deterministas."""
    instancias = list(dict.fromkeys(resultados["instancia"]))
    fig, ejes = plt.subplots(1, len(instancias), figsize=(3.6 * len(instancias), 4.8), squeeze=False)
    for eje, instancia in zip(ejes[0], instancias):
        sub = resultados[resultados["instancia"] == instancia]
        cajas = [sub.loc[sub["metodo"] == m, "objetivo"].to_numpy() for m in ("aleatoria", "genetico")]
        eje.boxplot(cajas, widths=0.5, showfliers=False)
        rng = np.random.default_rng(0)  # solo para separar visualmente los puntos
        for i, (valores, color) in enumerate(zip(cajas, ("#ff7f0e", COLORES["genetico"])), start=1):
            eje.scatter(i + rng.uniform(-0.12, 0.12, len(valores)), valores, s=10, alpha=0.6, color=color)
        for metodo, estilo, etiqueta in (("base", ":", "Política base"), ("voraz", "--", "Voraz")):
            valor = sub.loc[sub["metodo"] == metodo, "objetivo"]
            if not valor.empty:
                eje.axhline(float(valor.iloc[0]), color="0.3", linestyle=estilo, linewidth=1.2, label=etiqueta)
        optimo = sub["optimo"].iloc[0]
        if pd.notna(optimo):
            eje.axhline(float(optimo), color="green", linewidth=1.2, label="Óptimo exacto")
        eje.set_xticks([1, 2], ["Aleatoria", "Genético"])
        eje.set_title(titulos.get(instancia, instancia), fontsize=10)
        eje.grid(alpha=0.3, axis="y")
    ejes[0][0].set_ylabel("Objetivo J (adimensional; menor es mejor)")
    etiquetas = {}
    for eje in ejes[0]:
        for manija, etiqueta in zip(*eje.get_legend_handles_labels()):
            etiquetas.setdefault(etiqueta, manija)
    fig.legend(list(etiquetas.values()), list(etiquetas.keys()), loc="lower center", ncol=len(etiquetas), fontsize=8,
               bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Escalabilidad: calidad de la solución con el mismo presupuesto de evaluaciones (30 semillas)")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=150, metadata={"Software": None})
    plt.close(fig)


def figura_dimensionamiento(planes: pd.DataFrame, ruta, metas=(80, 90, 95)) -> None:
    """Cobertura de los casos de 2024 según el número de brigadas, por capacidad y tiempo máximo de viaje."""
    umbrales = sorted(planes["umbral_min"].unique())
    capacidades = sorted(planes["capacidad"].unique())
    colores = dict(zip(capacidades, ("#d62728", "#1f77b4", "#2ca02c", "#9467bd")))
    fig, ejes = plt.subplots(1, len(umbrales), figsize=(4.6 * len(umbrales), 5.6), sharey=True, squeeze=False)
    for eje, umbral in zip(ejes[0], umbrales):
        for capacidad in capacidades:
            sub = planes[(planes["umbral_min"] == umbral) & (planes["capacidad"] == capacidad)]
            optimo = sub[sub["enfoque"] == "cobertura"].sort_values("k")
            regla = sub[sub["enfoque"] == "regla"].sort_values("k")
            eje.fill_between(optimo["k"], optimo["sim_ic95_inferior_pct"], optimo["sim_ic95_superior_pct"],
                             color=colores[capacidad], alpha=0.12)
            eje.plot(optimo["k"], optimo["cobertura_casos_2024_pct"], marker="o", color=colores[capacidad],
                     label=f"Óptimo, C = {capacidad:g}")
            eje.plot(regla["k"], regla["cobertura_casos_2024_pct"], linestyle=":", color=colores[capacidad],
                     label=f"Regla de más casos, C = {capacidad:g}")
        for meta in metas:
            eje.axhline(meta, color="0.6", linewidth=0.8, linestyle="--")
        eje.set_title(f"Tiempo máximo de viaje: {umbral:g} min")
        eje.set_xlabel("Número de brigadas")
        eje.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        eje.grid(alpha=0.3)
    ejes[0][0].set_ylabel("Cobertura de los casos reales de 2024 (%)")
    ejes[0][0].set_ylim(0, 102)
    manijas, etiquetas = ejes[0][0].get_legend_handles_labels()
    fig.legend(manijas, etiquetas, loc="lower center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, 0.01))
    fig.suptitle("Dimensionamiento en Chiquimula: cobertura según brigadas, capacidad y tiempo de viaje "
                 "(banda: IC 95 % simulado)")
    fig.tight_layout(rect=(0, 0.13, 1, 0.95))
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=150, metadata={"Software": None})
    plt.close(fig)


def figura_tamizaje(planes: pd.DataFrame, ruta, metas=(50, 80, 90)) -> None:
    """Casos identificados según el número de brigadas, por productividad y tiempo de viaje, para ambos objetivos."""
    propuestos = planes[planes["propuesto"]]
    umbrales = sorted(propuestos["umbral_min"].unique())
    productividades = sorted(propuestos["productividad"].unique())
    colores = dict(zip(productividades, ("#d62728", "#1f77b4", "#2ca02c", "#9467bd")))
    fig, ejes = plt.subplots(1, len(umbrales), figsize=(4.6 * len(umbrales), 5.6), sharey=True, squeeze=False)
    for eje, umbral in zip(ejes[0], umbrales):
        for productividad in productividades:
            sub = propuestos[(propuestos["umbral_min"] == umbral) & (propuestos["productividad"] == productividad)]
            for objetivo, estilo, nombre in (("casos", "-", "objetivo: identificar casos"),
                                             ("ninos", ":", "objetivo: evaluar niños")):
                curva = sub[sub["objetivo"] == objetivo].sort_values("k")
                eje.plot(curva["k"], curva["casos_pct"], linestyle=estilo, marker="o" if estilo == "-" else None,
                         markersize=3, color=colores[productividad], label=f"{productividad:g}/día, {nombre}")
        for meta in metas:
            eje.axhline(meta, color="0.6", linewidth=0.8, linestyle="--")
        eje.set_title(f"Tiempo máximo de viaje: {umbral:g} min")
        eje.set_xlabel("Número de brigadas")
        eje.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
        eje.grid(alpha=0.3)
    ejes[0][0].set_ylabel("Casos esperados identificados (% de los casos de 2024)")
    ejes[0][0].set_ylim(0, 102)
    manijas, etiquetas = ejes[0][0].get_legend_handles_labels()
    fig.legend(manijas, etiquetas, loc="lower center", ncol=3, fontsize=8, bbox_to_anchor=(0.5, 0.01))
    fig.suptitle("Tamizaje en Chiquimula: casos identificados según brigadas, productividad (evaluaciones/día) y viaje")
    fig.tight_layout(rect=(0, 0.13, 1, 0.95))
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=150, metadata={"Software": None})
    plt.close(fig)


def figura_convergencia(convergencia: pd.DataFrame, ruta) -> None:
    """Mejor objetivo y mediana de la población por generación."""
    fig, eje = plt.subplots(figsize=(8, 4.5))
    eje.plot(convergencia["generacion"], convergencia["mejor"], marker="o", markersize=3, label="Mejor individuo")
    eje.plot(convergencia["generacion"], convergencia["mediana"], linestyle="--", label="Mediana de la población")
    eje.set_xlabel("Generación")
    eje.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    eje.set_ylabel("Objetivo J (adimensional; menor es mejor)")
    eje.set_title("Convergencia del algoritmo genético (condición nominal, semilla raíz)")
    eje.legend()
    eje.grid(alpha=0.3)
    _guardar(fig, ruta)
