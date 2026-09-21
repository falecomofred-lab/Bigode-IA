#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
VOZ - transcricao local de audio (Whisper)

Mesma ideia do ModelProvider: o resto do sistema so pede "transcreva este audio".
Se houver whisper.cpp na unidade, roda 100% offline com qualidade de ChatGPT.
Se nao houver, o frontend cai para o reconhecimento do proprio navegador.

Como instalar o Whisper no pendrive:
  D:\voz\whisper-cli.exe      (ou main.exe)  - binario do whisper.cpp
  D:\voz\ggml-small.bin       - modelo (recomendado ggml-small ou ggml-medium)

Venure - venure.com.br
"""

import subprocess
import tempfile
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
RAIZ = APP_ROOT.parent

NOMES_EXE = ("whisper-cli.exe", "whisper-cli", "main.exe",
             "whisper.exe", "whisper-cpp.exe")


def _pastas():
    return [RAIZ / "voz", APP_ROOT / "voz", RAIZ, APP_ROOT]


def executavel():
    for pasta in _pastas():
        if not pasta.exists():
            continue
        for nome in NOMES_EXE:
            alvo = pasta / nome
            if alvo.exists():
                return alvo
    return None


def modelo():
    melhor, tamanho = None, -1
    for pasta in _pastas():
        if not pasta.exists():
            continue
        for arquivo in pasta.glob("ggml-*.bin"):
            # prefere o maior modelo disponivel (mais preciso)
            if arquivo.stat().st_size > tamanho:
                melhor, tamanho = arquivo, arquivo.stat().st_size
    return melhor


# ----------------------------------------------------------------------
# WHISPER NA MODAL                                            (17/09/2026)
# ----------------------------------------------------------------------
# O `disponivel: False` daqui embaixo foi, durante meses, o motivo real de
# o microfone nunca funcionar direito: sem whisper.cpp no disco, a pagina
# caia no ditado do proprio Chrome, que dentro da barra lateral da extensao
# nem chega a gravar.
#
# Agora ha um terceiro caminho, e ele vem ANTES do navegador na ordem:
#
#     1. whisper.cpp no disco      offline, sem custo, se voce instalar
#     2. Whisper large-v3 na Modal placa de verdade, centavos por dia
#     3. ditado do Chrome          ultimo recurso, precisa de internet
#
# A ordem e essa de proposito: o que roda na sua maquina ganha do que roda
# fora, e o que voce controla ganha do que depende do Google.


def _config():
    """Le o config.json do Cerebro. Sem travar nada se ele nao existir."""
    import json
    try:
        return json.loads((APP_ROOT / "config.json").read_text(
            encoding="utf-8"))
    except Exception:
        return {}


def modal_ligado():
    """(url, token) do endpoint de voz na Modal, ou (None, None)."""
    alvo = _config().get("voz_modal") or {}
    url = str(alvo.get("url") or "").strip()
    token = str(alvo.get("token") or "").strip()
    return (url, token) if url.startswith("https://") else (None, None)


def _transcrever_modal(wav_bytes, idioma, url, token):
    import base64
    import json
    import urllib.request

    corpo = json.dumps({
        "token": token,
        "idioma": idioma,
        "wav": base64.b64encode(wav_bytes).decode("ascii"),
    }).encode("utf-8")
    pedido = urllib.request.Request(
        url, data=corpo, headers={"Content-Type": "application/json"})
    try:
        # 180 s: o primeiro pedido do dia acorda o conteiner (~20 s) e so
        # depois transcreve. Um timeout curto transformaria "esta ligando"
        # em "deu erro", e a pessoa desistiria bem antes de funcionar.
        with urllib.request.urlopen(pedido, timeout=180) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except Exception as erro:
        return {"ok": False, "erro": "Modal: %s" % str(erro)[:200]}


def status():
    exe, mod = executavel(), modelo()
    if exe and mod:
        return {
            "motor": "whisper",
            "disponivel": True,
            "modelo": mod.stem.replace("ggml-", ""),
            "gb": round(mod.stat().st_size / 1e9, 2),
        }
    url, _ = modal_ligado()
    if url:
        return {
            "motor": "modal",
            "disponivel": True,
            "modelo": "large-v3 (Modal)",
        }
    return {
        "motor": "navegador",
        "disponivel": False,
        "motivo": ("Sem Whisper. Instale o whisper.cpp ou publique o "
                   "modal_voz.py — enquanto isso, o ditado do Chrome."),
    }


def transcrever(wav_bytes, idioma="pt"):
    exe, mod = executavel(), modelo()
    if not (exe and mod):
        url, token = modal_ligado()
        if url:
            return _transcrever_modal(wav_bytes, idioma, url, token)
        return {"ok": False, "erro": "whisper_ausente"}

    temporario = Path(tempfile.gettempdir()) / ("cerebro_voz_%d.wav" % int(time.time() * 1000))
    try:
        temporario.write_bytes(wav_bytes)
        comando = [
            str(exe), "-m", str(mod), "-f", str(temporario),
            "-l", idioma, "-nt", "-np", "-t", "4",
        ]
        resultado = subprocess.run(comando, capture_output=True, text=True,
                                   encoding="utf-8", errors="ignore", timeout=180)
        texto = (resultado.stdout or "").strip()
        if not texto and resultado.returncode != 0:
            return {"ok": False, "erro": (resultado.stderr or "")[-300:]}

        linhas = []
        for linha in texto.splitlines():
            limpa = linha.strip()
            if not limpa or limpa.startswith("[") or limpa.startswith("whisper_"):
                continue
            linhas.append(limpa)
        return {"ok": True, "texto": " ".join(linhas).strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "erro": "tempo esgotado"}
    except Exception as erro:
        return {"ok": False, "erro": str(erro)}
    finally:
        try:
            temporario.unlink()
        except Exception:
            pass
