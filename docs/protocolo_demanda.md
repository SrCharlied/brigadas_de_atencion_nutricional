# Protocolo de selección y validación del modelo de demanda

**Estado:** **CONGELADO** el 2026-10-22 con aprobación del equipo, antes de ejecutar el backtest con datos reales.
**Responsable:** Integrante 1.
**Regla de oro:** este protocolo se congela **antes** de ejecutar el backtest con datos reales. Cualquier cambio posterior se registra en §9 como desviación, con fecha y motivo.

## 1. Objetivo

Elegir, usando solo el periodo de desarrollo, cómo estimar la demanda municipal esperada (casos registrados por año) y cómo generar su variabilidad aleatoria para la simulación. Después, validar ese modelo **una sola vez** contra los registros reservados del MSPAS de 2023–2024.

## 2. Datos

- **Unidad:** municipio-año en Chiquimula (GT20, 11 municipios). Fuente: `data/processed/panel_GT20.csv`.
- **Variable respuesta:** `casos_registrados` (MSPAS).
- **Exposición:** `poblacion_0_4` (proyección INE). La población de 2023–2024 puede usarse para predecir esos años: es una proyección publicada, no el resultado que se valida.
- **Desarrollo:** 2015–2022 (88 observaciones). **Validación:** 2023–2024 (22 observaciones).
- **Celdas `sin_registro`:** se excluyen del ajuste y de las métricas, se reportan y no se imputan como cero. En Chiquimula no hay ninguna.

## 3. Modelos candidatos de la media

`y_it` son los casos del municipio `i` en el año `t`; `P_it`, su población de 0–4 años; `μ_it`, los casos esperados.

| Modelo | Ajuste con los años de entrenamiento `T` | Predicción |
|---|---|---|
| **M0: media estable** | `r_i = Σ_T y_it / Σ_T P_it` (tasa agregada del municipio en todo `T`) | `μ_it = r_i · P_it` |
| **M1: nivel reciente** | Igual que M0, pero solo con los **3 últimos años** de `T` | `μ_it = r_i · P_it` |
| **M2: tendencia común** | `log μ_it = α_i + β·(t − t̄) + log P_it`, con un intercepto por municipio y **una pendiente común**, estimado por máxima verosimilitud Poisson | Extrapola `β` a los años objetivo |

En M2, la estimación Poisson de la media sigue siendo consistente aunque haya sobredispersión (cuasi-verosimilitud). La dispersión se trata aparte, en §5.

Número de parámetros de la media (`p`): M0 = 11, M1 = 11, M2 = 12.

## 4. Selección de la media: backtest con origen móvil

Horizonte de 2 años, igual que la validación real.

| Pliegue | Entrenamiento `T` | Prueba |
|---|---|---|
| 1 | 2015–2018 | 2019–2020 |
| 2 | 2015–2019 | 2020–2021 |
| 3 | 2015–2020 | 2021–2022 |

**Métrica de decisión:** `WAPE = Σ|y − μ| / Σ y` sobre los municipio-año de prueba, promediada sin ponderar entre los 3 pliegues. Como información adicional, no para decidir, se reportan el MAE municipal y el sesgo `Σ(μ − y) / Σ y`.

**Regla de decisión (fijada antes de ejecutar):**

1. Se calcula el WAPE promedio de cada modelo.
2. Un modelo más complejo (M1 o M2) **califica** si su WAPE es ≤ 0.90 × WAPE(M0), es decir, si mejora a M0 en al menos un 10 %.
3. Si ninguno califica, se elige **M0**. Si califica uno, se elige ese. Si califican los dos, se elige el de menor WAPE; si empatan, el más simple (M1 antes que M2).

## 5. Selección de la distribución: Poisson o binomial negativa

Con el modelo de media elegido, ajustado en **todo** 2015–2022:

1. Se calcula la dispersión de Pearson: `φ = Σ (y − μ)² / μ / (n − p)`, con n = 88.
2. Se ajusta una binomial negativa NB2 (`Var = μ + a·μ²`), dejando `μ` fijo en los valores del modelo elegido y estimando `a ≥ 0` por máxima verosimilitud.
3. Se calcula la razón de verosimilitudes `LR = 2(ℓ_NB − ℓ_Poisson)`. Como `a = 0` está en la frontera, el valor p es `0.5 · P(χ²₁ > LR)`.
4. **Regla:** se usa binomial negativa si `φ > 1.5` **y** `p < 0.05`; si no, Poisson.

## 6. Validación final (una sola ejecución)

1. Se ajusta el modelo elegido en 2015–2022 y se predicen 2023 y 2024.
2. Se reporta contra los registros del MSPAS:
   - MAE municipal (casos por municipio y año);
   - WAPE;
   - sesgo con signo, en casos y en porcentaje;
   - error por año (total previsto frente a observado);
   - ranking de carga: correlación de Spearman y coincidencia de los 3 municipios con más casos;
   - gráfico de observado frente a estimado;
   - el mismo análisis para M0, como modelo de referencia, si el elegido no es M0.
3. Esto valida **la demanda municipal agregada**. No valida tiempos de atención, capacidad de las brigadas, resultados clínicos ni prevalencia real.

## 7. Interfaz para la simulación (Integrantes 2 y 3)

`brigadas/demanda.py` ofrecerá:

- `μ_i` por municipio para un año objetivo, ajustado solo con los años de desarrollo;
- generación de escenarios `d_i ~ Poisson(μ_i)` o `NB2(μ_i, a)` con un `numpy.random.Generator` explícito, sin estado aleatorio global;
- un multiplicador de escala para la sensibilidad de demanda +20 %.

El año objetivo de los experimentos lo define `docs/diseno_experimental.md`.

## 8. Conocimiento previo declarado

Durante el perfil de calidad de datos (Tarea 0.2) y la decisión del departamento (Tarea 0.3), el equipo **ya vio** los totales de casos y las tasas agregadas de 2023–2024 de Chiquimula y del país: en general suben respecto de 2015–2022 (`docs/decision_departamento.md`). Ningún parámetro se ajusta con esos años. Este protocolo limita el efecto de ese conocimiento fijando de antemano candidatos, pliegues, métrica y umbrales. El informe lo declara como limitación.

## 9. Registro de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-10-22 | Borrador inicial | — |
| 2026-10-22 | Congelado | Aprobación del equipo antes de ejecutar el backtest |

## 10. Resultados de la ejecución (2026-10-22, sin desviaciones del protocolo)

Comando: `python -m scripts.validar_demanda --config configs/piloto_chiquimula.json`. Cifras exactas en `resultados/demanda_*.json`.

### 10.1 Backtest (§4)

| Pliegue | M0 WAPE | M1 WAPE | M2 WAPE |
|---|---|---|---|
| 1 (2015–2018 → 2019–2020) | 0.374 | 0.369 | **0.352** |
| 2 (2015–2019 → 2020–2021) | **0.294** | 0.337 | 0.374 |
| 3 (2015–2020 → 2021–2022) | **0.221** | 0.253 | 0.375 |
| **Promedio** | **0.297** | 0.320 | 0.367 |

Para calificar, un modelo debía tener un WAPE ≤ 0.267 (0.90 × 0.297). Ni M1 ni M2 califican, así que **se elige M0**. La tendencia de M2 extrapolaba la caída de 2015–2019 y subestimó todos los pliegues (sesgo de −31 % a −36 %).

### 10.2 Dispersión (§5)

Con M0 en 2015–2022 (n = 88, p = 11): **φ = 7.40**, `a` = 0.116, valor p ≈ 1e-72. Se cumplen ambas condiciones, así que **se usa binomial negativa NB2**.

### 10.3 Validación contra el MSPAS 2023–2024 (§6)

| Métrica | Valor |
|---|---|
| Observaciones | 22 municipio-año |
| Casos observados / esperados | 2,068 / 1,285.3 |
| MAE municipal | 36.4 casos por municipio y año |
| WAPE | 0.387 |
| Sesgo | **−782.7 casos (−37.9 %)** |
| 2023: observado / esperado | 934 / 645.8 (error −288.2) |
| 2024: observado / esperado | 1,134 / 639.5 (error −494.5) |
| Spearman del ranking municipal | **0.938** |
| Coincidencia de los 3 con más casos | **3/3** (Chiquimula, Jocotán, Camotán) |

**Interpretación:**

- El modelo **ordena bien** los municipios por carga: el ranking casi coincide y acierta los 3 de mayor demanda.
- Pero **subestima el nivel** de 2023–2024 en un 38 %, y más en 2024 que en 2023. Es coherente con el aumento sistémico documentado en `docs/decision_departamento.md`, que ningún candidato podía anticipar con datos de 2015–2022.
- Para la simulación, la **distribución relativa** de la demanda entre municipios es confiable; el **nivel absoluto** no.
- La sensibilidad de demanda +20 % (plan §6) cubre solo una parte de la brecha observada. El diseño experimental (Integrantes 2 y 3) debería considerar un escenario de nivel cercano al observado.

## 11. Salidas

- `resultados/demanda_backtest.json`: WAPE, MAE y sesgo por modelo y pliegue, más el modelo elegido según la regla.
- `resultados/demanda_dispersion.json`: φ, `a`, LR, valor p y distribución elegida.
- `resultados/demanda_validacion.json` y la figura de observado frente a estimado.
