"""ATUALIZAR O CODIGO SEM DERRUBAR

Celula 11 do Colab. Traz o codigo novo do Drive e reinicia so o Bigode --
o motor continua de pe e o seu link nao muda.

POR QUE VIROU ARQUIVO   (10/09)
    A celula fazia isto tudo por conta propria, e dependia de tres coisas
    que nasciam em OUTRAS celulas: CASA (celula 3), PASTA_BIGODE e JANELA
    (celula 1). Funcionava quando voce rodava tudo em ordem.

    So que o Colab cai o tempo todo. Voce reconecta, quer so trazer a
    correcao, roda a 11 sozinha -- e toma:

        NameError: name 'CASA' is not defined

    Uma celula chamada "atualizar sem derrubar" que exige ter rodado a
    sessao inteira antes nao cumpre o nome. Aqui ela se vira sozinha:
    descobre o que falta e busca no proprio catalogo.

Venure - venure.com.br
"""

import shutil
import os
import subprocess
import time
import urllib.request
from pathlib import Path

CASA = Path("/content/bigode")
RAIZ_DRIVE = Path("/content/drive/MyDrive")


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
print("  ATUALIZANDO O CODIGO")
print("=" * 66)

if not _garantir_drive():
    raise SystemExit("Nao consegui montar o Drive.")

# ---- o que veio das celulas de cima, e o que falta ------------------------
#
# Em vez de estourar NameError, buscamos no catalogo -- que e a mesma fonte
# que a celula 1 usa. Uma verdade so, em um lugar so.
_falta = [n for n in ("PASTA_BIGODE", "PASTA_GGUF", "JANELA")
          if n not in globals()]
if _falta:
    print("\n  Faltavam: %s" % ", ".join(_falta))
    print("  Buscando no catalogo (mesma fonte da celula 1)...")
    _cat = RAIZ_DRIVE / "projetos/Cerebro/catalogo_ia.py"
    if not _cat.is_file():
        raise SystemExit("Nao achei %s. Rode o sincronizar-bigode.ps1." % _cat)
    if "IA" not in globals():
        IA = "granite"
    exec(_cat.read_text(encoding="utf-8"), globals())

ORIGEM = RAIZ_DRIVE / PASTA_BIGODE                            # noqa: F821
if not ORIGEM.is_dir():
    raise SystemExit("Nao achei o projeto em %s" % ORIGEM)

# ---- o codigo -------------------------------------------------------------
#
# Se a celula 3 nao rodou nesta sessao, /content/bigode nem existe. Copiar
# tudo do zero e melhor do que reclamar: o resultado e o mesmo que a celula
# 3 daria, sem o download de gigabytes da IA.
if not CASA.is_dir():
    print("\n  Primeira copia desta sessao (a celula 3 nao rodou).")
    # O QUE FICA DE FORA, E POR QUE
    #
    # Medido em 10/09: a primeira versao desta copia passou de 3 minutos e
    # ainda nao tinha terminado. O peso nao eram os .py -- eram milhares de
    # arquivinhos de `conversas`, `Historico` e `auditoria`, cada um com sua
    # ida e volta pelo Drive montado.
    #
    # E nenhum deles precisa estar aqui:
    #     Historico   o config aponta direto para o Drive
    #     chroma_db   idem
    #     conversas   nascem nesta sessao; as velhas sao de outra maquina
    #     auditoria   so serve quando voce roda a bateria a mao
    #     Arquivos GGUF   9 GB que a celula 3 traz por outro caminho
    print("  (pulando conversas, Historico e auditoria - o config aponta")
    print("   direto para o Drive, e copiar isso custa minutos)")
    shutil.copytree(ORIGEM, CASA,
                    ignore=shutil.ignore_patterns(
                        "Arquivos GGUF", "_antes-*", "chroma_db",
                        "__pycache__", "conversas", "Historico", "auditoria",
                        ".git", ".pytest_cache", "*.log"))
else:
    for p in ORIGEM.glob("*.py"):
        shutil.copy2(p, CASA / p.name)
    for sub in ("memoria", "habilidades", "web", "extensao-chrome", "agentes"):
        if (ORIGEM / sub).is_dir():
            shutil.copytree(ORIGEM / sub, CASA / sub, dirs_exist_ok=True)

print("  Codigo: %d arquivos .py" % len(list(CASA.glob("*.py"))))
print("  Tela:   %s" % ("index.html no lugar"
                        if (CASA / "web" / "index.html").is_file()
                        else "FALTA o web/index.html"))

# ---- a configuracao -------------------------------------------------------
#
# O config.json que veio do Drive e o do Windows, com G:\ dentro. Sem
# reaplicar, o Bigode sobe apontando para um motor que nao existe aqui.
#
# Quem faz isso e o adaptar.py -- o mesmo que a celula 5 e o ligar_bigode.py
# usam. Um trecho copiado em tres lugares e como se cria diferenca entre
# eles: alguem conserta um e esquece os outros.
_ADAPTAR = RAIZ_DRIVE / "projetos/Cerebro/adaptar.py"
if not _ADAPTAR.is_file():
    raise SystemExit("Nao achei %s. Rode o sincronizar-bigode.ps1." % _ADAPTAR)
_ADAPTAR_CALADO = True
exec(_ADAPTAR.read_text(encoding="utf-8"), globals())

# ---- reiniciar SO o Bigode ------------------------------------------------
#
# `pkill -f cerebro.py` mira o Bigode pelo nome. Nao toca no motor nem no
# cloudflared -- e por isso que o seu link sobrevive.
subprocess.run("pkill -f cerebro.py", shell=True) if os.name != "nt" else None
time.sleep(2)

_log = open("/content/bigode.log", "w")
proc_bigode = subprocess.Popen(["python3", "cerebro.py"], cwd=str(CASA),
                               stdout=_log, stderr=subprocess.STDOUT)
print("\n  Reiniciando", end="")
_vivo = False
for _i in range(45):
    time.sleep(2)
    try:
        urllib.request.urlopen("http://127.0.0.1:7000/api/login/estado",
                               timeout=3)
        _vivo = True
        break
    except Exception:
        print(".", end="")

print()
print("=" * 66)
if _vivo:
    print("  DE PE COM O CODIGO NOVO. Seu link continua o mesmo.")
    print("  Abra o link e de F5 -- a tela nova aparece sozinha.")
else:
    print("  NAO SUBIU. O que ele disse:")
    print(open("/content/bigode.log").read()[-2000:])
print("=" * 66)
print()
