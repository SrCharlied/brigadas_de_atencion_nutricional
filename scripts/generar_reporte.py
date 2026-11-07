"""Genera tablas y figuras a partir de resultados/.

Responsable: Integrante 3. Pendiente de implementar (Hito 5).
Lee los datos experimentales en resultados/ genera 3 figuras para comportamiento, comparacion de escenarios y sensibilidad.

"""

import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuración visual global
sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({'font.sans-serif': 'DejaVu Sans', 'font.size': 11})

FIGURAS_DIR = "resultados/Figuras"

def asegurar_directorios():
    os.makedirs(FIGURAS_DIR, exist_ok=True)

def graficar_comparacion_escenarios(df_replicas):
    """Figura 1: Comparación corregida para evitar que el texto choque con el boxplot."""
    plt.figure(figsize=(9, 6))
    
    df_melted = df_replicas.melt(
        id_vars=["replica"], 
        value_vars=["cobertura_base", "cobertura_optimizada"],
        var_name="Escenario", 
        value_name="Cobertura (%)"
    )
    df_melted["Escenario"] = df_melted["Escenario"].replace({
        "cobertura_base": "Escenario Base (Voraz)",
        "cobertura_optimizada": "Escenario Mejorado (AG)"
    })
    
    ax = sns.boxplot(x="Escenario", y="Cobertura (%)", data=df_melted, palette=["#e74c3c", "#2ecc71"], width=0.4)
    sns.stripplot(x="Escenario", y="Cobertura (%)", data=df_melted, color="black", alpha=0.5, jitter=0.2, size=6)
    
    plt.title("Figura 1: Comparación de Cobertura Simulada entre Escenarios (30 Réplicas)", fontsize=13, fontweight='bold', pad=15)
    plt.ylabel("Cobertura de Demanda (%)")
    plt.xlabel("Configuración del Modelo")
    
    # Ampliamos el límite superior del eje Y para dar espacio holgado a las etiquetas de promedio
    plt.ylim(45, 105)
    
    media_base = df_replicas["cobertura_base"].mean()
    media_opt = df_replicas["cobertura_optimizada"].mean()
    
    # Posicionamos el texto de forma segura arriba de los bigotes de la caja
    ax.text(0, 75.0, f"Promedio: {media_base:.1f}%", horizontalalignment='center', fontweight='bold', color='#c0392b', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    ax.text(1, 95.0, f"Promedio: {media_opt:.1f}%", horizontalalignment='center', fontweight='bold', color='#27ae60', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
    
    plt.tight_layout()
    ruta_guardado = os.path.join(FIGURAS_DIR, "figura1_comparacion_escenarios.png")
    plt.savefig(ruta_guardado, dpi=300)
    plt.close()
    print(f"[+] Figura 1 guardada en: {ruta_guardado}")

def graficar_comportamiento_replicas(df_replicas):
    """Figura 2: Leyenda colocada en la parte inferior para proteger el título y evitar solapamientos."""
    plt.figure(figsize=(10, 6.5))
    
    plt.plot(df_replicas["replica"], df_replicas["cobertura_base"], marker='o', color='#e74c3c', label='Escenario Base', linestyle='--')
    plt.plot(df_replicas["replica"], df_replicas["cobertura_optimizada"], marker='s', color='#2ecc71', label='Escenario Optimizado (AG)', linestyle='-')
    
    plt.axhline(df_replicas["cobertura_base"].mean(), color='#e74c3c', linestyle=':', alpha=0.7, label='Media Base')
    plt.axhline(df_replicas["cobertura_optimizada"].mean(), color='#2ecc71', linestyle=':', alpha=0.7, label='Media Optimizada')
    
    plt.title("Figura 2: Variabilidad de Cobertura por Réplica Independiente", fontsize=13, fontweight='bold', pad=15)
    plt.xlabel("Número de Réplica (Semilla Independiente)")
    plt.ylabel("Cobertura (%)")
    
    # Colocamos la leyenda abajo del eje X (fuera del área del gráfico) en 2 columnas ordenadas
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=True, facecolor='white', framealpha=0.9)
    
    plt.ylim(45, 98)
    plt.xticks(range(1, 31, 2))
    
    # Guardar con bbox_inches='tight' para asegurar que la leyenda de abajo no se corte al exportar
    ruta_guardado = os.path.join(FIGURAS_DIR, "figura2_variabilidad_replicas.png")
    plt.savefig(ruta_guardado, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[+] Figura 2 guardada en: {ruta_guardado}")

def graficar_sensibilidad(df_sensibilidad):
    """Figura 3: Análisis de Sensibilidad."""
    plt.figure(figsize=(9, 5))
    
    sns.lineplot(
        x="variacion_demanda_pct", 
        y="cobertura_promedio_simulada", 
        data=df_sensibilidad, 
        marker='D', 
        color='#2980b9', 
        linewidth=2.5, 
        markersize=8
    )
    
    plt.title("Figura 3: Análisis de Sensibilidad ante Variaciones en la Demanda Municipal", fontsize=13, fontweight='bold', pad=15)
    plt.xlabel("Variación de Demanda respecto al Escenario Base (%)")
    plt.ylabel("Cobertura Promedio Estimada (%)")
    plt.axvline(0, color='gray', linestyle='--', alpha=0.6, label='Escenario Nominal (0%)')
    plt.legend(loc='upper right')
    plt.ylim(78, 83)
    
    plt.tight_layout()
    ruta_guardado = os.path.join(FIGURAS_DIR, "figura3_analisis_sensibilidad.png")
    plt.savefig(ruta_guardado, dpi=300)
    plt.close()
    print(f"[+] Figura 3 guardada en: {ruta_guardado}")

def main():
    asegurar_directorios()  
    print(" REGENERANDO GRÁFICAS")

    
    try:
        df_replicas = pd.read_csv("resultados/baseline_GT20_replicas.csv")
        df_sensibilidad = pd.read_csv("resultados/sensibilidad_resultados.csv")
        
        graficar_comparacion_escenarios(df_replicas)
        graficar_comportamiento_replicas(df_replicas)
        graficar_sensibilidad(df_sensibilidad)
        
        print("\n Las graficas estan guardadas")
        
    except FileNotFoundError as e:
        print(f"\n[ERROR] No se encontraron los archivos de resultados. Corre primero: python scripts/ejecutar_experimentos.py")

if __name__ == "__main__":
    main()