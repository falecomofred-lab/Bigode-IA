# ENVIAR_GITHUB.ps1 — manda o Cerebro e a Pipi para o GitHub
#
# venure.com.br · 13/09/2026
#
# COMO RODAR
#
#     powershell -ExecutionPolicy Bypass -File .\ENVIAR_GITHUB.ps1 -Apenas pipi
#     powershell -ExecutionPolicy Bypass -File .\ENVIAR_GITHUB.ps1 -Apenas cerebro
#     powershell -ExecutionPolicy Bypass -File .\ENVIAR_GITHUB.ps1
#
#     Acrescente -Ensaio para ver o que ele faria, sem enviar nada.
#
# ELE CONFERE ANTES DE ENVIAR
#     Lista o que o Git PRETENDE mandar e procura, nessa lista, nomes que
#     nunca deveriam sair daqui:
#
#         config.json  usuarios.json  conexoes.json  modal.json
#         motor.chave  motor_remoto.txt  memoria/projetos/
#         conversas/   Historico/   *.gguf
#
#     Se achar qualquer um, PARA e nao envia nada.
#
#     Nao e paranoia. Ate hoje o .gitignore listava so o conexoes.json,
#     enquanto o README prometia proteger cinco coisas. A promessa estava
#     num texto que o Git nao le.

param(
    [ValidateSet('tudo', 'cerebro', 'pipi')]
    [string]$Apenas = 'tudo',
    [switch]$Ensaio
)

$CEREBRO  = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJETOS = Split-Path -Parent $CEREBRO
$PIPI     = Join-Path $PROJETOS 'Pipi IA'

# NOME EXATO, NAO PEDACO DE NOME                             (14/09)
#
#     A primeira versao comparava com -like "*config.json*", e isso
#     barrava o `config.json.patch` -- um arquivo de diff, sem segredo
#     nenhum dentro, que eu conferi antes de liberar.
#
#     Falso positivo em trava de seguranca nao e inofensivo: ele ensina
#     a pessoa a ignorar o aviso. Depois de duas ou tres vezes, quando a
#     trava pegar um segredo de verdade, ela ja vai ser lida como
#     chateacao e contornada.
#
#     Agora a comparacao e por nome exato do arquivo, ou por pasta.
$ARQUIVOS_PROIBIDOS = @(
    'config.json', 'usuarios.json', 'conexoes.json', 'modal.json',
    'motor.chave', 'motor_remoto.txt', 'config.local.json'
)
$PASTAS_PROIBIDAS = @(
    'memoria/projetos/', 'conversas/', 'Historico/', 'chroma_db/',
    'auditoria/', 'producao/', 'Criativos/'
)
$EXTENSOES_PROIBIDAS = @('.gguf', '.safetensors', '.bin', '.ckpt')

Write-Host ''
Write-Host ('=' * 72)
Write-Host ('  ENVIAR PARA O GITHUB' + $(if ($Ensaio) { '   (ENSAIO — nao envio nada)' } else { '' }))
Write-Host ('=' * 72)

# ---- o git existe? ---------------------------------------------------
$temGit = $true
try { git --version 2>$null | Out-Null; if ($LASTEXITCODE -ne 0) { $temGit = $false } }
catch { $temGit = $false }

if (-not $temGit) {
    Write-Host ''
    Write-Host '  O comando `git` nao foi encontrado.'
    Write-Host '  Instale em https://git-scm.com/download/win e rode de novo.'
    Write-Host ''
    exit 1
}

function Perigosos($lista) {
    $achados = @()
    foreach ($arq in $lista) {
        $normal = $arq.Replace('\', '/')
        $nome = Split-Path $normal -Leaf
        $ext = [System.IO.Path]::GetExtension($normal)

        if ($ARQUIVOS_PROIBIDOS -contains $nome) { $achados += $arq; continue }
        if ($EXTENSOES_PROIBIDAS -contains $ext) { $achados += $arq; continue }

        $naPasta = $false
        foreach ($p in $PASTAS_PROIBIDAS) {
            if ($normal -like "$p*" -or $normal -like "*/$p*") { $naPasta = $true; break }
        }
        if ($naPasta) { $achados += $arq }
    }
    return ($achados | Select-Object -Unique)
}

# SEGREDO DENTRO DE ARQUIVO DE CODIGO                        (14/09)
#
#     O .gitignore protege por NOME de arquivo. Ele nao ajuda em nada
#     quando o segredo esta escrito dentro de um .py que deve subir.
#
#     Foi o que aconteceu: o cerebro.py trazia o endereco real do
#     endpoint da Modal, com o nome da workspace, como valor padrao.
#     Passaria por qualquer conferencia baseada em nome de arquivo.
#
#     Esta funcao le o CONTEUDO do que vai subir e procura os formatos
#     que mais vazam por descuido.
$PADROES = @(
    @{ nome = 'token do GitHub';       re = 'gh[pousr]_[A-Za-z0-9]{20,}' },
    @{ nome = 'token da HuggingFace';  re = 'hf_[A-Za-z0-9]{20,}' },
    @{ nome = 'chave da OpenAI';       re = 'sk-[A-Za-z0-9_\-]{20,}' },
    @{ nome = 'chave da Anthropic';    re = 'sk-ant-[A-Za-z0-9_\-]{20,}' },
    @{ nome = 'chave do Google';       re = 'AIza[A-Za-z0-9_\-]{30,}' },
    @{ nome = 'endpoint da Modal';     re = '[a-z0-9\-]+--[a-z0-9\-]+\.modal\.run' },
    @{ nome = 'Authorization fixo';    re = 'Bearer\s+[A-Za-z0-9_\-]{20,}' }
)

# CPF: VALIDAR, NAO RECONHECER O FORMATO                     (14/09)
#
#     A primeira versao casava com \d{3}\.\d{3}\.\d{3}-\d{2} e barrou o
#     auditar_qualidade.py, que tem `limpar_cpf('123.456.789-00')` --
#     dado de TESTE, e nem CPF valido e.
#
#     Foi o segundo falso positivo seguido desta trava. Isso nao e
#     detalhe: trava barulhenta vira habito de ignorar, e quando ela
#     pegar um segredo de verdade ja vai ser lida como chateacao.
#
#     Um CPF real tem dois digitos verificadores que fecham uma conta.
#     Placeholder de teste quase nunca fecha. Validar em vez de casar o
#     formato elimina a classe inteira de falso positivo.
function CpfValido([string]$texto) {
    $d = ($texto -replace '\D', '')
    if ($d.Length -ne 11) { return $false }
    if ($d -match '^(\d)\1{10}$') { return $false }   # 111.111.111-11 e afins

    $n = $d.ToCharArray() | ForEach-Object { [int]::Parse($_) }

    $soma = 0
    for ($i = 0; $i -lt 9; $i++) { $soma += $n[$i] * (10 - $i) }
    $r = $soma % 11
    $dv1 = if ($r -lt 2) { 0 } else { 11 - $r }
    if ($n[9] -ne $dv1) { return $false }

    $soma = 0
    for ($i = 0; $i -lt 10; $i++) { $soma += $n[$i] * (11 - $i) }
    $r = $soma % 11
    $dv2 = if ($r -lt 2) { 0 } else { 11 - $r }
    return ($n[10] -eq $dv2)
}

function SegredosNoConteudo($pasta, $lista) {
    $achados = @()
    foreach ($rel in $lista) {
        $caminho = Join-Path $pasta $rel
        if (-not (Test-Path -LiteralPath $caminho -PathType Leaf)) { continue }
        # So texto: binario nao interessa e atrasa.
        if ($rel -notmatch '\.(py|ps1|bat|md|json|html|js|css|ya?ml|txt|ipynb)$') { continue }
        try { $texto = Get-Content -LiteralPath $caminho -Raw -ErrorAction Stop }
        catch { continue }
        foreach ($p in $PADROES) {
            if ($texto -match $p.re) {
                # Mostra o achado CORTADO: a mensagem nao pode virar o
                # vazamento que ela existe para evitar.
                $trecho = $Matches[0]
                if ($trecho.Length -gt 18) { $trecho = $trecho.Substring(0, 12) + '...' }
                $achados += ("{0}  ->  {1} ({2})" -f $rel, $p.nome, $trecho)
                break
            }
        }

        # CPF: so acusa quando os digitos verificadores fecham.
        foreach ($m in ([regex]'\d{3}\.?\d{3}\.?\d{3}-?\d{2}').Matches($texto)) {
            if (CpfValido $m.Value) {
                # Nunca imprime o numero inteiro: os tres primeiros
                # digitos bastam para voce achar o arquivo.
                $achados += ("{0}  ->  CPF real ({1}...)" -f $rel, $m.Value.Substring(0, 3))
                break
            }
        }
    }
    return ($achados | Select-Object -Unique)
}

function Enviar($pasta, $nome, $remoto, $mensagem) {
    Write-Host ''
    Write-Host ('  ' + ('-' * 68))
    Write-Host "  $nome"
    Write-Host "  $pasta"

    if (-not (Test-Path -LiteralPath $pasta)) {
        Write-Host '     pasta nao encontrada -- pulando.'
        return
    }

    Push-Location $pasta
    try {
        # A TRAVA ESQUECIDA                                     (13/09)
        #   Achei um .git\index.lock na pasta do Cerebro. Ele sobra
        #   quando um git anterior foi interrompido, e trava TODO comando
        #   seguinte com "Unable to create index.lock: File exists" --
        #   uma mensagem que nao diz que basta apagar o arquivo.
        $lock = Join-Path $pasta '.git\index.lock'
        if (Test-Path -LiteralPath $lock) {
            Write-Host '     Removendo um index.lock esquecido de um git interrompido.'
            if (-not $Ensaio) { Remove-Item -LiteralPath $lock -Force }
        }

        $novo = -not (Test-Path -LiteralPath (Join-Path $pasta '.git'))

        # ENSAIO NUM REPOSITORIO QUE AINDA NAO EXISTE           (13/09)
        #   A primeira versao disto quebrava aqui: em ensaio ela pulava o
        #   `git init` e logo depois chamava `git status`, que nao roda
        #   fora de um repositorio. O ensaio morria justamente no caso em
        #   que ele e mais util -- o repositorio novo.
        if ($novo -and $Ensaio) {
            Write-Host '     Repositorio novo: eu faria `git init` e adicionaria o remoto.'
            Write-Host "     remoto: $remoto"
            $visiveis = @(
                Get-ChildItem -LiteralPath $pasta -Recurse -File -Force `
                    -ErrorAction SilentlyContinue |
                ForEach-Object {
                    $_.FullName.Substring($pasta.Length).TrimStart('\').Replace('\', '/')
                } | Where-Object { $_ -notlike '.git/*' }
            )
            $perigo = Perigosos $visiveis
            if ($perigo.Count -gt 0) {
                Write-Host ''
                Write-Host '     ATENCAO -- estes existem na pasta e precisam estar no .gitignore:'
                foreach ($a in $perigo) { Write-Host "       $a" }
                Write-Host '     (no ensaio eu nao consigo saber se o .gitignore os barra;'
                Write-Host '      rode de verdade e o script confere antes de enviar)'
            }
            return
        }

        if ($novo) {
            Write-Host '     Repositorio novo. Inicializando...'
            git init -b main 2>$null | Out-Null
            if ($remoto) { git remote add origin $remoto 2>$null | Out-Null }
        }

        if (-not $Ensaio) { git add -A }

        # --porcelain devolve "XY caminho". Tiramos os dois marcadores e
        # as aspas que o Git poe quando o nome tem espaco.
        $lista = @(
            git status --porcelain 2>$null | ForEach-Object {
                ($_ -replace '^..\s+', '').Trim('"')
            } | Where-Object { $_ }
        )

        if ($lista.Count -eq 0) {
            Write-Host '     Nada mudou desde o ultimo envio.'
            return
        }

        # ---- a conferencia que importa ----------------------------
        $perigo = Perigosos $lista
        if ($perigo.Count -gt 0) {
            Write-Host ''
            Write-Host '     PAREI. Estes NAO podem ir para o GitHub:'
            foreach ($a in $perigo) { Write-Host "       $a" }
            Write-Host ''
            Write-Host '     O .gitignore deveria estar barrando isso. Se o arquivo ja'
            Write-Host '     foi commitado alguma vez, o .gitignore nao o remove --'
            Write-Host '     e preciso rodar:  git rm --cached <arquivo>'
            Write-Host ''
            Write-Host '     Nada foi enviado.'
            if (-not $Ensaio) { git reset 2>$null | Out-Null }
            return
        }

        # ---- segredo escrito DENTRO de arquivo de codigo -----------
        $vazando = SegredosNoConteudo $pasta $lista
        if ($vazando.Count -gt 0) {
            Write-Host ''
            Write-Host '     PAREI. Achei segredo escrito dentro do codigo:'
            foreach ($a in $vazando) { Write-Host "       $a" }
            Write-Host ''
            Write-Host '     O .gitignore nao ajuda aqui: ele protege por NOME de'
            Write-Host '     arquivo, e estes sao arquivos que devem subir. Tire o'
            Write-Host '     valor do codigo e ponha no config.json.'
            Write-Host ''
            Write-Host '     Nada foi enviado.'
            if (-not $Ensaio) { git reset 2>$null | Out-Null }
            return
        }

        Write-Host ("     {0} arquivos prontos." -f $lista.Count)
        foreach ($a in ($lista | Select-Object -First 12)) { Write-Host "       $a" }
        if ($lista.Count -gt 12) {
            Write-Host ("       ... e mais {0}" -f ($lista.Count - 12))
        }

        if ($Ensaio) {
            Write-Host '     (ensaio) nao commitei nem enviei.'
            return
        }

        git commit -m $mensagem | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host '     O commit falhou. Veja a mensagem acima.'
            return
        }

        Write-Host '     Commit feito. Enviando...'
        git push -u origin main
        if ($LASTEXITCODE -eq 0) {
            Write-Host '     Enviado.'
        } else {
            Write-Host ''
            Write-Host '     O push falhou. As causas comuns:'
            Write-Host '       . o GitHub pediu login e nao havia credencial salva'
            Write-Host '       . o repositorio remoto nao existe ainda'
            Write-Host '       . ha commits no GitHub que voce nao tem aqui'
            Write-Host '         (nesse caso: git pull --rebase origin main)'
        }
    }
    finally { Pop-Location }
}

if ($Apenas -in @('tudo', 'cerebro')) {
    Enviar $CEREBRO 'Bigode IA (Cerebro)' '' `
        'Tuneis que convivem, chave do motor, trava do Modal, venure.css e os notebooks'
}

if ($Apenas -in @('tudo', 'pipi')) {
    Enviar $PIPI 'Pipi IA' 'https://github.com/falecomofred-lab/Pipi-IA.git' `
        'Pipi: login do Bigode, tela nova, Modal e tipos MIME corretos'
}

Write-Host ''
Write-Host ('=' * 72)
if ($Ensaio) {
    Write-Host '  ENSAIO TERMINADO. Nada foi enviado.'
    Write-Host '  Rode sem -Ensaio para valer.'
} else {
    Write-Host '  TERMINADO.'
    Write-Host ''
    Write-Host '  CONFIRA A VISIBILIDADE -- so voce pode mudar:'
    Write-Host '    github.com/falecomofred-lab/Pipi-IA/settings'
    Write-Host '    github.com/falecomofred-lab/Bigode-IA/settings'
    Write-Host '    role ate o fim -> Change repository visibility -> Private'
}
Write-Host ('=' * 72)
Write-Host ''
