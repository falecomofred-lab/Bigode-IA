#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIGAR A VISÃO DO BIGODE — e conferir que ele viu mesmo
Venure · venure.com.br · 20/09/2026

    python usar_modal_olho.py

O TESTE É DIFERENTE DOS OUTROS, E DE PROPÓSITO

    Um modelo de visão quebrado não devolve erro: devolve uma descrição
    plausível. "Uma tela de computador com texto" serve para quase qualquer
    print, e passaria num teste que só olhasse se veio texto.

    Então o teste manda uma imagem construída aqui, com uma PALAVRA
    ESCOLHIDA dentro, e confere se essa palavra aparece na resposta. Se ele
    leu a palavra, ele está vendo. Se descreveu bonito sem citá-la, está
    inventando -- e inventar com confiança é exatamente o que não pode.

    A imagem é desenhada com o Pillow, em memória. Se o Pillow não estiver
    instalado aqui, o teste avisa em vez de fingir que passou.

A senha é digitada sem eco.
"""

import base64
import getpass
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))       # o Python embutido nao poe o proprio dir
CONFIG = BASE / "config.json"

# Uma palavra que não aparece por acaso em descrição de imagem nenhuma.
SEGREDO = "JABUTICABA"


def ler_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def imagem_de_teste():
    """Um retângulo branco com a palavra secreta em preto, grande.

    Devolve (base64, None) ou (None, motivo).
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None, ("o Pillow não está instalado neste Python.\n"
                      "      Rode: python -m pip install pillow")

    figura = Image.new("RGB", (900, 320), (255, 255, 255))
    desenho = ImageDraw.Draw(figura)
    # Sem fonte escolhida: a padrão do Pillow é pequena, então a palavra vai
    # ampliada por um desenho em imagem menor e um resize. Feio, e legível --
    # que é o único requisito aqui.
    pequena = Image.new("RGB", (225, 80), (255, 255, 255))
    ImageDraw.Draw(pequena).text((12, 30), SEGREDO, fill=(0, 0, 0))
    figura.paste(pequena.resize((900, 320), Image.LANCZOS), (0, 0))
    desenho.rectangle([(0, 0), (899, 319)], outline=(0, 0, 0), width=4)

    memoria = io.BytesIO()
    figura.save(memoria, "PNG")
    return base64.b64encode(memoria.getvalue()).decode("ascii"), None


def main():
    print()
    print("  A VISÃO DO BIGODE")
    print("  " + "-" * 62)
    print("  O endereço sai no fim de:")
    print("      python -m modal deploy modal_olho.py")

    dados = ler_config()
    antes = dados.get("olho_modal") or {}

    url = input("\n  Endereço (…-olhar.modal.run): ").strip() \
        or str(antes.get("url") or "")
    if not url.startswith("https://"):
        print("\n  [x] O endereço precisa começar com https://")
        return 1

    if "olhar" not in url and "olho" not in url:
        print("\n  [!] Este endereço não parece o da visão.")
        print("      O da visão termina em `-olhar.modal.run`.")
        if input("\n      Continuar assim mesmo? (s/N) ").strip().lower() \
                not in ("s", "sim"):
            return 1

    token = getpass.getpass("  Senha (não aparece ao digitar): ").strip() \
        or str(antes.get("token") or "")
    if not token:
        print("\n  [x] Sem senha o endpoint recusa — e deve recusar mesmo.")
        return 1

    figura, motivo = imagem_de_teste()
    if figura is None:
        print("\n  [x] Não consegui montar a imagem de teste: %s" % motivo)
        print("\n      Sem imagem de teste eu não gravo nada: seria dizer")
        print("      que funciona sem ter conferido.")
        return 1

    print("\n  Mandando uma imagem com uma palavra escondida dentro…")
    print("  (o primeiro pedido do dia acorda a placa: até ~90 s)")

    corpo = json.dumps({"token": token, "imagem": figura,
                        "pergunta": "Que palavra está escrita nesta imagem? "
                                    "Responda em português."}).encode("utf-8")
    inicio = time.time()
    try:
        pedido = urllib.request.Request(
            url, data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(pedido, timeout=300) as r:
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

    resposta = str(saida.get("texto") or "")
    print("\n       modelo ....... %s" % saida.get("modelo", "?"))
    print("       imagem ....... %s" % saida.get("tamanho", "?"))
    print("       na placa ..... %.1fs   (total %.1fs)"
          % (saida.get("segundos", 0), levou))
    print("       ele disse .... %r" % resposta[:180])

    if SEGREDO.lower() not in resposta.lower():
        print("\n  [x] REPROVADO. A palavra na imagem era %r e ele não a" % SEGREDO)
        print("      citou. Ou não está enxergando, ou está inventando uma")
        print("      descrição plausível — que é pior, porque não parece erro.")
        print("\n      Não gravei nada no config.json.")
        return 1

    print("\n  [ok] ELE LEU A PALAVRA. Está enxergando de verdade.")

    dados["olho_modal"] = {"url": url, "token": token, "ligada": True}
    CONFIG.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print("\n  Gravado. Agora você pode colar um print na conversa (Ctrl+V)")
    print("  ou anexar uma foto, e perguntar sobre ela.")
    print("  Recarregue a página com Ctrl+F5.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
