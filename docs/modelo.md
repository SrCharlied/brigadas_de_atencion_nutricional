# Modelo de simulación, restricciones y política base

**Responsable:** Denis Rodríguez · **Revisión:** Integrante 3 (pruebas y función objetivo)

Este documento describe lo que está implementado en `brigadas/contratos.py`, `distancias.py`, `asignacion.py`, `baseline.py`, `exacto.py` y `simulacion.py`. Todo resultado es **simulado**: no afirma reducción real de desnutrición ni recomienda una distribución al MSPAS.

## 1. Clasificación de cada insumo

| Insumo | Tipo | Origen |
|---|---|---|
| Casos registrados por municipio | Dato oficial agregado | MSPAS (Integrante 1) |
| Población 0–4 | Proyección oficial | INE (Integrante 1) |
| Centroides municipales | Referencia geográfica | HDX/OCHA (Integrante 1) |
| Distancias | Derivado: km geodésicos entre centroides | `distancias.py` |
| `K`, capacidad, `D_max` | **Supuestos de escenario** | `configs/piloto_chiquimula.json` (bloque `_supuestos`) |
| Pesos `w_c`, `w_d`, `w_e` | **Supuesto de escenario** | `PesosObjetivo` en `contratos.py` |
| Demanda por réplica | Dato simulado (M0 + binomial negativa, `a = 0.116`) | `demanda.py` vía `simulacion.generador_binomial_negativa` |
| `tests/fixtures/caso_pequeno.json` | Dato sintético de verificación | equipo |

Los valores de `configs/piloto_chiquimula.json` para Chiquimula (`GT20`): 3 brigadas, 150 casos por brigada y año, `D_max = 40 km`. Son **provisionales** (ver bloque `_supuestos`) y deben estudiarse con sensibilidad. No representan políticas actuales del MSPAS.

## 2. Unidades

- **Demanda y capacidad:** casos registrados **por municipio y año**. Se confirma la unidad propuesta por el Integrante 1: la capacidad es casos atendibles por brigada y año.
- **Distancia:** kilómetros geodésicos entre centroides municipales (haversine, radio 6 371.0088 km). **No** equivale a distancia vial ni a tiempo de viaje.
- **Cobertura:** proporción en [0, 1]; en los resultados por réplica se reporta como porcentaje.

## 3. Conjuntos, parámetros y decisiones

- `I`: municipios con demanda; `J = I`: candidatos a base (índices 0…n−1, mismo orden que la matriz de distancias).
- `d_i`: demanda del municipio `i` en la réplica; `dist_ij`: distancia en km.
- `K`: número de brigadas; cada brigada opera desde una base distinta.
- `C`: capacidad por brigada y periodo; `D_max`: distancia máxima para contar cobertura.
- Decisiones: qué `K` bases (política base, GA o enumerador) y qué brigada atiende a cada municipio (regla de asignación de la sección 4).

## 4. Regla de asignación capacitada (determinista)

Implementada en `asignacion.asignar_capacitado`:

1. Procesar municipios por demanda descendente (empate: menor índice).
2. Elegibles: bases con `dist ≤ D_max` y capacidad restante > 0.
3. Si alguna elegible cubre toda la demanda, elegir la más cercana (empate: menor posición de brigada).
4. Si ninguna la cubre completa, elegir la de mayor capacidad restante (empate: más cercana, menor posición) y cubrir `min(d_i, restante)`.
5. Sin elegibles: municipio **explícitamente no cubierto** (`asignaciones[i] = None`).

Un municipio se asigna como máximo a una brigada (no se divide su demanda). La regla es una heurística reproducible; no garantiza la asignación óptima para unas bases dadas. El "óptimo" del enumerador exacto es óptimo **respecto a la elección de bases bajo esta regla**.

## 5. Restricciones y cómo se verifican

| Restricción | Dónde se garantiza | Dónde se verifica |
|---|---|---|
| Exactamente `K` bases distintas en rango | `validar_bases` (lanza `ValueError`) | `verificar_resultado`, `ejecutar_replica` |
| Ninguna brigada excede `C` | regla de asignación | `verificar_resultado` (recalcula cargas) |
| Cada municipio asignado ≤ 1 vez | estructura `asignaciones[i]` | tests |
| Cobertura solo dentro de `D_max` | elegibilidad | `verificar_resultado` |
| No se crea demanda ni capacidad | `cubierta_i ≤ d_i`, carga ≤ `C` | `verificar_resultado` |
| La política no altera la demanda | arreglo de solo lectura | `test_simulacion.py` |

`verificar_resultado` no reutiliza la lógica de asignación: sirve como verificador independiente para cualquier política (incluido el GA). En la simulación, una fila solo es `factible = True` si la política lo declara **y** el verificador no encuentra violaciones.

## 6. Métricas por réplica

Calculadas por `asignacion.calcular_indicadores`:

- **Cobertura** = demanda cubierta / demanda total. Convención: si la demanda total es 0, cobertura = 1 (no hay nada que cubrir).
- **Demanda no cubierta** = total − cubierta.
- **Distancia media** ponderada por demanda cubierta (km). `NaN` si nada se cubre.
- **Percentil 90 de distancia**, ponderado por demanda cubierta (km). `NaN` si nada se cubre.
- **Peor cobertura municipal** = min(cubierta_i / d_i) entre municipios con demanda > 0 (1 si no hay demanda).
- **Utilización por brigada** = carga / `C` (`NaN` si `C = 0`).

## 7. Función objetivo (minimizar)

```text
J = w_c · (1 − cobertura)
  + w_d · min(1, distancia_media / D_max)          # si D_max = ∞, se divide por la mayor distancia de la matriz
  + w_e · (1 − peor_cobertura_municipal)
```

- Cada término está en [0, 1]; si nada se cubre, el término de distancia vale 0 (lo domina el de cobertura).
- Pesos por defecto (supuesto): `w_c = 1.0`, `w_d = 0.1`, `w_e = 0.1`. La cobertura es la métrica principal, por eso `w_c` debe ser positivo y dominante.
- Los pesos se fijan **antes** de observar resultados finales y se estudian con sensibilidad.
- No se suman penalizaciones de factibilidad: las bases inválidas se rechazan con `ValueError` y el GA debe repararlas antes de evaluar (decisión: no aceptar soluciones inválidas aunque tengan buen objetivo).

## 8. Política base (Escenario A)

`baseline.crear_politica_base(demanda_referencia)`:

- Bases = los `K` municipios con mayor **demanda media de desarrollo** (empate: menor índice).
- Asignación = misma regla capacitada que la política optimizada.
- Las bases dependen solo de la referencia de desarrollo, nunca de la demanda de la réplica ni de 2023–2024.
- Se denomina **heurística base**, no política actual del MSPAS.

`crear_politica_bases_fijas(bases)` envuelve una solución fija (por ejemplo, las mejores bases del GA) con el mismo contrato.

## 9. Flujo de réplicas y semillas

`simulacion.ejecutar_replicas(config, generador, politicas, distancias)`:

1. `derivar_semillas(semilla_raiz, replicas)` produce una semilla entera por réplica (`SeedSequence`), registrada en cada fila.
2. De cada semilla salen dos flujos: uno para la demanda y otro para las políticas.
3. La demanda se genera **una vez** por réplica y se entrega como arreglo de solo lectura a todas las políticas. La sensibilidad se hace con otro generador (`escala = 1.2`, o 1.6 según `docs/interfaz_demanda.md`) y las **mismas semillas**, cambiando el nombre de `escenario`.
4. Cada política recibe un generador nuevo creado desde el mismo flujo: el orden de ejecución no altera resultados y las diferencias son pareadas.
5. Se mide el tiempo de cada política y se guardan los campos del contrato `ResultadoReplica` (`guardar_resultados_csv` / `cargar_resultados_csv`).

`generador_binomial_negativa(mu, a, escala)` envuelve `demanda.generar_demanda` del Integrante 1. `generador_poisson` queda solo para pruebas: los datos reales están sobredispersos (φ ≈ 7.4).

Orden de índices: `distancias.cargar_municipios_csv` devuelve los municipios **ordenados por código**, el mismo orden que usa `demanda.ajustar(...).media(...)`.

## 10. Verificación con casos conocidos

`tests/fixtures/caso_pequeno.json`: 5 municipios sintéticos en línea (0, 4, 20, 36, 40 km), demanda (10, 6, 10, 6, 10), `K = 2`, `C = 100`, `D_max = 5`.

- Óptimo calculado a mano: bases {0, 4}, cubre 32 de 42 (76.2 %), distancia media 1.5 km, `J = 0.3681`.
- Política base: {0, 2} (empate de demanda 10 resuelto por índice), cubre 26 de 42 (61.9 %).
- El enumerador exacto reproduce el óptimo manual.

`exacto.calcular_gap` = (J_h − J_opt)/|J_opt|; si `J_opt = 0`, devuelve 0 cuando ambos son 0 e `inf` en otro caso (reportar además la diferencia absoluta).

## 11. Pruebas implementadas (sección 7.2 del plan)

| Propiedad | Test |
|---|---|
| 1. Demanda cero sin división inválida | `test_demanda_cero_cobertura_definida_sin_division_invalida` |
| 2. Capacidad suficiente y `D_max = ∞` cubren todo | `test_capacidad_suficiente_y_distancia_infinita_cubre_todo` |
| 3. Capacidad cero → cobertura cero | `test_capacidad_cero_cobertura_cero` |
| 4. Más capacidad no reduce la mejor cobertura | `test_aumentar_capacidad_no_reduce_mejor_cobertura` (15 instancias) |
| 5. Ninguna brigada excede capacidad | `test_ninguna_brigada_excede_capacidad_ni_se_crea_demanda` |
| 6. Municipio asignado ≤ 1 vez | ídem |
| 7. Exactamente `K` bases válidas | `test_validar_bases_rechaza`, `test_k_mayor_que_municipios` |
| 8. Misma demanda para todas las políticas | `test_politicas_reciben_la_misma_demanda_y_no_pueden_mutarla` |
| 9. Misma semilla reproduce resultados | `test_misma_semilla_reproduce_resultados` |
| 10. Métricas en rango | `test_metricas_en_rango` |

La propiedad 4 se comprobó empíricamente en instancias aleatorias pequeñas; como la regla de asignación es heurística, no es una demostración general.

## 12. Ejecución con datos reales (Hito 2)

```powershell
python -m scripts.ejecutar_baseline --config configs/piloto_chiquimula.json
```

1. Carga los municipios de `GT20` desde `data/processed/municipios.csv` y congela la matriz en `data/processed/distancias_GT20.csv`.
2. Calcula la referencia de la política base: casos medios 2015–2022 por municipio (años sin registro se excluyen, no se toman como cero).
3. Ajusta M0 con 2015–2022 y calcula `mu` con la población proyectada del año objetivo (`--anio-objetivo`, por defecto 2024; solo usa población, no casos de ese año). El año objetivo definitivo lo fija `docs/diseno_experimental.md` (Integrante 3).
4. Corre 30 réplicas pareadas con escala 1.0 y 1.2.
5. Evalúa la política base con los **casos observados** de 2023 y 2024 (`evaluar_demanda_fija`), como pidió el Integrante 1 para la comparación con la referencia real.

Salidas en `resultados/baseline_GT20_*.csv/json`. El algoritmo genético se integra pasando otra política con la firma `Politica` (o `crear_politica_bases_fijas(mejores_bases)`).

## 13. Respuesta a `docs/interfaz_demanda.md`

- **Unidad de capacidad:** confirmada, casos por brigada y año.
- **Cualquier vector de demanda:** toda política acepta un vector arbitrario; para los casos reales usar `simulacion.evaluar_demanda_fija(observado, politicas, distancias, config, escenario="observado_2023")`.
- **Misma demanda por réplica:** garantizado y probado (`test_politicas_reciben_la_misma_demanda_y_no_pueden_mutarla`).
- **Sin estado aleatorio global:** semillas derivadas con `SeedSequence`; cada política recibe su `rng`.

## 14. Limitaciones

- Centroides y distancias geodésicas: subestiman el acceso real en zonas montañosas o con poca red vial.
- La regla de asignación no divide la demanda de un municipio entre brigadas.
- La demanda simulada representa escenarios de conteos agregados, no llegadas diarias ni necesidad clínica.
- Capacidad, `K`, `D_max` y pesos son supuestos: los resultados dependen de ellos y deben acompañarse de sensibilidad.
