"""TRAZER O BIGODE E A IA DO DRIVE   -   celula 3

Copia o codigo e o .gguf escolhido para o disco do Colab.

POR QUE COPIAR, E NAO LER DO DRIVE
    O Drive montado e uma pasta de rede disfarcada de pasta local. Cada
    leitura vai e volta pela internet. Um modelo de 4 GB lido de la durante
    o trabalho deixa o Bigode lento de um jeito que parece defeito do
    modelo -- e nao e.

    Copia uma vez, usa mil.

DEPENDE DE
    Nada. Se as celulas de cima nao rodaram, ele busca no catalogo -- que e
    a mesma fonte que a celula 1 usa.

DEIXA PARA TRAS
    CASA     /content/bigode, onde o codigo mora nesta sessao
    MODELO   o caminho do .gguf ja no disco local

Venure - venure.com.br
"""

import shutil
import time
from pathlib import Path

CASA = Path("/content/bigode")
RAIZ_DRIVE = Path("/content/drive/MyDrive")
CATALOGO_PY = RAIZ_DRIVE / "projetos/Cerebro/catalogo_ia.py"


def _garantir_drive():
    if RAIZ_DRIVE.is_dir():
        return True
    try:
        from google.colab import drive
        drive.mount("/content/drive")
        return RAIZ_DRIVE.is_dir()
    except Exception:
        return False


print()
print("=" * 66)
print("  TRAZENDO O BIGODE E A IA")
print("=" * 66)

if not _garantir_drive():
    raise SystemExit("Nao consegui montar o Drive.")

# Em vez de estourar NameError quando a celula 1 nao rodou, buscamos no
# catalogo. Uma verdade so, num lugar so.
if any(n not in globals() for n in ("PASTA_BIGODE", "PASTA_GGUF", "ARQUIVOS")):
    if not CATALOGO_PY.is_file():
        raise SystemExit("Nao achei %s. Rode o sincronizar-bigode.ps1."
                         % CATALOGO_PY)
    if "IA" not in globals():
        IA = "granite"
    exec(CATALOGO_PY.read_text(encoding="utf-8"), globals())

# ---- o codigo -------------------------------------------------------------
origem = RAIZ_DRIVE / PASTA_BIGODE                            # noqa: F821
if not origem.is_dir():
    raise SystemExit("Nao achei o projeto em %s" % origem)

if CASA.exists():
    shutil.rmtree(CASA)

# O que fica de fora, e por que:
#   Arquivos GGUF   9 GB que entram por outro caminho, logo abaixo
#   Historico       o config aponta direto para o Drive
#   chroma_db       idem
#   conversas       nascem nesta sessao; as velhas sao de outra maquina
#   auditoria       so serve quando voce roda a bateria a mao
#
# Sao milhares de arquivinhos, cada um com sua ida e volta pelo Drive. Em
# 10/09 essa copia passou de tres minutos ate a lista ficar assim.
shutil.copytree(origem, CASA, ignore=shutil.ignore_patterns(
    "Arquivos GGUF", "_antes-*", "chroma_db", "__pycache__",
    "conversas", "Historico", "auditoria", ".git", ".pytest_cache", "*.log"))

print("\n  Codigo: %d arquivos .py" % len(list(CASA.rglob("*.py"))))
# Confere a tela que o cerebro.py REALMENTE serve. Ate 13/09 isto olhava o
# colab.html, que deixou de ser a porta de entrada -- entao dizia "no lugar"
# mesmo quando faltava o index.html, e o Bigode abria vazio.
print("  Tela:   %s" % ("index.html no lugar"
                        if (CASA / "web" / "index.html").is_file()
                        else "FALTA o web/index.html"))

# ---- a IA -----------------------------------------------------------------
_arquivo = ARQUIVOS[IA]                                       # noqa: F821
_origem_ia = Path(PASTA_GGUF) / _arquivo                      # noqa: F821

if not _origem_ia.is_file():
    print("\n  Nao achei: %s" % _origem_ia)
    print("  O que tem na pasta:")
    for _a in Path(PASTA_GGUF).glob("*.gguf"):                # noqa: F821
        print("   ", _a.name)
    raise SystemExit()

Path("/content/modelos").mkdir(exist_ok=True)
MODELO = "/content/modelos/" + _arquivo

if Path(MODELO).is_file():
    print("\n  A IA ja esta no disco. Nao precisa baixar de novo.")
else:
    _gb = _origem_ia.stat().st_size / 1e9
    print("\n  Trazendo %s (%.1f GB). Um a tres minutos..." % (IA, _gb))  # noqa: F821
    _t0 = time.time()
    shutil.copy2(_origem_ia, MODELO)
    print("  Pronto em %.0fs" % (time.time() - _t0))

print()
print("=" * 66)
print("  IA escolhida: %s" % IA)                              # noqa: F821
print("  arquivo ..... %s" % _arquivo)
print("=" * 66)
print()
