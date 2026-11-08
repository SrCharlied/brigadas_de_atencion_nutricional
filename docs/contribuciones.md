# Registro de contribuciones

**Estado:** BORRADOR para que lo revise el equipo antes de la entrega. Cada integrante confirma su fila. Los hechos salen del historial de git del repositorio.

## Integrante 1 — datos, demanda y validación real

- Requisitos de la guía (`docs/requisitos.md`).
- Adquisición y verificación de datos (MSPAS, INE vía UNFPA, HDX) con checksums SHA-256; datos crudos versionados.
- Tablas de correspondencia territorial y reporte de calidad.
- Selección del departamento piloto (`docs/decision_departamento.md`).
- Protocolo y modelo de demanda; validación contra 2023–2024 (`docs/protocolo_demanda.md`).
- Detección de la saturación de capacidad y regla de recalibración de parámetros (`docs/protocolo_parametros.md`).
- Actualización de la política base a los parámetros congelados.
- **Del 8 de noviembre de 2026, sustituyendo la parte asignada al Integrante 3:**
  - diseño experimental congelado (`docs/diseno_experimental.md`);
  - algoritmo genético (`brigadas/genetico.py`);
  - experimentos, métricas y visualizaciones (`brigadas/experimentos.py`, `metricas.py`, `visualizacion.py`, `scripts/ejecutar_experimentos.py`, `scripts/generar_reporte.py`);
  - documentación de la técnica (`docs/algoritmo_genetico.md`).
- Borrador del informe técnico.
- Herramienta de IA usada: Claude Code (Anthropic). Ver la declaración en el informe.

## Integrante 2 (Denis Rodríguez) — simulación, política base y restricciones

- Contratos compartidos y matriz de distancias.
- Regla de asignación capacitada y verificador independiente de restricciones.
- Política base y enumerador exacto.
- Flujo de réplicas con semillas pareadas y evaluación con demanda fija.
- Caso conocido y pruebas de propiedades internas.
- Documentación del modelo (`docs/modelo.md`).
- Rama `feat/simulacion-baseline`, commit `e1fe74a` (2 de noviembre de 2026).

## Integrante 3 — algoritmo genético, experimentos y visualización (asignado)

- Commit `d469ac3` (7 de noviembre de 2026): versiones de `scripts/ejecutar_experimentos.py` y `scripts/generar_reporte.py`, y tres figuras.
- Ese commit no implementaba el algoritmo genético: los módulos `genetico.py`, `experimentos.py`, `metricas.py` y `visualizacion.py` seguían vacíos. Los valores de cobertura del script eran de relleno, generados al azar y sin conexión con el modelo. Además, el script sobrescribía los resultados reales de la política base.
- El 8 de noviembre, el Integrante 1 reemplazó esos archivos por la implementación descrita arriba y regeneró los resultados de la política base.

> Pendiente: el equipo decide la redacción final de esta sección y si el Integrante 3 aporta en el informe o la presentación.
