"""CATALOGO DAS IAs - qual existe, qual cabe, qual serve para que

O QUE MUDOU (09/09, noite)
--------------------------
Antes a celula 1 tinha duas IAs escritas na mao e um caminho fixo dentro do
Meu Drive. Mas as IAs de verdade nunca moraram la: moram no pendrive, que o
Google Drive para Desktop espelha em

    G:\\Outros computadores\\USB e dispositivos externos\\Pen IA

que no Colab aparece como

    /content/drive/Othercomputers/USB e dispositivos externos/Pen IA

Duas copias dos mesmos arquivos, e a celula 1 olhava para a errada. Agora o
catalogo le a pasta de verdade.

POR QUE UM ARQUIVO, E NAO CODIGO NA CELULA
------------------------------------------
Dicionario dentro de celula de notebook e o pior lugar para editar: o editor
do Colab fecha chave sozinho, a indentacao escorrega, e a correcao morre com
a sessao. Aqui e um .py normal, que o `sincronizar-bigode.ps1` espalha para
as tres copias como qualquer outro arquivo do projeto.

O QUE ELE DECIDE SOZINHO
------------------------
Nao ha lista de "cabe / nao cabe" escrita na mao. O tamanho vem do arquivo e
a memoria vem da placa. Se um dia a maquina for uma A100 de 40 GB, o mesmo
codigo passa a aceitar os modelos grandes sem ninguem mexer em nada.

Como usar (celula 1 do Colab):

    IA = "granite"
    from google.colab import drive; drive.mount('/content/drive')
    exec(open('/content/drive/MyDrive/projetos/Cerebro/catalogo_ia.py').read())

Venure - venure.com.br
"""

import os
import subprocess
from pathlib import Path

# ---------------------------------------------------------------- os lugares
PASTA_GGUF = "/content/drive/Othercomputers/USB e dispositivos externos/Pen IA"
PASTA_BIGODE = "projetos/Cerebro"          # este continua no Meu Drive

# ---------------------------------------------------------------- o catalogo
#
# `janela` e por modelo de proposito. Janela grande custa memoria de video
# (o cache de atencao cresce com ela). Num modelo de 4 GB sobra espaco para
# 16k; num de 10 GB, 16k estoura a placa e o motor morre no meio da primeira
# resposta -- falha que aparece como "o Bigode nao subiu", sem dizer por que.
CATALOGO = {
    "granite": {
        "arquivo": "granite-4.0-h-tiny-7b-Q4_K_M.gguf",
        "janela": 16384,
        "para": "conversa, leitura de arquivo, tarefa do dia a dia",
        "nota": "o mais rapido que voce tem",
    },
    "granite-apex": {
        "arquivo": "granite-4.0-h-tiny-APEX-i-quality-torch.gguf",
        "janela": 16384,
        "para": "mesmo que o granite, um pouco mais caprichado",
        "nota": "quantizacao diferente do mesmo modelo",
    },
    "qwen-coder": {
        "arquivo": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "janela": 16384,
        "para": "codigo do dia a dia",
        "nota": "le o prompt mais devagar que o granite",
    },
    "qwen-coder-leve": {
        "arquivo": "qwen2.5-coder-7b-instruct-q3_k_m.gguf",
        "janela": 16384,
        "para": "o mesmo, comprimido mais forte",
        "nota": "menor e mais burro; so se faltar memoria",
    },
    "deepseek": {
        "arquivo": "DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf",
        "janela": 8192,
        "para": "CODIGO DIFICIL - refatorar, achar bug, arquitetura",
        "nota": "o mais forte que cabe na T4; MoE, so 2,4B acendem por vez",
    },
    "qwen3-14b": {
        "arquivo": "qwen3-14b-Q4_K_M.gguf",
        "janela": 8192,
        "para": "raciocinio longo",
        "nota": "o nome diz Q4 mas o arquivo tem 18,8 GB - confira o que baixou",
    },
    "qwen3-coder-30b": {
        "arquivo": "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M (1).gguf",
        "janela": 8192,
        "para": "codigo, modelo grande",
        "nota": "precisa de uma placa maior que a T4",
    },
}

# Compatibilidade: o resto do notebook e o trocar_ia.py ainda falam ARQUIVOS.
ARQUIVOS = {nome: dados["arquivo"] for nome, dados in CATALOGO.items()}


# ------------------------------------------------------------ quanto cabe
def _memoria_da_placa_gb():
    """Quanto de memoria de video existe, medido. Zero quando nao ha placa."""
    try:
        saida = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            text=True).strip().splitlines()[0]
        return float(saida) / 1024.0
    except Exception:
        return 0.0


def _memoria_ram_gb():
    """A RAM que da para USAR. E ela que manda quando o motor roda na CPU.

    MEMORIA LIVRE E MEMORIA DISPONIVEL NAO SAO A MESMA COISA   (10/09)

        A primeira versao disto usava `SC_AVPHYS_PAGES`, que conta so as
        paginas COMPLETAMENTE livres. No Linux isso e quase sempre um numero
        pequeno e enganoso: o sistema usa toda a RAM sobrando como cache de
        disco, e esse cache e devolvido no instante em que alguem precisa.

        Medido nesta sessao, logo depois de copiar alguns gigabytes:

            SC_AVPHYS_PAGES  ->  0,1 GB    "nao cabe nada"
            MemAvailable     ->  ~10 GB    a verdade

        A tabela dizia NAO para as sete IAs numa maquina com espaco de
        sobra. `MemAvailable` existe no /proc/meminfo exatamente para
        responder "quanto da para abrir de programa novo" -- ja descontando
        o que e cache reciclavel.
    """
    try:
        with open("/proc/meminfo") as f:
            for linha in f:
                if linha.startswith("MemAvailable:"):
                    return float(linha.split()[1]) / 1e6      # kB -> GB
    except Exception:
        pass
    try:
        return (os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES")) / 1e9
    except Exception:
        return 12.0                      # o comum no Colab gratuito


# SEM PLACA, A CONTA E OUTRA   (10/09)
#
#     Antes isto devolvia 15.0 quando nao achava placa -- chutava uma T4. O
#     resultado era uma tabela dizendo "cabe: sim" para modelos de 10 GB
#     numa maquina que nao tinha GPU nenhuma.
#
#     Agora, sem placa, quem manda e a RAM: o motor roda no processador e o
#     modelo inteiro vai para a memoria comum.
VRAM_GB = _memoria_da_placa_gb()
TEM_PLACA = VRAM_GB > 0
MEMORIA_GB = VRAM_GB if TEM_PLACA else _memoria_ram_gb()

# A FOLGA E DIFERENTE NA PLACA E NA RAM   (10/09, medido)
#
#     NA PLACA: o modelo entra INTEIRO na VRAM, e ainda precisam caber o
#     cache de atencao e o proprio servidor. Sem 2,5 GB de folga, um modelo
#     de 14 GB "cabe" em 15 GB na conta e morre na pratica.
#
#     NA RAM: o llama.cpp usa mmap. Ele nao carrega o arquivo inteiro para a
#     memoria -- mapeia o arquivo em disco e o sistema traz as paginas
#     conforme precisa. Entao o gasto real e bem menor que o tamanho do
#     .gguf.
#
#     Exigir os mesmos 2,5 GB nos dois casos foi erro meu: numa sessao com
#     6 GB livres, o granite de 4,2 GB era recusado -- e ele roda.
FOLGA_GB = 2.5 if TEM_PLACA else 1.2


def _tamanho_gb(arquivo):
    try:
        return os.path.getsize(os.path.join(PASTA_GGUF, arquivo)) / 1e9
    except Exception:
        return None                      # nao esta na pasta


# ------------------------------------------------------------------ a mesa
print()
print("=" * 74)
if TEM_PLACA:
    print("  AS IAs QUE VOCE TEM      placa: %.1f GB de memoria" % VRAM_GB)
else:
    print("  AS IAs QUE VOCE TEM      SEM PLACA - %.1f GB de RAM livre"
          % MEMORIA_GB)
print("=" * 74)
print()
print("  %-17s %8s  %-5s %s" % ("nome", "tamanho", "cabe?", "para que serve"))
print("  " + "-" * 70)

_disponiveis = []
for _nome, _d in CATALOGO.items():
    _gb = _tamanho_gb(_d["arquivo"])
    if _gb is None:
        _d["cabe"] = False
        print("  %-17s %8s  %-5s %s" % (_nome, "--", "?", "nao esta na pasta"))
        continue
    _d["gb"] = _gb
    _d["cabe"] = (_gb + FOLGA_GB) <= MEMORIA_GB
    if _d["cabe"]:
        _disponiveis.append(_nome)
    print("  %-17s %6.1f GB  %-5s %s" % (
        _nome, _gb, "sim" if _d["cabe"] else "NAO", _d["para"]))

print()
print("  Quando usar qual")
print("  " + "-" * 70)
if TEM_PLACA:
    print("  conversa, ler arquivo, tarefa curta ....... granite")
    print("  escrever codigo comum ..................... qwen-coder")
    print("  codigo dificil, refatorar, achar bug ...... deepseek")
else:
    # Sem placa, recomendar o deepseek seria cruel: 10 GB no processador
    # significa minutos por resposta, mesmo quando cabe na RAM.
    print("  SEM PLACA: fique nas leves, senao cada resposta leva minutos.")
    print("  conversa e leitura de arquivo ............. granite   (4,2 GB)")
    print("  codigo, se precisar ....................... qwen-coder-leve (3,8 GB)")
print()

# ------------------------------------------------------- validar a escolha
IA = str(globals().get("IA", "granite")).strip()

if IA not in CATALOGO:
    raise SystemExit(
        "\n  IA = %r nao existe.\n  Escolha uma destas: %s\n"
        % (IA, ", ".join(sorted(CATALOGO))))

_escolhido = CATALOGO[IA]

if not _escolhido.get("cabe"):
    # Parar aqui e de proposito. Deixar seguir gasta tres minutos copiando
    # um arquivo que a placa vai recusar, e a mensagem de erro que aparece
    # la na frente ("o motor nao subiu") nao aponta para ca.
    # Quando NENHUMA cabe, "Cabem hoje: " sozinho nao ajuda ninguem. O que
    # a pessoa precisa saber e o que FAZER -- e quase sempre e liberar
    # memoria, porque a sessao acumula lixo ao longo das horas.
    _saida = ("\n  %r pesa %.1f GB e %s tem %.1f GB livres.\n  Nao cabe."
              % (IA, _escolhido.get("gb", 0),
                 "a placa" if TEM_PLACA else "a RAM (sem placa)",
                 MEMORIA_GB))
    if _disponiveis:
        _saida += "\n  Cabem hoje: %s\n" % ", ".join(_disponiveis)
    else:
        _saida += (
            "\n\n  NENHUMA cabe agora -- e isso quase sempre e memoria"
            "\n  ocupada por esta sessao, nao falta de espaco de verdade."
            "\n"
            "\n  Ambiente de execucao -> Reiniciar sessao"
            "\n  Depois rode tudo de novo. Uma sessao nova tem ~12 GB"
            "\n  livres; esta tem %.1f.\n" % MEMORIA_GB)
    raise SystemExit(_saida)

JANELA = _escolhido["janela"]

print("=" * 74)
print("  ESCOLHIDA: %s" % IA)
print("  arquivo .. %s" % _escolhido["arquivo"])
print("  tamanho .. %.1f GB    janela: %d" % (_escolhido["gb"], JANELA))
print("  serve para %s" % _escolhido["para"])
print("=" * 74)
print()
