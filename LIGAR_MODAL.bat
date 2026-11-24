@echo off
setlocal EnableExtensions
title Ligar o motor da Modal - Bigode IA
cd /d "%~dp0"
rem Usa o Python do sistema primeiro: e nele que o programa "modal" costuma estar.
set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY if exist "%LOCALAPPDATA%\Bigode\python\python.exe" set "PY=%LOCALAPPDATA%\Bigode\python\python.exe"
if not defined PY (
  echo [ERRO] Python nao encontrado.
  pause & exit /b 1
)
"%PY%" "%~dp0LIGAR_MODAL.py"
endlocal
