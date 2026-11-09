# Estudio de dimensionamiento: cuántas brigadas y dónde

> **Superado el 2026-11-08 por `docs/estudio_tamizaje.md`.** Este estudio expresa la capacidad de una brigada en "casos atendidos por año" (150 / 221 / 300), una unidad sin respaldo empírico. La evidencia del PMA, de UNICEF y de la OPS muestra que las brigadas **evalúan niños** y que los casos son una fracción pequeña de esas evaluaciones. Los resultados se conservan como antecedente. Siguen siendo válidos la comparación entre línea recta y carretera (§9.4) y el hallazgo del techo de la regla rígida (§9.1).

**Estado:** **CONGELADO** el 2026-11-08, antes de implementar y ejecutar. Aprobado por el equipo (Integrante 1).
**Naturaleza:** estudio de planificación posterior a la validación. La validación del modelo de demanda (`docs/protocolo_demanda.md`) ya está cerrada, así que aquí se usan los casos reales de 2024 para planificar. No modifica los experimentos principales (`docs/diseno_experimental.md`).

## 1. Pregunta

> ¿Cuántas brigadas hacen falta, y dónde ubicarlas, para cubrir una proporción dada de los casos registrados reales en Chiquimula? ¿Cómo cambia la respuesta según la capacidad de cada brigada, el tiempo de viaje aceptable y el criterio de prioridad?

## 2. Datos

- **Demanda de planificación:** casos registrados por el MSPAS en **2024** (1,134 en los 11 municipios), el dato real más reciente.
- **Robustez:** casos de **2023** (934) y **30 réplicas simuladas** alrededor del nivel de 2024: binomial negativa con media igual a los casos de 2024 de cada municipio, `a` = 0.116 y semillas derivadas de 20261021.
- **Tiempos de viaje por carretera:** matriz de OSRM sobre OpenStreetMap (`data/referencia/osrm_chiquimula.json`, consultada el 2026-11-08). Se promedian ida y vuelta (asimetría máxima de 0.3 min) para obtener una matriz simétrica en minutos.
- **Vulnerabilidad:** tasa de 2024 por cada 1,000 menores de 5 años (casos / población INE × 1,000).

## 3. Factores (72 configuraciones)

| Factor | Valores | Justificación |
|---|---|---|
| Brigadas K | 1, 2, …, 8 | Curva completa en lugar de un solo valor |
| Capacidad por brigada C | 150, 221 y 300 casos/año | No hay dato oficial: rango bajo, medio (valor del piloto) y alto |
| Tiempo máximo de viaje T | 45, 60 y 90 minutos (solo ida) | 60 min permite ir y volver en unas 2 h y dejar la mayor parte de una jornada de 8 h para atender; 45 es restrictivo; 90 equivale casi a no tener restricción (54 de 55 pares) |

## 4. Enfoques (tres planes por configuración)

| Enfoque | Cómo elige las K bases |
|---|---|
| `regla` | Los K municipios con más casos en 2024 (la regla obvia) |
| `cobertura` (principal) | **Óptimo exacto** del objetivo J del modelo (pesos 1.0 / 0.1 / 0.1), con el tiempo de viaje como distancia y T como radio, sobre la demanda de 2024 |
| `vulnerabilidad` (alternativo) | **Óptimo exacto** de la cobertura ponderada por vulnerabilidad, `V = Σ tasa_i · (cubierta_i / casos_i) / Σ tasa_i`, sobre la demanda de 2024. Desempate: menor J; si persiste, el orden lexicográfico |

La asignación de municipios a bases usa la regla capacitada del modelo (`docs/modelo.md` §4) en los tres enfoques. La enumeración es exhaustiva: como máximo C(11, 5) = 462 combinaciones por configuración.

## 5. Métricas por plan

- Cobertura de los casos de 2024 (planificación) y de 2023 (robustez).
- Cobertura simulada: media e IC 95 % (t de Student, 29 grados de libertad) en las 30 réplicas.
- Cobertura ponderada por vulnerabilidad (V), con los casos de 2024.
- Tiempo medio de viaje ponderado por los casos cubiertos (min).
- Municipios sin cobertura.

## 6. Tabla de decisión y configuración de referencia

- **Tabla de decisión:** para cada C y T, el **menor K** cuyo plan `cobertura` alcanza el 80, el 90 y el 95 % de los casos de 2024, junto con su cobertura en 2023 y en la simulación.
- **Configuración de referencia para el informe y el mapa:** C = 221 y T = 60 min (valores centrales), con el **menor K que cubra al menos el 90 %** de los casos de 2024. La meta del 90 % es ilustrativa; la tabla de decisión muestra las demás metas.

## 7. Qué se reporta

- Las 72 configuraciones con los tres enfoques, sin descartar ninguna.
- La comparación de la distancia en línea recta con la vial (razón y correlación), como evidencia sobre el supuesto de distancia de los experimentos principales.

## 8. Salidas

- `resultados/dimensionamiento_planes.csv`: una fila por configuración y enfoque.
- `resultados/dimensionamiento_decision.csv` y `dimensionamiento_resumen.json`.
- `resultados/figuras/dimensionamiento_curvas.png` y `dimensionamiento_mapa.png`.

## 9. Resultados (2026-11-08)

Comando: `python -m scripts.ejecutar_dimensionamiento` (unos 25 s). Cifras exactas en `resultados/dimensionamiento_*`.

### 9.1 Regla rígida (la del modelo): hay un techo

Con un municipio atendido como máximo por una brigada, la cobertura de los casos de 2024 no puede superar Σ min(casos, C):

- 73.0 % con C = 150;
- 88.4 % con C = 221, que se alcanza con 5 brigadas;
- 96.6 % con C = 300.

Agregar brigadas por encima de ese punto no cambia nada. Jocotán (338 casos) y Camotán (236) necesitan más de una brigada.

### 9.2 Variante divisible: cuántas brigadas hacen falta (enfoque de cobertura, casos de 2024)

| Capacidad | 45 min | 60 min | 90 min |
|---|---|---|---|
| 150 | 7 brigadas → 89.0 %; 8 → 89.0 % (no llega al 90 %) | 7 → 92.6 %; **8 → 100 %** | 7 → 92.6 %; 8 → 100 % |
| 221 | **5 → 95.6 %**; 6 → 100 % | **5 → 97.4 %**; 6 → 100 % | 5 → 97.4 %; 6 → 100 % |
| 300 | **4 → 97.5 %** | **4 → 100 %** | 4 → 100 % |

**Configuración de referencia** (C = 221, 60 min, meta del 90 %): **5 brigadas** en Chiquimula, Jocotán, Camotán, Esquipulas y San Jacinto.

| Medida | Valor |
|---|---|
| Casos de 2024 cubiertos | 97.4 % (= 5 × 221 / 1,134: el límite es la capacidad total) |
| Casos de 2023 cubiertos | 100 % |
| Simulación | 93.0 % |
| Tiempo medio de viaje | 14.9 min |
| Municipios sin cobertura | 0 |

En esta configuración, los tres enfoques (regla, cobertura y vulnerabilidad) eligen el mismo plan.

### 9.3 Cuándo importa la ubicación y cuándo el enfoque

1. **Con la demanda real, la palanca principal es el número de brigadas.** La cobertura crece casi exactamente como brigadas × capacidad hasta cubrir todo. Cuando la capacidad total no alcanza, casi cualquier ubicación cerca de los municipios grandes la llena.
2. **La ubicación importa cuando el tiempo de viaje restringe.** Con 45 min y C = 221, el plan óptimo cubre 95.6 % con 5 brigadas y 100 % con 6, frente al 85.3 % y el 88.4 % de la regla de más casos. Con 60 min la cobertura empata, pero el óptimo reduce el viaje medio (con 4 brigadas: 8.7 frente a 17.7 min).
3. **El enfoque de vulnerabilidad muestra una disyuntiva real cuando hay pocas brigadas** (C = 221, 60 min). Con 3 brigadas elige Esquipulas, Concepción Las Minas e Ipala:

   | | Enfoque de cobertura | Enfoque de vulnerabilidad |
   |---|---|---|
   | Casos cubiertos | 58.5 % | 46.3 % |
   | Cobertura ponderada por vulnerabilidad | 25.5 % | 70.4 % |
   | Municipios sin cobertura | 8 | 3 |

   El enfoque de cobertura concentra la capacidad en Jocotán y Camotán (100 % cada uno) y en la mitad de Chiquimula. El de vulnerabilidad cubre completos 8 municipios medianos y pequeños, entre ellos San José La Arada y San Jacinto, los de tasa más alta, y deja fuera a Jocotán y Camotán. La disyuntiva es volumen en pocos municipios grandes frente a alcance en muchos municipios. Con 5 o más brigadas los enfoques coinciden.

### 9.4 Línea recta frente a carretera

La distancia por carretera es, en mediana, **1.74 veces** la distancia en línea recta (39.6 frente a 22.3 km), con un tiempo mediano de 50 min. El orden de cercanía se conserva en buena medida (Spearman 0.83). Esto confirma que los experimentos principales, hechos en línea recta, subestiman las distancias reales, aunque la estructura de cercanía es parecida.

### 9.5 Limitaciones propias del estudio

- Los tiempos de OSRM suponen un automóvil en condiciones normales; en caminos rurales o en época de lluvia el viaje real puede ser mayor.
- La regla divisible es voraz: no reparte la demanda de forma óptima. Como los municipios grandes se procesan primero, pueden agotar la capacidad de la brigada con base en un municipio pequeño. En el plan de 5 brigadas, San Jacinto queda atendido desde Camotán; con 3 brigadas, San Juan Ermita (plan de cobertura) e Ipala (plan de vulnerabilidad) quedan sin atención aunque sean sede de una base.
- Las capacidades (150, 221 y 300) siguen siendo supuestos; por eso se presenta el rango completo.
- La planificación usa un solo año (2024); la robustez se revisa con 2023 y con la simulación.

## 10. Registro de cambios

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-08 | Congelado | Antes de implementar y ejecutar |
| 2026-11-08 | **Desviación: se agrega la variante de asignación `divisible`.** Los resultados con la regla original (`rigida`) se conservan y se reportan junto a los de la variante | Con la regla del modelo cada municipio lo atiende como máximo una brigada. En 2024 Jocotán (338 casos) y Camotán (236) superan la capacidad de una brigada de 221, así que la cobertura tiene un techo de Σ min(casos, C): 73.0 % con C = 150, 88.4 % con 221 y 96.6 % con 300, sin importar cuántas brigadas haya. Para dimensionar, un municipio grande debe poder recibir más de una brigada |

### Variante `divisible` (desviación del 2026-11-08)

- **Regla:** los municipios se procesan por casos descendentes, como en la regla original. La demanda de cada uno puede repartirse entre todas las brigadas a su alcance (tiempo ≤ T), tomando primero la más cercana, hasta cubrirla o agotar las capacidades.
- **Lo que no cambia:** el objetivo J, las métricas y la enumeración exhaustiva. J usa la misma función del modelo (`asignacion.calcular_objetivo`), con la distancia media ponderada por los casos atendidos.
- **Verificación:** un verificador independiente comprueba capacidad, tiempo máximo y demanda en cada plan.
- **Implementación:** `brigadas/dimensionamiento.py` (`asignar_divisible`), sin modificar el código del modelo.
- **Configuración de referencia** (§6): se evalúa con la variante `divisible`, porque con la regla rígida la meta del 90 % es inalcanzable para C = 221.
- **Figura adicional (2026-11-08):** en la configuración de referencia (5 brigadas) los tres enfoques eligen el mismo plan, así que su mapa no muestra diferencias. Se agrega `dimensionamiento_mapa_k3.png` (3 brigadas, mismos C y T), que ilustra la disyuntiva entre los enfoques de cobertura y de vulnerabilidad. No cambia ningún resultado.
