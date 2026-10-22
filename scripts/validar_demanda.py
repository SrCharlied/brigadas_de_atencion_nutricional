"""Selección y validación del modelo de demanda según docs/protocolo_demanda.md.

1. Backtest de M0, M1 y M2 solo con los años de desarrollo y regla de decisión (§4).
2. Poisson o binomial negativa con el modelo elegido en todo el desarrollo (§5).
3. Validación única contra los años reservados (§6).

Salidas:
    resultados/demanda_backtest.json
    resultados/demanda_dispersion.json
    resultados/demanda_validacion.json
    resultados/figuras/validacion_demanda.png

Uso:
    python -m scripts.validar_demanda --config configs/piloto_chiquimula.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from brigadas import demanda  # noqa: E402
from brigadas.config import cargar_configuracion  # noqa: E402
from brigadas.datos import ErrorDatos  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
PROCESADOS = RAIZ / "data" / "processed"
RESULTADOS = RAIZ / "resultados"


def _escribir_json(ruta: Path, contenido: dict) -> None:
    ruta.write_text(json.dumps(contenido, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parametros(modelo: demanda.ModeloDemanda) -> dict:
    if modelo.nombre == "M2":
        return {
            "beta_por_anio": modelo.beta,
            "anio_centro": modelo.anio_centro,
            "interceptos_log": dict(zip(modelo.codigos, modelo.interceptos)),
        }
    return {"tasa_por_1000": {c: t * 1000 for c, t in zip(modelo.codigos, modelo.tasas)}}


ETIQUETA_MINIMA = 100  # casos; debajo de este valor los nombres se enciman


def figura_validacion(union: pd.DataFrame, nombres: dict[str, str], modelo: str, titulo: str, ruta: Path) -> None:
    fig, eje = plt.subplots(figsize=(7, 6))
    for anio, grupo in union.groupby("anio"):
        eje.scatter(grupo["casos_registrados"], grupo["mu"], label=f"{anio}", s=45, alpha=0.85)
    limite = 1.08 * max(union["casos_registrados"].max(), union["mu"].max())
    eje.plot([0, limite], [0, limite], color="0.4", linestyle="--", linewidth=1, label="Estimado = observado")
    for fila in union.itertuples():
        if max(fila.casos_registrados, fila.mu) >= ETIQUETA_MINIMA:
            eje.annotate(nombres[fila.codigo], (fila.casos_registrados, fila.mu), fontsize=7, alpha=0.75,
                         xytext=(4, 3), textcoords="offset points")
    eje.set_xlim(0, limite)
    eje.set_ylim(0, limite)
    eje.set_xlabel("Casos registrados observados (MSPAS), casos por municipio y año")
    eje.set_ylabel(f"Casos esperados por el modelo {modelo}, casos por municipio y año")
    eje.set_title(titulo)
    eje.legend(title="Año", loc="upper left")
    eje.text(0.99, 0.01, f"Sin etiqueta: municipios con menos de {ETIQUETA_MINIMA} casos", transform=eje.transAxes,
             ha="right", va="bottom", fontsize=7, color="0.35")
    eje.grid(alpha=0.3)
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=150, metadata={"Software": None})
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    config = cargar_configuracion(args.config)

    ruta_panel = PROCESADOS / f"panel_{config.departamento}.csv"
    if not ruta_panel.exists():
        print(f"ERROR: falta {ruta_panel.name}; ejecute python -m scripts.preparar_datos", file=sys.stderr)
        return 1
    panel = pd.read_csv(ruta_panel, dtype={"codigo": str})
    desarrollo = panel[panel["anio"].isin(config.anios_desarrollo)]
    validacion = panel[panel["anio"].isin(config.anios_validacion)]

    try:
        # §4: el backtest y la regla solo ven años de desarrollo.
        pliegues = demanda.backtest(desarrollo, anios_permitidos=config.anios_desarrollo)
        promedio = pliegues.groupby("modelo")["wape"].mean().to_dict()
        elegido = demanda.elegir_modelo(promedio)

        # §5: dispersión con el modelo elegido en todo el desarrollo.
        modelo = demanda.ajustar(desarrollo, elegido, config.anios_desarrollo)
        observadas = desarrollo[desarrollo["casos_registrados"].notna()]
        ajuste = observadas.merge(modelo.media(observadas), on=["codigo", "anio"])
        dispersion = demanda.evaluar_dispersion(ajuste["casos_registrados"], ajuste["mu"], modelo.parametros)

        # §6: validación única contra los años reservados.
        evaluados = {elegido: modelo}
        if elegido != "M0":
            evaluados["M0"] = demanda.ajustar(desarrollo, "M0", config.anios_desarrollo)
        validaciones = {
            nombre: demanda.metricas_validacion(validacion, m.media(validacion)) for nombre, m in evaluados.items()
        }
    except ErrorDatos as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    RESULTADOS.mkdir(parents=True, exist_ok=True)
    _escribir_json(
        RESULTADOS / "demanda_backtest.json",
        {
            "protocolo": "docs/protocolo_demanda.md §4",
            "departamento": config.departamento,
            "pliegues": pliegues.to_dict("records"),
            "wape_promedio": promedio,
            "umbral_mejora": demanda.UMBRAL_MEJORA,
            "limite_para_calificar": demanda.UMBRAL_MEJORA * promedio["M0"],
            "modelo_elegido": elegido,
        },
    )
    _escribir_json(
        RESULTADOS / "demanda_dispersion.json",
        {
            "protocolo": "docs/protocolo_demanda.md §5",
            "modelo_media": elegido,
            "observaciones": int(len(ajuste)),
            "parametros_media": modelo.parametros,
            "umbral_phi": demanda.UMBRAL_PHI,
            "nivel_significancia": demanda.NIVEL_SIGNIFICANCIA,
            **dispersion,
        },
    )
    _escribir_json(
        RESULTADOS / "demanda_validacion.json",
        {
            "protocolo": "docs/protocolo_demanda.md §6",
            "referencia": "Casos registrados MSPAS, años reservados; ver docs/fuentes.md",
            "anios_validacion": list(config.anios_validacion),
            "modelo_elegido": elegido,
            "parametros_modelo": _parametros(modelo),
            "metricas": validaciones,
            "advertencia": "Valida la demanda municipal agregada de casos registrados; no valida tiempos de atencion, "
            "capacidad de brigadas, resultados clinicos ni prevalencia.",
        },
    )
    union = validacion.merge(modelo.media(validacion), on=["codigo", "anio"])
    nombres = panel.drop_duplicates("codigo").set_index("codigo")["nombre"].to_dict()
    anios_texto = f"{min(config.anios_validacion)}-{max(config.anios_validacion)}"
    titulo = f"Validación de la demanda: observado vs. estimado ({panel['departamento'].iloc[0]}, {anios_texto})"
    figura_validacion(union, nombres, elegido, titulo, RESULTADOS / "figuras" / "validacion_demanda.png")

    print(f"WAPE promedio backtest: { {k: round(v, 4) for k, v in promedio.items()} } -> elegido {elegido}")
    print(f"dispersión: phi={dispersion['phi']:.3f}, a={dispersion['a']:.4f}, p={dispersion['valor_p']:.3g} "
          f"-> {dispersion['distribucion']}")
    for nombre, m in validaciones.items():
        print(f"validación {nombre}: MAE={m['mae']:.2f} WAPE={m['wape']:.3f} sesgo={m['sesgo_relativo']:+.3f} "
              f"spearman={m['spearman_ranking']:.3f} top3={m['coincidencia_top3']}/3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
