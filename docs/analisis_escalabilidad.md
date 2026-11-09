# Análisis adicional: escalabilidad del algoritmo genético

**Estado:** **CONGELADO** el 2026-11-08, antes de implementar y ejecutar.
**Responsable:** Integrante 1.
**Naturaleza:** análisis **adicional**, posterior a los experimentos principales (`docs/diseno_experimental.md`). No modifica ni reemplaza sus resultados. Cualquier cambio posterior se registra en §8 como desviación.

## 1. Motivo y pregunta

En Chiquimula hay solo 165 combinaciones de 3 bases: la enumeración exhaustiva basta y el algoritmo genético encuentra el óptimo desde la población inicial. La pregunta es:

> En problemas donde la enumeración es costosa o imposible, ¿el algoritmo genético, **con los mismos parámetros congelados**, encuentra mejores soluciones que alternativas simples con el mismo presupuesto de evaluaciones?

## 2. Instancias

Las reglas son las del piloto: demanda de referencia = casos medios de 2015–2022 y capacidad total = demanda de referencia total / K, redondeada.

| Instancia | Municipios | K | C | `D_max` | Combinaciones | ¿Óptimo exacto? |
|---|---|---|---|---|---|---|
| Huehuetenango (GT13) | 33 | 4 | 1,346.7 / 4 → **337** | Mediana de las distancias del departamento: 35.13 → **35 km** | 40,920 | **Sí**, por enumeración |
| Nacional, K = 10 | 338 | 10 | 17,442.6 / 10 → **1,744** | **22 km** | 4.7 × 10^18 | No |
| Nacional, K = 20 | 338 | 20 | → **872** | **22 km** | 8.8 × 10^31 | No |
| Nacional, K = 40 | 338 | 40 | → **436** | **22 km** | 1.6 × 10^52 | No |

- **Nacional:** se excluyen los 2 municipios sin ningún registro en 2015–2022 (GT1021 y GT1230), porque no se imputan como cero.
- **Radio:** la mediana de las distancias a escala nacional (cientos de km) no representa un radio de servicio, así que se conserva el radio del piloto, 22 km.
- **Pesos:** w = 1.0 / 0.1 / 0.1.
- El objetivo J se evalúa sobre la demanda de referencia, sin simulación estocástica: aquí se compara la calidad de la búsqueda, no la cobertura simulada.

## 3. Métodos comparados

| Método | Descripción | Presupuesto |
|---|---|---|
| `base` | Los K municipios con mayor demanda de referencia | 1 evaluación |
| `voraz` | Agrega, una a una, la base que más reduce J (empate: menor índice) | Unas K × n evaluaciones (determinista) |
| `aleatoria` | K-subconjuntos aleatorios distintos; se queda con el mejor | **El mismo número de evaluaciones únicas que usó el algoritmo genético con la misma semilla** |
| `genetico` | `brigadas/genetico.py` con los parámetros congelados (población 40, 100 generaciones máx., parada tras 20 sin mejora, torneo 3, cruce 0.9, mutación 0.3, elitismo 2) | Lo que use hasta su criterio de parada |

- Los métodos estocásticos (`aleatoria` y `genetico`) se ejecutan con **30 semillas** (0 a 29) por instancia.
- Para cada semilla, la búsqueda aleatoria recibe exactamente el presupuesto que gastó el algoritmo genético con esa semilla. Es una comparación pareada.

## 4. Métricas

- Objetivo J (menor es mejor) y cobertura de la demanda de referencia (%).
- Evaluaciones únicas y tiempo de ejecución (s).
- **Huehuetenango:** brecha frente al óptimo exacto y proporción de ejecuciones que lo alcanzan.
- **Nacional:** brecha frente a la mejor solución encontrada por cualquier método (no hay óptimo conocido).
- **Diferencia pareada** de J y de cobertura (genético − aleatoria) con IC 95 % (t de Student, 29 grados de libertad).

## 5. Qué se reporta

- Todo, aunque el algoritmo genético pierda contra la búsqueda voraz o la aleatoria.
- **No se ajustan los parámetros del algoritmo genético** para este análisis: medir si los parámetros congelados escalan es parte de la pregunta.

## 6. Salidas

- `resultados/escalabilidad_resultados.csv`: una fila por instancia, método y semilla.
- `resultados/escalabilidad_resumen.csv` y `escalabilidad_resumen.json`.
- `resultados/figuras/escalabilidad.png`.

## 7. Resultados (2026-11-08, sin desviaciones del diseño)

Comando: `python -m scripts.ejecutar_escalabilidad` (unos 28 minutos). Cifras exactas en `resultados/escalabilidad_*`.

### 7.1 Objetivo J medio (menor es mejor) y cobertura de la demanda de referencia

| Instancia | Base | Voraz | Aleatoria | Genético | Evaluaciones del genético |
|---|---|---|---|---|---|
| Huehuetenango, K = 4 (óptimo J = 0.0558) | 0.298 (83.6 %) | 0.166 (98.0 %) | 0.123 (99.0 %) | **0.076 (99.6 %)** | 506 de 40,920 |
| Nacional, K = 10 | 0.775 (35.4 %) | **0.659 (50.0 %)** | 0.770 (39.0 %) | 0.679 (47.9 %) | 1,879 (voraz: 3,335) |
| Nacional, K = 20 | 0.656 (46.9 %) | **0.478 (67.4 %)** | 0.639 (51.8 %) | 0.519 (63.7 %) | 2,772 (voraz: 6,570) |
| Nacional, K = 40 | 0.482 (64.1 %) | **0.335 (81.0 %)** | 0.511 (64.1 %) | 0.385 (76.7 %) | 3,143 (voraz: 12,740) |

### 7.2 Genético frente a aleatoria, mismo presupuesto (30 pares por instancia)

| Instancia | Diferencia de cobertura (IC 95 %) | Genético mejor en |
|---|---|---|
| Huehuetenango, K = 4 | +0.6 pp (0.4 a 0.9) | 28 de 30 |
| Nacional, K = 10 | +8.9 pp (8.4 a 9.4) | 30 de 30 |
| Nacional, K = 20 | +11.9 pp (11.3 a 12.4) | 30 de 30 |
| Nacional, K = 40 | +12.5 pp (12.0 a 13.1) | 30 de 30 |

### 7.3 Interpretación

1. **Frente a la búsqueda aleatoria,** con el mismo presupuesto de evaluaciones, el algoritmo genético es mejor en 118 de 120 pares, y la ventaja crece con el tamaño del problema. Su búsqueda guiada sí aporta: con K = 40, la búsqueda aleatoria es incluso peor que la política base.
2. **Frente a la política base,** el algoritmo genético es mucho mejor en todas las instancias: entre 12 y 17 pp más de cobertura a escala nacional.
3. **Frente al voraz:**
   - en Huehuetenango gana el algoritmo genético (J 0.076 frente a 0.166);
   - **a escala nacional gana el voraz**, con una brecha del genético frente al voraz del 3 al 15 % en J. El voraz usa entre 1.8 y 4 veces más evaluaciones.
4. **Con los parámetros congelados,** el algoritmo genético alcanza el óptimo exacto de Huehuetenango solo en 3 de 30 ejecuciones (brecha media del 35 %), evaluando el 1.2 % del espacio. La parada tras 20 generaciones sin mejora y la población de 40 resultan cortas para espacios grandes. Era una limitación prevista y queda confirmada.
5. **Conclusión:** el algoritmo genético escala mejor que la búsqueda aleatoria y que la heurística base, pero con estos parámetros no supera a una heurística voraz bien diseñada a escala nacional. Mejoras naturales, **no probadas aquí**: más población y generaciones, o sembrar la población inicial con la solución voraz (híbrido).

## 8. Registro de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-08 | Congelado | Antes de implementar y ejecutar |
| 2026-11-08 | Ejecutado y resultados agregados en §7 | Sin desviaciones del diseño |
