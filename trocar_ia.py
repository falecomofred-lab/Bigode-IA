"""TROCAR DE IA SEM PERDER O LINK

O problema
----------
No Colab, a celula 1 so escreve uma variavel: IA = "granite". Mudar essa
palavra nao troca nada -- o motor ja subiu com o arquivo antigo. Para valer,
era preciso rodar de novo as celulas 1, 3 e 6. A 3 copia gigabytes do Drive
e a 6 sobe o motor. E, ate 09/09, muita gente resolvia clicando em "Executar
tudo" -- que passa pela celula 11 e DERRUBA O TUNEL. O link muda, e a
extensao do Chrome, que guarda o endereco antigo, para de falar.

O que este arquivo faz
----------------------
Troca so o motor. O Bigode continua de pe na porta 7000 e o tunel continua
apontando para ela -- entao O LINK NAO MUDA e a extensao nao precisa ser
mexida. ~40 segundos se o modelo ja estiver na maquina, ~2 minutos se
precisar trazer do Drive.

Como usar (no Colab)
--------------------
Uma celula de duas linhas:

    NOVA = "deepseek"
    exec(open('/content/drive/MyDrive/projetos/Cerebro/trocar_ia.py').read())

Le do Drive de proposito: assim a correcao que voce faz no Windows vale na
proxima troca sem precisar rodar a celula 9.

Precisa que as celulas 1 a 7 ja tenham rodado -- e delas que vem o CATALOGO.

Venure - venure.com.br
"""

import shutil
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# --- de onde vem o que este arquivo precisa ---------------------------------
# Roda dentro do notebook (exec), entao le as variaveis que ja existem la.
# Se alguma faltar, e porque as celulas de cima nao rodaram: dizer isso e
# melhor do que estourar um NameError seco tres linhas adiante.
_faltando = [n for n in ("CATALOGO", "PASTA_GGUF") if n not in globals()]
if _faltando:
    raise SystemExit(
        "Faltou rodar as celulas de cima. Nao encontrei: %s\n"
        "Rode as celulas 1 a 7 primeiro." % ", ".join(_faltando))

_nova = str(globals().get("NOVA", "")).strip()
if _nova not in CATALOGO:                                     # noqa: F821
    raise SystemExit(
        "NOVA = %r nao existe. As que voce tem: %s"
        % (_nova, ", ".join(sorted(CATALOGO))))                # noqa: F821

_d = CATALOGO[_nova]                                          # noqa: F821

# A mesma trava do catalogo, repetida aqui: quem troca de IA pela metade da
# sessao nao releu a tabela, e um modelo que nao cabe derruba o motor -- que
# e justamente o processo que esta funcionando agora.
if not _d.get("cabe", True):
    raise SystemExit(
        "%r pesa %.1f GB e nao cabe nesta placa. %s\n"
        "O motor atual continua de pe -- nada foi mexido."
        % (_nova, _d.get("gb", 0), _d.get("nota", "")))

_arquivo = _d["arquivo"]
_janela = _d["janela"]
_destino = "/content/modelos/" + _arquivo

print("=" * 66)
print("  TROCANDO PARA: %s" % _nova)
print("  %s" % _d["para"])
print("=" * 66)

# --- 1. o .gguf esta na maquina? -------------------------------------------
# Se voce ja usou essa IA nesta sessao, ela continua em /content/modelos e
# pulamos a copia. Trocar de ida e volta custa 40s, nao 3 minutos.
if Path(_destino).is_file():
    print("\n  Ja esta aqui. Nao precisa baixar de novo.")
else:
    _origem = Path(PASTA_GGUF) / _arquivo                     # noqa: F821
    if not _origem.is_file():
        print("\n  Nao achei no Drive:", _origem)
        print("  O que tem na pasta:")
        for _a in _origem.parent.glob("*.gguf"):
            print("   ", _a.name)
        raise SystemExit()
    Path("/content/modelos").mkdir(exist_ok=True)
    print("\n  Trazendo do Drive (%.1f GB)..."
          % (_origem.stat().st_size / 1e9))
    _t0 = time.time()
    shutil.copy2(_origem, _destino)
    print("  Pronto em %.0fs" % (time.time() - _t0))

# --- 2. derruba SO o motor --------------------------------------------------
# O `pkill` mira o modulo pelo nome. Nao toca em cerebro.py nem em
# cloudflared -- e por isso que o link sobrevive.
print("\n  Desligando o motor antigo...")
subprocess.run("pkill -f llama_cpp.server", shell=True) if os.name != "nt" else None
time.sleep(3)

# --- 3. sobe o novo na mesma porta -----------------------------------------
# Mesma porta 8082. Do lado do Bigode nada muda: ele continua batendo em
# http://127.0.0.1:8082 e nem fica sabendo que trocou de IA.
_cmd = [sys.executable, "-m", "llama_cpp.server",
        "--model", _destino,
        "--host", "127.0.0.1", "--port", "8082",
        "--n_ctx", str(_janela),
        "--n_gpu_layers", "-1",
        "--n_threads", "2"]

_log = open("/content/motor.log", "w")
proc_motor = subprocess.Popen(_cmd, stdout=_log, stderr=subprocess.STDOUT)

print("  Subindo %s (janela %d)" % (_nova, _janela), end="")
_vivo = False
for _i in range(120):
    time.sleep(2)
    try:
        urllib.request.urlopen("http://127.0.0.1:8082/v1/models", timeout=3)
        print("\n  No ar em %ds." % (_i * 2))
        _vivo = True
        break
    except Exception:
        print(".", end="")

if not _vivo:
    print("\n\n  O motor nao subiu. O que ele disse:")
    print(open("/content/motor.log").read()[-2000:])
    raise SystemExit()

# --- 4. avisar o Bigode da janela nova -------------------------------------
# O Bigode corta o prompt pela janela que esta no config.json. Trocar de um
# modelo de 16k para um de 8k sem avisar faz ele mandar prompt grande demais
# e o motor recusar -- erro que aparece como resposta vazia.
#
# NAO REINICIAR O BIGODE AQUI  (aprendido na marra, 09/09)
#     A primeira versao deste trecho matava e subia o cerebro.py para ele
#     reler a janela. Funcionou -- e derrubou o tunel junto: o cloudflared
#     viu a origem sumir, encerrou a conexao com a borda e o link passou a
#     devolver 530. Justamente a coisa que este arquivo existe para nao
#     fazer.
#
#     E era desnecessario. `config()` no cerebro.py le o config.json inteiro
#     a cada pergunta -- nao guarda nada em memoria. Escrever o arquivo ja
#     basta: a proxima pergunta ja usa a janela nova.
try:
    import json
    _cfg_arq = Path("/content/bigode/config.json")
    _cfg = json.loads(_cfg_arq.read_text(encoding="utf-8-sig"))
    if _cfg.get("contexto") != _janela:
        _cfg["contexto"] = _janela
        _cfg_arq.write_text(json.dumps(_cfg, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print("  Janela ajustada para %d (sem reiniciar nada)." % _janela)
except Exception as _e:
    print("  (nao consegui ajustar a janela do Bigode: %s)" % _e)

# --- 5. conferir que o Bigode esta de pe -----------------------------------
try:
    urllib.request.urlopen("http://127.0.0.1:7000/api/login/estado", timeout=5)
    _bigode = "de pe"
except Exception:
    _bigode = "CAIU -- rode a celula 7"

# guarda o estado novo para as celulas seguintes
IA = _nova
JANELA = _janela
MODELO = _destino

print()
print("=" * 66)
print("  AGORA VOCE ESTA USANDO: %s" % _nova)
print("  arquivo ... %s" % _arquivo)
print("  janela .... %d" % _janela)
print("  Bigode .... %s" % _bigode)
print("  O LINK CONTINUA O MESMO. Nao mexa na extensao.")
print("=" * 66)
