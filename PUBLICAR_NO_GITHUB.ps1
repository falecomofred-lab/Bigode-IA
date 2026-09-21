# TROCAR OS DOIS REPOSITORIOS DO GITHUB
# Venure - venure.com.br - 17/09/2026
#
#     cd "G:\Meu Drive\projetos\Cerebro"
#     .\PUBLICAR_NO_GITHUB.ps1 -Ensaio     <- mostra e nao faz nada
#     .\PUBLICAR_NO_GITHUB.ps1             <- faz
#
# O QUE ELE FAZ, E POR QUE NESSA ORDEM
#
#   1. Roda o TESTAR_TUDO.py e PARA se qualquer credencial aparecer.
#      Esta e a unica etapa que nao tem volta se der errado: codigo
#      quebrado se conserta no commit seguinte, token publicado nao.
#
#   2. APAGA os dois repositorios do GitHub, com historico.
#      Nao e exagero. O historico do Git guarda tudo o que ja passou por
#      ele: apagar o config.json hoje nao apaga o token que estava nele
#      em agosto -- um `git log -p` ainda le. Como por estes dois repos
#      ja passaram token da Hugging Face, token da Modal e o usuarios.json
#      com e-mail e hash de senha, limpar por cima seria fingir.
#
#      O repositorio novo nasce sem historico nenhum. E o unico jeito
#      honesto de dizer "nao tem segredo ai dentro".
#
#   3. Cria os dois DE NOVO, PRIVADOS.
#      O Bigode era publico. Ele le pasta, roda comando e entra no
#      navegador: nao e coisa para ficar aberta.
#
#   4. Sobe um commit unico, ja filtrado pelos .gitignore.
#
# PRECISA DO gh (GitHub CLI)
#   winget install GitHub.cli
#   gh auth login
#
# Sem o gh, a parte de apagar e criar tem de ser feita a mao no site --
# o script diz exatamente onde clicar.

param([switch]$Ensaio)

# 'Continue', nao 'Stop'. Com 'Stop' o PowerShell trata QUALQUER linha que
# um programa externo escreva no stderr como erro fatal -- e tanto o `gh`
# quanto o `git push` escrevem ali no uso normal (o push manda a barra de
# progresso pelo stderr). O script ja confere $LASTEXITCODE em cada etapa
# que importa; e o exit code que diz se deu certo, nao o stderr.
$ErrorActionPreference = 'Continue'
$conta   = 'falecomofred-lab'
$projetos = @(
  @{ Nome = 'Bigode-IA'; Pasta = 'G:\Meu Drive\projetos\Cerebro';
     Desc  = 'Bigode IA - assistente da Venure que roda na sua maquina' },
  @{ Nome = 'Pipi-IA';   Pasta = 'G:\Meu Drive\projetos\Pipi IA';
     Desc  = 'Pipi IA - geracao de imagem da Venure' }
)

function Titulo($t) { Write-Host "`n  $t" -ForegroundColor Cyan
                      Write-Host ('  ' + ('-' * 62)) -ForegroundColor DarkGray }
function Bom($t)    { Write-Host "  [ok] $t" -ForegroundColor Green }
function Ruim($t)   { Write-Host "  [X]  $t" -ForegroundColor Red }
function Aviso($t)  { Write-Host "  [!]  $t" -ForegroundColor Yellow }

# ----------------------------------------------------------------------
Titulo ' 1. CONFERINDO SE HA SEGREDO NO QUE VAI SUBIR'

Push-Location 'G:\Meu Drive\projetos\Cerebro'
& python TESTAR_TUDO.py
$notaTeste = $LASTEXITCODE
Pop-Location

if ($notaTeste -ne 0) {
  Ruim 'O TESTAR_TUDO reprovou. Nao vou publicar nada.'
  Write-Host '       Conserte o que ele apontou e rode de novo.' -ForegroundColor DarkGray
  exit 1
}
Bom 'nada de credencial, e os arquivos compilam'

# ----------------------------------------------------------------------
Titulo ' 2. O gh ESTA INSTALADO E LOGADO?'

$temGh = $null -ne (Get-Command gh -ErrorAction SilentlyContinue)
if ($temGh) {
  & gh auth status 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) { $temGh = $false }
}

if (-not $temGh) {
  Aviso 'gh ausente ou sem login. A parte do site fica com voce:'
  Write-Host ''
  foreach ($p in $projetos) {
    Write-Host "       APAGAR:  https://github.com/$conta/$($p.Nome)/settings" -ForegroundColor DarkGray
    Write-Host '                 desca ate Danger Zone > Delete this repository' -ForegroundColor DarkGray
  }
  Write-Host ''
  Write-Host '       CRIAR:   https://github.com/new  (marque Private, sem README)' -ForegroundColor DarkGray
  Write-Host ''
  Write-Host '       Depois rode este script de novo -- ele segue do passo 4.' -ForegroundColor DarkGray
  Write-Host ''
  if (-not $Ensaio) {
    $r = Read-Host '       Ja apagou e criou os dois no site? (digite SIM)'
    if ($r -ne 'SIM') { Ruim 'Parando aqui.'; exit 1 }
  }
} else {
  Bom 'gh pronto'
}

# ----------------------------------------------------------------------
Titulo ' 3. APAGAR O ANTIGO E CRIAR O NOVO (PRIVADO)'

foreach ($p in $projetos) {
  $alvo = "$conta/$($p.Nome)"
  if ($Ensaio) { Aviso "ENSAIO: apagaria e recriaria $alvo como privado"; continue }
  if (-not $temGh) { continue }

  & gh repo view $alvo 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "       apagando $alvo …" -ForegroundColor DarkGray
    & gh repo delete $alvo --yes
    if ($LASTEXITCODE -ne 0) {
      Ruim "nao consegui apagar $alvo"
      Write-Host '       Falta permissao: gh auth refresh -h github.com -s delete_repo' -ForegroundColor DarkGray
      exit 1
    }
    Bom "$alvo apagado, com historico"
  } else {
    Aviso "$alvo nao existe mais (ja apagado)"
  }

  & gh repo create $alvo --private --description $p.Desc
  if ($LASTEXITCODE -ne 0) { Ruim "nao consegui criar $alvo"; exit 1 }
  Bom "$alvo criado, PRIVADO e vazio"
}

# ----------------------------------------------------------------------
Titulo ' 4. SUBIR O COMECO LIMPO'

foreach ($p in $projetos) {
  Write-Host "`n       $($p.Nome)" -ForegroundColor White
  if (-not (Test-Path $p.Pasta)) { Ruim "pasta nao existe: $($p.Pasta)"; exit 1 }

  Push-Location $p.Pasta
  try {
    if ($Ensaio) {
      # O `git add --dry-run` e a hora de ver a lista de verdade. Se algo
      # que nao devia aparecer aqui, o .gitignore e que esta furado.
      Write-Host '       ENSAIO: o git levaria estes arquivos:' -ForegroundColor Yellow
      if (Test-Path '.git') {
        & git add --all --dry-run 2>$null | Select-Object -First 40
      } else {
        Write-Host '       (sem .git ainda)' -ForegroundColor DarkGray
      }
      continue
    }

    # O .git antigo vai embora junto com o historico. Renomeia em vez de
    # apagar: se algo der errado nos proximos 3 comandos, da para voltar.
    if (Test-Path '.git') {
      $guardado = ".git-antigo-$(Get-Date -Format yyyyMMdd-HHmmss)"
      Rename-Item '.git' $guardado
      Bom "historico antigo guardado em $guardado"
    }

    & git init -b main    | Out-Null
    & git add --all
    & git -c user.name='Venure' -c user.email='contato@venure.com.br' `
          commit -m "$($p.Nome) - versao de 17/09/2026" | Out-Null
    & git remote add origin "https://github.com/$conta/$($p.Nome).git"
    & git push -u origin main --force

    if ($LASTEXITCODE -ne 0) { Ruim 'o push falhou'; exit 1 }

    $n = (& git ls-files | Measure-Object).Count
    Bom "$n arquivos publicados em https://github.com/$conta/$($p.Nome)"
  }
  finally { Pop-Location }
}

Titulo ' PRONTO'
Write-Host '  Os dois repositorios sao novos, privados e sem historico.' -ForegroundColor Green
Write-Host ''
Write-Host '  Uma coisa que o script NAO faz por voce:' -ForegroundColor Yellow
Write-Host '  revogar os tokens que ja estiveram nos repos antigos. Apagar o' -ForegroundColor DarkGray
Write-Host '  repositorio tira a copia do GitHub, mas se alguem leu antes, o' -ForegroundColor DarkGray
Write-Host '  token continua valendo. Revogue em:' -ForegroundColor DarkGray
Write-Host '    huggingface.co/settings/tokens   e   modal.com/settings/tokens' -ForegroundColor DarkGray
Write-Host ''
if (-not $Ensaio) {
  Write-Host '  As pastas .git-antigo-* podem ser apagadas quando voce confirmar' -ForegroundColor DarkGray
  Write-Host '  que os repositorios novos estao certos.' -ForegroundColor DarkGray
  Write-Host ''
}
