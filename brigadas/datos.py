"""Lectura, validación y unión de las fuentes de datos.

Fuentes: registros MSPAS de desnutrición aguda (casos registrados agregados), límites
y centroides municipales HDX/OCHA y proyecciones de población INE (serie 2015-2030 y COD-PS).
Las ausencias de registro se conservan como faltantes: nunca se convierten en cero.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import pandas as pd


class ErrorDatos(ValueError):
    """Los datos no cumplen el contrato esperado."""


COLUMNAS_MSPAS = {
    "Año": "anio",
    "Departamento": "departamento",
    "Municipio": "municipio",
    "grupo_etario": "grupo_etario",
    "sexo": "sexo",
    "cantidad": "cantidad",
}
GRUPOS_ETARIOS = frozenset({"<1m", "1m-2m", "2m-1a", "1a-4a"})
SEXOS = frozenset({"F", "M"})
LLAVE_MSPAS = ["anio", "departamento", "municipio", "grupo_etario", "sexo"]

_ENTERO_NO_NEGATIVO = re.compile(r"^\d+$")


def normalizar_nombre(texto: str) -> str:
    """Mayúsculas, sin tildes ni diacríticos y con espacios simples."""
    descompuesto = unicodedata.normalize("NFKD", str(texto))
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_marcas).strip().upper()


def sha256_archivo(ruta: str | Path) -> str:
    resumen = hashlib.sha256()
    with Path(ruta).open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def _primeros(valores, limite: int = 5) -> str:
    valores = list(dict.fromkeys(str(v) for v in valores))
    texto = ", ".join(valores[:limite])
    return texto + (", ..." if len(valores) > limite else "")


# --- MSPAS --------------------------------------------------------------------


def leer_mspas(ruta: str | Path) -> pd.DataFrame:
    """Lee el CSV oficial del MSPAS sin modificar su contenido y valida el contrato."""
    df = pd.read_csv(ruta, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    faltantes = [c for c in COLUMNAS_MSPAS if c not in df.columns]
    if faltantes:
        raise ErrorDatos(f"columnas faltantes en MSPAS: {', '.join(faltantes)}")
    df = df[list(COLUMNAS_MSPAS)].rename(columns=COLUMNAS_MSPAS)
    for columna in df.columns:
        df[columna] = df[columna].str.strip()

    for columna in ("anio", "cantidad"):
        invalidos = df.loc[~df[columna].str.fullmatch(_ENTERO_NO_NEGATIVO.pattern), columna]
        if not invalidos.empty:
            raise ErrorDatos(
                f"{columna} debe ser entero no negativo; valores inválidos: {_primeros(invalidos)}"
            )
    for columna, permitidos in (("sexo", SEXOS), ("grupo_etario", GRUPOS_ETARIOS)):
        desconocidos = df.loc[~df[columna].isin(permitidos), columna]
        if not desconocidos.empty:
            raise ErrorDatos(f"{columna} con categorías desconocidas: {_primeros(desconocidos)}")
    vacios = df.loc[(df["departamento"] == "") | (df["municipio"] == "")]
    if not vacios.empty:
        raise ErrorDatos(f"{len(vacios)} filas con departamento o municipio vacío")

    df["anio"] = df["anio"].astype(int)
    df["cantidad"] = df["cantidad"].astype(int)
    duplicadas = df.duplicated(LLAVE_MSPAS, keep=False)
    if duplicadas.any():
        raise ErrorDatos(f"{int(duplicadas.sum())} filas duplicadas en la llave {LLAVE_MSPAS}")
    return df


def agregar_mspas(df: pd.DataFrame) -> pd.DataFrame:
    """Suma casos registrados sobre sexo y grupo etario por año, departamento y municipio."""
    return (
        df.groupby(["anio", "departamento", "municipio"], as_index=False, sort=True)["cantidad"]
        .sum()
        .rename(columns={"cantidad": "casos_registrados"})
    )


# --- Referencia territorial ---------------------------------------------------


def validar_municipios(municipios: pd.DataFrame) -> pd.DataFrame:
    requeridas = ["codigo", "nombre", "codigo_departamento", "departamento", "latitud", "longitud"]
    faltantes = [c for c in requeridas if c not in municipios.columns]
    if faltantes:
        raise ErrorDatos(f"columnas faltantes en municipios: {', '.join(faltantes)}")
    duplicados = municipios.loc[municipios["codigo"].duplicated(keep=False), "codigo"]
    if not duplicados.empty:
        raise ErrorDatos(f"códigos de municipio duplicados: {_primeros(duplicados)}")
    nulos = municipios[requeridas].isna().any(axis=1)
    if nulos.any():
        raise ErrorDatos(f"municipios con campos nulos: {_primeros(municipios.loc[nulos, 'codigo'])}")
    return municipios


def leer_municipios_hdx(ruta_xlsx: str | Path) -> pd.DataFrame:
    """Municipios (ADM2) de la tabla HDX/OCHA, sin las entidades lacustres (código terminado en 00)."""
    hoja = pd.read_excel(ruta_xlsx, sheet_name="gtm_admin2", dtype={"adm2_pcode": str, "adm1_pcode": str})
    hoja = hoja.loc[~hoja["adm2_pcode"].str.endswith("00")]
    municipios = (
        hoja.rename(
            columns={
                "adm2_pcode": "codigo",
                "adm2_name": "nombre",
                "adm1_pcode": "codigo_departamento",
                "adm1_name": "departamento",
                "center_lat": "latitud",
                "center_lon": "longitud",
            }
        )[["codigo", "nombre", "codigo_departamento", "departamento", "latitud", "longitud"]]
        .sort_values("codigo")
        .reset_index(drop=True)
    )
    return validar_municipios(municipios)


def leer_alias_departamentos(ruta: str | Path) -> pd.DataFrame:
    return pd.read_csv(ruta, dtype=str, keep_default_na=False)


def leer_correspondencias(ruta: str | Path) -> pd.DataFrame:
    return pd.read_csv(ruta, dtype=str, keep_default_na=False)


def asignar_codigos(
    pares: pd.DataFrame,
    municipios: pd.DataFrame,
    alias_departamentos: pd.DataFrame,
    correspondencias: pd.DataFrame,
) -> pd.DataFrame:
    """Asigna un código municipal a cada par (departamento, municipio) del MSPAS.

    Primero por nombre normalizado dentro del departamento; después mediante la tabla
    manual de correspondencias. Los pares sin código se conservan con ``metodo_union =
    "sin_union"`` para que el reporte de calidad los muestre.
    """
    validar_municipios(municipios)
    resultado = pares[["departamento", "municipio"]].copy().reset_index(drop=True)

    alias = {
        normalizar_nombre(o): normalizar_nombre(d)
        for o, d in zip(alias_departamentos["departamento_fuente"], alias_departamentos["departamento_referencia"])
    }
    deptos_ref = (
        municipios.assign(_k=municipios["departamento"].map(normalizar_nombre))
        .drop_duplicates("_k")
        .set_index("_k")["codigo_departamento"]
    )
    clave_depto = resultado["departamento"].map(normalizar_nombre).map(lambda k: alias.get(k, k))
    resultado["codigo_departamento"] = clave_depto.map(deptos_ref)
    resultado["_km"] = resultado["municipio"].map(normalizar_nombre)

    por_nombre = municipios.assign(_km=municipios["nombre"].map(normalizar_nombre))
    repetidos = por_nombre.duplicated(["codigo_departamento", "_km"], keep=False)
    if repetidos.any():
        raise ErrorDatos(f"nombres municipales ambiguos en la referencia: {_primeros(por_nombre.loc[repetidos, 'codigo'])}")
    resultado = resultado.merge(
        por_nombre[["codigo_departamento", "_km", "codigo"]], on=["codigo_departamento", "_km"], how="left"
    )
    resultado["metodo_union"] = resultado["codigo"].notna().map({True: "nombre_normalizado", False: "sin_union"})

    if not correspondencias.empty:
        codigos_validos = municipios.set_index("codigo")["codigo_departamento"]
        inexistentes = correspondencias.loc[~correspondencias["codigo"].isin(codigos_validos.index), "codigo"]
        if not inexistentes.empty:
            raise ErrorDatos(f"correspondencias con códigos inexistentes: {_primeros(inexistentes)}")
        manual = correspondencias.assign(
            clave_depto=correspondencias["departamento_fuente"].map(normalizar_nombre),
            clave_muni=correspondencias["municipio_fuente"].map(normalizar_nombre),
        )
        if manual.duplicated(["clave_depto", "clave_muni"]).any():
            raise ErrorDatos("la tabla de correspondencias repite pares departamento-municipio")
        resultado["_kd"] = resultado["departamento"].map(normalizar_nombre)
        for fila in manual.itertuples():
            coincide = (resultado["_kd"] == fila.clave_depto) & (resultado["_km"] == fila.clave_muni)
            if not coincide.any():
                raise ErrorDatos(
                    f"correspondencia sin par en la fuente: {fila.departamento_fuente} / {fila.municipio_fuente}"
                )
            posicion = resultado.index[coincide][0]
            if resultado.at[posicion, "metodo_union"] != "sin_union":
                raise ErrorDatos(
                    f"correspondencia obsoleta: {fila.departamento_fuente} / {fila.municipio_fuente} "
                    "ya une por nombre; elimínela de la tabla"
                )
            if codigos_validos[fila.codigo] != resultado.at[posicion, "codigo_departamento"]:
                raise ErrorDatos(f"correspondencia {fila.codigo} pertenece a otro departamento")
            resultado.at[posicion, "codigo"] = fila.codigo
            resultado.at[posicion, "metodo_union"] = "correspondencia_manual"
        resultado = resultado.drop(columns="_kd")

    asignados = resultado.loc[resultado["codigo"].notna(), "codigo"]
    repetidos = asignados[asignados.duplicated(keep=False)]
    if not repetidos.empty:
        raise ErrorDatos(f"varios municipios MSPAS asignados al mismo código: {_primeros(repetidos)}")
    return resultado.drop(columns="_km")[["departamento", "municipio", "codigo_departamento", "codigo", "metodo_union"]]


# --- Población ----------------------------------------------------------------


def _hoja_adm2(ruta: Path) -> str:
    hojas = pd.ExcelFile(ruta).sheet_names
    candidatas = [h for h in hojas if "adm2" in h.lower() and "pop" in h.lower()]
    if len(candidatas) != 1:
        raise ErrorDatos(f"no se identificó una única hoja ADM2 de población en {ruta.name}: {hojas}")
    return candidatas[0]


def leer_poblacion_cod_ps(ruta: str | Path, anio: int) -> pd.DataFrame:
    """Población de 0 a 4 años por municipio desde una tabla COD-PS (INE vía HDX)."""
    ruta = Path(ruta)
    if ruta.suffix.lower() == ".csv":
        tabla = pd.read_csv(ruta, dtype={"ADM2_PCODE": str})
    else:
        tabla = pd.read_excel(ruta, sheet_name=_hoja_adm2(ruta), dtype={"ADM2_PCODE": str})
    columna_anio = next((c for c in tabla.columns if c.lower() == "year"), None)
    if columna_anio is None or "ADM2_PCODE" not in tabla or "T_00_04" not in tabla:
        raise ErrorDatos(f"{ruta.name} no tiene columnas year, ADM2_PCODE y T_00_04")
    anios = set(tabla[columna_anio].unique())
    if anios != {anio}:
        raise ErrorDatos(f"{ruta.name} contiene años {sorted(anios)}; se esperaba {anio}")
    tabla = tabla.loc[~tabla["ADM2_PCODE"].str.endswith("00")]
    if tabla["ADM2_PCODE"].duplicated().any():
        raise ErrorDatos(f"{ruta.name} tiene códigos duplicados")
    poblacion = pd.to_numeric(tabla["T_00_04"], errors="coerce")
    if poblacion.isna().any() or (poblacion < 0).any():
        raise ErrorDatos(f"{ruta.name} tiene T_00_04 nulo o negativo")
    return pd.DataFrame(
        {"codigo": tabla["ADM2_PCODE"].to_numpy(), "anio": anio, "poblacion_0_4": poblacion.astype(int).to_numpy()}
    ).sort_values("codigo", ignore_index=True)


_TITULO_INE = re.compile(r"^Departamento\s+(?P<departamento>.+?),\s*municipio\s*(?P<municipio>.*)$")
_FILA_ANIOS_INE = 7


def _valores_enteros(fila: pd.Series, contexto: str) -> list[int]:
    valores = pd.to_numeric(fila, errors="coerce")
    if valores.isna().any() or (valores < 0).any() or (valores % 1 != 0).any():
        raise ErrorDatos(f"{contexto}: valores no enteros, nulos o negativos")
    return [int(v) for v in valores]


def _leer_hoja_ine(tabla: pd.DataFrame, nombre_hoja: str, archivo: str) -> pd.DataFrame:
    contexto = f"{archivo} / {nombre_hoja}"
    titulo = _TITULO_INE.match(str(tabla.iat[1, 0]).strip())
    if titulo is None:
        raise ErrorDatos(f"{contexto}: título no reconocido: {tabla.iat[1, 0]!r}")
    municipio = titulo["municipio"].strip()
    nombre_desde = "titulo"
    if not municipio:
        # Dos hojas oficiales traen el título sin municipio; la pestaña sí lo nombra.
        municipio, nombre_desde = nombre_hoja.strip(), "hoja"

    anios = _valores_enteros(tabla.iloc[_FILA_ANIOS_INE, 1:], f"{contexto}, fila de años")
    if anios != list(range(anios[0], anios[0] + len(anios))):
        raise ErrorDatos(f"{contexto}: los años no son consecutivos: {anios}")

    etiquetas = tabla[0].map(lambda v: str(v).strip() if pd.notna(v) else "")
    columnas = slice(1, 1 + len(anios))
    secciones = {}
    for seccion in ("Ambos sexos", "Hombres", "Mujeres"):
        inicio = etiquetas.index[etiquetas == seccion]
        if len(inicio) != 1:
            raise ErrorDatos(f"{contexto}: se esperaba una sección {seccion!r}")
        fila = next((i for i in etiquetas.index[etiquetas == "0 a 4"] if i > inicio[0]), None)
        if fila is None:
            raise ErrorDatos(f"{contexto}: falta la fila '0 a 4' en {seccion!r}")
        secciones[seccion] = (fila, _valores_enteros(tabla.iloc[fila, columnas], f"{contexto}, {seccion} 0 a 4"))

    ambos = secciones["Ambos sexos"][1]
    suma_sexos = [h + m for h, m in zip(secciones["Hombres"][1], secciones["Mujeres"][1])]
    if suma_sexos != ambos:
        raise ErrorDatos(f"{contexto}: hombres + mujeres de 0 a 4 no coincide con ambos sexos")
    fila_ambos = secciones["Ambos sexos"][0]
    edades = [
        _valores_enteros(tabla.iloc[fila_ambos + 1 + edad, columnas], f"{contexto}, edad {edad}") for edad in range(5)
    ]
    if [str(etiquetas.iat[fila_ambos + 1 + e]).removesuffix(".0") for e in range(5)] != ["0", "1", "2", "3", "4"]:
        raise ErrorDatos(f"{contexto}: las edades simples 0-4 no siguen a la fila '0 a 4'")
    if [sum(col) for col in zip(*edades)] != ambos:
        raise ErrorDatos(f"{contexto}: la suma de edades simples 0-4 no coincide con '0 a 4'")

    return pd.DataFrame(
        {
            "departamento": titulo["departamento"].strip(),
            "municipio": municipio,
            "hoja": nombre_hoja,
            "nombre_desde": nombre_desde,
            "anio": anios,
            "poblacion_0_4": ambos,
        }
    )


def leer_proyeccion_ine(ruta: str | Path) -> pd.DataFrame:
    """Población de 0 a 4 años por municipio y año desde un libro departamental del INE (2015-2030).

    Cada hoja es un municipio. Se valida que hombres + mujeres = ambos sexos y que las
    edades simples 0..4 sumen el grupo "0 a 4".
    """
    ruta = Path(ruta)
    hojas = pd.read_excel(ruta, sheet_name=None, header=None)
    resultado = pd.concat(
        [_leer_hoja_ine(tabla, nombre, ruta.name) for nombre, tabla in hojas.items()], ignore_index=True
    )
    claves = resultado.drop_duplicates("hoja")[["departamento", "municipio"]].map(normalizar_nombre)
    if claves.duplicated().any():
        raise ErrorDatos(f"{ruta.name}: municipios repetidos en varias hojas")
    return resultado


def comparar_poblaciones(principal: pd.DataFrame, control: pd.DataFrame) -> pd.DataFrame:
    """Diferencias entre dos fuentes de población en los municipio-año que comparten o les faltan."""
    anios = set(control["anio"])
    combinado = principal.loc[principal["anio"].isin(anios), ["codigo", "anio", "poblacion_0_4"]].merge(
        control[["codigo", "anio", "poblacion_0_4"]],
        on=["codigo", "anio"],
        how="outer",
        suffixes=("_principal", "_control"),
    )
    combinado = combinado.rename(
        columns={"poblacion_0_4_principal": "poblacion_principal", "poblacion_0_4_control": "poblacion_control"}
    )
    combinado["poblacion_principal"] = combinado["poblacion_principal"].astype("Int64")
    combinado["poblacion_control"] = combinado["poblacion_control"].astype("Int64")
    combinado["diferencia"] = combinado["poblacion_principal"] - combinado["poblacion_control"]
    distintos = combinado["diferencia"].ne(0).fillna(True)
    return combinado.loc[distintos].sort_values(["codigo", "anio"], ignore_index=True)


# --- Panel municipio-año ------------------------------------------------------


def construir_panel(
    casos: pd.DataFrame,
    poblacion: pd.DataFrame,
    municipios: pd.DataFrame,
    anios,
) -> pd.DataFrame:
    """Panel completo municipio × año con estado explícito de cada dato.

    - ``casos_registrados`` queda faltante (NA) cuando el MSPAS no publica fila.
    - ``poblacion_0_4`` queda faltante cuando la proyección no cubre el municipio o año.
    - ``tasa_por_1000`` solo se calcula si ambos datos existen y la población es positiva.
    """
    if casos.duplicated(["codigo", "anio"]).any():
        raise ErrorDatos("casos duplicados por municipio-año")
    if poblacion.duplicated(["codigo", "anio"]).any():
        raise ErrorDatos("población duplicada por municipio-año")
    ajenos = set(casos["codigo"]) - set(municipios["codigo"])
    if ajenos:
        raise ErrorDatos(f"casos con códigos fuera de la referencia: {_primeros(sorted(ajenos))}")

    malla = pd.MultiIndex.from_product(
        [sorted(municipios["codigo"]), sorted(int(a) for a in anios)], names=["codigo", "anio"]
    ).to_frame(index=False)
    casos = casos.astype({"codigo": str, "anio": int})
    poblacion = poblacion.astype({"codigo": str, "anio": int})
    panel = (
        malla.merge(municipios[["codigo", "nombre", "codigo_departamento", "departamento"]], on="codigo")
        .merge(casos[["codigo", "anio", "casos_registrados"]], on=["codigo", "anio"], how="left")
        .merge(poblacion[["codigo", "anio", "poblacion_0_4"]], on=["codigo", "anio"], how="left")
    )
    panel["casos_registrados"] = panel["casos_registrados"].astype("Int64")
    panel["poblacion_0_4"] = panel["poblacion_0_4"].astype("Int64")
    panel["estado_registro"] = panel["casos_registrados"].notna().map({True: "con_registro", False: "sin_registro"})
    panel["estado_poblacion"] = "con_poblacion"
    panel.loc[panel["poblacion_0_4"].isna(), "estado_poblacion"] = "sin_poblacion"
    panel.loc[panel["poblacion_0_4"].eq(0).fillna(False), "estado_poblacion"] = "poblacion_cero"

    calculable = panel["casos_registrados"].notna() & (panel["estado_poblacion"] == "con_poblacion")
    tasa = pd.Series(pd.NA, index=panel.index, dtype="Float64")
    tasa[calculable] = (
        panel.loc[calculable, "casos_registrados"] / panel.loc[calculable, "poblacion_0_4"] * 1000
    ).astype("Float64")
    panel["tasa_por_1000"] = tasa
    return panel.sort_values(["codigo", "anio"], ignore_index=True)
