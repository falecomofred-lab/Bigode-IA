# -*- coding: utf-8 -*-
"""Indexa os domínios configurados no ChromaDB persistente local.

Uso:
    python ingestao_chroma.py
    python ingestao_chroma.py --status
"""

from __future__ import annotations

import argparse
import json

import chroma_memoria


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingestão semântica do Bigode IA")
    parser.add_argument("--status", action="store_true", help="mostra o status sem indexar")
    args = parser.parse_args()
    resultado = chroma_memoria.status() if args.status else chroma_memoria.indexar_dominios()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if not resultado.get("erro") else 1


if __name__ == "__main__":
    raise SystemExit(main())
