@echo off
rem  LIGAR TUDO — um clique, sem perguntas
rem  Venure · venure.com.br · 20/09/2026
rem
rem     LIGAR_TUDO.bat            liga memoria, voz, visao e guru
rem     LIGAR_TUDO.bat indexar    reindexa a memoria na placa
rem
rem  POR QUE UM .BAT E NAO SO O .PY
rem     O `python` do PATH e o do Windows, e nele o ChromaDB nao esta
rem     instalado. Rodar por ele da "ChromaDB nao esta instalado", que
rem     parece problema de instalacao e e so o interpretador errado.
rem     Este arquivo escolhe o Python certo sozinho.

setlocal
cd /d "%~dp0"

set "PY=%LOCALAPPDATA%\Bigode\python\python.exe"
if not exist "%PY%" set "PY=G:\Outros computadores\USB e dispositivos externos\Pen IA\Cerebro\python\python.exe"
if not exist "%PY%" set "PY=%~dp0python\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" LIGAR_TUDO.py %*

echo.
pause
