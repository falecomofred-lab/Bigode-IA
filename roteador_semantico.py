# -*- coding: utf-8 -*-
"""Roteamento leve de consultas para coleções configuráveis do ChromaDB."""

from __future__ import annotations

import re

import chroma_memoria


PADROES = {
    "codigo": {
        "palavras": {"python", "javascript", "typescript", "fastapi", "código", "codigo", "programação", "programacao", "api", "bug", "teste", "build", "software"},
        "modelo": "modelo-codigo",
    },
    "seguros": {
        "palavras": {"seguro", "seguros", "susep", "apólice", "apolice", "sinistro", "cobertura", "franquia", "risco", "seguradora"},
        "modelo": "modelo-seguros",
    },
    "cannabis": {
        "palavras": {"cannabis", "canabidiol", "anvisa", "plantio", "cultivo", "thc", "medicinal", "terpeno", "cbd"},
        "modelo": "modelo-cannabis",
    },
}


def _tokens(texto: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9À-ÿ_\-]{3,}", (texto or "").lower()))


def classificar_consulta(pergunta: str) -> dict:
    tokens = _tokens(pergunta)
    configurados = chroma_memoria.dominios_configurados()
    pontuacao = []
    for nome, item in configurados.items():
        if not item.get("ativo", True):
            continue
        regras = PADROES.get(nome, {})
        palavras = set(regras.get("palavras", set())) | set(item.get("palavras", []))
        pontos = len(tokens & palavras)
        if pontos:
            pontuacao.append((pontos, nome, regras.get("modelo")))
    if not pontuacao:
        return {"colecao": "todas", "colecoes": chroma_memoria.colecoes_ativas(), "modelo": None, "confianca": 0.0, "motivos": []}
    pontuacao.sort(reverse=True)
    pontos, nome, modelo = pontuacao[0]
    total = sum(item[0] for item in pontuacao) or 1
    regras = PADROES.get(nome, {})
    motivos = sorted(tokens & (set(regras.get("palavras", set())) | set(configurados[nome].get("palavras", []))))
    return {"colecao": nome, "colecoes": [nome], "modelo": modelo, "confianca": round(pontos / total, 2), "motivos": motivos}
