# Nota para los Integrantes 2 y 3: cómo usar la demanda

**De:** Integrante 1 · **Fecha:** 2026-10-22 · **Rama:** `feat/datos-demanda`

Los datos y el modelo de demanda están listos y validados. Esta nota explica cómo usarlos en la simulación, qué cuidar y qué necesitamos de ustedes.

## 1. Qué está listo

| Qué | Dónde |
|---|---|
| Municipios de Chiquimula con código y centroide (para la matriz de distancias) | `data/processed/municipios.csv` (filtrar `codigo_departamento == "GT20"`) |
| Casos registrados y población 0–4 por municipio y año, 2012–2024 | `data/processed/panel_GT20.csv` |
| Modelo de demanda elegido y sus parámetros | `resultados/demanda_validacion.json`, `resultados/demanda_dispersion.json` |
| Funciones de demanda | `brigadas/demanda.py` |
| Cómo se eligió el modelo y la validación | `docs/protocolo_demanda.md` (congelado) |

Para regenerar todo desde cero, ver `README.md`: `descargar_datos`, después `preparar_datos` y luego `validar_demanda`.

## 2. Modelo elegido

- **Media:** M0, la tasa estable por municipio de 2015–2022 multiplicada por la población proyectada del año objetivo.
- **Variabilidad:** binomial negativa NB2, `Var = μ + a·μ²` con **`a = 0.116`**. Los datos están muy sobredispersos (φ = 7.4), así que **no usen Poisson**.

## 3. Cómo generar la demanda de una réplica

```python
import json

import numpy as np
import pandas as pd

from brigadas import demanda

panel = pd.read_csv("data/processed/panel_GT20.csv", dtype={"codigo": str})
desarrollo = panel[panel["anio"].between(2015, 2022)]
modelo = demanda.ajustar(desarrollo, "M0", range(2015, 2023))

# Año objetivo: lo definen ustedes en docs/diseno_experimental.md.
objetivo = panel[panel["anio"] == 2024].sort_values("codigo")
mu = modelo.media(objetivo)["mu"].to_numpy()  # mismo orden que objetivo (por código)

a = json.loads(open("resultados/demanda_dispersion.json", encoding="utf-8").read())["a"]
rng = np.random.default_rng(semilla_de_la_replica)
d = demanda.generar_demanda(mu, rng, "binomial_negativa", a=a, escala=1.0)
```

- **Orden:** ordenen los municipios por `codigo` tanto en la demanda como en la matriz de distancias, para que los índices coincidan.
- **Misma demanda para las dos políticas:** generen `d` **una vez por réplica** y pásenla a la política base y al algoritmo genético (plan §5.4). No generen una demanda distinta para cada política.
- **Sensibilidad:** usen `escala=1.2` para +20 %. Con `replicas=n` se obtienen `n` escenarios de una vez, en un arreglo de forma `(n, 11)`.
- **Reproducibilidad:** siempre con un `rng` explícito; no usen `np.random.seed` ni estado global.

## 4. Lo que deben saber antes de diseñar los experimentos

1. **El nivel absoluto está subestimado.** Contra los registros reales de 2023–2024, el modelo previó 1,285 casos y hubo 2,068 (**−38 %**). Pero **ordena muy bien** los municipios (Spearman 0.94; acierta los 3 con más casos). En otras palabras, el *dónde* es confiable y el *cuánto* no.
2. **La sensibilidad de +20 % se queda corta.** El nivel observado equivale a una escala de aproximadamente **1.6** (2,068 / 1,285). Sugerimos agregar un escenario con esa escala o justificar por qué no.
3. **Con capacidad 150, la restricción de capacidad está activa:** la capacidad total cubre el 68 % de la demanda media de 2015–2022. **Con `D_max = 40 km`, la restricción de distancia casi no limita** (53 de 55 pares quedan dentro). Ver el bloque `_supuestos` en `configs/piloto_chiquimula.json`.
4. **No usen 2023–2024 para calibrar** pesos ni parámetros del algoritmo genético. Son la referencia real reservada.
5. Los valores de demanda son **casos registrados**, no prevalencia ni necesidad clínica.

## 5. Lo que necesitamos de ustedes

1. **Comparación con la realidad (rúbrica, 6 pts):** la guía pide comparar la referencia real, la base y la mejorada con las mismas métricas. Cuando estén listas la política base y el algoritmo genético, necesitamos poder llamar a `resolver_politica(...)` con la **demanda observada** de 2023 y 2024 (los casos reales del panel, no simulados). Así calculamos qué fracción de los casos reales cubre cada política. Esa comparación la hacemos nosotros; solo necesitamos que la interfaz del plan §9 acepte cualquier vector de demanda.
2. **Revisión cruzada:** el Integrante 2 revisa nuestro PR (pipeline y contratos de datos), según el plan §10.
3. **Año objetivo y escenarios:** definirlos en `docs/diseno_experimental.md` para que coincida con lo que validamos.

Dudas, a nosotros. Si algo de la interfaz no les sirve, mejor ajustarlo ahora que después de los experimentos.
