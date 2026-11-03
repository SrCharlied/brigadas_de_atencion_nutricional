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

- Los archivos oficiales ya vienen versionados en `data/raw/`. `descargar_datos` verifica su SHA-256 contra `data/descargas.json` y solo descarga las fuentes que falten en `data/fuentes.json`. Si una versión publicada cambió o un portal bloquea la descarga, se detiene sin reemplazar archivos.
- `preparar_datos` genera el panel municipio × año en `data/processed/` y, en `resultados/`, el reporte de calidad (`calidad_datos.json`), la tabla de unión territorial (`union_municipios.csv`) y la comparación de departamentos candidatos (`candidatos_departamento.csv`).

Detalles de las fuentes y sus limitaciones: `docs/fuentes.md` y `data/README.md`.

## Demanda

```powershell
.\.venv\Scripts\python.exe -m scripts.validar_demanda --config configs/piloto_chiquimula.json
```

Aplica el protocolo congelado de `docs/protocolo_demanda.md`: backtest de los modelos M0, M1 y M2 con los años de desarrollo, elección entre Poisson y binomial negativa, y validación única contra el MSPAS de 2023–2024. Las salidas quedan en `resultados/demanda_*.json` y `resultados/figuras/validacion_demanda.png`.

## Estructura

```text
brigadas/    paquete principal (datos, demanda, simulación, GA, métricas, visualización)
scripts/     puntos de entrada reproducibles
configs/     escenarios en JSON
data/        fuentes, referencias territoriales y datos (raw se versiona; processed se regenera)
tests/       pruebas pytest
docs/        documentación del proyecto (docs/privado/ no se versiona)
resultados/  salidas de los scripts
```
