@echo off
title CEREBRO - Instalador
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALAR_NO_PENDRIVE.ps1"
