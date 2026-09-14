# SINCRONIZAR.ps1 - deixa as tres copias do Bigode falando a mesma lingua
#
#     Drive     G:\Meu Drive\projetos\Cerebro          <- a versao boa
#     Local     C:\Users\Frederico\Downloads\Cerebro
#     Pendrive  G:\Outros computadores\...\Pen IA\Cerebro
#
# POR QUE O DRIVE MANDA
#     Em 12/09 o Manus escreveu direto no Drive. Desde entao o Local esta
#     tres dias atras (sem modal_cliente, runtime, pesquisa_profunda) e o
#     Pendrive esta bem mais atras ainda. Uma delas tem que ser a verdade,
#     e a unica candidata e o Drive.
#
# POR QUE ELE NAO PUXA DE VOLTA SOZINHO
#     Seria comodo dizer "o arquivo mais novo vence". Mas "mais novo" e a
#     data do arquivo, nao a qualidade dele: copiar uma pasta antiga hoje
#     deixa tudo com a data de hoje. O Pendrive tem arquivos "(1).py", que
#     e o que o navegador faz quando voce baixa duas vezes -- sinal de que
#     aquela pasta ja foi remexida na mao.
#
#     Entao ele NAO puxa. Ele AVISA: lista o que esta mais novo fora do
#     Drive e deixa voce olhar antes. Se for coisa boa, voce copia para o
#     Drive e roda de novo.
#
# O QUE ELE NUNCA TOCA
#     Cada copia tem a sua vida. Sao respeitados em todas:
#
#         config.json        o motor, as pastas e a janela daquela maquina
#         conexoes.json      as suas chaves
#         usuarios.json      as contas de acesso
#         conversas\         o que voce conversou
#         Historico\         o diario
#         chroma_db\         a memoria semantica
#         projetos\ auditoria\ producao\
#         python\            o Python portatil do pendrive
#         *.gguf  *.log      as IAs e os registros
#
#     E ele NUNCA APAGA nada no destino. So acrescenta e atualiza.
#
# Rode assim, na pasta do Cerebro no Drive:
#
#     powershell -ExecutionPolicy Bypass -File .\SINCRONIZAR.ps1
#
# Para so ver o que ele faria, sem mexer em nada:
#
#     powershell -ExecutionPolicy Bypass -File .\SINCRONIZAR.ps1 -Ensaio
#
# Venure - venure.com.br

param([switch]$Ensaio)

$ErrorActionPreference = 'Stop'

$DRIVE = Split-Path -Parent $MyInvocation.MyCommand.Path
$DESTINOS = @(
    @{ nome = 'Local';    caminho = 'C:\Users\Frederico\Downloads\Cerebro' },
    @{ nome = 'Pendrive'; caminho = 'G:\Outros computadores\USB e dispositivos externos\Pen IA\Cerebro' }
)

# Pastas que pertencem a cada copia e nao viajam.
$PASTAS_FORA = @(
    'conversas', 'Historico', 'chroma_db', 'auditoria', 'projetos',
    'producao', 'Criativos', 'python', '__pycache__', '.pytest_cache',
    '.git', 'node_modules'
)

# Arquivos que pertencem a cada copia e nao viajam.
$ARQUIVOS_FORA = @(
    'config.json', 'conexoes.json', 'usuarios.json',
    'motor.chave', 'motor_remoto.txt',
    '*.gguf', '*.log', '*.pyc', '*.crdownload',
    '* (1).*', '* (2).*'          # sobras de download repetido
)

Write-Host ''
Write-Host ('=' * 72)
if ($Ensaio) {
    Write-Host '  SINCRONIZAR  --  ENSAIO (nao vou mexer em nada)'
} else {
    Write-Host '  SINCRONIZAR  --  Drive  ->  Local e Pendrive'
}
Write-Host ('=' * 72)
Write-Host ''
Write-Host "  Fonte: $DRIVE"
Write-Host ''

# ---------------------------------------------------------------- avisos
# Antes de copiar, olhar se alguem mexeu fora do Drive. Sobrescrever em
# silencio um trabalho que voce fez no Local seria imperdoavel.
function Avisar-MaisNovos($destino, $nome) {
    $novos = @()
    Get-ChildItem -LiteralPath $DRIVE -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object {
            $rel = $_.FullName.Substring($DRIVE.Length).TrimStart('\')
            $primeiro = ($rel -split '\\')[0]
            ($PASTAS_FORA -notcontains $primeiro) -and ($rel -notlike '_lixo-*')
        } |
        ForEach-Object {
            $rel = $_.FullName.Substring($DRIVE.Length).TrimStart('\')
            $la = Join-Path $destino $rel
            if (Test-Path -LiteralPath $la) {
                $outro = Get-Item -LiteralPath $la
                # 2 segundos de folga: sistemas de arquivo diferentes
                # guardam a hora com precisao diferente.
                if ($outro.LastWriteTime -gt $_.LastWriteTime.AddSeconds(2)) {
                    $novos += $rel
                }
            }
        }
    return $novos
}

$temAviso = $false
foreach ($d in $DESTINOS) {
    if (-not (Test-Path -LiteralPath $d.caminho)) { continue }
    $novos = Avisar-MaisNovos $d.caminho $d.nome
    if ($novos.Count -gt 0) {
        $temAviso = $true
        Write-Host ("  ATENCAO -- estes arquivos estao MAIS NOVOS no {0}:" -f $d.nome)
        foreach ($n in $novos) { Write-Host ("      {0}" -f $n) }
        Write-Host ''
        Write-Host '      Eu vou sobrescrever com a versao do Drive.'
        Write-Host '      Se algum deles for trabalho seu, copie para o Drive'
        Write-Host '      ANTES de continuar.'
        Write-Host ''
    }
}

if ($temAviso -and -not $Ensaio) {
    $r = Read-Host '  Continuar mesmo assim? (s/N)'
    if ($r -ne 's' -and $r -ne 'S') {
        Write-Host ''
        Write-Host '  Parei. Nada foi alterado.'
        Write-Host ''
        exit 0
    }
    Write-Host ''
}

# ---------------------------------------------------------------- copia
$argsBase = @('/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NC', '/NS', '/NP', '/R:1', '/W:1')
foreach ($p in $PASTAS_FORA) { $argsBase += @('/XD', $p) }
foreach ($a in $ARQUIVOS_FORA) { $argsBase += @('/XF', $a) }
if ($Ensaio) { $argsBase += '/L' }          # /L = so lista, nao copia

foreach ($d in $DESTINOS) {
    Write-Host ('  ' + ('-' * 68))
    Write-Host ("  {0}" -f $d.nome)
    Write-Host ("  {0}" -f $d.caminho)

    if (-not (Test-Path -LiteralPath $d.caminho)) {
        Write-Host '     NAO ENCONTRADO -- pulando.'
        if ($d.nome -eq 'Pendrive') {
            Write-Host '     O pendrive esta espetado? O Drive para Desktop esta ligado?'
        }
        Write-Host ''
        continue
    }

    # /E copia subpastas, inclusive vazias. SEM /MIR e SEM /PURGE: nada e
    # apagado no destino, jamais.
    & robocopy $DRIVE $d.caminho @argsBase | Out-Null
    $codigo = $LASTEXITCODE

    # Robocopy: 0 = nada mudou, 1 = copiou, 2 = extras, 3 = os dois.
    # 8 ou mais e falha de verdade.
    if ($codigo -ge 8) {
        Write-Host ("     FALHOU (codigo {0}). Veja se a pasta esta aberta em outro programa." -f $codigo)
    } elseif ($Ensaio) {
        Write-Host '     (ensaio) seria atualizado.'
    } elseif ($codigo -eq 0) {
        Write-Host '     Ja estava igual.'
    } else {
        Write-Host '     Atualizado.'
    }
    Write-Host ''
}

# ---------------------------------------------------------------- fim
Write-Host ('=' * 72)
if ($Ensaio) {
    Write-Host '  ENSAIO TERMINADO. Nada foi alterado.'
    Write-Host '  Rode sem -Ensaio para valer.'
} else {
    Write-Host '  PRONTO.'
    Write-Host ''
    Write-Host '  Confira que as tres estao inteiras:'
    Write-Host '      python conferir_tudo.py'
    Write-Host ''
    Write-Host '  Lembre: config.json, conversas e Historico continuam'
    Write-Host '  diferentes em cada copia. E de proposito.'
}
Write-Host ('=' * 72)
Write-Host ''
