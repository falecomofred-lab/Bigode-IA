#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INDEXAR VAULT - Cria índice de palavras-chave para busca no Obsidian.
"""

import json
import re
from pathlib import Path


BASE = Path(__file__).resolve().parent
with open(BASE / "config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

VAULT = Path(config.get("vault_path", ""))
if not VAULT.exists():
    raise SystemExit(f"Vault não encontrado: {VAULT}")

INDICE = VAULT.parent / "vault_index.json"

STOPWORDS = set("""
de da do das dos a o as os e ou que para por com sem no na nos nas um uma em
ao aos eu voce meu minha seu sua como qual quais quando onde porque isso isto
esse essa este esta ser estar tem ter faz fazer preciso quero pode posso mais
menos muito todo toda todos todas nao sim entao aqui sobre ate tambem ja bem
mesmo cada outro nosso the and for you with this that
""".split())


def extrair_palavras(texto):
    return set(re.findall(r"[a-zA-Z0-9À-ÿ_\-]{3,}", texto.lower())) - STOPWORDS


def indexar():
    indice = {}
    for md in VAULT.rglob("*.md"):
        try:
            conteudo = md.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        palavras = extrair_palavras(conteudo)
        for p in palavras:
            indice.setdefault(p, []).append({
                "arquivo": str(md.relative_to(VAULT)),
                "caminho": str(md),
                "trecho": conteudo[:2000],
            })
    with open(INDICE, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)
    print(f"Índice criado: {INDICE} ({len(indice)} palavras)")


if __name__ == "__main__":
    indexar()
