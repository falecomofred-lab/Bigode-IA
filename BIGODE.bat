@echo off
setlocal EnableExtensions EnableDelayedExpansion
title BIGODE IA - Venure
cd /d "%~dp0"
set "ROOT=%~dp0"
set "PORT=8082"
set "BIGODE_PORT=7000"
set "LOG=%ROOT%motor.log"

echo ============================================================
echo                       BIGODE IA
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

rem ---------------------------------------------------------------------
rem MOTOR REMOTO PRIMEIRO                                     (17/09)
rem
rem   Este arquivo subia o llamafile SEMPRE e, se ele nao respondesse em
rem   90 segundos, SAIA COM ERRO -- sem nunca abrir o Bigode. Com o
rem   provedor em Hugging Face ou Modal nao existe motor local para subir:
rem   o modelo roda longe daqui. Era esperar 90 segundos por nada e depois
rem   desistir.
rem
rem   Quem responde qual provedor esta valendo e o config.json, lido pelo
rem   Python -- para nao haver duas verdades, uma no .bat e outra no
rem   cerebro.py.
rem ---------------------------------------------------------------------
rem   Quem responde e o _provedor.py: uma palavra na saida e um codigo.
rem   Python em arquivo, e nao inline -- os parenteses do codigo Python
rem   dentro de um `for /f` quebravam o proprio `cmd`, com a mensagem
rem   "/'config.json').read_text(encoding foi inesperado neste momento."
rem ---------------------------------------------------------------------
rem QUAL MOTOR DA MODAL ABRIR                                 (18/09)
rem
rem   BIGODE_PERFIL decide, e o padrao e `codigo` -- o DeepSeek-Coder-V2,
rem   que foi o pedido: velocidade de placa com o modelo de codigo.
rem
rem   Para abrir com o Qwen numa vez so, sem editar nada:
rem       set BIGODE_PERFIL=conversa  &&  BIGODE.bat
rem
rem   UMA RESSALVA QUE IMPORTA NO DIA A DIA
rem       O DeepSeek NAO faz chamada de ferramenta nativa -- o chat
rem       template dele e o formato antigo "User:/Assistant:", sem secao de
rem       tools. O Bigode cai no protocolo de texto, que funciona e erra
rem       mais. Para ler arquivo, mexer no navegador e desenhar pela Pipi,
rem       o perfil `conversa` acerta mais.
rem
rem   Se o perfil escolhido ainda nao estiver configurado, o motor_perfil
rem   avisa e NAO troca nada -- o Bigode abre com o que ja estava valendo,
rem   em vez de nao abrir.
rem ---------------------------------------------------------------------
if not defined BIGODE_PERFIL set "BIGODE_PERFIL=codigo"
"%PY%" "%ROOT%motor_perfil.py" %BIGODE_PERFIL%
echo.

set "PROVARQ=%TEMP%\bigode_provedor.txt"
set "REMOTO="
set "PRONTO=0"
"%PY%" "%ROOT%_provedor.py" > "%PROVARQ%" 2>nul
if not errorlevel 1 set "PRONTO=1"
if exist "%PROVARQ%" set /p REMOTO=<"%PROVARQ%"
del "%PROVARQ%" >nul 2>&1

if /i "%REMOTO%"=="local" set "REMOTO="

if defined REMOTO (
  echo Motor: %REMOTO% ^(roda fora desta maquina^)
  if "%PRONTO%"=="0" (
    echo.
    echo [AVISO] O provedor esta escolhido, mas falta a credencial.
    if /i "%REMOTO%"=="huggingface" echo         Rode:  python usar_huggingface.py
    if /i "%REMOTO%"=="modal"       echo         Rode:  python usar_modal_motor.py
    echo         Vou abrir a tela mesmo assim -- ela mostra o mesmo recado.
  ) else (
    rem ACORDAR A PLACA AGORA, E NAO NA SUA PRIMEIRA PERGUNTA  (18/09)
    rem
    rem   O conteiner da Modal dorme depois de 5 minutos sem uso. Acordar
    rem   leva de 20 a 40 segundos -- e essa espera caia inteira na
    rem   primeira pergunta do dia, numa caixa de texto que nao responde.
    rem   Parecia travamento, e foi exatamente a queixa de hoje.
    rem
    rem   Os segundos de placa sao os mesmos; o que muda e que agora eles
    rem   passam aqui, com um recado na tela, antes de voce digitar.
    "%PY%" "%ROOT%motor_perfil.py" --acordar
  )
  echo.
  goto ABRIR
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
echo Motor local verificado.

:ABRIR
rem QUEM ABRE O NAVEGADOR E O cerebro.py, NAO ESTE ARQUIVO     (17/09)
rem
rem   Eu tinha posto um `start "" "http://127.0.0.1:7000"` aqui. Mas o
rem   cerebro.py ja faz isso na partida, e faz melhor: ele monta o
rem   endereco a partir da configuracao de rede, entao acerta o IP quando
rem   "acesso_rede" esta ligado.
rem
rem   Resultado dos dois juntos: DUAS janelas do Chrome, com dois
rem   enderecos diferentes para a mesma porta -- 127.0.0.1:7000 e o nome
rem   da maquina:7000. Uma delas ficava sobrando em toda abertura.
echo Abrindo o Bigode...
"%PY%" "%ROOT%cerebro.py"
echo.
echo Bigode encerrado. Consulte %LOG% se houver erro.
pause
endlocal
