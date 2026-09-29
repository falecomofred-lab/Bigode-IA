@echo off
rem  LIMPAR A PASTA — dois cliques, sem briga com o Windows
rem  Venure · venure.com.br · 22/09/2026
rem
rem     LIMPAR_A_PASTA.bat          mostra o que faria (nao mexe em nada)
rem     LIMPAR_A_PASTA.bat fazer    move de verdade, para a quarentena
rem
rem  POR QUE ESTE ARQUIVO EXISTE
rem     O Windows recusa rodar .ps1 sem assinatura digital:
rem
rem        "O arquivo nao esta assinado digitalmente.
rem         Nao e possivel executar este script no sistema atual."
rem
rem     Isso nao e defeito do script -- e a politica padrao do Windows, e
rem     ela existe por um bom motivo: impedir que um .ps1 baixado por
rem     engano rode com dois cliques.
rem
rem     O `-ExecutionPolicy Bypass` libera SO ESTA execucao, deste arquivo,
rem     agora. Nao muda a configuracao da maquina, e o proximo .ps1 que
rem     aparecer na sua pasta continua bloqueado como deve.

setlocal
cd /d "%~dp0"

if /i "%~1"=="fazer" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0LIMPAR_A_PASTA.ps1" -Fazer
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0LIMPAR_A_PASTA.ps1"
)

echo.
pause
