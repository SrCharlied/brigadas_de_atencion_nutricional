"""Interfaz web local (Streamlit) para la demostración.

Uso (o doble clic en demo_web.bat):
    .\\.venv\\Scripts\\python.exe -m streamlit run app.py
Se abre en el navegador (http://localhost:8501); no necesita internet.
Usa el mismo cálculo que scripts/planificar.py.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from scripts.menu import tabla_rapida
from scripts.planificar import NOMBRES_METODO, RANGOS, calcular_plan, cargar_contexto, guardar_mapa

RAIZ = Path(__file__).resolve().parent
RESULTADOS = RAIZ / "resultados"
FIGURAS = RESULTADOS / "figuras"
ESTUDIO_PRODUCTIVIDAD = (20.0, 27.5, 35.0)
ESTUDIO_TIEMPO = (45.0, 60.0, 90.0)

st.set_page_config(page_title="Brigadas nutricionales — Chiquimula", page_icon="🩺", layout="wide")


@st.cache_resource
def contexto():
    return cargar_contexto()


@st.cache_data(show_spinner=False)
def plan(brigadas: int, productividad: float, tiempo: float, objetivo: str):
    return calcular_plan(contexto(), brigadas, productividad, tiempo, objetivo)


@st.cache_data(show_spinner=False)
def mapa(brigadas: int, productividad: float, tiempo: float, objetivo: str) -> bytes:
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = guardar_mapa(contexto(), plan(brigadas, productividad, tiempo, objetivo), Path(carpeta) / "plan.png")
        return ruta.read_bytes()


@st.cache_data
def leer_json(nombre: str) -> dict:
    return json.loads((RESULTADOS / nombre).read_text(encoding="utf-8"))


# --- Barra lateral: parámetros -----------------------------------------------------------
st.sidebar.header("Parámetros")
brigadas = st.sidebar.slider("Número de brigadas", 1, 15, 6)
productividad = st.sidebar.select_slider("Evaluaciones por brigada y día (PMA: 20 a 35)",
                                         options=[20.0, 22.5, 25.0, 27.5, 30.0, 32.5, 35.0], value=27.5)
tiempo = st.sidebar.select_slider("Viaje máximo en minutos (solo ida)", options=[30.0, 45.0, 60.0, 75.0, 90.0, 120.0],
                                  value=60.0)
objetivo_texto = st.sidebar.radio("Objetivo", ["Identificar más casos", "Evaluar a más niños"])
objetivo = "casos" if objetivo_texto.startswith("Identificar") else "ninos"
st.sidebar.caption("Supuestos: 220 días de campo al año y una ronda de tamizaje anual. "
                   "Casos esperados = niños evaluados × tasa de casos 2024 del municipio.")
bajo, alto = RANGOS["tiempo"]
if not bajo <= tiempo <= alto:
    st.sidebar.warning(f"El estudio cubrió viajes de {bajo:g} a {alto:g} min; este valor es una extrapolación.")

st.title("Brigadas de atención nutricional en Chiquimula")
st.caption("Resultados simulados con supuestos declarados; casos registrados por el MSPAS, no prevalencia.")

planificador, cuantas, resultados, supuestos = st.tabs(
    ["Planificador", "¿Cuántas brigadas?", "Resultados del estudio", "Supuestos y fuentes"])

# --- Planificador ---------------------------------------------------------------------------
with planificador:
    with st.spinner("Calculando el mejor plan…"):
        c = plan(brigadas, productividad, tiempo, objetivo)
    ctx = contexto()
    r = c.resultado
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Casos identificados", f"{100 * r.casos_identificados / ctx.casos.sum():.1f} %",
                f"{r.casos_identificados:,.0f} de {ctx.casos.sum():,.0f}", delta_color="off")
    col2.metric("Niños evaluados", f"{100 * r.ninos_evaluados / ctx.ninos.sum():.1f} %",
                f"{r.ninos_evaluados:,.0f} de {ctx.ninos.sum():,.0f}", delta_color="off")
    col3.metric("Viaje medio", f"{r.tiempo_medio_min:.1f} min")
    col4.metric("Capacidad por brigada", f"{c.capacidad:,.0f}", "evaluaciones al año", delta_color="off")

    izquierda, derecha = st.columns([3, 2])
    with izquierda:
        st.image(mapa(brigadas, productividad, tiempo, objetivo), use_container_width=True)
    with derecha:
        st.subheader("Bases")
        bases = pd.DataFrame({"municipio": [ctx.nombres[j] for j in c.conteo],
                              "brigadas": list(c.conteo.values())}).sort_values("municipio")
        st.dataframe(bases, hide_index=True, use_container_width=True)
        st.caption(f"Método: {NOMBRES_METODO[c.metodo]} ({c.segundos:.1f} s).")
    st.subheader("Detalle por municipio")
    st.dataframe(c.tabla, hide_index=True, use_container_width=True)

# --- ¿Cuántas brigadas? ---------------------------------------------------------------------
with cuantas:
    ruta = RESULTADOS / "tamizaje_planes.csv"
    if productividad not in ESTUDIO_PRODUCTIVIDAD or tiempo not in ESTUDIO_TIEMPO or not ruta.exists():
        st.info("Esta vista usa los resultados del estudio de tamizaje, que cubre 20, 27.5 o 35 evaluaciones por día "
                "y viajes de 45, 60 o 90 minutos. Elija esos valores en la barra lateral.")
    else:
        planes = pd.read_csv(ruta)
        curvas = pd.DataFrame({
            "Identificar casos": tabla_rapida(planes, productividad, tiempo, "casos").set_index("brigadas")["casos %"],
            "Evaluar niños": tabla_rapida(planes, productividad, tiempo, "ninos").set_index("brigadas")["casos %"],
        })
        st.subheader(f"Casos identificados según el número de brigadas ({productividad:g}/día, viaje ≤ {tiempo:g} min)")
        st.line_chart(curvas, x_label="Número de brigadas", y_label="Casos identificados (%)")
        st.dataframe(tabla_rapida(planes, productividad, tiempo, objetivo), hide_index=True, use_container_width=True)

# --- Resultados del estudio ---------------------------------------------------------------
with resultados:
    validacion = leer_json("demanda_validacion.json")
    m = validacion["metricas"][validacion["modelo_elegido"]]
    experimentos = leer_json("experimentos_resumen.json")
    nominal = next(f for f in experimentos["resumen"] if f["condicion"] == "nominal")
    a, b, d = st.columns(3)
    a.metric("Demanda: orden de municipios", f"Spearman {m['spearman_ranking']:.2f}",
             f"nivel {100 * m['sesgo_relativo']:+.1f} % (subestima)", delta_color="off")
    b.metric("Algoritmo genético frente a base (3 brigadas)", f"{nominal['diferencia_media_pp']:+.1f} pp",
             f"IC 95 %: {nominal['ic95_inferior_pp']:+.1f} a {nominal['ic95_superior_pp']:+.1f}", delta_color="off")
    referencia = leer_json("tamizaje_resumen.json")["referencia"]
    plan_referencia = next(p for p in referencia["planes"] if p["objetivo"] == "casos")
    d.metric(f"Propuesta ({referencia['productividad']:g}/día, meta {referencia['meta_pct']} %)",
             f"{referencia['k_minimo']} brigadas", f"{plan_referencia['casos_pct']:.0f} % de los casos esperados",
             delta_color="off")
    for archivo, pie in (
        ("tamizaje_curvas.png", "Casos identificados según brigadas, productividad y tiempo de viaje."),
        ("comparacion_escenarios.png", "Política base frente al algoritmo genético en cada condición y con casos reales."),
        ("validacion_demanda.png", "Demanda estimada frente a los casos reales de 2023-2024."),
        ("escalabilidad.png", "Escalabilidad del algoritmo genético en problemas mayores."),
    ):
        if (FIGURAS / archivo).exists():
            st.image(str(FIGURAS / archivo), caption=pie, use_container_width=True)

# --- Supuestos y fuentes ------------------------------------------------------------------
with supuestos:
    st.markdown(
        """
- **Casos registrados:** MSPAS, desnutrición aguda en menores de 5 años, 2012–2024. No son prevalencia.
- **Población de 0 a 4 años:** proyecciones del INE (2015–2030).
- **Productividad:** 20 a 35 evaluaciones por brigada y día (PMA, 2020, San Marcos).
- **Proporción de casos en operativos reales:** 1.9 % en Huehuetenango (UNICEF, 2020) y 0.4 % en Alta Verapaz (OPS, 2022).
- **Tiempos de viaje:** por carretera, con OSRM sobre OpenStreetMap.
- **Supuestos:** 220 días de campo al año; una ronda de tamizaje anual; el seguimiento de los casos detectados no se modela.
- **Método:** reparto óptimo de niños entre brigadas con programación lineal. La ubicación se calcula con enumeración exacta (hasta 5 brigadas) y, para más, con el mejor plan entre el algoritmo genético y la heurística voraz.

Detalle completo en `docs/estudio_tamizaje.md` y en el informe técnico.
"""
    )
