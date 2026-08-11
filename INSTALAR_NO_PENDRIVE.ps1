# =====================================================================
#  CEREBRO - Instalador
#  Copia tudo para o pendrive e deixa pronto para usar em qualquer PC.
#  Venure - venure.com.br
# =====================================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   V E N U R E   -   C E R E B R O" -ForegroundColor Cyan
Write-Host "   Instalador do pendrive" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------- 1. Descobrir o pendrive ----------------------------------
$origem = $PSScriptRoot

$candidatos = Get-Volume | Where-Object {
    $_.DriveLetter -and $_.DriveLetter -ne 'C' -and $_.SizeRemaining -gt 1GB
} | Sort-Object DriveLetter

if (-not $candidatos) { Write-Host "Nenhuma unidade disponivel encontrada." -ForegroundColor Red; exit }

Write-Host "Unidades disponiveis:"
foreach ($v in $candidatos) {
    $temModelo = (Get-ChildItem "$($v.DriveLetter):\" -Filter *.gguf -ErrorAction SilentlyContinue).Count -gt 0
    $marca = if ($temModelo) { "  <-- tem modelo .gguf" } else { "" }
    Write-Host ("   {0}:  {1}  ({2:N1} GB livres){3}" -f $v.DriveLetter, $v.FileSystemLabel, ($v.SizeRemaining/1GB), $marca)
}
Write-Host ""

$comModelo = $candidatos | Where-Object {
    (Get-ChildItem "$($_.DriveLetter):\" -Filter *.gguf -ErrorAction SilentlyContinue).Count -gt 0
} | Select-Object -First 1

$sugerida = if ($comModelo) { $comModelo.DriveLetter } else { $candidatos[0].DriveLetter }
$letra = Read-Host "Letra da unidade do pendrive [$sugerida]"
if ([string]::IsNullOrWhiteSpace($letra)) { $letra = $sugerida }
$letra = $letra.TrimEnd(':').ToUpper()
$destino = "${letra}:\Cerebro"

Write-Host ""
Write-Host "Instalando em $destino" -ForegroundColor Yellow
Write-Host ""

# ---------- 2. Copiar os arquivos ------------------------------------
Write-Host "[1/4] Copiando arquivos..."
New-Item -ItemType Directory -Path $destino -Force | Out-Null

$itens = @("cerebro.py","ferramentas.py","indexar.py","mcp_servidor.py",
           "config.json","conexoes.json","LEIAME.md","PROJETO_CEREBRO.md",
           "prototipo.html","web","memoria",
           "ATUALIZAR_MEMORIA.bat")

foreach ($item in $itens) {
    $caminho = Join-Path $origem $item
    if (Test-Path $caminho) {
        Copy-Item $caminho -Destination $destino -Recurse -Force
        Write-Host "      + $item"
    }
}

# ---------- 3. Python portatil ---------------------------------------
Write-Host ""
Write-Host "[2/4] Python portatil"
$pastaPy = Join-Path $destino "python"

if (Test-Path (Join-Path $pastaPy "python.exe")) {
    Write-Host "      ja existe, pulando."
} else {
    $resp = Read-Host "      Baixar Python portatil (~15 MB)? Deixa o pen autonomo em qualquer PC [S/n]"
    if ($resp -ne 'n' -and $resp -ne 'N') {
        try {
            $url = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip"
            $zip = Join-Path $env:TEMP "python-portatil.zip"
            Write-Host "      baixando..."
            Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
            New-Item -ItemType Directory -Path $pastaPy -Force | Out-Null
            Expand-Archive -Path $zip -DestinationPath $pastaPy -Force
            Remove-Item $zip -Force

            # libera importacao de modulos da pasta do script
            Get-ChildItem $pastaPy -Filter "python*._pth" | ForEach-Object {
                $conteudo = Get-Content $_.FullName
                $conteudo = $conteudo -replace '^#\s*import site', 'import site'
                $conteudo += "`n."
                Set-Content $_.FullName $conteudo
            }
            Write-Host "      pronto." -ForegroundColor Green
        } catch {
            Write-Host "      falhou ($($_.Exception.Message)). Vai usar o Python do PC." -ForegroundColor Yellow
        }
    }
}

# ---------- 4. Launcher na raiz --------------------------------------
Write-Host ""
Write-Host "[3/4] Criando o atalho na raiz do pendrive..."

$bat = @"
@echo off
setlocal enabledelayedexpansion
title CEREBRO - Venure
cd /d "%~dp0"
color 0B

echo.
echo   ============================================================
echo      V E N U R E
echo      C E R E B R O
echo   ============================================================
echo.

set "MOTOR="
set "MODELO="
for %%F in ("%~dp0llamafile*.exe") do if not defined MOTOR set "MOTOR=%%~fF"
for %%F in ("%~dp0*.gguf")        do if not defined MODELO set "MODELO=%%~fF"

if not defined MOTOR  (echo   [ERRO] llamafile nao encontrado na raiz do pendrive. & pause & exit /b)
if not defined MODELO (echo   [ERRO] nenhum modelo .gguf na raiz do pendrive.      & pause & exit /b)

set "PY="
if exist "%~dp0Cerebro\python\python.exe" set "PY=%~dp0Cerebro\python\python.exe"
if not defined PY (where python >nul 2>&1 && set "PY=python")
if not defined PY (echo   [ERRO] Python nao encontrado. & pause & exit /b)

echo   Motor ..: %MODELO%
echo   Python .: %PY%
echo.

tasklist /fi "imagename eq llamafile*" 2>nul | find /i "llamafile" >nul
if errorlevel 1 (
  echo   Ligando o motor em segundo plano ^(leva alguns minutos^)...
  start "Motor Cerebro" /min cmd /c ""%MOTOR%" -m "%MODELO%" --server --port 8082 --gpu disable --no-mmap -c 8192"
) else (
  echo   Motor ja estava rodando.
)

echo.
"%PY%" "%~dp0Cerebro\cerebro.py"
pause
"@

Set-Content -Path "${letra}:\CEREBRO.bat" -Value $bat -Encoding ASCII
Write-Host "      ${letra}:\CEREBRO.bat criado." -ForegroundColor Green

# ---------- 5. Ajustar caminhos e indexar ----------------------------
Write-Host ""
Write-Host "[4/4] Ajustando configuracao..."

$semBom = New-Object System.Text.UTF8Encoding $false
$cfgPath = Join-Path $destino "config.json"
$cfg = ([IO.File]::ReadAllText($cfgPath)).TrimStart([char]0xFEFF) | ConvertFrom-Json
$cfg.pastas_liberadas = @("G:\Meu Drive\projetos", $destino)
[IO.File]::WriteAllText($cfgPath, ($cfg | ConvertTo-Json -Depth 6), $semBom)

$py = if (Test-Path (Join-Path $pastaPy "python.exe")) { Join-Path $pastaPy "python.exe" } else { "python" }
$resp = Read-Host "      Indexar seus projetos do Drive agora? [S/n]"
if ($resp -ne 'n' -and $resp -ne 'N') {
    Push-Location $destino
    & $py "indexar.py"
    Pop-Location
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "   PRONTO" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "   Para usar:  clique 2x em  ${letra}:\CEREBRO.bat"
Write-Host "   Interface:  http://localhost:7000"
Write-Host ""
Write-Host "   Ponte com o Claude - use este comando nas conexoes MCP:"
Write-Host "   $py $destino\mcp_servidor.py" -ForegroundColor Cyan
Write-Host ""
Read-Host "Pressione Enter para sair"
