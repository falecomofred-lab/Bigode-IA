"""LIGAR O MOTOR NA GPU   -   celula 6

Sobe o llama_cpp.server na porta 8082, com TODAS as camadas na placa.

ONDE MORA O GANHO
    `--n_gpu_layers -1` poe o modelo inteiro na GPU. No notebook do Fred o
    motor sobe sem placa e le o prompt a ~60 tokens por segundo; numa T4
    isso passa de mil. E a diferenca entre esperar e conversar.

    E a leitura do prompt e 92% do tempo de resposta -- medido neste
    projeto. Por isso ela e o que importa, nao a velocidade de escrita.

DEPENDE DE
    Nada. Se as celulas de cima nao rodaram, ele acha o .gguf em
    /content/modelos e a janela no catalogo.

Venure - venure.com.br
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

PORTA = 8082
RAIZ_DRIVE = Path("/content/drive/MyDrive")
CATALOGO_PY = RAIZ_DRIVE / "projetos/Cerebro/catalogo_ia.py"
ARQ_CHAVE = Path("/content/motor.chave")

# A CHAVE E CRIADA AQUI, SEMPRE   (13/09)
#
#     O motor sobe com chave mesmo quando so o Colab vai falar com ele.
#     Ligar a chave depois, na hora que o tunel abre, exigiria derrubar o
#     motor e esperar de novo -- e e justamente na pressa que a gente
#     esquece, e ai a placa fica exposta num endereco publico.
#
#     A chave e a mesma durante toda a sessao: fica em /content/motor.chave.
#     Se esta celula rodar de novo para trocar de IA, o endereco publicado e
#     a chave continuam valendo, e nada precisa ser recolado no Windows.
#     O try existe porque alguem ja quis rodar este arquivo no Windows, onde
#     /content nao existe. Sem chave gravada o hibrido nao fecha, mas o
#     motor sobe do mesmo jeito -- e essa e a parte que nao pode quebrar.
CHAVE_MOTOR = ""
try:
    if ARQ_CHAVE.is_file():
        CHAVE_MOTOR = ARQ_CHAVE.read_text().strip()
    if not CHAVE_MOTOR:
        CHAVE_MOTOR = uuid.uuid4().hex
        ARQ_CHAVE.parent.mkdir(parents=True, exist_ok=True)
        ARQ_CHAVE.write_text(CHAVE_MOTOR)
except Exception:
    CHAVE_MOTOR = CHAVE_MOTOR or uuid.uuid4().hex


def _no_ar():
    """De pe? Com a chave ligada, perguntar sem ela devolve 401.

    401 tambem prova que o motor esta respondendo -- so que dizendo "quem e
    voce". Por isso 401 e 403 contam como vivo. Sem isso, a espera de quatro
    minutos passava inteira achando que ele nao tinha subido.
    """
    pedido = urllib.request.Request("http://127.0.0.1:%d/v1/models" % PORTA)
    pedido.add_header("Authorization", "Bearer " + CHAVE_MOTOR)
    try:
        urllib.request.urlopen(pedido, timeout=3)
        return True
    except urllib.error.HTTPError as e:
        return e.code in (401, 403)
    except Exception:
        return False


print()
print("=" * 66)
print("  LIGANDO O MOTOR")
print("=" * 66)

# ---- o que ligar ----------------------------------------------------------
if "MODELO" not in globals() or not Path(str(globals().get("MODELO"))).is_file():
    # A celula 3 nao rodou nesta sessao. Em vez de reclamar, procuramos o
    # que ja esta no disco -- que e exatamente o que ela teria deixado.
    _achados = sorted(Path("/content/modelos").glob("*.gguf")) \
        if Path("/content/modelos").is_dir() else []
    if not _achados:
        raise SystemExit(
            "Nao ha nenhum .gguf em /content/modelos. Rode a celula 3.")
    MODELO = str(_achados[0])
    print("\n  A celula 3 nao rodou. Usando o que ja esta no disco:")
    print("  %s" % Path(MODELO).name)

if "JANELA" not in globals():
    if CATALOGO_PY.is_file():
        if "IA" not in globals():
            IA = "granite"
        exec(CATALOGO_PY.read_text(encoding="utf-8"), globals())
    else:
        JANELA = 8192

# Janela grande custa memoria de video: o cache de atencao cresce com ela.
# Num modelo de 10 GB numa placa de 15, 16k nao cabe junto -- e o motor
# morre no meio da primeira resposta, sem dizer por que.
_gb = Path(MODELO).stat().st_size / 1e9
if _gb > 8 and JANELA > 8192:                                 # noqa: F821
    print("\n  Modelo de %.1f GB: baixando a janela de %d para 8192."
          % (_gb, JANELA))                                    # noqa: F821
    JANELA = 8192


# ---- com placa ou sem placa ----------------------------------------------
#
# `-1` poe TODAS as camadas na GPU. `0` nao poe nenhuma: tudo no processador.
# Mandar `-1` numa maquina sem placa faz o motor abortar na partida.
def _tem_placa():
    try:
        subprocess.check_output(["nvidia-smi"], stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


TEM_PLACA = _tem_placa()

if not TEM_PLACA:
    # No processador, quem manda e a memoria RAM e o numero de nucleos. O
    # Colab gratuito da 2 vCPU e ~12 GB. Um modelo de 10 GB cabe na conta e
    # engasga na pratica: sobra pouco para o cache e para o proprio Python.
    # `MemAvailable`, e nao "memoria livre".
    #
    # No Linux a memoria livre e quase sempre perto de zero: o sistema usa
    # tudo o que sobra como cache de disco, e devolve na hora que alguem
    # precisa. Medido nesta sessao: 0,1 GB "livres" contra ~10 GB
    # disponiveis. Olhar o numero errado fazia o Bigode recusar um modelo
    # de 4 GB numa maquina com espaco de sobra.
    _livre = 12.0
    try:
        with open("/proc/meminfo") as _f:
            for _l in _f:
                if _l.startswith("MemAvailable:"):
                    _livre = float(_l.split()[1]) / 1e6        # kB -> GB
                    break
    except Exception:
        pass
    # Folga menor que na placa: o llama.cpp usa mmap na CPU, entao nao
    # carrega o arquivo inteiro para a memoria.
    if _gb + 1.2 > _livre:
        raise SystemExit(
            "Sem placa, este modelo nao cabe: %.1f GB de arquivo e %.1f GB "
            "disponiveis de RAM. Escolha um mais leve na celula 1 -- o "
            "granite (4,2 GB) e o mais rapido que voce tem." % (_gb, _livre))
    # Janela menor no processador: cada token de contexto e reprocessado
    # pela CPU, e 16k ali significa minutos de espera por mensagem.
    #
    # 8192 E O CHAO, NAO 4096   (10/09)
    #     Minha primeira versao baixava para 4096 e teria quebrado tudo. O
    #     config() do cerebro.py tem um piso de 8192 justamente porque o
    #     prompt do sistema mais o esquema das ferramentas ja ocupam ~3800
    #     tokens -- em 4096 nao sobra espaco nem para a pergunta.
    #
    #     Motor em 4096 com o Bigode achando que tem 8192 e o pior dos
    #     mundos: funciona nas mensagens curtas e morre na primeira longa,
    #     com um erro que nao aponta para ca.
    if JANELA > 8192:                                         # noqa: F821
        print("\n  Sem placa: baixando a janela de %d para 8192, senao cada"
              % JANELA)                                       # noqa: F821
        print("  mensagem leva minutos so para reler a conversa.")
        JANELA = 8192

# ---- derrubar o que estiver de pe -----------------------------------------
# Dois motores na mesma porta geram um erro que nao explica nada.
subprocess.run("pkill -f llama_cpp.server", shell=True) if os.name != "nt" else None
time.sleep(2)

# `--host 0.0.0.0` e nao 127.0.0.1: no modo hibrido o cloudflared precisa
# alcancar o motor. Quem protege e a chave, nao o endereco de escuta.
cmd = [sys.executable, "-m", "llama_cpp.server",
       "--model", MODELO,
       "--host", "0.0.0.0", "--port", str(PORTA),
       "--api_key", CHAVE_MOTOR,
       "--n_ctx", str(JANELA),                                # noqa: F821
       "--n_gpu_layers", "-1" if TEM_PLACA else "0",
       "--n_threads", "2"]

_log = open("/content/motor.log", "w")
_log.write("COMANDO: %s\n\n" % " ".join(cmd))
_log.flush()
proc_motor = subprocess.Popen(cmd, stdout=_log, stderr=subprocess.STDOUT)


# A JANELA QUE VALE E ESTA, NAO A DO CATALOGO   (10/09)
#
#     O adaptar.py (celula 5) grava no config.json a janela do catalogo --
#     16384 para o granite. Mas as duas regras acima podem ter baixado esse
#     numero: para 8192 num modelo grande, para 4096 quando nao ha placa.
#
#     Se o config continuar dizendo 16384 enquanto o motor sobe com 4096, o
#     Bigode monta um prompt maior do que o servidor aceita e a resposta
#     morre no meio, com um erro que nao aponta para ca. Entao a ultima
#     palavra sobre a janela e desta celula, e ela precisa voltar para o
#     arquivo.
_cfg_arq = Path("/content/bigode/config.json")
if _cfg_arq.is_file():
    try:
        _cfg = json.loads(_cfg_arq.read_text(encoding="utf-8-sig"))
        _mudou = False
        if _cfg.get("contexto") != JANELA:                    # noqa: F821
            print("\n  Ajustando a janela do config: %s -> %d."
                  % (_cfg.get("contexto"), JANELA))           # noqa: F821
            _cfg["contexto"] = JANELA                         # noqa: F821
            _mudou = True
        # O Bigode daqui de dentro tambem precisa da chave: o motor agora
        # responde 401 para quem nao mandar o Bearer -- inclusive ele.
        if _cfg.get("llm_chave") != CHAVE_MOTOR:
            _cfg["llm_chave"] = CHAVE_MOTOR
            _mudou = True
        if _mudou:
            _cfg_arq.write_text(
                json.dumps(_cfg, ensure_ascii=False, indent=2),
                encoding="utf-8")
    except Exception as erro:
        print("\n  Nao consegui ajustar a janela do config: %s" % erro)

print("\n  Subindo %s (janela %d)" % (Path(MODELO).name, JANELA), end="")  # noqa: F821
_vivo = False
for _i in range(120):
    time.sleep(2)
    if _no_ar():
        print("\n  No ar em %ds." % (_i * 2))
        _vivo = True
        break
    print(".", end="")

print()
print("=" * 66)
if _vivo:
    print("  MOTOR DE PE na porta %d  (%s)."
          % (PORTA, "GPU" if TEM_PLACA else "processador"))
    if not TEM_PLACA:
        print()
        print("  Sem placa, conte com 2 a 5 palavras por segundo. Serve para")
        print("  conversa curta; ler projeto inteiro vai doer.")
else:
    print("  O MOTOR NAO SUBIU. O que ele disse:")
    print(open("/content/motor.log").read()[-2000:])
print("=" * 66)
print()
