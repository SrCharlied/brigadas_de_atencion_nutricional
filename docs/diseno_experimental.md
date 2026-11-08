# Diseño experimental y parámetros del algoritmo genético

**Estado:** **CONGELADO** el 2026-11-08, antes de implementar y ejecutar el algoritmo genético y los experimentos.
**Responsable:** Integrante 1. Esta parte le correspondía al Integrante 3; ver `docs/contribuciones.md`.
**Regla de oro:** nada de este documento se cambia después de ver resultados. Cualquier cambio se registra en §8 como desviación, con fecha y motivo.

Complementa a `docs/protocolo_parametros.md`, que fija K, C, `D_max` y la sensibilidad, y a `docs/modelo.md`, donde están la regla de asignación y la función objetivo.

## 1. Pregunta experimental

Bajo los mismos supuestos, la misma información de decisión y la misma demanda simulada, ¿cuánto cambia la cobertura cuando las bases las elige el algoritmo genético en lugar de la heurística base?

## 2. Políticas comparadas

| Política | Cómo elige las K bases | Información que usa |
|---|---|---|
| `base` | Los K municipios con mayor demanda media de desarrollo (`baseline.crear_politica_base`) | Casos medios de 2015–2022 |
| `genetico` | Algoritmo genético que minimiza el objetivo J (`docs/modelo.md` §7) evaluado sobre la **misma demanda de referencia** | Casos medios de 2015–2022 |

Las dos asignan con la misma regla capacitada y se evalúan con la demanda de cada réplica. **Ninguna política ve la demanda de la réplica ni la de 2023–2024 al decidir.** El algoritmo genético se ejecuta dentro de cada réplica con el generador aleatorio de esa réplica, así que su propia variabilidad queda incluida en los resultados.

## 3. Algoritmo genético: parámetros fijados

| Elemento | Valor |
|---|---|
| Representación | Tupla ordenada de K índices de municipio distintos |
| Aptitud | Objetivo J (a minimizar) de `asignacion.evaluar_bases` sobre la demanda de referencia, con caché por cromosoma |
| Población | 40 individuos; inicialización con K-subconjuntos aleatorios sin repetición |
| Selección | Torneo de tamaño 3 |
| Cruce | Probabilidad 0.9: el hijo toma K genes al azar, sin repetición, de la unión de los genes de ambos padres. Preserva la unicidad por construcción |
| Mutación | Probabilidad 0.3 por hijo: reemplaza una base al azar por un municipio que no sea base |
| Elitismo | Los 2 mejores pasan sin cambios |
| Terminación | 100 generaciones como máximo, o 20 generaciones seguidas sin mejora del mejor J |
| Desempate | Menor J; si empatan, la tupla lexicográficamente menor |
| Aleatoriedad | Solo el `numpy.random.Generator` recibido; nunca estado global |

## 4. Condiciones

Cada condición tiene **30 réplicas** con las semillas derivadas de `semilla_raiz` = 20261021, iguales en todas las condiciones (pareadas).

| Condición | Demanda | C | `D_max` |
|---|---|---|---|
| `nominal` | M0 2024 × 1.0 | 221 | 22 km |
| `demanda_x1.2` | × 1.2 | 221 | 22 km |
| `demanda_x1.6` | × 1.6 | 221 | 22 km |
| `capacidad_177` | × 1.0 | 177 | 22 km |
| `dmax_40` | × 1.0 | 221 | 40 km |

- La demanda simulada es la media M0 con la población proyectada de **2024** y la variabilidad binomial negativa (`a` = 0.116), según `docs/protocolo_demanda.md`.
- **Referencia real:** ambas políticas, con los parámetros nominales, se evalúan con los casos observados de 2023 y 2024.

## 5. Métricas y estadística

- **Por política y condición:** media, desviación estándar y mediana de la cobertura (%), de la distancia media ponderada (km) y de la peor cobertura municipal.
- **Diferencia pareada** (`genetico` − `base`) por réplica, con su media, desviación estándar e **intervalo de confianza del 95 %** con la distribución t de Student (29 grados de libertad). Se reporta en puntos porcentuales y como cambio relativo respecto de la media de la base.
- **Calidad del algoritmo genético:** en cada condición, el óptimo exacto sobre la demanda de referencia (`exacto.enumerar_optimo`, 165 combinaciones) y, para las 30 ejecuciones, la brecha relativa del objetivo y la proporción que alcanza el óptimo.
- **Convergencia:** el mejor J y la mediana de J por generación en la ejecución con la semilla raíz de la condición nominal.
- **Tiempo de ejecución** por política.

## 6. Visualizaciones

1. Mapa de Chiquimula con la demanda media de desarrollo, las bases de cada política y las asignaciones del algoritmo genético. Muestra el comportamiento del sistema.
2. Cobertura media por condición y política, con su intervalo de confianza del 95 %. Compara escenarios y muestra la sensibilidad.
3. Distribución de las diferencias pareadas por condición. Muestra la variabilidad.
4. Convergencia del algoritmo genético.
5. Validación de la demanda: ya existe (`validacion_demanda.png`).

## 7. Qué no se hará

- No se ajustan los parámetros del algoritmo genético ni los pesos según los resultados.
- No se descartan condiciones ni réplicas.
- Si el algoritmo genético empata con la política base, se reporta tal cual.

## 8. Registro de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-08 | Congelado | Antes de implementar y ejecutar |
