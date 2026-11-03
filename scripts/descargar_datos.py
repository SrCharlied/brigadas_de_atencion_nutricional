"""Descarga las fuentes de data/fuentes.json a data/raw y verifica su checksum SHA-256.

El registro data/descargas.json se versiona: en una copia limpia del repositorio, la
descarga debe reproducir exactamente los mismos archivos. Si el servidor publica una
versión distinta, el script se detiene en lugar de mezclar versiones sin aviso.

Uso:
    python -m scripts.descargar_datos            # descarga lo faltante y verifica lo existente
    python -m scripts.descargar_datos --forzar   # acepta y registra una versión nueva
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from brigadas.datos import sha256_archivo

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "data" / "fuentes.json"
REGISTRO = RAIZ / "data" / "descargas.json"
DESTINO = RAIZ / "data" / "raw"
AGENTE = "brigadas-nutricion/0.1 (proyecto academico)"


class ErrorDescarga(RuntimeError):
    pass


def problema_respuesta(estado: int | None, encabezados) -> str | None:
    """Describe por qué una respuesta del servidor no es el archivo pedido, o None si es válida."""
    if estado in (None, 200):
        return None
    if str(encabezados.get("x-amzn-waf-action", "")).lower() == "challenge":
        return (
            f"el servidor respondió HTTP {estado} con un desafío antibots (AWS WAF) en lugar del archivo. "
            "No es un cambio de versión; reintente más tarde o use los archivos versionados en data/raw"
        )
    return f"el servidor respondió HTTP {estado} en lugar del archivo"


def _bajar(url: str, destino: Path, timeout: float) -> None:
    """Descarga a un temporal y solo reemplaza ``destino`` si la respuesta es válida y no vacía."""
    temporal = destino.with_name(destino.name + ".part")
    solicitud = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(solicitud, timeout=timeout) as respuesta:
            problema = problema_respuesta(getattr(respuesta, "status", None), respuesta.headers)
            if problema:
                raise ErrorDescarga(f"{destino.name}: {problema}")
            with temporal.open("wb") as salida:
                while bloque := respuesta.read(1 << 20):
                    salida.write(bloque)
        if temporal.stat().st_size == 0:
            raise ErrorDescarga(f"{destino.name}: la descarga llegó vacía (0 bytes); no se reemplazó ningún archivo")
    except Exception:
        temporal.unlink(missing_ok=True)
        raise
    temporal.replace(destino)


def sincronizar(
    fuentes: list[dict],
    registro: dict,
    destino: Path,
    forzar: bool = False,
    timeout: float = 120,
) -> dict[str, str]:
    """Descarga o verifica cada fuente y actualiza ``registro`` en sitio.

    Devuelve el estado por fuente: ``descargado``, ``verificado`` o ``actualizado``.
    """
    destino.mkdir(parents=True, exist_ok=True)
    estados: dict[str, str] = {}
    for fuente in fuentes:
        ruta = destino / fuente["archivo"]
        previo = registro.get(fuente["id"])
        if ruta.exists() and not forzar:
            suma = sha256_archivo(ruta)
            if previo and previo["sha256"] != suma:
                raise ErrorDescarga(
                    f"{ruta.name}: el checksum local ({suma[:12]}) no coincide con el registrado "
                    f"({previo['sha256'][:12]}). No edite archivos raw; use --forzar para volver a descargar."
                )
            if previo:
                estados[fuente["id"]] = "verificado"
                continue
        else:
            _bajar(fuente["url"], ruta, timeout)
            suma = sha256_archivo(ruta)
            if previo and previo["sha256"] != suma and not forzar:
                ruta.unlink()
                raise ErrorDescarga(
                    f"{fuente['id']}: la versión publicada cambió (registrado {previo['sha256'][:12]}, "
                    f"recibido {suma[:12]}). Revise la fuente y use --forzar para aceptarla."
                )
            if previo and previo["sha256"] == suma:
                # Misma versión que la registrada: el registro versionado no cambia.
                estados[fuente["id"]] = "descargado"
                continue
        cambio = previo is not None and previo["sha256"] != suma
        registro[fuente["id"]] = {
            "url": fuente["url"],
            "archivo": f"data/raw/{fuente['archivo']}",
            "sha256": suma,
            "bytes": ruta.stat().st_size,
            "fecha_descarga_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "licencia": fuente.get("licencia"),
        }
        estados[fuente["id"]] = "actualizado" if cambio else "descargado"
    return estados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--forzar", action="store_true", help="volver a descargar y registrar versiones nuevas")
    args = parser.parse_args(argv)

    fuentes = json.loads(CATALOGO.read_text(encoding="utf-8"))["fuentes"]
    registro = json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.exists() else {}
    try:
        estados = sincronizar(fuentes, registro, DESTINO, forzar=args.forzar)
    except ErrorDescarga as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    finally:
        REGISTRO.write_text(json.dumps(registro, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for identificador, estado in estados.items():
        print(f"{estado:<12} {identificador}  {registro[identificador]['sha256'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
