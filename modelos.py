#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MODEL PROVIDER - camada de abstracao dos modelos locais

O restante do sistema nunca fala com o motor diretamente: fala com o provedor.
Trocar de runtime (llamafile, llama-server, outro) significa escrever outro
adaptador aqui, sem tocar no frontend nem no orquestrador.

Venure - venure.com.br
"""

import json
import re
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

APP_ROOT = Path(__file__).resolve().parent
RAIZ = APP_ROOT.parent          # unidade/pendrive onde o app vive


# --------------------------------------------------------------------------
# ONDE AS IAs MORAM, DE VERDADE   (centralizado em 10/09)
#
# Ate aqui cada copia procurava num lugar diferente, e NENHUMA sabia da pasta
# onde os .gguf realmente estao:
#
#     C:\...\Downloads\Cerebro  ->  olhava Downloads e Downloads\Cerebro
#     D:\Cerebro (pendrive)     ->  olhava D:\ e D:\Cerebro
#     Colab                     ->  so achava porque a celula 5 mandava
#
# Por isso a tela mostrava IA nenhuma no computador: nao havia .gguf em
# nenhum desses lugares.
#
# A lista agora mora AQUI, no codigo -- e nao no config.json. A razao e boba
# e importante: o sincronizar-bigode.ps1 PRESERVA o config.json de cada copia
# (para nao pisar na senha nem no modelo escolhido). Um caminho escrito la
# nunca chegaria nas outras duas. No codigo, chega nas tres.
#
# A ORDEM IMPORTA
#     O pendrive vem primeiro. Quando ele esta plugado, ler dali e
#     instantaneo; o MESMO arquivo pelo G: e um download do Google Drive.
#     Como `listar()` deduplica por NOME de arquivo, a copia local vence e o
#     G: fica sendo a rede de seguranca de quem esta sem o pendrive.
PEN_WINDOWS = r"G:\Outros computadores\USB e dispositivos externos\Pen IA"
PEN_COLAB = "/content/drive/Othercomputers/USB e dispositivos externos/Pen IA"

PASTAS_PADRAO = [PEN_WINDOWS, PEN_COLAB, "/content/modelos"]

# AS IAs DE IMAGEM FICAM DE FORA DESTA LISTA, DE PROPOSITO
#
#     Elas moram em `Pen IA/IA Imagem` e quem le e o ComfyUI, nao o
#     llama.cpp. Se entrassem aqui, apareceriam na tela junto com as de
#     texto e o Bigode tentaria carregar um modelo de difusao como se fosse
#     de conversa -- falha com uma mensagem que nao explica nada.
#
#     Quem cuida delas e o imagens.py.


# --------------------------------------------------------------------------
# Nomes de produto
# --------------------------------------------------------------------------

def tamanho_params(arquivo):
    """Extrai o tamanho em bilhoes de parametros do nome do arquivo."""
    achado = re.search(r"[-_](\d{1,3})b\b", (arquivo or "").lower())
    return achado.group(1) + "B" if achado else ""


def apelido(arquivo, gb):
    """Nome de produto Venure, com a familia junto para nunca repetir.

    O nome vinha do TAMANHO do arquivo, e isso enganava: o Qwen 7B (4,7 GB)
    e o Granite (4,2 GB) caiam os dois na faixa "Venure Rapido" -- sendo que
    um faz 3,8 tok/s e o outro 9,6. O rotulo dizia "Rapido" justamente para
    o mais lento dos dois, e nao havia como perceber olhando a tela.

    Agora o nome vem da VELOCIDADE MEDIDA nesta maquina. Quando nao existe
    medida, cai para o tamanho -- mas ai o nome nao promete velocidade.
    """
    medido = perfil(arquivo, gb)
    detalhe = familia(arquivo)["familia"]
    params = tamanho_params(arquivo)
    if params:
        detalhe += " " + params

    if medido["perfil"] == "pesado":
        base = "Venure Pesado"
    elif medido["tok_s_medido"]:
        base = "Venure Rapido" if medido["perfil"] == "rapido" else "Venure Preciso"
    elif gb >= 15:
        base = "Venure Grande"
    elif gb >= 10:
        base = "Venure Medio"
    else:
        base = "Venure Leve"

    return "%s · %s" % (base, detalhe)


def quantizacao(nome):
    achado = re.search(r"(Q\d[_A-Z0-9]*|F16|BF16|IQ\d[_A-Z0-9]*)", nome, re.I)
    return achado.group(1).upper() if achado else ""


# familia -> (rotulo, chave do logo no frontend)
FAMILIAS = [
    ("deepseek",  "DeepSeek",  "deepseek"),
    ("qwen",      "Qwen",      "qwen"),
    ("devstral",  "Devstral",  "mistral"),
    ("codestral", "Codestral", "mistral"),
    ("mistral",   "Mistral",   "mistral"),
    ("mixtral",   "Mixtral",   "mistral"),
    ("phi",       "Phi",       "phi"),
    ("gemma",     "Gemma",     "gemma"),
    ("codegemma", "CodeGemma", "gemma"),
    ("starcoder", "StarCoder", "starcoder"),
    ("granite",   "Granite",   "granite"),
    ("yi",        "Yi",        "generico"),
    ("glm",       "GLM",       "generico"),
    ("kimi",      "Kimi",      "generico"),
    ("llama",     "Llama",     "generico"),
]


def familia(arquivo):
    baixo = (arquivo or "").lower()
    for chave, rotulo, logo in FAMILIAS:
        if chave in baixo:
            return {"familia": rotulo, "logo": logo}
    return {"familia": "Modelo local", "logo": "generico"}


# --------------------------------------------------------------------------
# Perfis: rapido x cuidadoso
# --------------------------------------------------------------------------
#
# O Granite sempre foi 2,5x mais rapido que o Qwen (9,6 contra 3,8 tok/s) e
# sempre foi descartado pelo mesmo motivo: inventa mais.
#
# O que mudou e que a trava contra invencao saiu do prompt e foi para o
# backend. Antes, "nao inventar" era um pedido -- e um modelo pequeno atende
# menos os pedidos. Agora a resposta sem leitura, sem comando e sem teste sai
# marcada NAO VERIFICADO na tela, independente do modelo. O selo nao depende
# de comportamento, entao a diferenca de disciplina entre Granite e Qwen deixa
# de ser invisivel: vira um carimbo que da para conferir.
#
# Por isso o Granite volta como perfil do dia a dia, e o Qwen fica para quando
# a resposta precisa estar certa de primeira. Numeros abaixo sao medidos nesta
# maquina (Ryzen 7 5825U, 32 GB, sem GPU) -- nao sao estimativa.

PERFIS = {
    "rapido": {
        "rotulo": "rápido",
        "para_que": "listar, ler, buscar, classificar, perguntar do dia a dia",
    },
    "cuidadoso": {
        "rotulo": "cuidadoso",
        "para_que": "escrever código, auditar, quando errar custa caro",
    },
    "pesado": {
        "rotulo": "pesado demais",
        "para_que": "não recomendado nesta máquina — falta memória",
    },
}

# pedaco do nome do arquivo -> (perfil, tok/s medido, observacao honesta)
#
# O qwen3-14b foi medido em 18/08 e o resultado foi ruim de um jeito que nao
# se ve no tamanho do arquivo: com ele carregado sobram 2,7 GB de RAM, e o
# Windows comeca a usar o PENDRIVE como memoria. A leitura de um prompt de
# 3.400 tokens levou 843 segundos -- 6,7x mais lento que no 7B, que le o mesmo
# prompt em 126 s. Nao e o modelo que e ruim: e que ele nao cabe aqui com
# folga. Marcado como "grande demais" para nao ser escolhido por engano.
MEDIDOS = [
    ("granite",        "rapido",    9.6, "o mais rápido medido; erra mais — confira o selo"),
    ("qwen2.5-coder",  "cuidadoso", 3.8, "o mais confiável para código nesta máquina"),
    # 18,6 GB, o mesmo tamanho do 14b que foi medido e nao coube. O numero
    # 2,9 tok/s e antigo e foi medido antes de sabermos do problema de
    # memoria -- provavelmente esta otimista pelo mesmo motivo.
    ("qwen3-coder",    "pesado",    2.9, "18,6 GB — mesmo tamanho do 14B, "
                                         "que travou por falta de memória"),
    ("qwen3-14b",      "pesado",    1.0, "NÃO CABE: sobram 2,7 GB de RAM e o "
                                         "Windows usa o pendrive como memória"),
]


def perfil(arquivo, gb=0):
    baixo = (arquivo or "").lower()
    for pedaco, qual, tok_s, nota in MEDIDOS:
        if pedaco in baixo:
            return {"perfil": qual, "tok_s_medido": tok_s, "nota": nota,
                    "recomendado": qual == "rapido"}
    # Nao medido ainda: chuta pelo tamanho, mas deixa claro que e chute.
    qual = "rapido" if gb and gb < 6 else "cuidadoso"
    return {"perfil": qual, "tok_s_medido": None,
            "nota": "ainda não medido nesta máquina", "recomendado": False}


# Modelos cujo template de conversa nao tem secao de ferramentas. Com eles, o
# function calling oficial e ignorado e precisamos do protocolo em texto.
SEM_FERRAMENTAS_NATIVAS = (
    "deepseek-coder-v2", "deepseek-coder-6.7", "deepseek-coder-1.3",
    "codellama", "starcoder", "codegemma", "stable-code", "wizardcoder",
)


def suporta_ferramentas(arquivo):
    baixo = (arquivo or "").lower()
    return not any(s in baixo for s in SEM_FERRAMENTAS_NATIVAS)


def especialidade(arquivo):
    baixo = (arquivo or "").lower()
    if "coder" in baixo or "code" in baixo or "devstral" in baixo:
        return "programacao"
    if "instruct" in baixo or "chat" in baixo or "it" in baixo.split("-"):
        return "conversa"
    return "geral"


# --------------------------------------------------------------------------
# Provedor local (llamafile / llama-server)
# --------------------------------------------------------------------------

class LocalModelProvider:

    def __init__(self, config_fn, salvar_fn):
        self._config = config_fn
        self._salvar = salvar_fn
        self._processo = None
        self._carregado = None
        self._inicio_carga = None
        self._tempo_carga = None
        self._ultima_velocidade = None

    # ---------------- descoberta ----------------

    def pastas(self):
        """Todo lugar onde pode haver .gguf de texto, sem repetir.

        `pastas_modelos` do config vem antes dos padroes: quem configurou a
        mao continua mandando. Os padroes entram depois, como rede.
        """
        extras = [Path(p) for p in (self._config().get("pastas_modelos") or [])]
        todas = [RAIZ, APP_ROOT] + extras + [Path(p) for p in PASTAS_PADRAO]

        vistas, saida = set(), []
        for p in todas:
            chave = str(p).lower()
            if chave in vistas:
                continue
            vistas.add(chave)
            saida.append(p)
        return saida

    def executavel(self):
        for pasta in self.pastas():
            for padrao in ("llamafile*.exe", "llama-server*.exe", "llamafile*"):
                for achado in sorted(pasta.glob(padrao)):
                    if achado.is_file():
                        return achado
        return None

    def listar(self):
        atual = self._config().get("modelo_atual", "")
        vistos, saida = set(), []
        for pasta in self.pastas():
            if not pasta.exists():
                continue
            for arquivo in sorted(pasta.glob("*.gguf")):
                # A chave e o NOME DO ARQUIVO, nao o caminho.
                #
                # 09/09: depois que a pasta do pendrive entrou na lista, a
                # tela passou a mostrar nove IAs para sete arquivos -- o
                # granite e o DeepSeek apareciam duas vezes, porque estao
                # em /content/modelos (a copia local) e tambem no Drive. Com
                # o caminho como chave, dois caminhos diferentes pareciam
                # dois modelos diferentes.
                #
                # Vence a PRIMEIRA pasta da lista, que e a local: `pastas()`
                # devolve a raiz e as extras nessa ordem, e ler do disco da
                # maquina e muito mais rapido que ler do Drive montado.
                chave = arquivo.name.lower()
                if chave in vistos:
                    continue
                vistos.add(chave)
                gb = round(arquivo.stat().st_size / 1e9, 1)
                saida.append({
                    "id": str(arquivo),
                    "nome": apelido(arquivo.stem, gb),
                    "arquivo": arquivo.stem,
                    "gb": gb,
                    "quantizacao": quantizacao(arquivo.stem),
                    "papel": "principal" if gb >= 15 else "rapido",
                    "especialidade": especialidade(arquivo.stem),
                    "ferramentas_nativas": suporta_ferramentas(arquivo.stem),
                    "incompleto": gb < 1.0,
                    "atual": str(arquivo) == atual,
                    **familia(arquivo.stem),
                    **perfil(arquivo.stem, gb),
                })
        # ---- nomes repetidos ganham sobrenome  (10/09) -------------------
        #
        # Na tela do Fred apareceram DOIS cartoes chamados
        # "Venure Preciso · Qwen 7B", e dois "Venure Rapido · Granite".
        # Sao arquivos diferentes -- Q4_K_M e Q3_K_M do mesmo modelo -- mas o
        # apelido vem da familia e da velocidade, e essas duas coisas sao
        # iguais nos dois. Dois botoes com o mesmo rotulo e escolha no escuro.
        #
        # Quem desempata e a quantizacao: e exatamente o que difere.
        contagem = {}
        for m in saida:
            contagem[m["nome"]] = contagem.get(m["nome"], 0) + 1
        for m in saida:
            if contagem[m["nome"]] > 1 and m["quantizacao"]:
                m["nome"] = "%s (%s)" % (m["nome"], m["quantizacao"])

        # O recomendado vem primeiro. Antes a lista abria pelo maior arquivo --
        # que nesta maquina e justamente o mais lento.
        saida.sort(key=lambda m: (not m["recomendado"], -m["gb"]))
        if saida and not any(m["atual"] for m in saida):
            saida[0]["atual"] = True
        return saida

    def atual(self):
        for modelo in self.listar():
            if modelo["atual"]:
                return modelo
        return None

    # ---------------- ciclo de vida ----------------

    def _porta(self):
        try:
            return urlparse(self._config()["llm_url"]).port or 8082
        except Exception:
            return 8082

    def online(self):
        endereco = urlparse(self._config()["llm_url"])
        base = "http://%s:%d/" % (endereco.hostname or "127.0.0.1", self._porta())
        try:
            with urllib.request.urlopen(base, timeout=4):
                return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            return False

    def descarregar(self):
        """Libera a memoria antes de subir outro modelo.

        Windows e Linux derrubam processo de formas diferentes, e desde
        09/09 o Bigode roda nos dois: no pendrive do Fred e numa maquina do
        Colab. `taskkill` nao existe em Linux -- ele falharia em silencio
        (capture_output engole tudo) e o modelo antigo continuaria ocupando
        a memoria da GPU, fazendo o novo nao subir por falta de espaco.
        """
        # Primeiro encerra somente o processo que este provedor abriu. Isso
        # evita derrubar outro llama-server/ComfyUI do usuário no Colab.
        if self._processo is not None:
            try:
                self._processo.terminate()
                self._processo.wait(timeout=8)
            except Exception:
                try:
                    self._processo.kill()
                except Exception:
                    pass
            self._processo = None
        if os.name == "nt":
            alvos = ('taskkill /f /fi "imagename eq llamafile*"',
                     'taskkill /f /fi "imagename eq llama-server*"')
        else:
            # Fallback apenas para processos antigos, sem referência local.
            # O servidor atual sempre cai no bloco acima.
            alvos = ("pkill -f 'llama_cpp.server --model'",)
        for cmd in alvos:
            subprocess.run(cmd, shell=True, capture_output=True)
        self._processo = None
        self._carregado = None
        time.sleep(2)

    # ------------------------------------------------------------- Colab
    #
    # POR QUE ESTE BLOCO EXISTE
    #     Ate 09/09 o Bigode no Colab so subia com o granite, e a tela nao
    #     deixava trocar. Dois motivos somados:
    #
    #     1. `listar()` varre `pastas_modelos`, que no Colab apontava so para
    #        /content/modelos -- e la dentro tinha UM arquivo, o que a celula
    #        3 copiou. As outras seis IAs existiam, mas fora do alcance.
    #
    #     2. `carregar()` exigia `executavel()` -- um llamafile ou
    #        llama-server em disco. No Colab nao ha nenhum: quem roda o
    #        motor e o `python -m llama_cpp.server`, que veio pelo pip. Entao
    #        mesmo listando, clicar em "trocar" responderia "nenhum
    #        executavel de motor encontrado".
    #
    #     Aqui os dois caminhos passam a existir de verdade, e a tela do
    #     Bigode volta a trocar de IA como fazia no pendrive.

    @staticmethod
    def _no_colab():
        return os.name != "nt" and Path("/content").is_dir()

    @staticmethod
    def _vram_gb():
        """Memoria da placa, medida. Zero quando nao ha placa."""
        try:
            saida = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=memory.total",
                 "--format=csv,noheader,nounits"],
                text=True).strip().splitlines()[0]
            return float(saida) / 1024.0
        except Exception:
            return 0.0

    def _carregar_no_colab(self, modelo):
        """Sobe um .gguf na GPU do Colab, pelo llama_cpp.server."""
        import shutil
        import sys

        registro = APP_ROOT / "motor.log"
        tamanho = modelo.stat().st_size / 1e9
        vram = self._vram_gb()

        # Recusar antes de gastar tres minutos copiando e melhor do que
        # deixar o motor morrer sem memoria la na frente -- erro que aparece
        # na tela como "o motor nao respondeu", sem dizer por que.
        if vram and (tamanho + 2.5) > vram:
            return {"ok": False, "msg":
                    "%s pesa %.1f GB e a placa tem %.1f GB. Nao cabe."
                    % (modelo.name, tamanho, vram)}

        # O .gguf pode estar no Drive montado. Ler de la durante o trabalho e
        # lento: cada acesso vai e volta pela rede. Traz para o disco local
        # uma vez e usa dali.
        if str(modelo).startswith("/content/drive/"):
            local = Path("/content/modelos") / modelo.name
            if not local.is_file():
                local.parent.mkdir(exist_ok=True)
                with open(registro, "w", encoding="utf-8") as saida:
                    saida.write("Trazendo %s do Drive (%.1f GB)...\n"
                                % (modelo.name, tamanho))
                try:
                    shutil.copy2(modelo, local)
                except Exception as erro:
                    return {"ok": False,
                            "msg": "nao consegui trazer do Drive: %s" % erro}
            modelo = local

        self.descarregar()

        cfg = self._config()
        janela = int(cfg.get("contexto", 8192))

        # Janela grande custa memoria de video: o cache de atencao cresce com
        # ela. Num modelo de 10 GB numa placa de 15, 16k nao cabe junto.
        if vram and (vram - tamanho) < 5.5:
            janela = min(janela, 8192)

        # llama_cpp.server nao entende as opcoes do llamafile (-c, -t, -tb,
        # --parallel, --cache-ram). Mandar uma delas faz ele abortar na
        # partida. Sao estas, e so estas.
        cmd = [sys.executable, "-m", "llama_cpp.server",
               "--model", str(modelo),
               "--host", "127.0.0.1",
               "--port", str(self._porta()),
               "--n_ctx", str(janela),
               "--n_gpu_layers", "-1",      # TODAS as camadas na placa
               "--n_threads", "2"]

        try:
            with open(registro, "w", encoding="utf-8") as saida:
                saida.write("COMANDO: %s\n\n" % " ".join(cmd))
                saida.flush()
                self._processo = subprocess.Popen(
                    cmd, stdout=saida, stderr=subprocess.STDOUT)
        except Exception as erro:
            return {"ok": False, "msg": "nao consegui subir o motor: %s" % erro}

        # A janela vai para o config.json porque quem corta o prompt e o
        # cerebro.py, e ele le esse arquivo a cada pergunta. Sem isto o
        # Bigode manda 16k para um motor de 8k e a resposta volta vazia.
        self._carregado = str(modelo)
        self._inicio_carga = time.time()
        self._tempo_carga = None
        self._salvar({"modelo_atual": str(modelo), "contexto": janela})

        gb = round(tamanho, 1)
        return {"ok": True, "msg": "carregando %s na GPU (janela %d)"
                                   % (apelido(modelo.stem, gb), janela)}

    def carregar(self, caminho):
        modelo = Path(caminho)
        if not modelo.exists():
            return {"ok": False, "msg": "modelo nao encontrado"}

        if self._no_colab():
            return self._carregar_no_colab(modelo)

        motor = self.executavel()
        if not motor:
            return {"ok": False, "msg": "nenhum executavel de motor encontrado na unidade"}

        self.descarregar()

        cfg = self._config()
        contexto = int(cfg.get("contexto", 4096))
        threads = int(cfg.get("threads", 8))

        # mmap acelera muito em SSD interno (carga preguicosa) e atrapalha em
        # pendrive (fica lendo do USB o tempo todo). Decide pelo disco do modelo.
        usar_mmap = cfg.get("usar_mmap")
        if usar_mmap is None:
            usar_mmap = str(modelo)[:1].upper() == "C"

        # Escrever texto e limitado pela memoria: mais threads nao ajuda e ate
        # atrapalha. Ler o prompt e calculo puro: usa TODOS os nucleos logicos.
        # E a diferenca entre esperar 3 minutos e esperar 1,5 pela leitura.
        import os
        logicos = os.cpu_count() or threads
        threads_leitura = int(cfg.get("threads_leitura") or logicos)

        # llamafile e llama-server nao falam a mesma lingua. "--server" e
        # "--gpu disable" sao do llamafile; o llama-server ja e servidor por
        # natureza e desliga a placa com "-ngl 0". Mandar a opcao errada faz o
        # motor parar de ler o RESTO da linha -- foi o que aconteceu aqui: as
        # opcoes depois dela viraram enfeite, e o motor subiu no padrao dele.
        eh_llamafile = "llamafile" in motor.name.lower()

        opcoes = ['--port %d' % self._porta()]
        if eh_llamafile:
            opcoes = ['--server'] + opcoes + ['--gpu disable']
        else:
            opcoes += ['-ngl 0']                  # nenhuma camada na placa

        opcoes += [
            '-c %d' % contexto,
            '-t %d' % threads,                    # geracao
            '-tb %d' % threads_leitura,           # leitura do prompt
            '-b 2048', '-ub 512',                 # lotes maiores na leitura
            # UMA conversa por vez.
            #
            # 23/08: o log do motor mostrou
            #     "n_parallel is set to auto, using n_parallel = 4"
            # ou seja, o `-np 1` que estava aqui foi IGNORADO. Com quatro
            # lugares e kv_unified, a janela e dividida: `-c 8192` virava
            # 2.048 tokens por conversa. O prompt do Bigode tem 3.600 --
            # nunca coube, e o motor derrubava a conexao.
            #
            # A forma longa e a que esta versao do llamafile entende.
            '--parallel 1',
            '--no-warmup',       # nao gasta tempo com a rodada vazia inicial
        ]

        # Cache de prompts: e o que evita reprocessar a conversa inteira a cada
        # mensagem. Modelos leves deixam RAM sobrando, entao ganham cache maior.
        # Pouco cache e pior que nenhum: cabe uma conversa so, e ela vive sendo
        # expulsa pela seguinte.
        livre_gb = 32 - (modelo.stat().st_size / 1e9) - 4      # folga p/ Windows
        cache_mb = int(max(1536, min(6144, livre_gb * 1024 * 0.45)))
        opcoes.append('--cache-ram %d' % cache_mb)
        if not usar_mmap:
            opcoes.append('--no-mmap')

        # Guarda a saida do motor num .bat temporario: assim as aspas do Windows
        # nao atrapalham e o erro fica registrado em vez de sumir com a janela.
        registro = APP_ROOT / "motor.log"
        script = APP_ROOT / "_motor.bat"
        linha = '"%s" -m "%s" %s' % (motor, modelo, " ".join(opcoes))

        # A PRIMEIRA linha do log passa a ser o comando exato que subiu o motor.
        # Sem isso, so da para descobrir se uma opcao pegou lendo o que o motor
        # diz de si mesmo e torcendo para bater -- foi assim que passou
        # despercebido que --parallel, -tb, --no-warmup e --cache-ram estavam
        # sendo ignorados. Agora o log responde sozinho: comando pedido em
        # cima, o que o motor entendeu embaixo.
        script.write_text(
            '@echo off\r\n'
            'echo COMANDO: %s > "%s"\r\n'
            'echo. >> "%s"\r\n'
            '%s >> "%s" 2>&1\r\n'
            % (linha.replace("%", "%%"), registro, registro, linha, registro),
            encoding="utf-8")
        if os.name == "nt":
            subprocess.Popen('start "Motor Bigode" /min "%s"' % script,
                             shell=True)
        else:
            # Em Linux (Colab) nao ha `start` nem .bat. Sobe direto e manda
            # a saida para o mesmo motor.log -- assim o espelho na tela e o
            # auditar_tudo continuam funcionando igual nos dois sistemas.
            #
            # Nota: no Colab quem sobe o motor e o proprio notebook, com o
            # llama-cpp-python e a GPU. Este caminho so e usado se voce
            # trocar de modelo pela tela la dentro.
            try:
                with open(registro, "w", encoding="utf-8") as saida:
                    saida.write("COMANDO: %s\n\n" % linha)
                    saida.flush()
                    subprocess.Popen([str(motor), "-m", str(modelo)]
                                     + " ".join(opcoes).split(),
                                     stdout=saida, stderr=subprocess.STDOUT)
            except Exception as erro:
                return {"ok": False, "msg": "nao consegui subir o motor: %s" % erro}

        self._carregado = str(modelo)
        self._inicio_carga = time.time()
        self._tempo_carga = None
        self._salvar({"modelo_atual": str(modelo)})

        gb = round(modelo.stat().st_size / 1e9, 1)
        return {"ok": True, "msg": "carregando " + apelido(modelo.stem, gb)}

    def garantir_carregado(self):
        """Sobe o modelo escolhido caso o motor nao esteja de pe."""
        if self.online():
            return True
        modelo = self.atual()
        if not modelo:
            return False
        self.carregar(modelo["id"])
        return False

    # ---------------- metricas ----------------

    def registrar_velocidade(self, tokens, segundos):
        if segundos > 0.4 and tokens > 4:
            self._ultima_velocidade = round(tokens / segundos, 1)

    def erro_recente(self):
        """Ultimas linhas de erro do motor, se ele nao subiu."""
        registro = APP_ROOT / "motor.log"
        if not registro.exists():
            return ""
        try:
            linhas = registro.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return ""
        ruins = [l.strip() for l in linhas
                 if any(m in l for m in ("error", "ERROR", "failed", "E srv",
                                         "unsupported", "cannot", "not supported"))]
        return " | ".join(ruins[-3:])[:400]

    def status(self):
        pronto = self.online()
        if pronto and self._inicio_carga and self._tempo_carga is None:
            self._tempo_carga = round(time.time() - self._inicio_carga, 1)

        modelo = self.atual() or {}
        estado = "online" if pronto else ("carregando" if self._inicio_carga else "parado")

        # quanto tempo ja esta carregando, e quanto costuma levar por GB no USB
        carregando_ha = None
        estimativa = None
        if estado == "carregando" and self._inicio_carga:
            carregando_ha = int(time.time() - self._inicio_carga)
            estimativa = int(float(modelo.get("gb", 8)) * 47)   # ~47s por GB no pendrive

        return {
            "estado": estado,
            "carregando_ha": carregando_ha,
            "estimativa_seg": estimativa,
            "pronto": pronto,
            "nome": modelo.get("nome", ""),
            "arquivo": modelo.get("arquivo", ""),
            "gb": modelo.get("gb", 0),
            "quantizacao": modelo.get("quantizacao", ""),
            "papel": modelo.get("papel", ""),
            "tempo_carga": self._tempo_carga,
            "tokens_seg": self._ultima_velocidade,
            "memoria_gb": self._memoria(),
        }

    def _memoria(self):
        try:
            saida = subprocess.run(
                'tasklist /fi "imagename eq llamafile*" /fo csv /nh',
                shell=True, capture_output=True, text=True, timeout=5).stdout
            achado = re.search(r'"([\d.]+) K"', saida.replace(" ", " "))
            if achado:
                kb = float(achado.group(1).replace(".", ""))
                return round(kb / 1_000_000, 1)
        except Exception:
            pass
        return None
