# Técnica adicional: algoritmo genético con restricciones

**Implementación:** `brigadas/genetico.py` · **Pruebas:** `tests/test_genetico.py` · **Diseño y parámetros congelados:** `docs/diseno_experimental.md`
**Responsable:** Integrante 1. Le correspondía al Integrante 3; ver `docs/contribuciones.md`.

## 1. Objetivo

Elegir los **K municipios base** de las brigadas que minimizan el objetivo J del modelo (`docs/modelo.md` §7):

```text
J = w_c·(1 − cobertura) + w_d·min(1, distancia_media / D_max) + w_e·(1 − peor_cobertura_municipal)
```

J se evalúa sobre la demanda de referencia: los casos medios de 2015–2022, la misma información que usa la política base. Es un problema combinatorio de localización con cobertura máxima y capacidad (Church y ReVelle, 1974): hay C(n, K) combinaciones posibles, que crecen muy rápido con n.

## 2. Funcionamiento

Un algoritmo genético mantiene una **población** de soluciones candidatas y la mejora por generaciones, imitando la selección natural (Holland, 1975; Goldberg, 1989):

1. **Selección:** los individuos con mejor aptitud tienen más probabilidad de reproducirse.
2. **Cruce:** combina los genes de dos padres en un hijo.
3. **Mutación:** introduce cambios aleatorios pequeños para mantener la diversidad.
4. **Elitismo:** conserva los mejores individuos para que la mejor solución nunca empeore.

Funciona en espacios grandes y discretos donde no hay gradiente y la enumeración es inviable. A cambio, no garantiza el óptimo global (Eiben y Smith, 2015).

## 3. Representación y restricciones

- **Cromosoma:** una tupla ordenada de K índices de municipio **distintos**, por ejemplo `(1, 4, 8)`.
- **Asignación:** la calcula el evaluador común `asignacion.evaluar_bases` con la regla capacitada determinista, la misma que usan la política base y el enumerador exacto. Así, el algoritmo solo decide dónde poner las bases y la comparación es justa.
- **Restricciones:** capacidad, radio `D_max` y "cada municipio se asigna como máximo una vez" se cumplen dentro del evaluador. La restricción "exactamente K bases distintas" se garantiza **por construcción**: los operadores nunca producen duplicados, así que no hace falta reparar ni penalizar. Es la estrategia de mantener la factibilidad, en lugar de penalizar soluciones inválidas (Deb, 2000).

## 4. Parámetros (fijados antes de ejecutar)

| Parámetro | Valor |
|---|---|
| Tamaño de población | 40 |
| Generaciones máximas | 100 |
| Parada por estancamiento | 20 generaciones sin mejora |
| Torneo | 3 individuos |
| Probabilidad de cruce | 0.9 |
| Probabilidad de mutación | 0.3 por hijo |
| Elitismo | 2 individuos |

## 5. Procedimiento de búsqueda

1. **Inicialización:** 40 subconjuntos aleatorios de K municipios distintos.
2. **Evaluación:** J de cada individuo, con caché, porque la misma combinación puede reaparecer.
3. **Nueva generación:** los 2 mejores pasan tal cual (elitismo). El resto se forma así:
   - **Selección por torneo:** de 3 individuos al azar gana el de menor J, y así se eligen los dos padres.
   - **Cruce** (probabilidad 0.9): el hijo toma K genes al azar, sin repetición, de la unión de los genes de los padres.
   - **Mutación** (probabilidad 0.3): una base del hijo se reemplaza por un municipio que no era base.
4. Se repite el paso 3 hasta el criterio de terminación.

**Desempate:** menor J; si hay empate, la tupla lexicográficamente menor. Toda la aleatoriedad viene del `numpy.random.Generator` recibido, sin estado global, así que con la misma semilla el resultado es idéntico.

## 6. Criterio de terminación

Se detiene al llegar a **100 generaciones** o tras **20 generaciones seguidas sin mejorar** el mejor J, lo que ocurra primero.

## 7. Integración con el modelo

`crear_politica_genetica(referencia)` devuelve una política con el contrato `Politica` del Integrante 2:

- Dentro de cada réplica, ejecuta el algoritmo sobre la demanda de referencia con el generador aleatorio de esa réplica, y evalúa las bases resultantes con la demanda simulada de la réplica.
- Las dos políticas reciben exactamente la misma demanda.
- El verificador independiente (`asignacion.verificar_resultado`) comprueba cada resultado.

## 8. Calidad de la solución (resultados)

En las **150 ejecuciones** (5 condiciones × 30 réplicas), el algoritmo **alcanzó el óptimo exacto** que da el enumerador de las 165 combinaciones: brecha 0. En promedio usó unas 22 generaciones y evaluó unas 97 combinaciones distintas (`resultados/experimentos_calidad.csv`). Las pruebas también comprueban que alcanza el óptimo en el caso conocido de 5 municipios y en 5 instancias aleatorias de 9 municipios.

**Observación honesta:** en Chiquimula el espacio de búsqueda es pequeño (165 combinaciones). Con una población de 40, la población inicial ya suele contener el óptimo; en la ejecución con la semilla raíz, el mejor individuo es óptimo desde la generación 0 (`resultados/figuras/convergencia_genetico.png`). La convergencia que se ve es la de la mediana de la población. En esta instancia, la enumeración exhaustiva sería suficiente.

## 9. Justificación frente a alternativas

| Alternativa | Ventaja | Por qué no como técnica principal |
|---|---|---|
| Enumeración exhaustiva | Óptimo garantizado | Inviable al crecer: con los 340 municipios del país y K = 10 hay del orden de 10^18 combinaciones. Aquí se usa como **referencia de calidad** |
| Programación entera (MCLP) | Óptimo con un solver | Requiere linealizar la regla de asignación heurística y un solver externo; la regla actual no es lineal |
| Búsqueda local / *hill climbing* | Simple y rápida | Se estanca en óptimos locales sin un mecanismo de diversidad |
| Algoritmo genético | Trata el evaluador como caja negra, mantiene la factibilidad por construcción y escala | No garantiza el óptimo; se mitiga comparándolo con el exacto donde es posible |

## 10. Limitaciones

1. **No garantiza el óptimo global.** En instancias grandes no hay una referencia exacta para medir la brecha.
2. **Sensible a los parámetros:** población, mutación y estancamiento se fijaron por criterio, sin calibrarlos; un problema mayor podría necesitar otros valores.
3. **Optimiza sobre la demanda de referencia,** no sobre la incertidumbre: en algunas réplicas la política base cubre más que el algoritmo, porque la demanda real de esa réplica difiere de la media.
4. **En este piloto el problema es pequeño:** la ventaja del algoritmo sobre la enumeración no se demuestra empíricamente aquí, solo se argumenta por escalabilidad.

## 11. Qué implementa una biblioteca y qué el equipo

- **Bibliotecas:** NumPy proporciona el generador de números aleatorios (`numpy.random.Generator`) y la mediana. No se usó ninguna biblioteca de algoritmos evolutivos (como DEAP o PyGAD).
- **Equipo:** representación, inicialización, selección por torneo, cruce que preserva la unicidad, mutación, elitismo, caché de aptitud, criterio de terminación, historial de convergencia, integración con el contrato `Politica` y análisis de brecha frente al óptimo exacto.

## 12. Referencias

- Church, R. y ReVelle, C. (1974). The maximal covering location problem. *Papers of the Regional Science Association*, 32(1), 101–118.
- Deb, K. (2000). An efficient constraint handling method for genetic algorithms. *Computer Methods in Applied Mechanics and Engineering*, 186(2–4), 311–338.
- Eiben, A. E. y Smith, J. E. (2015). *Introduction to Evolutionary Computing* (2.ª ed.). Springer.
- Goldberg, D. E. (1989). *Genetic Algorithms in Search, Optimization, and Machine Learning*. Addison-Wesley.
- Holland, J. H. (1975). *Adaptation in Natural and Artificial Systems*. University of Michigan Press.
