@echo off
rem Abre la interfaz web de la demostración en el navegador (doble clic).
rem Requiere haber creado el entorno: py -3.12 -m venv .venv  y  pip install -r requirements.txt
rem Para cerrarla: cierre esta ventana o presione Ctrl+C.
chcp 65001 > nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno .venv. Cree el entorno antes, segun el README.
    pause
    exit /b 1
)
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m streamlit run app.py
