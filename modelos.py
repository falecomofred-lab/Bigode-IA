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
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

APP_ROOT = Path(__file__).resolve().parent
RAIZ = APP_ROOT.parent          # unidade/pendrive onde o app vive


# --------------------------------------------------------------------------
# Nomes de produto
# --------------------------------------------------------------------------

def tamanho_params(arquivo):
    """Extrai o tamanho em bilhoes de parametros do nome do arquivo."""
    achado = re.search(r"[-_](\d{1,3})b\b", (arquivo or "").lower())
    return achado.group(1) + "B" if achado else ""


def apelido(arquivo, gb):
    """Nome de produto Venure, com a familia junto para nunca repetir."""
    if gb >= 15:
        base = "Venure Core"
    elif gb >= 10:
        base = "Venure Pro"
    elif gb >= 4:
        base = "Venure Rapido"
    else:
        base = "Venure Leve"

    detalhe = familia(arquivo)["familia"]
    params = tamanho_params(arquivo)
    if params:
        detalhe += " " + params
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
        extras = [Path(p) for p in (self._config().get("pastas_modelos") or [])]
        return [RAIZ, APP_ROOT] + extras

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
                chave = str(arquivo).lower()
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
                })
        saida.sort(key=lambda m: -m["gb"])
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
        """Libera a memoria antes de subir outro modelo."""
        subprocess.run('taskkill /f /fi "imagename eq llamafile*"',
                       shell=True, capture_output=True)
        subprocess.run('taskkill /f /fi "imagename eq llama-server*"',
                       shell=True, capture_output=True)
        self._processo = None
        self._carregado = None
        time.sleep(2)

    def carregar(self, caminho):
        modelo = Path(caminho)
        if not modelo.exists():
            return {"ok": False, "msg": "modelo nao encontrado"}

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

        opcoes = [
            '--server', '--port %d' % self._porta(),
            '--gpu disable',
            '-c %d' % contexto,
            '-t %d' % threads,                    # geracao
            '-tb %d' % threads_leitura,           # leitura do prompt
            '-b 2048', '-ub 512',                 # lotes maiores na leitura
            '--parallel 1',      # uma conversa por vez: mais contexto e menos RAM
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
        script.write_text(
            '@echo off\r\n"%s" -m "%s" %s > "%s" 2>&1\r\n'
            % (motor, modelo, " ".join(opcoes), registro),
            encoding="utf-8")
        subprocess.Popen('start "Motor Cerebro" /min "%s"' % script, shell=True)

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
