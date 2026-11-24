@echo off
title Testes reais do Bigode
cd /d "%~dp0"
set "PY="
if exist "%LOCALAPPDATA%\Bigode\python\python.exe" set "PY=%LOCALAPPDATA%\Bigode\python\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
echo Com o Bigode ABERTO, este teste manda 10 perguntas reais e mede.
echo Pode levar de 10 a 40 minutos no motor do computador.
echo.
"%PY%" "%~dp0testes_reais\rodar_testes.py" %*
