@echo off
:: ─────────────────────────────────────────────────────────────────
::  Peucar Mobile — Lanzador para Celular (Red Local)
:: ─────────────────────────────────────────────────────────────────
title Movil: Peucar App
set IP_LOCAL=192.168.1.46

cd /d "%~dp0mobile-app"

echo [INIC] Iniciando App Movil...
echo [INFO] Tu IP local es: %IP_LOCAL%
echo [INFO] Para entrar desde tu celular, usa: http://%IP_LOCAL%:3000
echo.
echo Presiona Ctrl+C para detener el servidor.
echo ─────────────────────────────────────────────────────────────────
echo.

:: Ejecutamos npm run dev usando cmd /c para evitar problemas con politicas de ejecucion de script .ps1 en PowerShell
:: Usamos -H 0.0.0.0 para permitir conexiones externas
cmd /c "npm run dev -- -H 0.0.0.0"

pause
