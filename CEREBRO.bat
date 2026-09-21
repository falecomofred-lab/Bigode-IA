@echo off
setlocal EnableExtensions EnableDelayedExpansion
title BIGODE IA - Venure
cd /d "%~dp0"
set "ROOT=%~dp0"
set "PORT=8082"
set "BIGODE_PORT=7000"
set "LOG=%ROOT%motor.log"

echo ============================================================
echo                 BIGODE IA - VENURE
echo          Motor textual: llamafile / llama.cpp
echo ============================================================
echo.

rem Python: preferir o Python portatil do projeto.
set "PY="
if exist "%ROOT%python\python.exe" set "PY=%ROOT%python\python.exe"
if not defined PY if exist "G:\Outros computadores\USB e dispositivos externos\Pen IA\Cerebro\python\python.exe" set "PY=G:\Outros computadores\USB e dispositivos externos\Pen IA\Cerebro\python\python.exe"
if not defined PY if exist "%ROOT%..\Pen IA\Cerebro\python\python.exe" set "PY=%ROOT%..\Pen IA\Cerebro\python\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY (
  echo [ERRO] Python nao encontrado.
  pause & exit /b 1
)

rem Motor textual: respeitar variavel; depois procurar no projeto e no Pen IA.
if not defined BIGODE_MOTOR if exist "%ROOT%llamafile-0.10.3.exe.exe" set "BIGODE_MOTOR=%ROOT%llamafile-0.10.3.exe.exe"
if not defined BIGODE_MOTOR if exist "%ROOT%..\llamafile-0.10.3.exe.exe" set "BIGODE_MOTOR=%ROOT%..\llamafile-0.10.3.exe.exe"
if not defined BIGODE_MOTOR if exist "G:\Outros computadores\USB e dispositivos externos\Pen IA\llamafile-0.10.3.exe.exe" set "BIGODE_MOTOR=G:\Outros computadores\USB e dispositivos externos\Pen IA\llamafile-0.10.3.exe.exe"
if not defined BIGODE_MOTOR for %%D in ("%ROOT%" "%ROOT%..") do for %%F in ("%%~fD\llamafile*.exe") do if not defined BIGODE_MOTOR set "BIGODE_MOTOR=%%~fF"
if not defined BIGODE_MOTOR (
  echo [ERRO] llamafile nao encontrado.
  echo Defina BIGODE_MOTOR com o caminho completo do executavel.
  pause & exit /b 1
)

rem Modelo textual: respeitar variavel; nunca escolher modelo de imagem.
if not defined BIGODE_MODELO if exist "G:\Outros computadores\USB e dispositivos externos\Pen IA\qwen3-14b-Q4_K_M.gguf" set "BIGODE_MODELO=G:\Outros computadores\USB e dispositivos externos\Pen IA\qwen3-14b-Q4_K_M.gguf"
if not defined BIGODE_MODELO if exist "%ROOT%modelos_dados\qwen3-14b-Q4_K_M.gguf" set "BIGODE_MODELO=%ROOT%modelos_dados\qwen3-14b-Q4_K_M.gguf"
if not defined BIGODE_MODELO for %%D in ("%ROOT%" "%ROOT%..") do for %%F in ("%%~fD\*.gguf") do if not defined BIGODE_MODELO set "BIGODE_MODELO=%%~fF"
if not defined BIGODE_MODELO (
  echo [ERRO] Nenhum GGUF textual configurado.
  echo Defina BIGODE_MODELO com o caminho completo do arquivo.
  pause & exit /b 1
)

echo Python : %PY%
echo Motor  : %BIGODE_MOTOR%
echo GGUF   : %BIGODE_MODELO%
echo.

powershell -NoProfile -Command "if (Test-NetConnection 127.0.0.1 -Port %PORT% -InformationLevel Quiet) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
  echo Iniciando o motor textual na porta %PORT%...
  start "Motor Bigode" /min cmd /c ""%BIGODE_MOTOR%" -m "%BIGODE_MODELO%" --server --port %PORT% --no-mmap -c 16384 -t 6 -tb 12 --parallel 1 --no-warmup >> "%LOG%" 2^>^&1"
) else echo Motor textual ja esta respondendo na porta %PORT%.

for /l %%N in (1,1,90) do (
  powershell -NoProfile -Command "if (Test-NetConnection 127.0.0.1 -Port %PORT% -InformationLevel Quiet) { exit 0 } else { exit 1 }" >nul 2>&1
  if not errorlevel 1 goto MOTOR_OK
  timeout /t 1 /nobreak >nul
)
echo [ERRO] O motor nao respondeu em 90 segundos. Consulte %LOG%.
pause & exit /b 1

:MOTOR_OK
echo Motor verificado. Abrindo o Bigode...
"%PY%" "%ROOT%cerebro.py"
echo.
echo Bigode encerrado. Consulte %LOG% se houver erro.
pause
endlocal
