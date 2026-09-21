@echo off
title CEREBRO - Atualizar memoria
cd /d "%~dp0"
echo ============================================================
echo   Lendo seus projetos do Drive e do GitHub...
echo ============================================================
echo.
python indexar.py
echo.
pause
