#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIGAR A VOZ DE VOLTA DO BIGODE — e ouvir antes de gravar
Venure · venure.com.br · 20/09/2026

    python usar_modal_fala.py

Pergunta o endereço e a senha, manda uma frase de teste, GRAVA O WAV numa
pasta e abre o tocador. Você ouve antes de o botão existir na tela.

O teste não é "respondeu 200". É: voltou áudio, com duração compatível com
o texto mandado? Um WAV de 0,2 segundo para uma frase de 12 palavras é um
endpoint que funcionou e uma voz que não carregou.

A senha é digitada sem eco. Já houve token vazando neste projeto por
aparecer na tela; uma vez basta.
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

FRASE = ("Olá, Fred. Aqui é o Bigode. A partir de agora eu posso responder "
         "falando, em vez de você ter que ler tudo.")


def ler_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def main():
    print()
    print("  A VOZ DE VOLTA DO BIGODE")
    print("  " + "-" * 62)
    print("  O endereço sai no fim de:")
    print("      python -m modal deploy modal_fala.py")

    dados = ler_config()
    antes = dados.get("fala_modal") or {}

    url = input("\n  Endereço (…-falar.modal.run): ").strip() \
        or str(antes.get("url") or "")
    if not url.startswith("https://"):
        print("\n  [x] O endereço precisa começar com https://")
        return 1

    # O MESMO TROPEÇO DO 404 DA VOZ                             (17/09)
    #   Todos os apps do Bigode vivem na mesma conta e os endereços se
    #   parecem. Colar o do motor de texto aqui devolve 404 -- que soa como
    #   "o deploy falhou" e manda procurar no lugar errado.
    if "falar" not in url and "fala" not in url:
        print("\n  [!] Este endereço não parece o da fala.")
        print("      O da fala termina em `-falar.modal.run`.")
        print("      O `-transcrever.modal.run` é o caminho de IDA (Whisper);")
        print("      o `-servidor.modal.run` é o motor de TEXTO. Os dois")
        print("      devolveriam 404 aqui.")
        if input("\n      Continuar assim mesmo? (s/N) ").strip().lower() \
                not in ("s", "sim"):
            return 1

    token = getpass.getpass("  Senha (não aparece ao digitar): ").strip() \
        or str(antes.get("token") or "")
    if not token:
        print("\n  [x] Sem senha o endpoint recusa — e deve recusar mesmo.")
        return 1

    print("\n  Mandando a frase de teste…")
    print("  (o primeiro pedido do dia acorda a máquina: até ~30 s)")

    corpo = json.dumps({"token": token, "texto": FRASE}).encode("utf-8")
    inicio = time.time()
    try:
        pedido = urllib.request.Request(
            url, data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(pedido, timeout=180) as r:
            saida = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as erro:
        print("\n  [x] Não consegui falar com a Modal.")
        print("      %s" % str(erro)[:240])
        return 1

    levou = time.time() - inicio

    if not saida.get("ok"):
        print("\n  [x] A Modal respondeu, mas recusou:")
        print("      %s" % saida.get("erro", "(sem motivo)"))
        print("\n      Não gravei nada no config.json.")
        return 1

    duracao = float(saida.get("duracao") or 0)
    print("\n  [ok] VOLTOU ÁUDIO.")
    print("       voz .......... %s" % saida.get("voz", "?"))
    print("       duração ...... %.1fs de fala" % duracao)
    print("       gerou em ..... %.2fs na máquina (%.1fs no total)"
          % (saida.get("segundos", 0), levou))

    # 118 caracteres de português falado dão uns 8 segundos. Menos de 3 é
    # sinal de voz que não carregou direito -- o endpoint responderia 200 do
    # mesmo jeito, e o defeito só apareceria no dia em que você clicasse.
    if duracao < 3.0:
        print("\n  [!] Áudio curto demais para esta frase (%.1fs)." % duracao)
        print("      Alguma coisa saiu errada na síntese.")
        print("      Não gravei nada no config.json.")
        return 1

    destino = BASE / "teste_da_voz.wav"
    try:
        destino.write_bytes(base64.b64decode(saida["wav"]))
        print("\n       gravei em .... %s" % destino)
    except Exception as erro:
        print("\n  [!] Não consegui gravar o arquivo: %s" % str(erro)[:150])

    if input("\n  Quer ouvir agora? (S/n) ").strip().lower() not in ("n", "nao", "não"):
        try:
            import os
            os.startfile(str(destino))      # Windows
        except Exception:
            print("      (abra o arquivo à mão: %s)" % destino)

    if input("\n  Ficou bom? Gravo no config.json? (S/n) ").strip().lower() \
            in ("n", "nao", "não"):
        print("\n  Não gravei. Para trocar de voz, mude VOZ e CAMINHO_VOZ")
        print("  no topo do modal_fala.py e publique de novo.")
        print("  A lista está em huggingface.co/rhasspy/piper-voices (pt/pt_BR).\n")
        return 0

    dados["fala_modal"] = {"url": url, "token": token, "ligada": True}
    CONFIG.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print("\n  Gravado. Cada resposta do Bigode ganha um botão de alto-falante.")
    print("  Recarregue a página com Ctrl+F5.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
