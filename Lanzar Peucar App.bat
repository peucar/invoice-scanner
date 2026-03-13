@echo off
title Peucar App
cd /d "%~dp0"

py --version >nul 2>&1
if %ERRORLEVEL% == 0 (
    set PYTHON_CMD=py
) else (
    python --version >nul 2>&1
    if %ERRORLEVEL% == 0 (
        set PYTHON_CMD=python
    ) else (
        echo Python no encontrado. Instala Python y marcalo en el PATH.
        pause
        exit /b 1
    )
)

echo Instalando dependencias...
%PYTHON_CMD% -m pip install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo Error instalando dependencias.
    pause
    exit /b 1
)

echo Iniciando aplicacion...
start /b py main.py
timeout /t 1 /nobreak >nul
exit
