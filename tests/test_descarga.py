import hashlib

import pytest

from scripts.descargar_datos import ErrorDescarga, sincronizar


@pytest.fixture
def origen(tmp_path):
    archivo = tmp_path / "origen" / "fuente.csv"
    archivo.parent.mkdir()
    archivo.write_bytes(b"a;b\r\n1;2\r\n")
    return archivo


def fuente_local(origen):
    return [{"id": "prueba", "url": origen.as_uri(), "archivo": "fuente.csv", "licencia": "CC-BY"}]


def test_descarga_registra_checksum(tmp_path, origen):
    registro = {}
    estados = sincronizar(fuente_local(origen), registro, tmp_path / "raw")
    assert estados == {"prueba": "descargado"}
    assert registro["prueba"]["sha256"] == hashlib.sha256(origen.read_bytes()).hexdigest()
    assert (tmp_path / "raw" / "fuente.csv").read_bytes() == origen.read_bytes()


def test_segunda_ejecucion_solo_verifica(tmp_path, origen):
    registro = {}
    sincronizar(fuente_local(origen), registro, tmp_path / "raw")
    fecha = registro["prueba"]["fecha_descarga_utc"]
    origen.write_bytes(b"cambio en el servidor")  # no debe volver a bajarse
    estados = sincronizar(fuente_local(origen), registro, tmp_path / "raw")
    assert estados == {"prueba": "verificado"}
    assert registro["prueba"]["fecha_descarga_utc"] == fecha


def test_copia_limpia_con_misma_version_conserva_registro(tmp_path, origen):
    registro = {}
    sincronizar(fuente_local(origen), registro, tmp_path / "raw")
    registro["prueba"]["fecha_descarga_utc"] = "2026-01-01T00:00:00+00:00"
    original = dict(registro["prueba"])
    (tmp_path / "raw" / "fuente.csv").unlink()  # clon nuevo: raw vacío, registro versionado
    estados = sincronizar(fuente_local(origen), registro, tmp_path / "raw")
    assert estados == {"prueba": "descargado"}
    assert registro["prueba"] == original


def test_archivo_raw_editado_se_detecta(tmp_path, origen):
    registro = {}
    sincronizar(fuente_local(origen), registro, tmp_path / "raw")
    (tmp_path / "raw" / "fuente.csv").write_bytes(b"editado a mano")
    with pytest.raises(ErrorDescarga, match="no coincide"):
        sincronizar(fuente_local(origen), registro, tmp_path / "raw")


def test_version_nueva_en_servidor_se_rechaza_sin_forzar(tmp_path, origen):
    registro = {}
    sincronizar(fuente_local(origen), registro, tmp_path / "raw")
    (tmp_path / "raw" / "fuente.csv").unlink()  # copia limpia del repositorio
    origen.write_bytes(b"version nueva")
    with pytest.raises(ErrorDescarga, match="cambió"):
        sincronizar(fuente_local(origen), registro, tmp_path / "raw")
    assert not (tmp_path / "raw" / "fuente.csv").exists()

    estados = sincronizar(fuente_local(origen), registro, tmp_path / "raw", forzar=True)
    assert estados == {"prueba": "actualizado"}
    assert registro["prueba"]["sha256"] == hashlib.sha256(b"version nueva").hexdigest()
