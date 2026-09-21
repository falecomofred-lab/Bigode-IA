# CONSERTAR_LIMPEZA.ps1 - desfaz o estrago do LIMPAR.ps1 de 13/09
#
# O QUE ACONTECEU
#   O LIMPAR.ps1 criou a quarentena DENTRO da pasta do Cerebro e, logo
#   depois, varreu o Cerebro inteiro com -Recurse procurando __pycache__.
#   A varredura enxergava a propria quarentena. Cada cache movido para la
#   era reencontrado e movido de novo, um nivel mais fundo, gerando
#
#       _lixo-2026-09-13\Cerebro\_lixo-2026-09-13\Cerebro\...
#
#   repetido ate o Windows recusar pelo tamanho do caminho.
#
# O QUE ESTE SCRIPT FAZ
#   1. Apaga SO o galho recursivo (que contem apenas caches do Python,
#      arquivos que o proprio Python recria sozinho).
#   2. Move o que sobrou da quarentena para FORA do Cerebro, para
#      projetos\_lixo-bigode-2026-09-13 -- assim nenhuma varredura futura
#      volta a enxerga-la.
#   3. Mostra o que ficou guardado la.
#
#   Nada de codigo e tocado. O conferir_tudo.py continua dando PASSOU.
#
# POR QUE ROBOCOPY E NAO Remove-Item
#   Remove-Item nao alcanca caminhos acima de 260 caracteres, e o galho
#   recursivo passa MUITO disso. O robocopy trabalha com caminho longo
#   nativamente: espelhar uma pasta vazia por cima esvazia o destino.
#
# Rode assim, na pasta do Cerebro:
#
#     powershell -ExecutionPolicy Bypass -File .\CONSERTAR_LIMPEZA.ps1
#
# Venure - venure.com.br

$ErrorActionPreference = 'Stop'

$cerebro   = Split-Path -Parent $MyInvocation.MyCommand.Path
$projetos  = Split-Path -Parent $cerebro
$quarentena = Join-Path $cerebro '_lixo-2026-09-13'
$galho      = Join-Path $quarentena 'Cerebro\_lixo-2026-09-13'
$novoDestino = Join-Path $projetos '_lixo-bigode-2026-09-13'

Write-Host ''
Write-Host ('=' * 70)
Write-Host '  CONSERTANDO A LIMPEZA'
Write-Host ('=' * 70)
Write-Host ''

if (-not (Test-Path -LiteralPath $quarentena)) {
    Write-Host '  Nao ha quarentena para consertar. Nada a fazer.'
    Write-Host ''
    exit 0
}

# ---- 1. apagar o galho recursivo -----------------------------------------
if (Test-Path -LiteralPath $galho) {
    Write-Host '  1. Apagando o galho recursivo (so caches do Python)...'

    $vazio = Join-Path $env:TEMP ('vazio_' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $vazio | Out-Null

    # /MIR espelha: como a origem esta vazia, o destino fica vazio.
    & robocopy $vazio $galho /MIR /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null

    # O robocopy devolve codigos abaixo de 8 para sucesso. Acima disso,
    # tentamos o rd com o prefixo \\?\, que tambem ignora o limite de 260.
    if ($LASTEXITCODE -ge 8) {
        Write-Host '     robocopy reclamou; tentando pelo rd...'
        & cmd /c rd /s /q "\\?\$galho" 2>$null
    }

    Remove-Item -LiteralPath $galho -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $vazio -Recurse -Force -ErrorAction SilentlyContinue

    if (Test-Path -LiteralPath $galho) {
        Write-Host ''
        Write-Host '     NAO CONSEGUI APAGAR TUDO.'
        Write-Host '     Sobrou algo em:'
        Write-Host "       $galho"
        Write-Host '     Apague pelo Explorador de Arquivos e rode este script de novo.'
        Write-Host ''
        exit 1
    }
    Write-Host '     Pronto.'
} else {
    Write-Host '  1. O galho recursivo ja nao existe.'
}

# ---- 2. tirar a quarentena de dentro do Cerebro ---------------------------
Write-Host ''
Write-Host '  2. Movendo a quarentena para fora da pasta do Cerebro...'

if (Test-Path -LiteralPath $novoDestino) {
    # Ja existe: junta o conteudo em vez de falhar.
    Get-ChildItem -LiteralPath $quarentena -Force | ForEach-Object {
        Move-Item -LiteralPath $_.FullName -Destination $novoDestino -Force
    }
    Remove-Item -LiteralPath $quarentena -Recurse -Force
} else {
    Move-Item -LiteralPath $quarentena -Destination $novoDestino -Force
}

Write-Host "     Agora em: $novoDestino"

# ---- 3. mostrar o que ficou guardado -------------------------------------
Write-Host ''
Write-Host '  3. O que esta guardado na quarentena:'
Write-Host ('  ' + ('-' * 66))

Get-ChildItem -LiteralPath $novoDestino -Recurse -File -ErrorAction SilentlyContinue |
    ForEach-Object {
        $rel = $_.FullName.Substring($novoDestino.Length).TrimStart('\')
        Write-Host ("     {0}" -f $rel)
    }

Write-Host ''
Write-Host ('=' * 70)
Write-Host '  CONSERTADO.'
Write-Host ''
Write-Host '  Confira que o codigo continua inteiro:'
Write-Host '      python conferir_tudo.py'
Write-Host ''
Write-Host '  Os __pycache__ voltam sozinhos na proxima vez que o Python'
Write-Host '  rodar. Nao ha nada a recuperar deles.'
Write-Host ('=' * 70)
Write-Host ''
