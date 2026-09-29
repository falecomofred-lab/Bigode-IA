#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIGAR O TRELLIS NO MODAL -- e conferir que ele gera um modelo de verdade
Venure · venure.com.br · 28/09/2026

    python usar_modal_trellis.py            testa e grava o endereco no config.json
    python usar_modal_trellis.py desligar   volta a usar so Hugging Face / PC

O endereco e montado a partir do da visao do Bigode (mesma conta Modal):
    https://<conta>--bigode-olho-olho-olhar.modal.run
 -> https://<conta>--bigode-trellis-trellis-gerar.modal.run
"""

import base64
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"


def ler_config():
    return json.loads(CONFIG.read_text(encoding="utf-8-sig"))


def gravar_config(cfg):
    # grava com copia de seguranca: o config.json tem os tokens do Fred
    copia = CONFIG.with_suffix(".json.bak")
    copia.write_text(CONFIG.read_text(encoding="utf-8-sig"), encoding="utf-8")
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def imagem_de_teste():
    """Uma foto real se houver; senao desenha uma caneca simples."""
    for p in (BASE / "producao_blender" / "entrada").glob("*"):
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            return p.read_bytes(), p.name
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (512, 512), "white")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((150, 140, 330, 400), 30, fill=(200, 40, 40))
    d.ellipse((310, 200, 400, 320), outline=(200, 40, 40), width=22)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), "caneca desenhada"


def main():
    cfg = ler_config()
    if len(sys.argv) > 1 and sys.argv[1] == "desligar":
        cfg.setdefault("trellis_modal", {})["ligada"] = False
        gravar_config(cfg)
        print("TRELLIS no Modal desligado.")
        return
    olho = str((cfg.get("olho_modal") or {}).get("url") or "")
    token = str((cfg.get("olho_modal") or {}).get("token") or "")
    if "--bigode-olho-olho-olhar" not in olho or not token:
        print("Nao achei o endereco/token da visao (olho_modal) no config.json.")
        return
    url = olho.replace("--bigode-olho-olho-olhar", "--bigode-trellis-trellis-gerar")
    dados, nome = imagem_de_teste()
    print("Testando", url, "com", nome, "(o primeiro pedido liga a placa: 2 a 5 min)...")
    inicio = time.time()
    corpo = {"token": token, "imagens": [base64.b64encode(dados).decode("ascii")], "seed": 1}
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1200) as r:
        resp = json.loads(r.read().decode("utf-8"))
    if not resp.get("ok"):
        print("FALHOU:", resp.get("erro"))
        print(resp.get("detalhe", ""))
        return
    saida = BASE / "producao_blender" / "gerados" / "teste_trellis_modal.glb"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_bytes(base64.b64decode(resp["glb"]))
    print("OK: modelo com %d KB em %.0f s (GPU: %s s). Arquivo: %s"
          % (saida.stat().st_size // 1024, time.time() - inicio, resp.get("segundos"), saida))
    cfg["trellis_modal"] = {"url": url, "ligada": True}
    gravar_config(cfg)
    print("Endereco gravado no config.json (trellis_modal). O Bigode ja usa na proxima geracao.")


if __name__ == "__main__":
    main()
