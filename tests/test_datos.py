import hashlib

import pandas as pd
import pytest

from brigadas import datos
from brigadas.datos import ErrorDatos

ENCABEZADO_MSPAS = "Año;Departamento;Municipio;grupo_etario;sexo;cantidad"


def escribir_mspas(ruta, filas):
    # El archivo oficial viene en UTF-8 con BOM y separador ';'.
    contenido = "\r\n".join([ENCABEZADO_MSPAS, *filas]) + "\r\n"
    ruta.write_bytes(contenido.encode("utf-8-sig"))
    return ruta


def municipios_ejemplo():
    return pd.DataFrame(
        {
            "codigo": ["GT2001", "GT2003", "GT2009", "GT1701"],
            "nombre": ["Chiquimula", "San Juan Ermita", "Quezaltepeque", "Flores"],
            "codigo_departamento": ["GT20", "GT20", "GT20", "GT17"],
            "departamento": ["Chiquimula", "Chiquimula", "Chiquimula", "Petén"],
            "latitud": [14.8, 14.76, 14.63, 16.93],
            "longitud": [-89.54, -89.43, -89.45, -89.89],
        }
    )


def departamentos_alias():
    return pd.DataFrame({"departamento_fuente": ["EL PETEN"], "departamento_referencia": ["PETEN"]})


def correspondencias_vacias():
    return pd.DataFrame(columns=["departamento_fuente", "municipio_fuente", "codigo", "nota"])


# --- normalización y checksum -------------------------------------------------


def test_normalizar_nombre_quita_tildes_espacios_y_mayusculas():
    assert datos.normalizar_nombre("  Cobán ") == "COBAN"
    assert datos.normalizar_nombre("San José  La Arada") == "SAN JOSE LA ARADA"
    assert datos.normalizar_nombre("PACHALÚN") == "PACHALUN"
    assert datos.normalizar_nombre("Peñón") == "PENON"


def test_sha256_archivo_coincide_con_hashlib(tmp_path):
    ruta = tmp_path / "x.bin"
    ruta.write_bytes(b"brigadas")
    assert datos.sha256_archivo(ruta) == hashlib.sha256(b"brigadas").hexdigest()


# --- lectura MSPAS ------------------------------------------------------------


def test_leer_mspas_lee_bom_y_separador_y_renombra(tmp_path):
    ruta = escribir_mspas(tmp_path / "m.csv", ["2020;CHIQUIMULA;JOCOTÁN;1a-4a;F;7"])
    df = datos.leer_mspas(ruta)
    assert list(df.columns) == ["anio", "departamento", "municipio", "grupo_etario", "sexo", "cantidad"]
    assert df.loc[0, "municipio"] == "JOCOTÁN"
    assert df.loc[0, "anio"] == 2020
    assert df.loc[0, "cantidad"] == 7


def test_leer_mspas_rechaza_columna_faltante(tmp_path):
    ruta = tmp_path / "m.csv"
    ruta.write_bytes("Año;Departamento;Municipio;sexo;cantidad\r\n2020;A;B;F;1\r\n".encode("utf-8-sig"))
    with pytest.raises(ErrorDatos, match="grupo_etario"):
        datos.leer_mspas(ruta)


@pytest.mark.parametrize("cantidad", ["-1", "abc", "", "2.5"])
def test_leer_mspas_rechaza_cantidad_invalida(tmp_path, cantidad):
    ruta = escribir_mspas(tmp_path / "m.csv", [f"2020;CHIQUIMULA;IPALA;1a-4a;F;{cantidad}"])
    with pytest.raises(ErrorDatos, match="cantidad"):
        datos.leer_mspas(ruta)


def test_leer_mspas_rechaza_categoria_desconocida(tmp_path):
    ruta = escribir_mspas(tmp_path / "m.csv", ["2020;CHIQUIMULA;IPALA;1a-4a;X;3"])
    with pytest.raises(ErrorDatos, match="sexo"):
        datos.leer_mspas(ruta)


def test_leer_mspas_rechaza_llave_duplicada(tmp_path):
    fila = "2020;CHIQUIMULA;IPALA;1a-4a;F;3"
    ruta = escribir_mspas(tmp_path / "m.csv", [fila, fila])
    with pytest.raises(ErrorDatos, match="duplicad"):
        datos.leer_mspas(ruta)


def test_agregar_mspas_suma_sexo_y_grupo_etario(tmp_path):
    ruta = escribir_mspas(
        tmp_path / "m.csv",
        [
            "2020;CHIQUIMULA;IPALA;1a-4a;F;3",
            "2020;CHIQUIMULA;IPALA;1a-4a;M;4",
            "2020;CHIQUIMULA;IPALA;<1m;F;1",
            "2021;CHIQUIMULA;IPALA;1a-4a;F;2",
        ],
    )
    agregado = datos.agregar_mspas(datos.leer_mspas(ruta))
    assert agregado.set_index("anio")["casos_registrados"].to_dict() == {2020: 8, 2021: 2}


# --- unión territorial --------------------------------------------------------


def pares(*filas):
    return pd.DataFrame(filas, columns=["departamento", "municipio"])


def test_asignar_codigos_une_por_nombre_normalizado_y_alias_de_departamento():
    resultado = datos.asignar_codigos(
        pares(("CHIQUIMULA", "CHIQUIMULA"), ("EL PETEN", "FLORES")),
        municipios_ejemplo(),
        departamentos_alias(),
        correspondencias_vacias(),
    )
    assert resultado["codigo"].tolist() == ["GT2001", "GT1701"]
    assert set(resultado["metodo_union"]) == {"nombre_normalizado"}


def test_asignar_codigos_aplica_correspondencia_manual():
    manual = pd.DataFrame(
        {
            "departamento_fuente": ["CHIQUIMULA"],
            "municipio_fuente": ["SAN JUAN LA ERMITA"],
            "codigo": ["GT2003"],
            "nota": ["HDX: San Juan Ermita"],
        }
    )
    resultado = datos.asignar_codigos(
        pares(("CHIQUIMULA", "SAN JUAN LA ERMITA")), municipios_ejemplo(), departamentos_alias(), manual
    )
    assert resultado.loc[0, "codigo"] == "GT2003"
    assert resultado.loc[0, "metodo_union"] == "correspondencia_manual"


def test_asignar_codigos_marca_sin_union_y_no_descarta_filas():
    resultado = datos.asignar_codigos(
        pares(("CHIQUIMULA", "QUETZALTEPEQUE"), ("CHIQUIMULA", "CHIQUIMULA")),
        municipios_ejemplo(),
        departamentos_alias(),
        correspondencias_vacias(),
    )
    assert len(resultado) == 2
    fila = resultado.set_index("municipio").loc["QUETZALTEPEQUE"]
    assert fila["metodo_union"] == "sin_union"
    assert pd.isna(fila["codigo"])


def test_asignar_codigos_rechaza_codigo_manual_inexistente():
    manual = pd.DataFrame(
        {"departamento_fuente": ["CHIQUIMULA"], "municipio_fuente": ["X"], "codigo": ["GT9999"], "nota": [""]}
    )
    with pytest.raises(ErrorDatos, match="GT9999"):
        datos.asignar_codigos(pares(("CHIQUIMULA", "X")), municipios_ejemplo(), departamentos_alias(), manual)


def test_asignar_codigos_rechaza_dos_nombres_al_mismo_codigo():
    manual = pd.DataFrame(
        {
            "departamento_fuente": ["CHIQUIMULA"],
            "municipio_fuente": ["CHIQUIMULA CABECERA"],
            "codigo": ["GT2001"],
            "nota": [""],
        }
    )
    with pytest.raises(ErrorDatos, match="GT2001"):
        datos.asignar_codigos(
            pares(("CHIQUIMULA", "CHIQUIMULA"), ("CHIQUIMULA", "CHIQUIMULA CABECERA")),
            municipios_ejemplo(),
            departamentos_alias(),
            manual,
        )


def test_asignar_codigos_rechaza_correspondencia_obsoleta():
    # Si el nombre ya une directamente, la entrada manual sobra y debe revisarse.
    manual = pd.DataFrame(
        {"departamento_fuente": ["CHIQUIMULA"], "municipio_fuente": ["CHIQUIMULA"], "codigo": ["GT2001"], "nota": [""]}
    )
    with pytest.raises(ErrorDatos, match="obsoleta"):
        datos.asignar_codigos(pares(("CHIQUIMULA", "CHIQUIMULA")), municipios_ejemplo(), departamentos_alias(), manual)


def test_validar_municipios_rechaza_codigos_duplicados():
    municipios = municipios_ejemplo()
    municipios.loc[1, "codigo"] = "GT2001"
    with pytest.raises(ErrorDatos, match="duplicad"):
        datos.validar_municipios(municipios)


# --- panel municipio-año ------------------------------------------------------


def test_panel_no_convierte_ausencia_en_cero():
    casos = pd.DataFrame({"codigo": ["GT2001"], "anio": [2022], "casos_registrados": [10]})
    poblacion = pd.DataFrame({"codigo": ["GT2001", "GT2001"], "anio": [2022, 2023], "poblacion_0_4": [2000, 1990]})
    panel = datos.construir_panel(casos, poblacion, municipios_ejemplo().iloc[:1], anios=[2022, 2023])

    fila_2023 = panel.set_index("anio").loc[2023]
    assert pd.isna(fila_2023["casos_registrados"])
    assert fila_2023["estado_registro"] == "sin_registro"
    assert pd.isna(fila_2023["tasa_por_1000"])

    fila_2022 = panel.set_index("anio").loc[2022]
    assert fila_2022["casos_registrados"] == 10
    assert fila_2022["estado_registro"] == "con_registro"
    assert fila_2022["tasa_por_1000"] == pytest.approx(5.0)


def test_panel_marca_municipio_ausente_en_poblacion():
    casos = pd.DataFrame({"codigo": ["GT2003"], "anio": [2022], "casos_registrados": [4]})
    poblacion = pd.DataFrame({"codigo": ["GT2001"], "anio": [2022], "poblacion_0_4": [2000]})
    panel = datos.construir_panel(casos, poblacion, municipios_ejemplo().iloc[:2], anios=[2022])

    fila = panel.set_index("codigo").loc["GT2003"]
    assert fila["casos_registrados"] == 4
    assert fila["estado_poblacion"] == "sin_poblacion"
    assert pd.isna(fila["poblacion_0_4"])
    assert pd.isna(fila["tasa_por_1000"])


def test_panel_cubre_todas_las_combinaciones_municipio_anio():
    casos = pd.DataFrame(columns=["codigo", "anio", "casos_registrados"])
    poblacion = pd.DataFrame(columns=["codigo", "anio", "poblacion_0_4"])
    panel = datos.construir_panel(casos, poblacion, municipios_ejemplo(), anios=[2022, 2023])
    assert len(panel) == len(municipios_ejemplo()) * 2
    assert not panel.duplicated(["codigo", "anio"]).any()


def test_panel_rechaza_casos_duplicados_por_municipio_anio():
    casos = pd.DataFrame({"codigo": ["GT2001", "GT2001"], "anio": [2022, 2022], "casos_registrados": [1, 2]})
    poblacion = pd.DataFrame(columns=["codigo", "anio", "poblacion_0_4"])
    with pytest.raises(ErrorDatos, match="duplicad"):
        datos.construir_panel(casos, poblacion, municipios_ejemplo(), anios=[2022])


# --- población ----------------------------------------------------------------


def test_leer_poblacion_cod_ps_csv(tmp_path):
    ruta = tmp_path / "pob.csv"
    pd.DataFrame(
        {"Year": [2024, 2024], "ADM2_PCODE": ["GT2001", "GT0100"], "T_00_04": [11952, 0], "F_00_04": [5900, 0]}
    ).to_csv(ruta, index=False)
    pob = datos.leer_poblacion_cod_ps(ruta, anio=2024)
    # Los lagos (código terminado en 00) no son municipios.
    assert pob.to_dict("records") == [{"codigo": "GT2001", "anio": 2024, "poblacion_0_4": 11952}]


def test_leer_poblacion_cod_ps_rechaza_anio_distinto(tmp_path):
    ruta = tmp_path / "pob.csv"
    pd.DataFrame({"Year": [2023], "ADM2_PCODE": ["GT2001"], "T_00_04": [1]}).to_csv(ruta, index=False)
    with pytest.raises(ErrorDatos, match="2024"):
        datos.leer_poblacion_cod_ps(ruta, anio=2024)


# --- proyecciones INE 2015-2030 ----------------------------------------------


def hoja_ine(municipio="Ipala", anios=(2015, 2016), hombres=(6, 5), mujeres=(4, 5), edades_extra=0):
    """Reproduce el formato de los libros INE: una hoja por municipio y tres secciones por sexo."""
    ancho = len(anios) + 1
    vacia = [None] * ancho

    def fila(etiqueta, valores):
        return [etiqueta, *valores]

    def seccion(nombre, totales_0_4):
        # Reparte el total 0-4 entre las edades simples 0..4 de forma exacta.
        edades = []
        for edad in range(5):
            edades.append(fila(edad, [t // 5 + (1 if edad < t % 5 else 0) for t in totales_0_4]))
        return [
            fila(nombre, [None] * len(anios)),
            fila("Total", [t * 10 for t in totales_0_4]),
            fila("0 a 4", list(totales_0_4)),
            *edades,
        ]

    ambos = [h + m for h, m in zip(hombres, mujeres)]
    filas = [
        vacia,
        fila(f"Departamento Chiquimula, municipio {municipio}", [None] * len(anios)),
        fila("Estimaciones y proyecciones de la población total según sexo y edad.", [None] * len(anios)),
        vacia,
        vacia,
        vacia,
        fila("Sexo y grupos de edad", ["Años", *[None] * (len(anios) - 1)]),
        fila(None, list(anios)),
        *seccion("Ambos sexos", ambos),
        *seccion("Hombres", list(hombres)),
        *seccion("Mujeres", list(mujeres)),
        fila("Fuente: Instituto Nacional de Estadística  2020", [None] * len(anios)),
    ]
    tabla = pd.DataFrame(filas)
    if edades_extra:
        tabla.iloc[11, 1] = tabla.iloc[11, 1] + edades_extra
    return tabla


def escribir_libro(ruta, hojas):
    with pd.ExcelWriter(ruta) as libro:
        for nombre, tabla in hojas.items():
            tabla.to_excel(libro, sheet_name=nombre, header=False, index=False)
    return ruta


def test_leer_proyeccion_ine_extrae_0_4_por_anio(tmp_path):
    ruta = escribir_libro(tmp_path / "20.xlsx", {"Ipala": hoja_ine()})
    pob = datos.leer_proyeccion_ine(ruta)
    assert pob[["departamento", "municipio", "anio", "poblacion_0_4"]].to_dict("records") == [
        {"departamento": "Chiquimula", "municipio": "Ipala", "anio": 2015, "poblacion_0_4": 10},
        {"departamento": "Chiquimula", "municipio": "Ipala", "anio": 2016, "poblacion_0_4": 10},
    ]
    assert set(pob["nombre_desde"]) == {"titulo"}


def test_leer_proyeccion_ine_usa_nombre_de_hoja_si_titulo_vacio(tmp_path):
    ruta = escribir_libro(tmp_path / "20.xlsx", {"San Lorenzo": hoja_ine(municipio="")})
    pob = datos.leer_proyeccion_ine(ruta)
    assert set(pob["municipio"]) == {"San Lorenzo"}
    assert set(pob["nombre_desde"]) == {"hoja"}


def test_leer_proyeccion_ine_rechaza_sexos_que_no_suman(tmp_path):
    tabla = hoja_ine()
    tabla.iloc[10, 1] = 99  # "0 a 4" de ambos sexos distinto de hombres + mujeres
    ruta = escribir_libro(tmp_path / "20.xlsx", {"Ipala": tabla})
    with pytest.raises(ErrorDatos, match="hombres"):
        datos.leer_proyeccion_ine(ruta)


def test_leer_proyeccion_ine_rechaza_edades_simples_que_no_suman(tmp_path):
    ruta = escribir_libro(tmp_path / "20.xlsx", {"Ipala": hoja_ine(edades_extra=1)})
    with pytest.raises(ErrorDatos, match="edades"):
        datos.leer_proyeccion_ine(ruta)


def test_leer_proyeccion_ine_rechaza_anios_no_consecutivos(tmp_path):
    ruta = escribir_libro(tmp_path / "20.xlsx", {"Ipala": hoja_ine(anios=(2015, 2017))})
    with pytest.raises(ErrorDatos, match="consecutivos"):
        datos.leer_proyeccion_ine(ruta)


def test_leer_proyeccion_ine_rechaza_municipio_repetido(tmp_path):
    ruta = escribir_libro(tmp_path / "20.xlsx", {"Ipala": hoja_ine(), "Ipala (2)": hoja_ine()})
    with pytest.raises(ErrorDatos, match="repetid"):
        datos.leer_proyeccion_ine(ruta)


def test_comparar_poblaciones_reporta_solo_diferencias():
    principal = pd.DataFrame({"codigo": ["A", "A", "B"], "anio": [2022, 2023, 2022], "poblacion_0_4": [10, 11, 5]})
    control = pd.DataFrame({"codigo": ["A", "A", "B"], "anio": [2022, 2023, 2022], "poblacion_0_4": [10, 12, 5]})
    diferencias = datos.comparar_poblaciones(principal, control)
    assert diferencias.to_dict("records") == [
        {"codigo": "A", "anio": 2023, "poblacion_principal": 11, "poblacion_control": 12, "diferencia": -1}
    ]


def test_comparar_poblaciones_reporta_faltantes_en_cualquiera():
    principal = pd.DataFrame({"codigo": ["A"], "anio": [2022], "poblacion_0_4": [10]})
    control = pd.DataFrame({"codigo": ["B"], "anio": [2022], "poblacion_0_4": [5]})
    diferencias = datos.comparar_poblaciones(principal, control)
    assert sorted(diferencias["codigo"]) == ["A", "B"]
