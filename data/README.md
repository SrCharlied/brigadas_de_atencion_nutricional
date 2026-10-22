# Datos

| Carpeta | Contenido | ¿Se versiona? |
|---|---|---|
| `raw/` | Archivos oficiales tal como se descargan. **No editar a mano.** | No; se regeneran con `python -m scripts.descargar_datos` |
| `interim/` | Intermedios temporales | No |
| `processed/` | Salidas de `scripts/preparar_datos.py` | No; se regeneran |
| `referencia/` | Tablas de correspondencia territorial revisadas por el equipo | **Sí** |
| `fuentes.json` | Catálogo de fuentes: URL, licencia y clasificación | **Sí** |
| `descargas.json` | Checksum SHA-256, tamaño y fecha de cada descarga | **Sí** |

## Tablas de referencia

- `referencia/departamentos_alias.csv`: nombres de departamento de las fuentes que difieren de HDX.
- `referencia/correspondencias_mspas.csv`: municipios del MSPAS cuyo nombre normalizado no coincide con HDX.
- `referencia/correspondencias_ine.csv`: municipios de las proyecciones INE cuyo nombre normalizado no coincide con HDX.

Cada fila de correspondencia indica el código HDX asignado y la razón.

`brigadas.datos.asignar_codigos` rechaza entradas obsoletas (pares que ya unen por nombre), códigos inexistentes, códigos de otro departamento y dos municipios asignados al mismo código.

## Salidas procesadas

`processed/panel_municipal.csv` contiene una fila por municipio × año (2012–2024):

| Columna | Significado |
|---|---|
| `casos_registrados` | Suma de casos registrados por el MSPAS (sexo y grupo etario agregados). Vacío si no hay fila en el MSPAS |
| `estado_registro` | `con_registro` / `sin_registro`. `sin_registro` **no** significa cero casos |
| `poblacion_0_4` | Proyección INE de 0–4 años (serie 2015–2030). Vacío en 2012–2014 |
| `estado_poblacion` | `con_poblacion` / `sin_poblacion` / `poblacion_cero` |
| `tasa_por_1000` | Casos registrados por cada 1,000 menores de 5 años; solo si ambos datos existen |
