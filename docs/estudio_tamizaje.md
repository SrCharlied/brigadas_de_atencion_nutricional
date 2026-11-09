# Estudio de tamizaje: cuántas brigadas para identificar cuántos casos

**Estado:** **CONGELADO** el 2026-11-08, antes de implementar y ejecutar. Aprobado por el equipo (Integrante 1).
**Sustituye** a la versión de `docs/estudio_dimensionamiento.md` como propuesta operativa. Aquella expresaba la capacidad en "casos atendidos por año" (150 / 221 / 300) sin respaldo empírico, y sus resultados se conservan como antecedente.

## 1. Pregunta

> ¿Con cuántas brigadas, y dónde, se evalúa a suficientes niños de 0 a 4 años para identificar un porcentaje dado de los casos esperados de desnutrición aguda en Chiquimula?

Una brigada **evalúa niños** (tamizaje) y, al evaluarlos, **identifica casos**. Los casos registrados no son la carga de trabajo: indican dónde es más probable encontrar casos.

## 2. Evidencia y supuestos

| Elemento | Valor | Fuente o tipo |
|---|---|---|
| Productividad | **20 / 27.5 / 35** evaluaciones por brigada y día (bajo / central / alto) | PMA, "Juventudes rurales a la cabeza de las brigadas de salud y nutrición" (18/12/2020): "cada brigada realiza una evaluación de 20 a 35 niñas y niños", jornada de 8:00 a 15:00, San Marcos. Es un solo reporte, de 2020, y evalúa a niños de 0 a 10 años |
| Días de campo al año | **220** | **Supuesto declarado**: año laboral menos vacaciones, capacitación y días no operativos |
| Capacidad anual por brigada | 220 × productividad = **4,400 / 6,050 / 7,700** evaluaciones | Derivado |
| Demanda de evaluación | Población de 0 a 4 años en 2024 por municipio (INE; 50,904 en total), **una ronda de tamizaje al año** | Proyección oficial y supuesto declarado. La recomendación de evaluar cada mes (especialista citado por Prensa Libre) se menciona como contraste, no se modela |
| Tasa de identificación | Casos registrados en 2024 / niños de 0 a 4 años, por municipio | MSPAS e INE. Es un indicador aproximado: **subestima** la prevalencia donde hubo poca búsqueda activa |
| Tiempo de viaje | Matriz OSRM por carretera (`data/referencia/osrm_chiquimula.json`); máximo de **45 / 60 / 90 min** solo de ida | Igual que el estudio anterior |
| Referencias de contraste | Huehuetenango (UNICEF, 16/12/2020): 13 brigadas evaluaron a 13,433 niños y detectaron 257 casos (1.9 %). Alta Verapaz (OPS, 24/10/2022): 19 brigadas, 5,574 niños, 21 casos (0.4 %) | Muestran que los casos son una fracción pequeña de las evaluaciones |

## 3. Modelo

- **Decisión:** cuántas brigadas `n_j ≥ 0` tienen base en cada municipio `j`, con `Σ n_j = K`. **Varias brigadas pueden compartir municipio.**
- **Asignación óptima para una ubicación dada** (programa lineal, `scipy.optimize.linprog`):
  - `x_ij` = niños del municipio `i` evaluados por las brigadas con base en `j`, solo si `tiempo_ij ≤ T`;
  - `Σ_j x_ij ≤ niños_i` y `Σ_i x_ij ≤ n_j · capacidad`.
- **Objetivo principal: casos identificados.** Maximizar `Σ_ij tasa_i · x_ij`.
- **Objetivo alternativo: niños evaluados.** Maximizar `Σ_ij x_ij`.
- **Desempate en ambos:** menor tiempo total de viaje ponderado por niños evaluados, mediante una penalización lexicográfica pequeña (ε = 1e-6 por niño-minuto, normalizada para que nunca supere un caso o un niño).
- **Métricas por plan:**
  - casos identificados esperados y su porcentaje sobre los casos de 2024;
  - niños evaluados y porcentaje;
  - el mismo plan evaluado con las tasas de 2023 (robustez);
  - tiempo medio de viaje;
  - municipios con menos del 50 % de sus niños evaluados.

## 4. Factores

| Factor | Valores |
|---|---|
| Brigadas K | 1 a 15 |
| Productividad | 20 / 27.5 / 35 evaluaciones por día |
| Tiempo máximo T | 45 / 60 / 90 min |
| Objetivo | casos identificados / niños evaluados |

En total, 15 × 3 × 3 × 2 = 270 configuraciones.

## 5. Métodos de búsqueda de la ubicación

| Método | Cuándo | Descripción |
|---|---|---|
| `exacto` | K ≤ 5 (como máximo C(15, 5) = 3,003 ubicaciones) | Enumeración de todas las combinaciones con repetición |
| `voraz` | Todas | Agrega una brigada a la vez donde más mejora el objetivo |
| `genetico` | Todas | El algoritmo de `brigadas/genetico.py`, **generalizado para permitir genes repetidos** (varias brigadas en un municipio), con los parámetros congelados (población 40, hasta 100 generaciones, parada tras 20 sin mejora, torneo 3, cruce 0.9, mutación 0.3, elitismo 2) y **5 semillas** por configuración |

- **Plan propuesto por configuración:** el óptimo exacto si K ≤ 5. Si no, la mejor solución entre el voraz y las 5 ejecuciones del genético. Se reporta qué método la encontró.
- **Calidad del algoritmo genético:** brecha frente al exacto (K ≤ 5) y frente al voraz (todas las K).

## 6. Tabla de decisión y configuración de referencia

- **Tabla de decisión:** para cada productividad y tiempo máximo, el menor K que identifica el **50, 80 y 90 %** de los casos esperados (objetivo principal) y su ubicación.
- **Referencia:** productividad 27.5 y T = 60 min, con el menor K que identifica al menos el **80 %** de los casos esperados.

## 7. Limitaciones declaradas

- La tasa de 2024 aproxima dónde están los casos, pero los registros dependen de la búsqueda previa.
- Una sola ronda de tamizaje al año; la recomendación mensual multiplicaría por 12 la necesidad.
- **No se modela el seguimiento** de los casos detectados (no hay dato público de cuántos puede acompañar una brigada).
- La productividad proviene de un solo reporte del PMA (2020, niños de 0 a 10 años); 220 días es un supuesto.
- Los tiempos de OSRM suponen un automóvil en condiciones normales.

## 8. Salidas

- `resultados/tamizaje_planes.csv`: una fila por configuración y método.
- `resultados/tamizaje_decision.csv` y `tamizaje_resumen.json`.
- Figuras de curvas y mapa en `resultados/figuras/`.

## 9. Resultados (2026-11-08, sin desviaciones del diseño)

Comando: `python -m scripts.ejecutar_tamizaje`. Cifras exactas en `resultados/tamizaje_*`.

### 9.1 Tabla de decisión (objetivo: identificar casos)

Menor número de brigadas que identifica la meta de los casos esperados de 2024. El tiempo máximo de viaje casi no cambia la respuesta: el número de brigadas es el mismo con 45, 60 y 90 min.

| Productividad (evaluaciones/día) | Capacidad anual | 50 % de los casos | 80 % | 90 % |
|---|---|---|---|---|
| 20 | 4,400 | 5 brigadas (59 %) | 8 (81–82 %) | 10 (93 %) |
| **27.5** | **6,050** | **3 (50 %)** | **6 (83 %)** | **7 (91 %)** |
| 35 | 7,700 | 3 (61 %) | 5 (86 %) | 6 (96 %) |

Evaluar a **todos** los niños una vez al año con 27.5 evaluaciones/día requiere unas 9 brigadas (50,904 / 6,050 = 8.4).

### 9.2 Configuración de referencia (27.5 evaluaciones/día, 60 min, meta del 80 %)

**6 brigadas:**

| Plan | Ubicación | Casos identificados | Niños evaluados | Robustez con tasas de 2023 | Viaje medio | Municipios con menos del 50 % evaluado |
|---|---|---|---|---|---|---|
| **Identificar casos** | Jocotán ×2, Camotán ×2, Esquipulas, Quezaltepeque | **83.1 %** | 71.3 % | 73.3 % | 14.2 min | 3 |
| Evaluar niños | Chiquimula ×2, Jocotán ×2, Camotán, Esquipulas | 75.0 % | 71.3 % | 72.0 % | 1.3 min | 6 |

- Con la misma cantidad de niños evaluados (la capacidad se usa completa en ambos planes), **orientar las brigadas a los municipios con más tasa identifica 8 puntos más de casos**.
- La brigada con base en Quezaltepeque no evalúa su propio municipio, que tiene de las tasas más bajas, sino municipios vecinos con tasa más alta. Es la decisión óptima del programa lineal bajo este objetivo.

### 9.3 Calidad del algoritmo genético

- **K ≤ 5 (óptimo exacto conocido):** el algoritmo genético alcanzó el óptimo en 448 de 450 ejecuciones (99.6 %).
- **K > 5 (sin óptimo conocido):** el mejor plan de cada configuración lo encontró el algoritmo genético en 103 de 180 configuraciones y el voraz en 77.
  - Cada ejecución del algoritmo genético alcanza ese mejor plan en el 50 % de los casos; el voraz, en el 54 %.
  - Los dos métodos se complementan, y por eso el plan propuesto toma el mejor de ambos.

### 9.4 Contraste con la recomendación mensual

Evaluar a todos los niños cada mes (12 rondas al año) requeriría unas 101 brigadas en Chiquimula (50,904 × 12 / 6,050). Muestra la distancia entre lo deseable y lo que permite una flota realista, y por qué priorizar con la tasa es útil.

## 10. Registro de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-08 | Congelado | Reformulación de la capacidad con evidencia del PMA, aprobada por el equipo |
| 2026-11-08 | Ejecutado y resultados agregados en §9 | Sin desviaciones del diseño |
