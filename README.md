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

## Simulación y política base

```powershell
.\.venv\Scripts\python.exe -m scripts.ejecutar_baseline --config configs/piloto_chiquimula.json
.\.venv\Scripts\python.exe -m scripts.demo_caso_pequeno
```

- `ejecutar_baseline` corre la heurística base (sin el algoritmo genético) con 30 réplicas pareadas por escala de demanda (×1.0, ×1.2 y ×1.6, ver `docs/protocolo_parametros.md`) y evaluación con los casos reales de 2023–2024. Requiere haber corrido antes los scripts de datos y demanda.
- `demo_caso_pequeno` usa una red **sintética** de 5 municipios con óptimo conocido.

Modelo, restricciones, unidades y supuestos: `docs/modelo.md`.

## Algoritmo genético y experimentos

```powershell
.\.venv\Scripts\python.exe -m scripts.ejecutar_experimentos --config configs/piloto_chiquimula.json
.\.venv\Scripts\python.exe -m scripts.generar_reporte --config configs/piloto_chiquimula.json
```

- `ejecutar_experimentos` compara la política base con el algoritmo genético en 5 condiciones (nominal, demanda ×1.2 y ×1.6, capacidad 177 y `D_max` de 40 km), con 30 réplicas pareadas cada una. También evalúa ambas con los casos reales de 2023–2024 y mide la brecha del algoritmo frente al óptimo exacto. Las salidas quedan en `resultados/experimentos_*`.
- `generar_reporte` produce las figuras en `resultados/figuras/`: mapa de asignación, comparación de escenarios, diferencias pareadas y convergencia.
- La columna `tiempo_ejecucion_ms` cambia en cada ejecución; el resto de los resultados es reproducible.

Diseño y parámetros congelados: `docs/diseno_experimental.md`. Técnica: `docs/algoritmo_genetico.md`.

### Análisis adicional de escalabilidad

```powershell
.\.venv\Scripts\python.exe -m scripts.ejecutar_escalabilidad
```

Compara el algoritmo genético con la política base, una búsqueda voraz y una búsqueda aleatoria con el mismo presupuesto de evaluaciones, en Huehuetenango (K = 4, con óptimo exacto) y en el país completo (K = 10, 20 y 40). Tarda unos 28 minutos. Después, `generar_reporte` produce `resultados/figuras/escalabilidad.png`. Diseño y resultados: `docs/analisis_escalabilidad.md`.

## Propuesta: estudio de tamizaje

```powershell
.\.venv\Scripts\python.exe -m scripts.ejecutar_tamizaje
```

Responde **cuántas brigadas hacen falta, y dónde, para identificar un porcentaje de los casos esperados** en Chiquimula.

- **Qué hacen las brigadas:** evalúan niños de 0 a 4 años (población INE 2024). La productividad es de 20 a 35 evaluaciones por día, según el PMA, por 220 días de campo (supuesto).
- **Casos identificados:** niños evaluados por la tasa de casos de 2024 de cada municipio.
- **Reparto de niños entre brigadas:** óptimo, con programación lineal y tiempos de viaje por carretera.
- **Búsqueda de la ubicación:** exacta (hasta 5 brigadas), voraz y con el algoritmo genético (varias brigadas pueden compartir municipio).
- **Duración:** entre 20 y 40 minutos.

Diseño y resultados: `docs/estudio_tamizaje.md`.

### Menú interactivo (demo)

Doble clic en **`demo.bat`**, o bien:

```powershell
.\.venv\Scripts\python.exe -m scripts.menu
```

Opciones:

1. **Planificar brigadas:** dónde ubicar N brigadas y cuántos casos identificarían, con mapa.
2. **Comparar números de brigadas:** tabla del estudio de tamizaje.
3. **Ver resultados principales:** validación de la demanda, política base frente al algoritmo genético y brigadas necesarias.
4. **Abrir una figura.**

Cada pregunta muestra su valor por defecto entre corchetes; Enter lo acepta. Requiere haber creado el `.venv` y haber instalado `requirements.txt`.

### Interfaz web

Doble clic en **`demo_web.bat`**, o bien:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Se abre en el navegador (`http://localhost:8501`) y no necesita internet. Tiene controles para el número de brigadas, la productividad, el tiempo de viaje y el objetivo, y cuatro pestañas:

- **Planificador:** indicadores, mapa y detalle por municipio.
- **¿Cuántas brigadas?:** curva y tabla del estudio.
- **Resultados del estudio.**
- **Supuestos y fuentes.**

Usa el mismo cálculo que el planificador por comando. Para cerrarla: Ctrl+C en la terminal o cerrar la ventana. La configuración (`.streamlit/config.toml`) desactiva el envío de estadísticas de uso.

### Planificador por comando

```powershell
.\.venv\Scripts\python.exe -m scripts.planificar --brigadas 6
.\.venv\Scripts\python.exe -m scripts.planificar --brigadas 4 --productividad 20 --tiempo 45 --objetivo ninos --mapa
```

Devuelve en segundos el plan para cualquier número de brigadas: bases, casos identificados, niños evaluados, tiempo de viaje y detalle por municipio. Con `--mapa` guarda `resultados/figuras/plan_<N>.png`. Avisa si los valores se salen del rango estudiado.

## Antecedente: estudio de dimensionamiento con capacidad en casos

Superado por el estudio de tamizaje: expresaba la capacidad en "casos atendidos por año", sin respaldo empírico. Se conserva como antecedente.

```powershell
.\.venv\Scripts\python.exe -m scripts.ejecutar_dimensionamiento
```

Responde cuántas brigadas hacen falta y dónde ubicarlas en Chiquimula, con los casos reales de 2024 y tiempos de viaje por carretera (OSRM sobre OpenStreetMap, guardados en `data/referencia/osrm_chiquimula.json`).

- Prueba de 1 a 8 brigadas, capacidad de 150, 221 o 300 casos/año y viaje máximo de 45, 60 o 90 minutos.
- Usa tres enfoques: regla de más casos, óptimo de cobertura y óptimo por vulnerabilidad.
- Compara dos reglas de asignación: la del modelo y una divisible, que permite repartir un municipio entre varias brigadas.

Tarda unos 25 segundos. Después, `generar_reporte` produce las curvas y los mapas. Diseño y resultados: `docs/estudio_dimensionamiento.md`.

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
