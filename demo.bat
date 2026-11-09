@echo off
rem Abre el menú interactivo de la demostración (doble clic).
rem Requiere haber creado el entorno: py -3.12 -m venv .venv  y  pip install -r requirements.txt
chcp 65001 > nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno .venv. Cree el entorno antes, segun el README.
    pause
    exit /b 1
)
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m scripts.menu
