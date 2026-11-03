# brigadas_de_atencion_nutricional
Proyecto Final - Modelación y Simulación

Sistema de apoyo a decisiones que compara una asignación territorial base de brigadas móviles de atención nutricional contra una asignación optimizada con un algoritmo genético. Usa la demanda municipal estimada a partir de los registros agregados de desnutrición aguda en menores de cinco años (MSPAS).

> Los resultados son **simulados** bajo supuestos declarados. No representan una reducción real de la desnutrición ni una recomendación operativa para el MSPAS.

## Entorno (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

## Datos

```powershell
.\.venv\Scripts\python.exe -m scripts.descargar_datos
.\.venv\Scripts\python.exe -m scripts.preparar_datos --config configs/piloto_chiquimula.json
```

- `descargar_datos` baja las fuentes de `data/fuentes.json` y verifica su SHA-256 contra `data/descargas.json`. Si la versión publicada cambió, se detiene.
- `preparar_datos` genera el panel municipio × año en `data/processed/` y, en `resultados/`, el reporte de calidad (`calidad_datos.json`), la tabla de unión territorial (`union_municipios.csv`) y la comparación de departamentos candidatos (`candidatos_departamento.csv`).

Detalles de las fuentes y sus limitaciones: `docs/fuentes.md` y `data/README.md`.

## Demanda

```powershell
.\.venv\Scripts\python.exe -m scripts.validar_demanda --config configs/piloto_chiquimula.json
```

Aplica el protocolo congelado de `docs/protocolo_demanda.md`: backtest de los modelos M0, M1 y M2 con los años de desarrollo, elección entre Poisson y binomial negativa, y validación única contra el MSPAS de 2023–2024. Las salidas quedan en `resultados/demanda_*.json` y `resultados/figuras/validacion_demanda.png`.

## Simulación y política base

```powershell
.\.venv\Scripts\python.exe -m scripts.ejecutar_baseline --config configs/piloto_chiquimula.json
.\.venv\Scripts\python.exe -m scripts.demo_caso_pequeno
```

- `ejecutar_baseline` corre la heurística base (sin el algoritmo genético) con 30 réplicas pareadas, sensibilidad +20 % y evaluación con los casos reales de 2023–2024. Requiere haber corrido antes los scripts de datos y demanda.
- `demo_caso_pequeno` usa una red **sintética** de 5 municipios con óptimo conocido.

Modelo, restricciones, unidades y supuestos: `docs/modelo.md`.

## Estructura

```text
brigadas/    paquete principal (datos, demanda, simulación, GA, métricas, visualización)
scripts/     puntos de entrada reproducibles
configs/     escenarios en JSON
data/        fuentes, referencias territoriales y datos (raw/processed no se versionan)
tests/       pruebas pytest
docs/        documentación del proyecto (docs/privado/ no se versiona)
resultados/  salidas de los scripts
```
