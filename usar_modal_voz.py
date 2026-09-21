#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIGAR A VOZ DO BIGODE NA MODAL — e provar que ela ouve
Venure · venure.com.br · 17/09/2026

    python usar_modal_voz.py

Pergunta o endereco e a senha, grava os dois no config.json, manda um audio
de teste gerado aqui mesmo e mostra o que voltou.

Nao imprime a senha em nenhum momento -- ela e digitada sem eco. Ja houve
token vazando neste projeto por aparecer na tela; uma vez basta.
"""

import base64
import getpass
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))       # o Python embutido nao poe o proprio dir
CONFIG = BASE / "config.json"


def tom_wav(segundos=1.2, hz=16000):
    """Um WAV de 16 kHz com um tom curto.

    Nao e fala, entao o Whisper vai devolver pouco ou nada de texto -- e ISSO
    e o que queremos saber. O teste aqui nao e "ele transcreveu certo", e sim
    "o audio chegou, o modelo rodou na placa e a resposta voltou". Se o
    caminho inteiro esta de pe, o resto e microfone.
    """
    import math
    import struct
    n = int(hz * segundos)
    quadros = b"".join(
        struct.pack("<h", int(9000 * math.sin(2 * math.pi * 440 * i / hz)))
        for i in range(n))
    cab = (b"RIFF" + struct.pack("<I", 36 + len(quadros)) + b"WAVEfmt "
           + struct.pack("<IHHIIHH", 16, 1, 1, hz, hz * 2, 2, 16)
           + b"data" + struct.pack("<I", len(quadros)))
    return cab + quadros


def ler_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    print()
    print("  VOZ DO BIGODE NA MODAL")
    print("  " + "-" * 60)

    dados = ler_config()
    antes = dados.get("voz_modal") or {}

    url = input("\n  Endereco (…-transcrever.modal.run): ").strip() \
        or str(antes.get("url") or "")
    if not url.startswith("https://"):
        print("\n  [x] O endereco precisa comecar com https://")
        print("      Ele sai no fim de `python -m modal deploy modal_voz.py`.")
        return 1

    # ESTE AVISO NASCEU DE UM 404                               (17/09)
    #
    # Os dois apps do Bigode vivem na mesma conta e os enderecos se parecem:
    #
    #     …--bigode-motor-servidor.modal.run       texto
    #     …--bigode-voz-voz-transcrever.modal.run  voz
    #
    # Colando o do motor aqui, a resposta e "HTTP Error 404: Not Found" --
    # que soa como "o deploy falhou" e manda procurar no lugar errado. O
    # endereco estava certo; era do app errado.
    if "voz" not in url and "transcrever" not in url:
        print("\n  [!] Este endereco nao parece ser o da voz.")
        print("      O da voz termina em `-transcrever.modal.run` e sai de")
        print("      `python -m modal deploy modal_voz.py`.")
        print("      O `-servidor.modal.run` e o motor de TEXTO: ele nao")
        print("      conhece esta rota e vai devolver 404.")
        if input("\n      Continuar assim mesmo? (s/N) ").strip().lower() \
                not in ("s", "sim"):
            return 1

    token = getpass.getpass("  Senha (nao aparece ao digitar): ").strip() \
        or str(antes.get("token") or "")
    if not token:
        print("\n  [x] Sem senha o endpoint recusa — e deve recusar mesmo.")
        return 1

    print("\n  Mandando um audio de teste…")
    print("  (o primeiro pedido do dia acorda a placa: ate ~40 s)")

    corpo = json.dumps({"token": token, "idioma": "pt",
                        "wav": base64.b64encode(tom_wav()).decode("ascii")
                        }).encode("utf-8")
    inicio = time.time()
    try:
        pedido = urllib.request.Request(
            url, data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(pedido, timeout=180) as r:
            saida = json.loads(r.read().decode("utf-8"))
    except Exception as erro:
        print("\n  [x] Nao consegui falar com a Modal.")
        print("      %s" % str(erro)[:240])
        print("\n      Confira se o deploy terminou e se o endereco esta certo.")
        return 1

    levou = time.time() - inicio

    if not saida.get("ok"):
        print("\n  [x] A Modal respondeu, mas recusou:")
        print("      %s" % saida.get("erro", "(sem motivo)"))
        print("\n      Nao gravei nada no config.json.")
        return 1

    print("\n  [ok] FUNCIONOU.")
    print("       modelo ...... %s" % saida.get("modelo", "?"))
    print("       transcricao .. %.1fs na placa, %.1fs no total"
          % (saida.get("segundos", 0), levou))
    print("       texto ........ %r" % (saida.get("texto") or ""))
    print("                      (vazio e o esperado: mandei um tom, nao fala)")

    dados["voz_modal"] = {"url": url, "token": token}
    CONFIG.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print("\n  Gravado no config.json. O botao de microfone ja usa a Modal.")
    print("  Recarregue a pagina com Ctrl+F5 e fale.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
