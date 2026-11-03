# Protocolo de recalibración de parámetros de escenario

**Estado:** **CONGELADO** el 2026-11-03 con aprobación del equipo, antes de cualquier comparación formal entre la política base y el algoritmo genético.
**Responsable:** Integrante 1. **Afecta a:** `configs/piloto_chiquimula.json` (Integrantes 2 y 3).
**Regla de oro:** los valores salen de reglas fijadas **antes** de comparar la política base con el algoritmo genético. Después de congelar, no se cambian para mejorar resultados; cualquier cambio se registra en §6 como desviación.

## 1. Motivo

Con los valores provisionales (3 brigadas × 150 = 450 casos/año, `D_max` = 40 km), la capacidad está saturada. Al evaluar las **165 combinaciones** posibles de 3 bases en Chiquimula con el evaluador del Integrante 2:

| Demanda | Cobertura en las 165 combinaciones | ¿La base es la óptima? |
|---|---|---|
| Real 2023 (934) | 48.2 % en todas | Sí |
| Real 2024 (1,134) | 39.7 % en todas | Sí |
| Esperada 2024 con M0 (639) | 70.4 % en todas | Sí |

El problema queda resuelto de antemano y no hay nada que optimizar. Los valores eran provisionales (`_supuestos` del config), así que se recalibran con reglas explícitas.

## 2. Reglas

Solo usan datos de desarrollo (2015–2022) y la geografía. No usan 2023–2024 ni el desempeño de ninguna política.

| Parámetro | Regla | Cálculo | Valor |
|---|---|---|---|
| `cantidad_brigadas` (K) | Sin cambio | — | **3** |
| `capacidad_por_brigada` (C) | **Capacidad total = demanda registrada media anual de desarrollo**, repartida entre K y redondeada al entero | 5,314 casos / 8 años = 664.25; 664.25 / 3 = 221.4 | **221** casos por brigada y año |
| `distancia_max_km` | **Mediana de las distancias entre centroides** del departamento (matriz de `brigadas/distancias.py`), redondeada al km | Mediana de 55 pares = 22.31 km | **22** km |
| Pesos `w_c`, `w_d`, `w_e` | Sin cambio (valores del Integrante 2 en `contratos.PesosObjetivo`) | — | 1.0 / 0.1 / 0.1 |

**Justificación:**

- **Capacidad:** dimensionar los recursos a la demanda media histórica es una regla de planificación común y no depende de la técnica que se compare. Con ella, la capacidad total (663) queda cerca de la demanda esperada de 2024 (639). Las réplicas con más demanda la exceden y las que tienen menos no: es justo la zona donde elegir las bases importa.
- **Distancia:** la mediana divide los pares de municipios en dos mitades (26 de 55 quedan a 22 km o menos). Así la restricción de acceso sí limita, a diferencia de los 40 km, que dejaban dentro 53 de 55.

## 3. Sensibilidad (se fija ahora, junto con las reglas)

| Variante | Cambio | Fuente |
|---|---|---|
| Demanda +20 % | `escala = 1.2` | Plan §6 (escenario C obligatorio) |
| Demanda al nivel observado | `escala = 1.6` (2,068 / 1,285 de la validación) | `docs/protocolo_demanda.md` §10.3. Es un escenario de estrés, no de calibración |
| Capacidad −20 % | C = 177 | Plan §6 |
| Distancia anterior | `D_max` = 40 km | Valor provisional previo |

## 4. Conocimiento previo declarado

Antes de escribir estas reglas, el equipo ya vio:

1. La saturación con C = 150 (§1).
2. Una evaluación exploratoria con **C = 250** y `D_max` = 40 km, demanda esperada de 2024: la base no era óptima y el mejor objetivo era un 24 % menor.

Ninguno de esos valores se adopta. C y `D_max` salen de las reglas de §2, elegidas por principio. Después de congelar este protocolo **no se hacen más comparaciones exploratorias** entre la base y el algoritmo genético antes de los experimentos formales.

## 5. Aplicación

Al congelar:

1. Actualizar `configs/piloto_chiquimula.json` (`capacidad_por_brigada` y `distancia_max_km`) y su bloque `_supuestos`.
2. Actualizar `docs/fuentes.md` §5 y `docs/interfaz_demanda.md` §4.
3. Avisar a los Integrantes 2 y 3: hay que volver a correr `ejecutar_baseline`, y el diseño experimental debe usar las variantes de §3.

## 6. Registro de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-03 | Borrador inicial | Saturación de capacidad detectada al revisar la rama `feat/simulacion-baseline` |
| 2026-11-03 | Congelado y aplicado a `configs/piloto_chiquimula.json` | Aprobación del equipo |
