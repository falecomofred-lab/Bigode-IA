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


def status():
    exe, mod = executavel(), modelo()
    if exe and mod:
        return {
            "motor": "whisper",
            "disponivel": True,
            "modelo": mod.stem.replace("ggml-", ""),
            "gb": round(mod.stat().st_size / 1e9, 2),
        }
    return {
        "motor": "navegador",
        "disponivel": False,
        "motivo": "Whisper nao encontrado. Usando o reconhecimento do navegador.",
    }


def transcrever(wav_bytes, idioma="pt"):
    exe, mod = executavel(), modelo()
    if not (exe and mod):
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
