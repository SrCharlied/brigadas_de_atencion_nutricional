"""Prepara el panel municipio-año y el reporte de calidad de datos.

Entradas: data/raw (verificado contra data/descargas.json) y data/referencia.
Salidas (sin marcas de tiempo, para que dos ejecuciones produzcan archivos idénticos):
    data/processed/municipios.csv
    data/processed/panel_municipal.csv
    data/processed/panel_<departamento>.csv
    resultados/calidad_datos.json
    resultados/union_municipios.csv
    resultados/candidatos_departamento.csv

Uso:
    python -m scripts.preparar_datos --config configs/piloto_chiquimula.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from brigadas import datos
from brigadas.config import cargar_configuracion

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "data" / "fuentes.json"
REGISTRO = RAIZ / "data" / "descargas.json"
REFERENCIA = RAIZ / "data" / "referencia"
PROCESADOS = RAIZ / "data" / "processed"
RESULTADOS = RAIZ / "resultados"


def verificar_raw(fuentes: list[dict], registro: dict) -> dict[str, Path]:
    rutas = {}
    for fuente in fuentes:
        entrada = registro.get(fuente["id"])
        ruta = RAIZ / "data" / "raw" / fuente["archivo"]
        if entrada is None or not ruta.exists():
            raise datos.ErrorDatos(f"falta {ruta.name}; ejecute python -m scripts.descargar_datos")
        if datos.sha256_archivo(ruta) != entrada["sha256"]:
            raise datos.ErrorDatos(f"{ruta.name} no coincide con su checksum registrado")
        rutas[fuente["id"]] = ruta
    return rutas


def _conteo(serie: pd.Series) -> dict:
    return {str(k): int(v) for k, v in serie.items()}


def resumen_mspas(largo: pd.DataFrame) -> dict:
    pares_por_anio = largo.drop_duplicates(["anio", "departamento", "municipio"]).groupby("anio").size()
    return {
        "codificacion": "utf-8 con BOM",
        "separador": ";",
        "columnas_originales": list(datos.COLUMNAS_MSPAS),
        "filas": len(largo),
        "anios": sorted(int(a) for a in largo["anio"].unique()),
        "filas_por_anio": _conteo(largo.groupby("anio").size()),
        "casos_registrados_por_anio": _conteo(largo.groupby("anio")["cantidad"].sum()),
        "filas_por_grupo_etario": _conteo(largo.groupby("grupo_etario").size()),
        "filas_por_sexo": _conteo(largo.groupby("sexo").size()),
        "cantidad_min": int(largo["cantidad"].min()),
        "cantidad_max": int(largo["cantidad"].max()),
        "filas_con_cantidad_cero": int((largo["cantidad"] == 0).sum()),
        "departamentos": int(largo["departamento"].nunique()),
        "pares_departamento_municipio": int(len(largo[["departamento", "municipio"]].drop_duplicates())),
        "pares_con_registro_por_anio": _conteo(pares_por_anio),
        "filas_duplicadas": 0,  # leer_mspas rechaza duplicados antes de llegar aquí
    }


def tabla_union(union: pd.DataFrame, municipios: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    registro = panel.groupby("codigo").agg(
        anios_con_registro=("estado_registro", lambda s: int((s == "con_registro").sum())),
        anios_sin_registro=("estado_registro", lambda s: int((s == "sin_registro").sum())),
        anios_con_poblacion=("estado_poblacion", lambda s: int((s == "con_poblacion").sum())),
    )
    tabla = municipios[["codigo", "codigo_departamento", "departamento", "nombre"]].merge(
        union[["codigo", "departamento", "municipio", "metodo_union"]].rename(
            columns={"departamento": "departamento_mspas", "municipio": "municipio_mspas"}
        ),
        on="codigo",
        how="outer",
    )
    tabla["metodo_union"] = tabla["metodo_union"].fillna("sin_registro_mspas")
    tabla = tabla.merge(registro, on="codigo", how="left")
    return tabla.sort_values(["codigo_departamento", "codigo", "municipio_mspas"], na_position="last", ignore_index=True)


def comparar_departamentos(panel: pd.DataFrame, union: pd.DataFrame, config) -> pd.DataFrame:
    desarrollo, validacion = list(config.anios_desarrollo), list(config.anios_validacion)
    filas = []
    for (codigo_depto, nombre), grupo in panel.groupby(["codigo_departamento", "departamento"]):
        pares = union[union["codigo_departamento"] == codigo_depto]
        periodo = grupo[grupo["anio"].isin(desarrollo + validacion)]
        completos = periodo.groupby("anio")["estado_registro"].apply(lambda s: (s == "con_registro").all())
        ultimo = grupo[grupo["anio"] == max(validacion)]
        casos_ultimo = ultimo["casos_registrados"].sum(skipna=True)
        poblacion_ultimo = ultimo["poblacion_0_4"].sum(skipna=True)
        filas.append(
            {
                "codigo_departamento": codigo_depto,
                "departamento": nombre,
                "municipios_referencia": grupo["codigo"].nunique(),
                "pares_mspas": len(pares),
                "pares_sin_union": int((pares["metodo_union"] == "sin_union").sum()),
                "pares_correspondencia_manual": int((pares["metodo_union"] == "correspondencia_manual").sum()),
                "municipios_nunca_registrados": int(
                    grupo.groupby("codigo")["estado_registro"].apply(lambda s: (s == "sin_registro").all()).sum()
                ),
                "celdas_sin_registro_periodo": int((periodo["estado_registro"] == "sin_registro").sum()),
                "anios_completos_periodo": int(completos.sum()),
                "anios_periodo": len(desarrollo) + len(validacion),
                "casos_desarrollo": int(grupo.loc[grupo["anio"].isin(desarrollo), "casos_registrados"].sum(skipna=True)),
                "casos_validacion": int(grupo.loc[grupo["anio"].isin(validacion), "casos_registrados"].sum(skipna=True)),
                f"casos_{max(validacion)}": int(casos_ultimo),
                f"poblacion_0_4_{max(validacion)}": int(poblacion_ultimo),
                f"tasa_por_1000_{max(validacion)}": round(float(casos_ultimo / poblacion_ultimo * 1000), 3)
                if poblacion_ultimo
                else None,
            }
        )
    return pd.DataFrame(filas).sort_values("codigo_departamento", ignore_index=True)


def observaciones(resumen: dict, union_tabla: pd.DataFrame, anios_poblacion: list[int], anios: list[int]) -> list[str]:
    notas = []
    if resumen["filas_con_cantidad_cero"] == 0:
        notas.append(
            "El CSV del MSPAS no contiene filas con cantidad 0: un municipio-año sin fila puede ser cero casos "
            "o falta de reporte. El panel lo marca como 'sin_registro' y no lo imputa."
        )
    sin_union = union_tabla[union_tabla["metodo_union"] == "sin_union"]
    if not sin_union.empty:
        notas.append(f"{len(sin_union)} pares MSPAS sin código municipal; revisar data/referencia.")
    nunca = union_tabla[union_tabla["metodo_union"] == "sin_registro_mspas"]
    for fila in nunca.itertuples():
        notas.append(
            f"{fila.codigo} {fila.nombre} ({fila.departamento}) existe en la referencia pero no aparece en el MSPAS "
            "en ningún año; no se asume cero."
        )
    faltantes = [a for a in anios if a not in anios_poblacion]
    if faltantes:
        notas.append(
            f"Sin población municipal 0-4 para {faltantes}: la serie de proyecciones INE comienza en "
            f"{anios_poblacion[0]}. Esos años solo admiten análisis de conteos absolutos."
        )
    return notas


def preparar_poblacion_ine(
    fuentes: list[dict], rutas: dict[str, Path], municipios: pd.DataFrame, alias: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Población 0-4 desde los 22 libros INE, con código municipal y unión completa obligatoria."""
    largo = []
    for fuente in (f for f in fuentes if f.get("uso") == "poblacion_principal"):
        libro = datos.leer_proyeccion_ine(rutas[fuente["id"]])
        libro["codigo_departamento_catalogo"] = fuente["codigo_departamento"]
        largo.append(libro)
    largo = pd.concat(largo, ignore_index=True)
    pares = largo[["departamento", "municipio", "nombre_desde", "codigo_departamento_catalogo"]].drop_duplicates()
    union = datos.asignar_codigos(
        pares, municipios, alias, datos.leer_correspondencias(REFERENCIA / "correspondencias_ine.csv")
    )
    union = union.merge(pares, on=["departamento", "municipio"])
    otro_departamento = union["codigo_departamento"] != union["codigo_departamento_catalogo"]
    if otro_departamento.any():
        raise datos.ErrorDatos(f"libros INE con departamento inesperado: {union.loc[otro_departamento, 'departamento'].unique()}")
    if (union["metodo_union"] == "sin_union").any():
        sin = union.loc[union["metodo_union"] == "sin_union", ["departamento", "municipio"]].to_dict("records")
        raise datos.ErrorDatos(f"municipios INE sin código: {sin}")
    faltantes = set(municipios["codigo"]) - set(union["codigo"])
    if faltantes:
        raise datos.ErrorDatos(f"municipios de la referencia sin proyección INE: {sorted(faltantes)}")
    poblacion = largo.merge(union[["departamento", "municipio", "codigo"]], on=["departamento", "municipio"])
    return poblacion[["codigo", "anio", "poblacion_0_4"]].sort_values(["codigo", "anio"], ignore_index=True), union


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    config = cargar_configuracion(args.config)

    fuentes = json.loads(CATALOGO.read_text(encoding="utf-8"))["fuentes"]
    registro = json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.exists() else {}
    try:
        rutas = verificar_raw(fuentes, registro)
        largo = datos.leer_mspas(rutas["mspas_desnutricion_aguda"])
        agregado = datos.agregar_mspas(largo)
        municipios = datos.leer_municipios_hdx(rutas["hdx_limites_tabla"])
        if config.departamento not in set(municipios["codigo_departamento"]):
            raise datos.ErrorDatos(f"departamento {config.departamento} no existe en la referencia")
        alias = datos.leer_alias_departamentos(REFERENCIA / "departamentos_alias.csv")
        union = datos.asignar_codigos(
            agregado[["departamento", "municipio"]].drop_duplicates(),
            municipios,
            alias,
            datos.leer_correspondencias(REFERENCIA / "correspondencias_mspas.csv"),
        )
        casos = agregado.merge(union, on=["departamento", "municipio"])
        casos = casos.loc[casos["codigo"].notna(), ["codigo", "anio", "casos_registrados"]]
        poblacion, union_ine = preparar_poblacion_ine(fuentes, rutas, municipios, alias)
        control = pd.concat(
            [
                datos.leer_poblacion_cod_ps(rutas[f["id"]], f["anio_poblacion"])
                for f in fuentes
                if f.get("uso") == "control_poblacion"
            ],
            ignore_index=True,
        )
        diferencias = datos.comparar_poblaciones(poblacion, control)
        anios = sorted(int(a) for a in largo["anio"].unique())
        panel = datos.construir_panel(casos, poblacion, municipios, anios)
    except datos.ErrorDatos as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    union_tabla = tabla_union(union, municipios, panel)
    candidatos = comparar_departamentos(panel, union, config)
    piloto = panel[panel["codigo_departamento"] == config.departamento]
    resumen = resumen_mspas(largo)
    anios_poblacion = sorted(int(a) for a in poblacion.loc[poblacion["anio"].isin(anios), "anio"].unique())

    calidad = {
        "fuentes": {
            f["id"]: {"archivo": registro[f["id"]]["archivo"], "sha256": registro[f["id"]]["sha256"]} for f in fuentes
        },
        "mspas": resumen,
        "union": {
            "pares_mspas": len(union),
            "por_metodo": _conteo(union.groupby("metodo_union").size()),
            "pares_sin_union": union.loc[union["metodo_union"] == "sin_union", ["departamento", "municipio"]].to_dict(
                "records"
            ),
            "municipios_referencia": len(municipios),
            "municipios_sin_registro_mspas": union_tabla.loc[
                union_tabla["metodo_union"] == "sin_registro_mspas", ["codigo", "nombre", "departamento"]
            ].to_dict("records"),
        },
        "poblacion": {
            "fuente": "INE, proyecciones municipales 2015-2030 por sexo y edad simple (UNFPA en HDX)",
            "anios_fuente": [int(poblacion["anio"].min()), int(poblacion["anio"].max())],
            "anios_en_panel": anios_poblacion,
            "municipios_por_anio": _conteo(poblacion.groupby("anio").size()),
            "anios_mspas_sin_poblacion": [a for a in anios if a not in anios_poblacion],
            "union_ine": {
                "por_metodo": _conteo(union_ine.groupby("metodo_union").size()),
                "nombre_tomado_de_pestana": union_ine.loc[
                    union_ine["nombre_desde"] == "hoja", ["codigo", "departamento", "municipio"]
                ].to_dict("records"),
            },
            "control_cod_ps": {
                "anios": sorted(int(a) for a in control["anio"].unique()),
                "celdas_comparadas": int(len(control)),
                "celdas_distintas": int(len(diferencias)),
                "diferencias": diferencias.astype({"anio": int}).to_dict("records"),
            },
        },
        "panel": {
            "celdas": len(panel),
            "con_registro_por_anio": _conteo(panel[panel["estado_registro"] == "con_registro"].groupby("anio").size()),
            "sin_registro_por_anio": _conteo(
                panel[panel["estado_registro"] == "sin_registro"].groupby("anio").size().reindex(anios, fill_value=0)
            ),
            "con_tasa_por_anio": _conteo(panel[panel["tasa_por_1000"].notna()].groupby("anio").size()),
        },
        "piloto": {
            "departamento": config.departamento,
            "municipios": int(piloto["codigo"].nunique()),
            "casos_registrados_por_anio": _conteo(piloto.groupby("anio")["casos_registrados"].sum()),
            "celdas_sin_registro": piloto.loc[piloto["estado_registro"] == "sin_registro", ["codigo", "nombre", "anio"]]
            .astype({"anio": int})
            .to_dict("records"),
        },
        "observaciones": observaciones(resumen, union_tabla, anios_poblacion, anios),
    }

    PROCESADOS.mkdir(parents=True, exist_ok=True)
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    municipios.to_csv(PROCESADOS / "municipios.csv", index=False, lineterminator="\n")
    panel.to_csv(PROCESADOS / "panel_municipal.csv", index=False, lineterminator="\n")
    piloto.to_csv(PROCESADOS / f"panel_{config.departamento}.csv", index=False, lineterminator="\n")
    union_tabla.to_csv(RESULTADOS / "union_municipios.csv", index=False, lineterminator="\n")
    candidatos.to_csv(RESULTADOS / "candidatos_departamento.csv", index=False, lineterminator="\n")
    (RESULTADOS / "calidad_datos.json").write_text(
        json.dumps(calidad, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"panel: {len(panel)} celdas, {panel['codigo'].nunique()} municipios, años {anios[0]}-{anios[-1]}")
    print(f"unión: {calidad['union']['por_metodo']}")
    for nota in calidad["observaciones"]:
        print(f"- {nota}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
