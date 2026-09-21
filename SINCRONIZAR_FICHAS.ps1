# ============================================================
# Leva as fichas PROJETO.md para dentro da memoria do Cerebro.
#
#   powershell -ExecutionPolicy Bypass -File .\SINCRONIZAR_FICHAS.ps1
#
# Depois disso, quando voce disser "olha o Sabor e Prosa", ele encontra a
# ficha sozinho pela ferramenta memoria() e ja sabe: o que o sistema faz, as
# pendencias, as convencoes e o que nao fazer ali.
#
# Rode de novo sempre que atualizar alguma ficha.
# ============================================================

$projetos = "G:\Meu Drive\projetos"
$cerebro  = if (Test-Path "D:\Cerebro") { "D:\Cerebro" } else { "$env:USERPROFILE\Downloads\Cerebro" }
$destino  = Join-Path $cerebro "memoria\projetos"

New-Item -ItemType Directory -Path $destino -Force | Out-Null

Write-Host ""
Write-Host "Cerebro em: $cerebro" -ForegroundColor Cyan
Write-Host ""

$fichas = Get-ChildItem $projetos -Directory -EA SilentlyContinue |
          Where-Object { $_.Name -notlike "_*" } |
          ForEach-Object {
              $f = Join-Path $_.FullName "PROJETO.md"
              if (Test-Path -LiteralPath $f) {
                  [PSCustomObject]@{ Projeto = $_.Name; Ficha = $f }
              }
          }

if (-not $fichas) {
    Write-Host "Nenhum PROJETO.md encontrado em $projetos" -ForegroundColor Yellow
    exit
}

foreach ($f in $fichas) {
    $alvo = Join-Path $destino ("$($f.Projeto).md")
    $texto = Get-Content -LiteralPath $f.Ficha -Raw -Encoding UTF8

    # Cabecalho que ajuda a memoria a casar a busca pelo nome do projeto,
    # inclusive quando o Fred escreve com espaco em vez de underline.
    $apelidos = ($f.Projeto -replace '[_-]', ' ')
    $cabeca = @"
# PROJETO: $($f.Projeto)

Também chamado de: $apelidos
Pasta: $projetos\$($f.Projeto)

---

"@
    Set-Content -LiteralPath $alvo -Value ($cabeca + $texto) -Encoding UTF8
    $kb = [math]::Round((Get-Item -LiteralPath $alvo).Length/1KB, 1)
    Write-Host ("  {0,-28} {1,6} KB" -f $f.Projeto, $kb) -ForegroundColor Gray
}

Write-Host ""
Write-Host "$($fichas.Count) fichas na memoria do Cerebro." -ForegroundColor Green
Write-Host "Pasta: $destino" -ForegroundColor Gray
Write-Host ""
Write-Host "Teste perguntando ao Cerebro:" -ForegroundColor Cyan
Write-Host '   "o que voce sabe sobre o Lucas Garage?"' -ForegroundColor White
Write-Host '   "quais pendencias tem no Sabor e Prosa?"' -ForegroundColor White
Write-Host ""
