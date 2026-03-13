@echo off
:: ─────────────────────────────────────────────────────────────────
::  Peucar App — Lanzador MODO DESARROLLADOR (Live Reload)
:: ─────────────────────────────────────────────────────────────────
title DEV MODO: Peucar App

cd /d "%~dp0"

:: Usaremos 'py' directamente ya que sabemos que lo tienes configurado
echo [INIC] Modo Desarrollador... Comprobando dependencias...
py -m pip install -r requirements.txt --quiet --exists-action i

echo [INFO] Iniciando servidor local (Watchdog)...
py dev_run.py
exit
