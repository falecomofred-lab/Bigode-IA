# PUBLICAR BIGODE IA + PIPI IA NO GITHUB -- com trava de seguranca   (29/09/2026)
#
#   Rode assim, dentro da pasta Cerebro:
#       powershell -ExecutionPolicy Bypass -File .\PUBLICAR_NO_GITHUB.ps1
#
#   So conferir, sem enviar nada:
#       powershell -ExecutionPolicy Bypass -File .\PUBLICAR_NO_GITHUB.ps1 -SoConferir
#
#   O QUE FAZ, EM CADA PROJETO (Cerebro e Pipi IA):
#     1. apaga os desktop.ini que o Google Drive enfia dentro da .git
#     2. garante no .gitignore os arquivos de senha, chave e dado pessoal
#     3. tira do GitHub (NAO do seu PC) qualquer arquivo sensivel que ja
#        estivesse sendo enviado
#     4. TRAVA 1 - nome proibido: config.json, conexoes.json, usuarios.json...
#     5. TRAVA 2 - formato de chave: hf_, sk-, ghp_, GOCSPX-, chave privada...
#     6. TRAVA 3 - suas chaves DE VERDADE: le os tokens dos seus arquivos de
#        configuracao AQUI no PC e procura cada um dentro do que vai subir.
#        Se aparecer em qualquer arquivo, para tudo. (O valor nunca e
#        mostrado na tela -- so o nome do arquivo onde apareceu.)
#     7. TRAVA 4 - arquivo acima de 50 MB
#     8. mostra a lista do que vai subir e PERGUNTA antes de enviar
#
#   Este script NAO apaga repositorio, NAO reescreve historico e NAO usa
#   --force. (O antigo que fazia isso foi renomeado para
#   PERIGO_APAGA_E_RECRIA_REPOS.ps1 -- nao rode.)

param([switch]$SoConferir)

$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot

$projetos = @(
  @{ Nome = "Bigode IA (Cerebro)"; Pasta = $PSScriptRoot
     Url  = "https://github.com/falecomofred-lab/Bigode-IA.git"
     Garantir = @("config.json", "conexoes.json", "usuarios.json", "modal.json", "ponte.txt",
                  "motor_remoto.txt", "motor.chave", "*.bak", "*.log", "*.wav",
                  "conversas/", "Historico/", "projetos/", "memoria/projetos/",
                  "memoria/fatos.json", "memoria/medicoes.jsonl", "chroma_db/",
                  "producao_blender/", "estudio/", "Claude outputs/", "auditoria/",
                  "_QUARENTENA_*/", "LINK_FIXO.txt", "PERIGO_APAGA_E_RECRIA_REPOS.ps1",
                  "Arquivos GGUF/", "*.gguf", "python/") },
  @{ Nome = "Pipi IA"; Pasta = (Join-Path $raiz "Pipi IA")
     Url  = "https://github.com/falecomofred-lab/Pipi-IA.git"
     Garantir = @("config.json", "usuarios.json", "modal.json", "cloudflare.json", "ponte.txt",
                  "motor_remoto.txt", "*.bak", "*.log", ".git-antigo*/", "producao/",
                  "*.gguf", "python/") }
)

# Arquivos que NUNCA podem estar no envio (nome exato, em qualquer pasta)
$nomesProibidos = '(^|/)(config\.json|config\.local\.json|conexoes\.json|usuarios\.json|modal\.json|cloudflare\.json|ponte\.txt|motor_remoto\.txt|motor\.chave|fatos\.json|medicoes\.jsonl|LINK_FIXO\.txt|\.env)$|\.(bak|pem|key|gguf|wav)$|(^|/)(\.git-antigo|conversas/|Historico/|memoria/projetos/|chroma_db/|producao_blender/)'

# Formato de chave conhecido (Hugging Face, OpenAI, GitHub, Google, AWS, chave privada)
$formatos = 'hf_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|GOCSPX-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----'

# Onde estao suas chaves de verdade (so lidas aqui, nunca enviadas)
$arquivosDeChave = @("config.json", "conexoes.json", "modal.json", "cloudflare.json", "usuarios.json")

function Juntar-Segredos($no, $chave, $lista) {
  if ($null -eq $no) { return }
  if ($no -is [string]) {
    $v = $no.Trim()
    $ehChave = $chave -match '(?i)token|key|chave|secret|senha|password|hash|sal$|client|api'
    $pareceAleatorio = ($v.Length -ge 32) -and ($v -notmatch '[\s/\\:@.]')
    if ($v.Length -ge 12 -and ($ehChave -or $pareceAleatorio) -and $v -notmatch '^(?i)cole_aqui') {
      [void]$lista.Add($v)
    }
    return
  }
  if ($no -is [System.Collections.IEnumerable] -and -not ($no -is [string])) {
    foreach ($item in $no) { Juntar-Segredos $item $chave $lista }
    return
  }
  if ($no -is [psobject]) {
    foreach ($p in $no.PSObject.Properties) { Juntar-Segredos $p.Value $p.Name $lista }
  }
}

function Ler-Segredos($pastas) {
  $lista = New-Object 'System.Collections.Generic.HashSet[string]'
  foreach ($pasta in $pastas) {
    foreach ($n in $arquivosDeChave) {
      $arq = Join-Path $pasta $n
      if (-not (Test-Path -LiteralPath $arq)) { continue }
      try {
        $json = Get-Content -LiteralPath $arq -Raw -Encoding UTF8 | ConvertFrom-Json
        Juntar-Segredos $json "" $lista
      } catch { }
    }
  }
  return ,$lista
}

function Checar-Commit($c) {
  $achou = @()
  $achou += git ls-tree -r --name-only $c | Where-Object { $_ -match $nomesProibidos }
  $achou += git grep -I -l -E $formatos $c 2>$null
  foreach ($s in $segredos) { $achou += git grep -I -l -F -e $s $c 2>$null }
  return $achou
}

$segredos = Ler-Segredos ($projetos | ForEach-Object { $_.Pasta })
Write-Host ("`nChaves reais lidas dos seus arquivos de configuracao: {0} (nao serao mostradas)" -f $segredos.Count) -ForegroundColor DarkGray

$resultado = @()

foreach ($p in $projetos) {
  Write-Host "`n==================== $($p.Nome) ====================" -ForegroundColor Cyan
  if (-not (Test-Path -LiteralPath $p.Pasta)) {
    Write-Host "  Pasta nao encontrada: $($p.Pasta) -- pulei." -ForegroundColor Yellow
    $resultado += "$($p.Nome): pasta nao encontrada"; continue
  }
  Set-Location -LiteralPath $p.Pasta

  if (-not (Test-Path -LiteralPath ".git")) {
    git init -b main | Out-Null
    git remote add origin $p.Url
  }
  # 1. desktop.ini do Google Drive dentro da .git quebra o Git ("bad object refs/desktop.ini")
  Get-ChildItem .git -Recurse -Force -Filter desktop.ini -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
  if (-not (git remote)) { git remote add origin $p.Url }

  # 1b. commits feitos aqui e AINDA NAO ENVIADOS tambem sobem no push.
  #     Se algum deles tiver arquivo ou chave sensivel, junto todos num so
  #     (git reset --soft): seus arquivos NAO mudam, so o historico local.
  git fetch -q origin 2>$null
  $ramo = git rev-parse --abbrev-ref HEAD 2>$null
  $remoto = if ($ramo -and $ramo -ne "HEAD") { git rev-parse --verify -q "origin/$ramo" 2>$null } else { $null }
  $pendentes = if ($remoto) { git rev-list "$remoto..HEAD" 2>$null } else { git rev-list HEAD 2>$null }
  $sujos = @()
  foreach ($c in $pendentes) { $sujos += Checar-Commit $c }
  if ($sujos) {
    Write-Host "  Commits locais ainda nao enviados tinham arquivo sensivel. Juntei-os (seus arquivos nao mudam)." -ForegroundColor Yellow
    if ($remoto) { git reset -q --soft $remoto } else { git update-ref -d HEAD }
  }

  # 2. .gitignore com tudo que e sensivel
  if (-not (Test-Path -LiteralPath ".gitignore")) { New-Item .gitignore -ItemType File | Out-Null }
  $atual = Get-Content -LiteralPath .gitignore -ErrorAction SilentlyContinue
  $faltam = $p.Garantir | Where-Object { $atual -notcontains $_ }
  if ($faltam) {
    Add-Content -LiteralPath .gitignore -Value ("`n# Garantido pelo PUBLICAR_NO_GITHUB.ps1 (29/09)")
    Add-Content -LiteralPath .gitignore -Value $faltam
    Write-Host ("  .gitignore: +{0} regra(s)" -f @($faltam).Count)
  }

  # 3. tira do envio o que ja estava sendo enviado por engano (fica no seu PC)
  git add -A 2>$null
  $rastreados = git ls-files
  $sairam = $rastreados | Where-Object { $_ -match $nomesProibidos }
  foreach ($s in $sairam) { git rm --cached --quiet -- "$s" 2>$null }
  if ($sairam) { Write-Host ("  Tirei do GitHub (continua no PC): {0}" -f ($sairam -join ", ")) -ForegroundColor Yellow }

  # 4..7. travas sobre TUDO que ficaria no repositorio
  $problemas = @()
  $problemas += git ls-files | Where-Object { $_ -match $nomesProibidos } | ForEach-Object { "nome proibido: $_" }
  $problemas += git grep --cached -I -l -E $formatos 2>$null | ForEach-Object { "formato de chave dentro de: $_" }
  foreach ($s in $segredos) {
    $problemas += git grep --cached -I -l -F -e $s 2>$null | ForEach-Object { "SUA CHAVE REAL dentro de: $_" }
  }
  git diff --cached --name-only --diff-filter=ACMR | ForEach-Object {
    $f = Get-Item -LiteralPath $_ -ErrorAction SilentlyContinue
    if ($f -and $f.Length -gt 50MB) { $problemas += ("arquivo grande ({0:N0} MB): {1}" -f ($f.Length / 1MB), $_) }
  }
  $problemas = $problemas | Sort-Object -Unique

  if ($problemas) {
    Write-Host "  PAREI. Nada deste projeto foi enviado:" -ForegroundColor Red
    $problemas | ForEach-Object { Write-Host "   - $_" -ForegroundColor Red }
    git reset --quiet
    $resultado += "$($p.Nome): BLOQUEADO"
    continue
  }
  Write-Host "  [ok] Nenhuma chave, senha ou dado pessoal no envio." -ForegroundColor Green

  $mudancas = git diff --cached --name-status
  if (-not $mudancas) {
    Write-Host "  Nada novo para enviar."
    $resultado += "$($p.Nome): sem mudancas"; continue
  }
  Write-Host ("  Vai subir {0} mudanca(s):" -f @($mudancas).Count)
  $mudancas | Select-Object -First 40 | ForEach-Object { Write-Host "    $_" }
  if (@($mudancas).Count -gt 40) { Write-Host "    ... e mais $(@($mudancas).Count - 40)" }

  if ($SoConferir) {
    git reset --quiet
    $resultado += "$($p.Nome): conferido (nada enviado)"; continue
  }
  $ok = Read-Host "  Enviar $($p.Nome) para o GitHub? (S/N)"
  if ($ok -notmatch '^[sS]') {
    git reset --quiet
    $resultado += "$($p.Nome): cancelado por voce"; continue
  }
  git commit -q -m ("Atualizacao {0}" -f (Get-Date -Format "dd/MM/yyyy HH:mm"))
  git push origin HEAD
  if ($LASTEXITCODE -eq 0) { $resultado += "$($p.Nome): ENVIADO" }
  else { $resultado += "$($p.Nome): commit feito, push FALHOU (veja a mensagem acima)" }
}

Set-Location -LiteralPath $PSScriptRoot
Write-Host "`n==================== RESUMO ====================" -ForegroundColor Cyan
$resultado | ForEach-Object { Write-Host "  $_" }
Write-Host ""
