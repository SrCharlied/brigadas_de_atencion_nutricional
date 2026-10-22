# Fuentes de datos

Responsable: Integrante 1. Los checksums y fechas exactas de descarga están en `data/descargas.json`. El reporte de calidad es `resultados/calidad_datos.json`.

## 1. Casos registrados — MSPAS

- **Recurso:** Morbilidad por desnutrición aguda (por departamento y municipio), 2012–2024.
- **Portal:** <https://datosabiertos.mspas.gob.gt/api/3/action/package_show?id=desnutricion>
- **Licencia:** Creative Commons Attribution.
- **Clasificación:** dato público oficial **agregado de casos registrados**. No es prevalencia, ni necesidad clínica individual, ni demanda operativa diaria.
- **Formato observado:** UTF-8 con BOM, separador `;`, fin de línea CRLF. Columnas `Año;Departamento;Municipio;grupo_etario;sexo;cantidad`.
- **Hallazgos (descarga del 2026-10-22, UTC):**
  - 19,671 filas, sin nulos, sin duplicados en la llave año–departamento–municipio–grupo–sexo.
  - Grupos etarios `<1m`, `1m-2m`, `2m-1a`, `1a-4a`; sexo `F`/`M`.
  - `cantidad` entre 1 y 417: **no hay filas con 0**. Una combinación ausente puede ser cero casos o falta de reporte, y el archivo no permite distinguirlas. El panel la marca `sin_registro` y no la imputa.
  - **No trae códigos municipales**, solo nombres. La unión se hace por nombre normalizado más una tabla manual (ver §4).
  - 339 pares departamento–municipio. San José La Máquina (GT1021, Suchitepéquez) no aparece en ningún año.
  - El total anual sube de forma marcada desde 2020 (15,547 en 2019 frente a 27,068 en 2020). Puede reflejar un cambio en la vigilancia o el registro; hay que considerarlo al modelar la demanda.

## 2. Límites y centroides — HDX/OCHA (COD-AB)

- **Portal:** <https://data.humdata.org/dataset/cod-ab-gtm>
- **Licencia:** CC BY-IGO.
- **Clasificación:** referencia geográfica pública con atribución.
- **Archivos:** tabla `gtm_admin_boundaries.xlsx` (códigos P-code y centroides `center_lat`/`center_lon`) y `gtm_admin_boundaries.geojson.zip` (polígonos).
- **Hallazgos:** 342 unidades ADM2, de las cuales 2 son lagos (Amatitlán GT0100 y Atitlán GT0700, código terminado en `00`). El pipeline las excluye y quedan **340 municipios**. Los límites tienen fecha `valid_on` 2019-02-07.
- **Limitación:** los centroides son geométricos y no equivalen a la cabecera municipal ni al punto de acceso real.

## 3. Población 0–4 años — INE

### 3.1 Fuente principal: serie INE 2015–2030 (UNFPA en HDX)

- **Portal:** <https://data.humdata.org/dataset/municipal-population-projections-of-guatemala-by-age-and-sex-2015-2030>
- **Producción:** INE Guatemala, con apoyo de CEPAL y UNFPA ("Fuente: Instituto Nacional de Estadística 2020" en cada hoja). Población al 30 de junio de cada año.
- **Licencia:** CC0 (dominio público).
- **Clasificación:** **proyección** poblacional oficial, no censo observado.
- **Formato:** 22 libros `.xlsx` (uno por departamento) con una hoja por municipio (340 en total). Cada hoja trae secciones "Ambos sexos", "Hombres" y "Mujeres" por edad simple y grupos quinquenales.
- **No trae códigos municipales.** La unión usa el nombre del título de cada hoja ("Departamento X, municipio Y"): 318 municipios unen por nombre normalizado y 22 mediante `data/referencia/correspondencias_ine.csv`, por ejemplo "Santa María Nebaj" frente a "Nebaj". El pipeline exige que los 340 municipios unan y que cada libro corresponda al departamento esperado.
- **Defecto en el original:** las hojas de San Lorenzo (San Marcos, GT1229) y San Gaspar Ixchil (Huehuetenango, GT1329) tienen el título sin nombre de municipio. Se usa el nombre de la pestaña, y `calidad_datos.json` lo registra.
- **Validaciones por hoja:** años consecutivos; hombres + mujeres = ambos sexos en el grupo 0–4; las edades simples 0..4 suman el grupo "0 a 4"; valores enteros no negativos. Las 340 hojas las cumplen.
- **Cobertura del panel:** 2015–2024. Para 2012–2014 no hay proyección, así que esos años solo sirven para análisis de conteos.
- El portal original `datos.ine.gob.gt` no respondió el 2026-10-22, y `www.ine.gob.gt` pide captcha. Por eso se usa la republicación oficial en HDX.

### 3.2 Control: COD-PS en HDX (2022–2024)

- **Portal:** <https://data.humdata.org/dataset/cod-ps-gtm>
- **Fuente primaria declarada:** INE Guatemala, proyecciones postcensales con base en el censo 2018 conciliado (método de componentes por departamento; distribución municipal por crecimiento logístico e IPF).
- **Licencia:** CC BY-IGO.
- **Cobertura:** solo **2022, 2023 y 2024**, con P-code idénticos a los límites.
- **Uso:** control cruzado de la serie principal. **Resultado: 0 diferencias en 1,020 celdas** (340 municipios × 3 años). Esto confirma que ambas publicaciones son la misma serie del INE y que la unión por nombre de la serie principal es correcta.

## 4. Correspondencias territoriales

- 325 de 339 pares MSPAS unen por nombre normalizado (mayúsculas, sin tildes, espacios simples) dentro de su departamento.
- 14 pares unen mediante `data/referencia/correspondencias_mspas.csv`, por variantes como "San Juan La Ermita" y "San Juan Ermita" o "Quetzaltepeque" y "Quezaltepeque".
- 1 alias de departamento: MSPAS "EL PETEN" corresponde a HDX "Petén".
- Resultado: 0 pares sin unión. 1 municipio de la referencia (GT1021) sin registros del MSPAS.

## 5. Parámetros que no provienen de fuentes

Son **supuestos de escenario** del equipo (plan §2.4): no tienen fuente oficial y **no son políticas, capacidades ni metas del MSPAS**. Se fijan antes de observar resultados finales y se estudian con sensibilidad (plan §4.7 y §6). El detalle de cada valor está en el bloque `_supuestos` de `configs/piloto_chiquimula.json`.

| Parámetro | Valor | Estado | Unidad | Efecto observado en Chiquimula |
|---|---|---|---|---|
| `cantidad_brigadas` | 3 | **Provisional** | brigadas | — |
| `capacidad_por_brigada` | 150 | **Provisional** | casos registrados por brigada y año (unidad por confirmar en `docs/modelo.md`) | La capacidad total de 450 cubre el 67.7 % de la demanda media de desarrollo y el 39.7 % de 2024: la restricción está activa |
| `distancia_max_km` | 40 | **Provisional** | km geodésicos entre centroides; no es distancia vial | 53 de 55 pares están dentro del radio: la restricción casi no limita |
| Pesos `w_c`, `w_d`, `w_e` | — | Por declarar (Integrantes 2 y 3) | — | — |
| Parámetros del GA | — | Por declarar (Integrante 3) | — | — |

Los campos que **no** son supuestos se clasifican en `_clasificacion` del mismo archivo: departamento (decisión del equipo), partición temporal (congelada), réplicas (mínimo exigido) y semilla (arbitraria, registrada).

## 6. Distinción de tipos de dato

| Tipo | Ejemplos en el proyecto |
|---|---|
| Registro oficial | `casos_registrados` (MSPAS) |
| Proyección oficial | `poblacion_0_4` (proyecciones INE 2015–2030; control COD-PS) |
| Referencia geográfica | códigos P-code, centroides y polígonos (HDX) |
| Derivado | `tasa_por_1000`, `estado_registro`, `estado_poblacion` |
| Supuesto | parámetros de brigadas en `configs/` |
| Simulado | demanda por réplica (Hito 3) |
