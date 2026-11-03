"""Configuración de escenarios: carga desde JSON y validación de dominio."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path


class ErrorConfiguracion(ValueError):
    """La configuración no cumple el contrato del escenario."""


@dataclass(frozen=True)
class ConfiguracionEscenario:
    departamento: str
    anios_desarrollo: tuple[int, ...]
    anios_validacion: tuple[int, ...]
    cantidad_brigadas: int
    capacidad_por_brigada: int
    distancia_max_km: float
    replicas: int
    semilla_raiz: int

    def __post_init__(self) -> None:
        if not isinstance(self.departamento, str) or not self.departamento.strip():
            raise ErrorConfiguracion("departamento debe ser un código no vacío")
        for nombre in ("anios_desarrollo", "anios_validacion"):
            anios = getattr(self, nombre)
            if not anios or not all(isinstance(a, int) for a in anios):
                raise ErrorConfiguracion(f"{nombre} debe contener al menos un año entero")
            if len(set(anios)) != len(anios):
                raise ErrorConfiguracion(f"{nombre} contiene años repetidos")
        if set(self.anios_desarrollo) & set(self.anios_validacion):
            raise ErrorConfiguracion("los años de desarrollo y validación se traslapan")
        if min(self.anios_validacion) <= max(self.anios_desarrollo):
            raise ErrorConfiguracion("los años de validación deben ser posteriores a los de desarrollo")
        _exigir_entero_positivo("cantidad_brigadas", self.cantidad_brigadas)
        _exigir_entero_positivo("replicas", self.replicas)
        if not isinstance(self.capacidad_por_brigada, int) or self.capacidad_por_brigada < 0:
            raise ErrorConfiguracion("capacidad_por_brigada debe ser un entero no negativo")
        if not isinstance(self.distancia_max_km, (int, float)) or self.distancia_max_km < 0:
            raise ErrorConfiguracion("distancia_max_km debe ser un número no negativo")
        if not isinstance(self.semilla_raiz, int) or self.semilla_raiz < 0:
            raise ErrorConfiguracion("semilla_raiz debe ser un entero no negativo")


def _exigir_entero_positivo(nombre: str, valor: object) -> None:
    if not isinstance(valor, int) or isinstance(valor, bool) or valor <= 0:
        raise ErrorConfiguracion(f"{nombre} debe ser un entero positivo")


def cargar_configuracion(ruta: str | Path) -> ConfiguracionEscenario:
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    esperados = {f.name for f in fields(ConfiguracionEscenario)}
    # Las claves que empiezan con "_" son notas para personas y no forman parte del contrato.
    datos = {k: v for k, v in datos.items() if not k.startswith("_")}
    desconocidos = sorted(set(datos) - esperados)
    if desconocidos:
        raise ErrorConfiguracion(f"campos desconocidos: {', '.join(desconocidos)}")
    faltantes = sorted(esperados - set(datos))
    if faltantes:
        raise ErrorConfiguracion(f"campos faltantes: {', '.join(faltantes)}")
    datos["anios_desarrollo"] = tuple(datos["anios_desarrollo"])
    datos["anios_validacion"] = tuple(datos["anios_validacion"])
    return ConfiguracionEscenario(**datos)
