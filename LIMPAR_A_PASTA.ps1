# LIMPAR A PASTA DO CEREBRO — movendo, nao apagando
# Venure - venure.com.br - 22/09/2026
#
#     .\LIMPAR_A_PASTA.ps1            <- mostra o que faria, nao mexe em nada
#     .\LIMPAR_A_PASTA.ps1 -Fazer     <- move de verdade
#
# POR QUE MOVER E NAO APAGAR
#
#   Apagar e a unica coisa deste projeto que nao tem volta. Tudo aqui foi
#   escolhido com cuidado, mas "com cuidado" nao e o mesmo que "com certeza":
#   basta um arquivo que alguem ainda chama para o Bigode parar, e ai nao ha
#   como desfazer.
#
#   Entao tudo vai para uma pasta _QUARENTENA_<data>. Voce roda o Bigode e a
#   Pipi normalmente por alguns dias. Se nada quebrou, apaga a quarentena
#   inteira de uma vez -- e ai sim e definitivo, com voce olhando.
#
# O QUE ELE NAO TOCA
#
#   . nenhum arquivo .py que o Bigode usa hoje
#   . a pasta web/ (a tela), memoria/, habilidades/, agentes/, chroma_db/
#   . config.json, conexoes.json, e qualquer coisa com segredo
#   . .git (o atual) -- so os .git-antigo-* que sobraram da republicacao
#   . qualquer .gguf que NAO tenha copia na pasta oficial (Pen IA)

param([switch]$Fazer)

$ErrorActionPreference = 'Continue'
$AQUI = Split-Path -Parent $MyInvocation.MyCommand.Path
$PEN  = 'G:\Outros computadores\USB e dispositivos externos\Pen IA'
$DEST = Join-Path $AQUI ("_QUARENTENA_" + (Get-Date -Format 'yyyyMMdd-HHmm'))

function Titulo($t) { Write-Host "`n  $t" -ForegroundColor Cyan
                      Write-Host ('  ' + ('-' * 66)) -ForegroundColor DarkGray }
function Nota($t)   { Write-Host "       $t" -ForegroundColor DarkGray }

# ----------------------------------------------------------------------
# 1. OS RESTOS DA REPUBLICACAO NO GITHUB
#    Os dois repositorios novos ja estao no ar e confirmados. Estas pastas
#    sao o historico antigo, guardado "por via das duvidas" no dia 21.
$pastas = @()
$pastas += Get-ChildItem -Path $AQUI -Directory -Force -Filter '.git-antigo-*' `
           -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }

# ----------------------------------------------------------------------
# 2. SOBRAS DE EDICAO
#    Arquivos .patch sao pedacos de alteracao ja aplicados. Guardar patch
#    aplicado e guardar a receita de um bolo que ja foi comido.
$arquivos = @(
  'cerebro.py.patch', 'ferramentas.py.patch', 'auditar_selo.py.patch',
  'temperamento.md.patch', 'config.json.patch',

  # 3. DOCUMENTOS DE AUDITORIA E PLANEJAMENTO JA CUMPRIDOS
  #    Todos descrevem estados do projeto que nao existem mais. Alguns
  #    foram escritos por outras IAs, outros por mim. Vale notar: estes
  #    .md estao DENTRO do dominio "codigo" da memoria -- ou seja, o
  #    Bigode os le como se fossem verdade sobre o projeto de hoje. Tirar
  #    daqui melhora a resposta dele, nao so a arrumacao.
  'AUDITORIA-MOTOR.md', 'AUDITORIA_MANUS.md', 'AUDITORIA_ACHADOS_INICIAIS.md',
  'AUDITORIA_BIGODE_2026.md', 'AUDITORIA_E_PLANO_OPERACIONAL.md',
  'CEREBRO-vs-MONKEYCODE.md', 'CHECKPOINT.md', 'ESTADO-ATUAL.md',
  'COMUNICACAO_HUMANIZADA.md', 'MOBILE_FIRST_BIGODE_PIPI.md',
  'SEPARACAO_BIGODE_PIPI.md', 'PROJETO_CEREBRO.md', 'COMO-AUDITAR.md',
  'O_QUE_O_BIGODE_FAZ.md', 'README-APLICACAO.md', 'todo.md',
  'IMPLEMENTACAO_PIPI_SOB_DEMANDA.md', 'IMPLEMENTACAO_PIPI_SOB_DEMANDA (1).md',
  'IMPLEMENTACAO_MELHORIAS_DRIVE.md',

  # 4. O COLAB, QUE SAIU DO PROJETO
  'Bigode_Colab_Pipi_IA.ipynb', 'pipi_colab.py', 'usar_motor_do_colab.py',
  'modal_api_teste.py',

  # 5. TELAS ANTIGAS
  #    A tela de verdade e web/index.html. Estes dois sao versoes de antes
  #    da separacao, e ninguem os serve.
  'prototipo.html', 'index.html',

  # 6. FOTOS DUPLICADAS
  #    As que valem estao em web/img/. Estas sao copias soltas na raiz.
  'bigode.jpeg', 'pipi_gata.jpeg',

  # 7. TESTES E AUDITORIAS SUBSTITUIDOS PELO TESTAR_TUDO.py
  'test_auditoria_precision.py', 'test_busca.py', 'test_caminhos.py',
  'test_comunicacao.py', 'test_multiplataforma.py', 'test_selo.py',
  'test_toolcall.py', 'test_v2_chroma.py',
  'auditar_motor.py', 'auditar_qualidade.py', 'auditar_selo.py',
  'auditar_todos.py', 'auditar_tudo.py', 'scripts_audit_config.py',

  # 8. SCRIPTS DE ARRUMACAO ANTERIORES
  #    Um deles, inclusive, se chama CONSERTAR_LIMPEZA -- foi escrito para
  #    consertar o que a limpeza anterior quebrou. Motivo de sobra para
  #    este aqui mover em vez de apagar.
  'LIMPAR.ps1', 'CONSERTAR_LIMPEZA.ps1', 'ENVIAR_GITHUB.ps1'
)

# ----------------------------------------------------------------------
# 9. MODELOS DUPLICADOS — E A REGRA QUE PROTEGE VOCE
#
#    A pasta oficial de modelos e a `Pen IA`; o BIGODE.bat carrega de la.
#    Estas copias dentro do projeto sao ~18 GB parados no Drive.
#
#    MAS: so move o que TEM copia la. Se a copia nao existir, o arquivo
#    fica onde esta e o script avisa. Mover o unico exemplar de um modelo
#    de 10 GB porque eu "tinha certeza" que havia outro seria a forma mais
#    cara possivel de eu estar errado.
$ggufCandidatos = @(
  (Join-Path $AQUI 'DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf'),
  (Join-Path $AQUI 'Arquivos GGUF\qwen2.5-coder-7b-instruct-q4_k_m.gguf'),
  (Join-Path $AQUI 'Arquivos GGUF\granite-4.0-h-tiny-7b-Q4_K_M.gguf')
)

# ----------------------------------------------------------------------
Write-Host ''
Write-Host '  LIMPEZA DA PASTA DO CEREBRO' -ForegroundColor White
Write-Host '  ====================================================================' -ForegroundColor DarkGray
if (-not $Fazer) {
  Write-Host '  ENSAIO: nada sera movido. Para valer, rode com  -Fazer' -ForegroundColor Yellow
}

$mover = @()
$bytes = 0

Titulo 'PASTAS'
foreach ($p in $pastas) {
  $t = (Get-ChildItem $p -Recurse -File -Force -EA SilentlyContinue |
        Measure-Object Length -Sum).Sum
  if (-not $t) { $t = 0 }
  $bytes += $t
  $mover += $p
  Write-Host ("  [mover] {0,-46} {1,8:N1} MB" -f (Split-Path $p -Leaf), ($t/1MB))
}
if (-not $pastas) { Nota 'nenhuma' }

Titulo 'ARQUIVOS'
$achados = 0
foreach ($nome in $arquivos) {
  $caminho = Join-Path $AQUI $nome
  if (Test-Path -LiteralPath $caminho) {
    $t = (Get-Item -LiteralPath $caminho).Length
    $bytes += $t; $mover += $caminho; $achados++
    Write-Host ("  [mover] {0,-46} {1,8:N0} KB" -f $nome, ($t/1KB))
  }
}
Nota "$achados arquivos encontrados de $($arquivos.Count) procurados"

Titulo 'MODELOS DUPLICADOS (so se houver copia na pasta oficial)'
foreach ($g in $ggufCandidatos) {
  if (-not (Test-Path -LiteralPath $g)) { continue }
  $nome = Split-Path $g -Leaf
  $oficial = Join-Path $PEN $nome
  $t = (Get-Item -LiteralPath $g).Length
  if (Test-Path -LiteralPath $oficial) {
    $bytes += $t; $mover += $g
    Write-Host ("  [mover] {0,-46} {1,8:N1} GB" -f $nome, ($t/1GB)) -ForegroundColor Green
    Nota "copia confirmada em Pen IA"
  } else {
    Write-Host ("  [FICA]  {0,-46} {1,8:N1} GB" -f $nome, ($t/1GB)) -ForegroundColor Yellow
    Nota "NAO achei copia em Pen IA -- este pode ser o unico. Nao vou mexer."
  }
}

Write-Host ''
Write-Host '  ====================================================================' -ForegroundColor DarkGray
Write-Host ("  {0} itens, {1:N2} GB" -f $mover.Count, ($bytes/1GB)) -ForegroundColor White
Write-Host '  ====================================================================' -ForegroundColor DarkGray

if (-not $Fazer) {
  Write-Host ''
  Write-Host '  Isto foi so o ensaio. Para mover de verdade:' -ForegroundColor Yellow
  Write-Host '      .\LIMPAR_A_PASTA.ps1 -Fazer' -ForegroundColor White
  Write-Host ''
  exit 0
}

if ($mover.Count -eq 0) { Write-Host "`n  Nada a fazer.`n"; exit 0 }

Write-Host ''
$r = Read-Host '  Mover estes itens para a quarentena? (digite SIM)'
if ($r -ne 'SIM') { Write-Host "`n  Parando aqui. Nada foi movido.`n"; exit 1 }

New-Item -ItemType Directory -Path $DEST -Force | Out-Null
$ok = 0; $erro = 0
foreach ($item in $mover) {
  try {
    Move-Item -LiteralPath $item -Destination $DEST -Force -ErrorAction Stop
    $ok++
  } catch {
    Write-Host ("  [x] nao consegui mover {0}: {1}" -f (Split-Path $item -Leaf), $_.Exception.Message) -ForegroundColor Red
    $erro++
  }
}

Write-Host ''
Write-Host "  Movi $ok itens ($erro falharam) para:" -ForegroundColor Green
Write-Host "      $DEST" -ForegroundColor White
Write-Host ''
Write-Host '  AGORA, NESTA ORDEM:' -ForegroundColor Yellow
Write-Host ''
Write-Host '    1. abra o Bigode e a Pipi e use normalmente por alguns dias'
Write-Host '    2. reindexe a memoria — varios .md sairam do dominio "codigo":'
Write-Host '         .\LIGAR_TUDO.bat indexar'
Write-Host '    3. se nada quebrou, apague a quarentena de uma vez:'
Write-Host "         Remove-Item -LiteralPath `"$DEST`" -Recurse -Force"
Write-Host ''
Write-Host '  So o passo 3 e definitivo. Ate la, tudo tem volta.' -ForegroundColor DarkGray
Write-Host ''
