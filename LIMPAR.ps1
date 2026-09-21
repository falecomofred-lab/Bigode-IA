# LIMPAR.ps1 - tira da frente o que nao serve mais
#
# Aprovado pelo Fred em 13/09/2026 (niveis 1 e 2 da lista).
#
# ELE NAO APAGA. Move para uma quarentena com a data no nome. Se algo fizer
# falta, esta tudo la. Apagar de verdade e decisao sua, depois de ver que
# nada quebrou.
#
# O ERRO QUE A PRIMEIRA VERSAO COMETEU   (e por que ele nao volta)
#
#     A quarentena ficava DENTRO da pasta do Cerebro, e logo depois o script
#     varria o Cerebro com -Recurse procurando __pycache__. A varredura
#     enxergava a propria quarentena: cada cache movido para la era
#     reencontrado e movido de novo, um nivel mais fundo, gerando
#
#         _lixo-2026-09-13\Cerebro\_lixo-2026-09-13\Cerebro\...
#
#     ate o Windows recusar pelo tamanho do caminho.
#
#     Tres mudancas impedem a repeticao:
#
#     1. A quarentena agora fica FORA das pastas varridas, um nivel acima,
#        em projetos\. Estruturalmente ela nao pode ser encontrada.
#     2. A lista de pastas a mover e fechada com @( ) ANTES de mover
#        qualquer coisa. Enumerar e mover ao mesmo tempo e a raiz do
#        problema.
#     3. Qualquer caminho que contenha "_lixo-" e ignorado, como cinto e
#        suspensorio.
#
# Rode assim, na pasta do Cerebro:
#
#     powershell -ExecutionPolicy Bypass -File .\LIMPAR.ps1
#
# Venure - venure.com.br

$ErrorActionPreference = 'Stop'

$cerebro  = Split-Path -Parent $MyInvocation.MyCommand.Path
$projetos = Split-Path -Parent $cerebro
$pipi     = Join-Path $projetos 'Pipi IA'

# FORA do Cerebro e FORA da Pipi. E isto que impede a recursao.
$lixo = Join-Path $projetos ('_lixo-bigode-' + (Get-Date -Format 'yyyy-MM-dd'))

Write-Host ''
Write-Host ('=' * 70)
Write-Host '  LIMPEZA - Bigode IA e Pipi IA'
Write-Host ('=' * 70)
Write-Host ''
Write-Host "  Quarentena: $lixo"
Write-Host ''

New-Item -ItemType Directory -Force -Path $lixo | Out-Null

$movidos = 0
$ausentes = 0

function Mover($origem, $rotuloDestino, $porque) {
    if (-not (Test-Path -LiteralPath $origem)) {
        Write-Host ("  -  nao existe: {0}" -f $rotuloDestino)
        $script:ausentes++
        return
    }
    $destino = Join-Path $script:lixo $rotuloDestino
    $pasta = Split-Path -Parent $destino
    if ($pasta -and -not (Test-Path -LiteralPath $pasta)) {
        New-Item -ItemType Directory -Force -Path $pasta | Out-Null
    }
    if (Test-Path -LiteralPath $destino) {
        Remove-Item -LiteralPath $destino -Recurse -Force
    }
    Move-Item -LiteralPath $origem -Destination $destino -Force
    Write-Host ("  OK {0}" -f $rotuloDestino)
    Write-Host ("       {0}" -f $porque)
    $script:movidos++
}

# ---------------------------------------------------------------- NIVEL 1
Write-Host '  NIVEL 1 - lixo tecnico'
Write-Host ('  ' + ('-' * 66))

Mover (Join-Path $cerebro '.pytest_cache') 'Cerebro\.pytest_cache' `
      'cache do pytest, recriado sozinho'

Mover (Join-Path $cerebro 'web\colab.html') 'Cerebro\web\colab.html' `
      'tela aposentada; nenhum codigo a serve desde 10/09'

Mover (Join-Path $cerebro 'INSTALAR_NO_PENDRIVE.ps1') 'Cerebro\INSTALAR_NO_PENDRIVE.ps1' `
      'o pendrive saiu do projeto'

Mover (Join-Path $pipi 'comfyui.log') 'Pipi IA\comfyui.log' `
      'log de uma execucao que falhou'

Mover (Join-Path $pipi 'index.html') 'Pipi IA\index.html' `
      'orfao: o servidor le o web\index.html'

# Os __pycache__. A lista e FECHADA antes de mover -- ver o cabecalho.
foreach ($raiz in @($cerebro, $pipi)) {
    if (-not (Test-Path -LiteralPath $raiz)) { continue }
    $nome = Split-Path -Leaf $raiz

    $achados = @(
        Get-ChildItem -LiteralPath $raiz -Directory -Recurse -Filter '__pycache__' `
            -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notlike '*_lixo-*' }
    )

    foreach ($p in $achados) {
        if (-not (Test-Path -LiteralPath $p.FullName)) { continue }
        $rel = $p.FullName.Substring($raiz.Length).TrimStart('\')
        Mover $p.FullName (Join-Path $nome $rel) 'cache do Python'
    }
}

# O relatorio com o nome corrompido. Nao da para escrever o nome aqui sem
# reintroduzir o mesmo problema de acentuacao que o corrompeu -- entao
# procuramos por padrao e preservamos o de nome legivel.
$bom = 'Relatório técnico de oportunidades de melhoria de velocidade — Bigode IA.md'
$relatorios = @(
    Get-ChildItem -LiteralPath $cerebro -File -Filter 'Relat*.md' |
    Where-Object { $_.Name -ne $bom }
)
foreach ($r in $relatorios) {
    Mover $r.FullName ('Cerebro\' + $r.Name) `
          'copia do relatorio com o nome corrompido por encoding'
}

# ---------------------------------------------------------------- NIVEL 2
Write-Host ''
Write-Host '  NIVEL 2 - duplicatas'
Write-Host ('  ' + ('-' * 66))

Mover (Join-Path $cerebro 'RELATORIO_MELHORIAS_VELOCIDADE_BIGODE_IA.md') `
      'Cerebro\RELATORIO_MELHORIAS_VELOCIDADE_BIGODE_IA.md' `
      'mesmo relatorio; fica o de nome legivel'

Mover (Join-Path $pipi 'workflow.example.json') 'Pipi IA\workflow.example.json' `
      'so o workflow.json e lido pelo servidor'

Mover (Join-Path $pipi 'workflow_flux_gguf.json') 'Pipi IA\workflow_flux_gguf.json' `
      'so o workflow.json e lido pelo servidor'

# ---------------------------------------------------------------- fim
Write-Host ''
Write-Host ('=' * 70)
Write-Host ("  {0} movidos, {1} ja nao estavam la." -f $movidos, $ausentes)
Write-Host ''
Write-Host '  NAO APAGUEI NADA. Esta tudo em:'
Write-Host ("      {0}" -f $lixo)
Write-Host ''
Write-Host '  Agora rode o autoteste para confirmar que nada quebrou:'
Write-Host '      python conferir_tudo.py'
Write-Host ''
Write-Host '  Se em uma semana nada tiver feito falta, apague a pasta.'
Write-Host ('=' * 70)
Write-Host ''
