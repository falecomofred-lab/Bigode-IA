@echo off
setlocal EnableExtensions
title CONFIGURAR O DEEPSEEK NA MODAL - Venure
cd /d "%~dp0"
set "ROOT=%~dp0"

rem ---------------------------------------------------------------------
rem CONFIGURAR O DEEPSEEK NA PLACA -- uma vez so             (18/09/2026)
rem
rem   Depois de rodar este arquivo, o BIGODE.bat abre direto no DeepSeek
rem   pela Modal. Voce nao precisa rodar isto de novo.
rem
rem   Sao tres passos, e o arquivo faz os tres na ordem certa:
rem     1. publica o app `bigode-coder` na sua conta da Modal
rem     2. voce cola o endereco que o passo 1 imprimir
rem     3. ele testa, guarda, e ja deixa o perfil `codigo` ligado
rem
rem   Por que nao esta tudo automatico: o endereco so existe DEPOIS do
rem   deploy, e ele e diferente em cada conta. Ler a saida do `modal` para
rem   adivinhar o endereco seria frageil -- o formato muda entre versoes, e
rem   um endereco errado gravado em silencio custa mais do que uma colagem.
rem ---------------------------------------------------------------------

echo ============================================================
echo        DEEPSEEK NA MODAL  -  configuracao unica
echo ============================================================
echo.

set "PY="
if exist "%ROOT%python\python.exe" set "PY=%ROOT%python\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY (
  echo [ERRO] Python nao encontrado.
  pause & exit /b 1
)

set "BIGODE_PERFIL=codigo"

echo [1 de 3]  Conferindo os arquivos antes de publicar...
echo.
"%PY%" "%ROOT%TESTAR_TUDO.py"
if errorlevel 1 (
  echo.
  echo [ERRO] O TESTAR_TUDO reprovou. Nao vou publicar com defeito conhecido.
  pause & exit /b 1
)

echo.
echo [2 de 3]  Publicando o DeepSeek na Modal...
echo           A primeira vez demora: ela baixa ~10 GB do modelo
echo           DURANTE a construcao da imagem, e nao no primeiro pedido.
echo.
"%PY%" -m modal deploy "%ROOT%modal_motor.py"
if errorlevel 1 (
  echo.
  echo [ERRO] O deploy falhou. O texto acima diz o motivo.
  echo        Se for falta de login:  python -m modal setup
  pause & exit /b 1
)

echo.
echo ============================================================
echo  Copie acima o endereco que termina em
echo      -bigode-coder-servidor.modal.run
echo  e cole no proximo passo. A senha e a mesma do bigode-token.
echo ============================================================
echo.
echo [3 de 3]  Guardando o endereco e ligando o perfil...
echo.
"%PY%" "%ROOT%usar_modal_motor.py"
if errorlevel 1 (
  echo.
  echo [ERRO] Nao guardei nada. Confira o endereco e a senha e rode de novo.
  pause & exit /b 1
)

"%PY%" "%ROOT%motor_perfil.py" codigo

echo.
echo ============================================================
echo  PRONTO. Agora e so abrir o BIGODE.bat -- ele ja sobe no
echo  DeepSeek pela Modal, e acorda a placa antes de voce digitar.
echo.
echo  Para voltar ao Qwen (melhor com ferramentas):
echo      python motor_perfil.py conversa
echo ============================================================
echo.
pause
endlocal
