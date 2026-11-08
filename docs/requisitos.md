# Requisitos académicos — Proyecto 2 (Tarea 0.1)

**Fuente:** guía oficial del Proyecto 2 de Modelización y Simulación, transcrita por el equipo el 2026-10-22.
**Estado:** congelado (v1). Cualquier cambio requiere acuerdo del equipo y debe registrarse en este archivo.
**Responsable:** Integrante 1. **Revisión:** Integrantes 2 y 3.

## 1. Datos generales

| Aspecto | Valor |
|---|---|
| Fecha de entrega | **Lunes 9 de noviembre de 2026**: informe, repositorio y evidencia, un día antes de la presentación |
| Presentación | **Martes 10 de noviembre de 2026** |
| Medio de entrega | El que comunique el canal oficial del curso |
| Avances parciales | La guía no establece ninguno |
| Aprobación de viabilidad | No requiere confirmación adicional (decisión del equipo, 2026-10-22) |
| Lenguaje | Python (recomendado por la guía) |
| Entorno de laboratorio | No se exige |

## 2. Rúbrica (50 puntos) y evidencia prevista

| Criterio | Pts | Subcriterios (pts) | Evidencia prevista | Responsable |
|---|---|---|---|---|
| Problema real y justificación | 4 | Contexto y relevancia (1), problema concreto (1), **objetivos medibles** (1), fuentes y evidencia (1) | Informe §Problema y §Objetivos; `docs/fuentes.md`; `resultados/calidad_datos.json` | Integrante 1 |
| Investigación de la técnica adicional | 5 | Fundamento y funcionamiento (2), calidad de fuentes (1), justificación de elección (1), limitaciones (1) | `docs/algoritmo_genetico.md` (ver §4) | Integrante 3 |
| Formulación del modelo | 5 | Variables y parámetros (2), reglas o ecuaciones (1), supuestos y restricciones (1), coherencia (1) | `docs/modelo.md`; `configs/` (`_supuestos`) | Integrante 2 |
| Simulación funcional | 7 | **Ejecución verificable (3)**, representación coherente (2), parametrización (1), organización y reproducibilidad (1) | `scripts/`, `configs/`, `README.md`, `tests/`; reproducción desde entorno limpio | Integrante 2 |
| Técnica adicional implementada | 6 | **Implementación operativa (3)**, integración con el modelo (2), explicación técnica (1) | `brigadas/genetico.py`, `tests/test_genetico.py`, comparación con enumeración exacta | Integrante 3 |
| Diseño experimental y validación | 5 | Diseño y condiciones (2), repeticiones y control de aleatoriedad (1), verificación, error e incertidumbre (2) | `docs/diseno_experimental.md`; `brigadas/experimentos.py`; pruebas de propiedades internas | Integrantes 2 y 3 |
| Comparación con escenario real | 6 | Datos o referencia documentada (2), comparación cuantitativa (2), interpretación (1), limitaciones (1) | `scripts/validar_demanda.py`; informe §Comparación con la vida real (ver §5) | Integrante 1 |
| Resultados y conclusiones | 4 | Tablas y gráficas (2), conclusiones sustentadas (2) | `resultados/`, `brigadas/visualizacion.py`, informe §Resultados y §Conclusiones | Integrante 3 (todos en conclusiones) |
| Presentación y dominio técnico | 8 | Claridad y organización (2), demostración verificable (2), **dominio y respuestas técnicas (3)**, participación y tiempo (1) | Diapositivas, demo preparada, video o capturas de respaldo, ensayo cronometrado | Todos |

## 3. Entregables

### 3.1 Informe técnico en PDF

Sin extensión, plantilla ni estilo de citas fijos. **Se deben citar todas las fuentes, datos, herramientas y usos de inteligencia artificial.**

| Sección obligatoria | Insumo principal |
|---|---|
| Portada | — |
| Problema | `docs/fuentes.md` |
| Objetivos | Por redactar: deben ser **medibles** |
| Fuentes | `docs/fuentes.md`, `data/descargas.json` |
| Técnica investigada | `docs/algoritmo_genetico.md` |
| Modelo | `docs/modelo.md` |
| Implementación | Código y la distinción entre lo que hace la biblioteca y lo que hace el equipo (§4) |
| Diseño experimental | `docs/diseno_experimental.md` |
| Validación | Pruebas de propiedades internas y casos conocidos |
| Comparación con la vida real | `scripts/validar_demanda.py` (§5) |
| Resultados | `resultados/` |
| Limitaciones | `docs/fuentes.md`, `docs/decision_departamento.md`, plan §17 |
| Conclusiones | Equipo |
| Referencias | Fuentes de datos, técnicas, herramientas y **uso de IA** |
| Contribuciones | `docs/contribuciones.md` |

### 3.2 Repositorio GitHub accesible para evaluación

| Requisito | Estado |
|---|---|
| Código fuente | En curso |
| README con instrucciones reproducibles | En curso (`README.md`) |
| `requirements.txt` o equivalente | Hecho (versiones fijas) |
| Datos autorizados o procedimiento para obtenerlos | Hecho: datos oficiales versionados en `data/raw/` (licencias abiertas), verificables con `scripts/descargar_datos.py` contra los checksums de `data/descargas.json`. Todas las fuentes son públicas, sin datos personales |
| Estructura organizada | Hecho (plan §8) |

"Accesible para evaluación" no exige que sea público.

### 3.3 Evidencia experimental

Resultados tabulados, parámetros, semillas, gráficas, métricas y los archivos necesarios para verificar las conclusiones. Destino: `resultados/` (versionado).

### 3.4 Presentación

Diapositivas y demostración funcional. **Máximo 15 minutos, incluyendo la demostración y la defensa.** Deben participar todos los integrantes activos. Ejecución preparada, con evidencia reproducible de respaldo por si fallan la conexión o el entorno.

| Bloque | Min | Integrante (plan §13) |
|---|---|---|
| Problema, objetivo y fuente real | 2 | 1 |
| Modelo, variables, restricciones y supuestos | 2 | 2 |
| Técnica investigada e integración | 3 | 3 |
| Demostración y ejecución | 3 | 3 |
| Resultados, validación y comparación real | 3 | 1 y 3 |
| Conclusiones, preguntas y defensa | 2 | Todos |

### 3.5 Registro de contribuciones

Resumen concreto de responsabilidades y aportes de cada integrante: `docs/contribuciones.md`.

## 4. Técnica adicional: algoritmo genético con restricciones

La guía exige una técnica vista en clase **más** una técnica adicional investigada. Los algoritmos genéticos con restricciones aparecen entre sus ejemplos.

Contenido obligatorio de `docs/algoritmo_genetico.md`:

- [ ] Objetivo.
- [ ] Representación de soluciones.
- [ ] Parámetros.
- [ ] Procedimiento de búsqueda o actualización.
- [ ] Criterio de terminación.
- [ ] Justificación frente a alternativas.
- [ ] **Al menos dos limitaciones.**
- [ ] **Tres fuentes técnicas identificables**, al menos una de documentación técnica, artículo académico o libro especializado.
- [ ] **Qué implementa una biblioteca y qué implementa el equipo.** Llamar una función y mostrar el resultado no basta.

## 5. Comparación con la realidad

La guía exige comparar, **con las mismas métricas y unidades**, la referencia real, la simulación base y la simulación mejorada. También pide:

- describir la fuente, la fecha, el periodo, el tamaño de muestra y las condiciones;
- cuantificar el error del modelo base (MAE, error absoluto, relativo u otra métrica justificada) y explicar **primero** qué tan bien corresponde con la realidad;
- reportar el cambio absoluto y, cuando corresponda, el porcentual;
- diferenciar la mejora simulada de la mejora real observada.

Los datos sintéticos solos no cuentan como validación.

**Aplicación a la propuesta:**

| Elemento | Propuesta |
|---|---|
| Referencia real | Casos registrados por el MSPAS en 2023–2024 en Chiquimula (11 municipios × 2 años = 22 observaciones; 2,068 casos). Reservados: no se usan para ajustar |
| Error del modelo base | Demanda esperada del modelo frente a la observada: MAE municipal, WAPE, error por año y ranking de municipios con mayor carga |
| Qué valida | La aproximación de la **demanda municipal agregada** |
| Qué no valida | Tiempos de atención, capacidad real de las brigadas, resultados clínicos ni reducción real de la desnutrición |

**Brecha detectada:** la referencia real (casos 2023–2024) solo permite validar la demanda. Para comparar base y mejora "con las mismas métricas y unidades" contra la realidad, se propone evaluar **ambas políticas con la demanda observada de 2023–2024** además de las réplicas simuladas. Así se reporta la *cobertura de casos registrados reales* de cada política, en casos y en porcentaje. Queda a decisión de los Integrantes 2 y 3 (`docs/diseno_experimental.md`).

## 6. Mínimos experimentales

| Requisito de la guía | Cómo se cumple | Estado |
|---|---|---|
| Al menos 3 condiciones: base, mejora y sensibilidad | Política base, algoritmo genético y 4 variantes de sensibilidad (`docs/diseno_experimental.md`) | **Hecho** |
| 30 o más repeticiones independientes por condición si hay aleatoriedad | 30 réplicas pareadas por condición (`resultados/experimentos_replicas.csv`) | **Hecho** |
| Registrar semillas | `semilla_raiz` 20261021 y la semilla de cada réplica en los CSV | **Hecho** |
| Promedio y dispersión | `resultados/experimentos_resumen.csv` (media, desviación estándar y mediana) | **Hecho** |
| Error e incertidumbre; comparación reproducible | Error de validación de la demanda (MAE, WAPE, sesgo) e IC 95 % de las diferencias pareadas; reproducción en un clon limpio con 21 salidas idénticas | **Hecho** |
| Al menos una propiedad interna verificada (consistencia, límites, conservación o caso conocido) | 10 propiedades con pruebas (`docs/modelo.md` §11), conservación de casos (239,805), caso conocido y algoritmo genético frente al óptimo exacto (150 de 150 con brecha 0) | **Hecho** |
| Al menos una prueba de sensibilidad, explicando qué cambia | Demanda ×1.2 y ×1.6, capacidad 177 y `D_max` de 40 km, interpretadas en el informe | **Hecho** |
| Al menos 3 visualizaciones: comportamiento del sistema, comparación de escenarios, variabilidad/error o sensibilidad | Mapa de asignación, comparación de escenarios, diferencias pareadas, convergencia y validación de la demanda (`resultados/figuras/`) | **Hecho** |
| Cada gráfica con título, ejes, unidades, leyenda cuando corresponda y explicación | Revisadas visualmente; la explicación va en el pie de figura del informe | **Hecho** |

Si el costo impidiera hacer 30 repeticiones, habría que justificarlo y aprobar previamente una alternativa.

## 7. Pendientes derivados de la guía

1. **Redactar objetivos medibles** para el informe (rúbrica, 1 pt). Por ejemplo: "cuantificar el MAE municipal de la demanda estimada frente a 2023–2024" o "estimar la diferencia de cobertura simulada entre base y algoritmo genético con 30 réplicas pareadas".
2. **Declarar el uso de IA** en las referencias del informe. Este repositorio se desarrolló con asistencia de Claude Code (Anthropic).
3. Decidir sobre la brecha de la §5 (evaluar las políticas con la demanda observada).
