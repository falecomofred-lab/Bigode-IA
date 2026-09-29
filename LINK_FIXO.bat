@echo off
setlocal EnableExtensions
title BIGODE - Link fixo (Tailscale Funnel)
cd /d "%~dp0"
set "ROOT=%~dp0"

rem =====================================================================
rem  LINK FIXO DO BIGODE                                     (29/09/2026)
rem
rem  Da ao Bigode um endereco https que NAO muda e abre de qualquer lugar
rem  (4G, Wi-Fi de outra casa), com o PC ligado em casa.
rem
rem    LINK_FIXO.bat            liga (so precisa rodar UMA vez)
rem    LINK_FIXO.bat status     mostra o link
rem    LINK_FIXO.bat desligar   tira o Bigode da internet
rem
rem  Depois de ligado, o link volta sozinho quando o PC reinicia.
rem  O BIGODE.bat continua igual: e ele que precisa estar aberto.
rem =====================================================================

echo ============================================================
echo                 BIGODE - LINK FIXO
echo ============================================================
echo.

rem --- Python (mesma ordem do BIGODE.bat) ------------------------------
set "PY="
if exist "%LOCALAPPDATA%\Bigode\python\python.exe" set "PY=%LOCALAPPDATA%\Bigode\python\python.exe"
if not defined PY if exist "%ROOT%python\python.exe" set "PY=%ROOT%python\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"

rem --- Tailscale -------------------------------------------------------
set "TS="
if exist "%ProgramFiles%\Tailscale\tailscale.exe" set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
if not defined TS for /f "delims=" %%T in ('where tailscale 2^>nul') do if not defined TS set "TS=%%T"

if not defined TS (
  echo  O Tailscale nao esta instalado. Ele e gratis.
  echo.
  where winget >nul 2>nul
  if not errorlevel 1 (
    echo  Instalando pelo winget...
    winget install --id Tailscale.Tailscale -e
  ) else (
    echo  Abrindo a pagina de download. Instale e rode este arquivo de novo.
    start "" "https://tailscale.com/download/windows"
    pause & exit /b 1
  )
  if exist "%ProgramFiles%\Tailscale\tailscale.exe" set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
)
if not defined TS (
  echo  [ERRO] Nao achei o tailscale.exe depois da instalacao.
  echo         Instale por https://tailscale.com/download/windows e rode de novo.
  pause & exit /b 1
)

if /i "%~1"=="desligar" goto desligar
if /i "%~1"=="status" goto status

rem --- 1. Login no Tailscale -------------------------------------------
"%TS%" status >nul 2>nul
if errorlevel 1 (
  echo  Entre na sua conta Tailscale ^(Google, Microsoft ou GitHub^).
  echo  Vai abrir o navegador. Depois volte aqui.
  echo.
  "%TS%" up
  "%TS%" status >nul 2>nul
  if errorlevel 1 (
    echo  [ERRO] O login no Tailscale nao terminou. Rode de novo.
    pause & exit /b 1
  )
)
echo  [ok] Tailscale conectado.

rem --- 2. Trava de seguranca -------------------------------------------
if not defined PY (
  echo  [PAREI] Python nao encontrado para conferir o login do Bigode.
  pause & exit /b 1
)
"%PY%" "%ROOT%link_fixo_checar.py"
if errorlevel 1 (
  echo.
  echo  Nada foi publicado. Corrija o que esta acima e rode de novo.
  pause & exit /b 1
)

rem --- 3. Liga o Funnel ------------------------------------------------
echo.
echo  Ligando o link publico para a porta 7000...
echo  Na PRIMEIRA vez o Tailscale pede para autorizar o Funnel:
echo  ele mostra um link -- abra, clique em Enable e volte aqui.
echo.
"%TS%" funnel --bg 7000
if errorlevel 1 (
  echo.
  echo  [ERRO] O Funnel nao ligou. Leia a mensagem acima.
  pause & exit /b 1
)

:status
echo.
echo ------------------------------------------------------------
"%TS%" funnel status
echo ------------------------------------------------------------

rem Pega SO a linha que comeca com https:// (antes pegava tambem "#" e "|--").
set "LINK="
set "TMPF=%TEMP%\bigode_funnel.txt"
"%TS%" funnel status > "%TMPF%" 2>nul
findstr /b /c:"https://" "%TMPF%" > "%TMPF%.link" 2>nul
for /f "usebackq tokens=1" %%U in ("%TMPF%.link") do set "LINK=%%U"
del "%TMPF%" "%TMPF%.link" >nul 2>nul

if not defined LINK (
  echo.
  echo  [!] O Funnel nao esta ligado. Rode:  .\LINK_FIXO.bat
  echo.
  pause & exit /b 1
)
> "%ROOT%LINK_FIXO.txt" echo %LINK%
echo.
echo  SEU LINK FIXO:  %LINK%
echo  ^(salvo tambem em LINK_FIXO.txt^)

rem O link so mostra algo se o Bigode estiver rodando na porta 7000.
echo.
curl.exe -s -o nul -m 5 http://127.0.0.1:7000/api/health
if errorlevel 1 (
  echo  [!] O BIGODE NAO ESTA RODANDO. O link abre em branco ou com erro 502.
  echo      Abra o BIGODE.bat em OUTRA janela e deixe aberta ^(nao aperte Ctrl+C^).
) else (
  echo  [ok] Bigode respondendo na porta 7000. O link deve abrir o login.
)
echo.
echo  Para funcionar de fora:
echo    - o PC fica ligado e SEM hibernar;
echo    - o BIGODE.bat fica aberto;
echo    - no icone do Tailscale ^(perto do relogio^): Preferences ^> Run unattended.
echo.
pause
exit /b 0

:desligar
"%TS%" funnel reset
echo.
echo  Pronto. O Bigode saiu da internet. Em casa continua em
echo  http://127.0.0.1:7000
if exist "%ROOT%LINK_FIXO.txt" del "%ROOT%LINK_FIXO.txt"
pause
exit /b 0
