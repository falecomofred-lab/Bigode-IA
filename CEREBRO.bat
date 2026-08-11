@echo off
setlocal enabledelayedexpansion
title CEREBRO - Venure
cd /d "%~dp0"

echo ============================================================
echo    V E N U R E
echo    C E R E B R O
echo ============================================================
echo.

REM ---- 1. Localizar o motor (llamafile + modelo) --------------
set "MOTOR="
set "MODELO="
set "PASTA_MOTOR="

for %%D in ("%~dp0.." "%~dp0") do (
  for %%F in ("%%~fD\llamafile*.exe") do if not defined MOTOR (
    set "MOTOR=%%~fF"
    set "PASTA_MOTOR=%%~dpF"
  )
  for %%F in ("%%~fD\*.gguf") do if not defined MODELO set "MODELO=%%~nxF"
)

if not defined MOTOR (
  echo [ERRO] Nao encontrei o llamafile^(.exe^) no pendrive.
  echo        Coloque-o na raiz do pendrive, junto do arquivo .gguf
  pause & exit /b
)
if not defined MODELO (
  echo [ERRO] Nao encontrei nenhum modelo .gguf no pendrive.
  pause & exit /b
)

echo   Motor ..: %MOTOR%
echo   Modelo .: %MODELO%
echo.

REM ---- 2. Escolher o Python -----------------------------------
set "PY="
if exist "%~dp0python\python.exe" set "PY=%~dp0python\python.exe"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [ERRO] Python nao encontrado neste computador.
  echo        Instale em https://python.org/downloads ^(marque "Add to PATH"^)
  pause & exit /b
)

REM ---- 3. Subir o motor em segundo plano ----------------------
tasklist /fi "imagename eq llamafile*" 2>nul | find /i "llamafile" >nul
if errorlevel 1 (
  echo   Ligando o motor em segundo plano...
  start "Motor Cerebro" /min cmd /c ""%MOTOR%" -m "%PASTA_MOTOR%%MODELO%" --server --port 8082 --gpu disable --no-mmap -c 8192"
) else (
  echo   Motor ja estava rodando.
)

echo.
REM ---- 4. Subir o Cerebro -------------------------------------
"%PY%" "%~dp0cerebro.py"

pause
