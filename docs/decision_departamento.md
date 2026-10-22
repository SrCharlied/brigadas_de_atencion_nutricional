# Decisión del departamento piloto (Tarea 0.3)

**Decisión:** **Chiquimula (GT20)**. Ratificada por el equipo el 2026-10-22.

**Evidencia:** `resultados/candidatos_departamento.csv` y `resultados/calidad_datos.json`, generados por `python -m scripts.preparar_datos --config configs/piloto_chiquimula.json`. Las cifras de este documento salen de esas salidas. Si los datos raw cambian, este documento debe revisarse.

## Criterios (plan §3, Tarea 0.3)

1. Unión completa de demanda, población y municipio.
2. Nombres y códigos territoriales reconciliables.
3. Suficiente historia utilizable en el periodo 2015–2024.
4. Tamaño manejable para la demostración y para la enumeración exacta en pruebas.
5. Volumen de casos suficiente para que la asignación sea significativa.

## Comparación de candidatos

Periodo de desarrollo 2015–2022 y de validación 2023–2024. Las tasas son casos registrados por cada 1,000 menores de 5 años, agregadas en el departamento. La distancia máxima es la geodésica entre centroides municipales.

| Criterio | **Chiquimula (GT20)** | Zacapa (GT19) | Alta Verapaz (GT16) |
|---|---|---|---|
| Municipios | **11** | 11 | 17 |
| Unión MSPAS–población–límites | **11/11** (2 por correspondencia manual) | 11/11 | 17/17 (1 manual) |
| Celdas municipio-año sin registro MSPAS (2015–2024) | **0** | 1 | 0 |
| Años completos en el periodo | **10/10** | 9/10 | 10/10 |
| Casos registrados, desarrollo | 5,314 | 3,317 | 12,233 |
| Casos registrados, validación | 2,068 | 1,266 | 6,184 |
| Tasa media, desarrollo | 12.6 | 14.3 | 9.1 |
| Tasa media, validación | 20.2 | 22.3 | 18.5 |
| Distancia máxima entre centroides | **47.4 km** | 61.9 km | 114.9 km |

## Justificación

- **Chiquimula** es el único de los tres que cumple a la vez: unión completa, ninguna celda sin registro (no hace falta tratar ausencias en el piloto), tamaño pequeño (11 municipios permiten enumerar exactamente todas las combinaciones de bases en las pruebas) y volumen suficiente (más de 5,000 casos en desarrollo).
- **Zacapa** se descarta por tener 1 celda sin registro y menos volumen. Queda como alternativa si se quiere probar el método en un segundo departamento del corredor seco.
- **Alta Verapaz** tiene más carga absoluta, pero con 17 municipios y 115 km de extensión la red es más grande, y la distancia geodésica representa peor el acceso real. Se descarta para el MVP y queda como posible extensión.

## Advertencias para las etapas siguientes

- **Aumento en el periodo de validación:** en 21 de los 22 departamentos la tasa de 2023–2024 supera la de 2015–2022 (la excepción es Huehuetenango: 7.2 frente a 7.1). Para el total nacional, ver `mspas.casos_registrados_por_anio` en `calidad_datos.json`. Es un cambio sistémico, que puede venir de un aumento de casos o de cambios en el registro, y no algo propio de Chiquimula. El modelo de demanda (Hito 3) debe decidir **antes de ver la validación** si modela la tendencia o si declara el sesgo como limitación.
- **Casos registrados no es prevalencia.** Toda cifra de este documento se refiere a registros del MSPAS.
- Las proyecciones de población del INE son proyecciones, no conteos censales.
- En las tasas departamentales, los municipio-año sin registro no suman casos pero sí población. En Chiquimula no hay ninguno, así que no afecta al piloto.
