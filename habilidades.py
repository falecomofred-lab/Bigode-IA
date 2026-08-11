#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HABILIDADES (Skills) - conhecimento sob demanda

Cada habilidade e uma pasta com um HABILIDADE.md dentro:

  habilidades/
    contrato-locacao/
      HABILIDADE.md      <- instrucoes completas
      modelo.docx        <- arquivos de apoio (opcional)
    api-rest-node/
      HABILIDADE.md

O HABILIDADE.md comeca com um cabecalho simples:

  ---
  nome: Contrato de locacao
  quando: contrato, locacao, aluguel, imobiliaria
  ---

  (instrucoes detalhadas aqui)

Only o cabecalho entra no prompt do sistema (barato). O corpo inteiro so e
carregado quando a habilidade e acionada - igual ao Claude.

Venure - venure.com.br
"""

import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
PASTA = BASE / "habilidades"


def _cabecalho(texto):
    meta, corpo = {}, texto
    if texto.lstrip().startswith("---"):
        partes = texto.split("---", 2)
        if len(partes) >= 3:
            for linha in partes[1].strip().splitlines():
                if ":" in linha:
                    chave, valor = linha.split(":", 1)
                    meta[chave.strip().lower()] = valor.strip()
            corpo = partes[2].strip()
    return meta, corpo


def listar():
    """Todas as habilidades instaladas, so com o resumo."""
    if not PASTA.exists():
        return []
    saida = []
    for pasta in sorted(PASTA.iterdir()):
        if not pasta.is_dir():
            continue
        arquivo = pasta / "HABILIDADE.md"
        if not arquivo.exists():
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            continue
        meta, corpo = _cabecalho(texto)
        saida.append({
            "id": pasta.name,
            "nome": meta.get("nome", pasta.name.replace("-", " ").title()),
            "quando": meta.get("quando", ""),
            "descricao": meta.get("descricao", ""),
            "ativa": meta.get("ativa", "sim").lower() not in ("nao", "não", "false", "0"),
            "linhas": len(corpo.splitlines()),
            "arquivos": [a.name for a in pasta.iterdir()
                         if a.is_file() and a.name != "HABILIDADE.md"],
        })
    return saida


def abrir(ident):
    """Conteudo completo de uma habilidade, para injetar no contexto."""
    arquivo = PASTA / ident / "HABILIDADE.md"
    if not arquivo.exists():
        disponiveis = ", ".join(h["id"] for h in listar()) or "nenhuma"
        return "Habilidade '%s' nao existe. Disponiveis: %s" % (ident, disponiveis)
    try:
        meta, corpo = _cabecalho(arquivo.read_text(encoding="utf-8-sig", errors="ignore"))
    except Exception as erro:
        return "Erro ao ler a habilidade: %s" % erro

    extras = [a.name for a in (PASTA / ident).iterdir()
              if a.is_file() and a.name != "HABILIDADE.md"]
    cabeca = "# HABILIDADE: %s\n\n" % meta.get("nome", ident)
    if extras:
        cabeca += ("Arquivos de apoio nesta habilidade (use ler_arquivo com o caminho "
                   "completo se precisar):\n%s\n\n"
                   % "\n".join("- %s" % (PASTA / ident / e) for e in extras))
    return cabeca + corpo[:14000]


def resumo_para_prompt():
    """Lista curta que entra no prompt do sistema."""
    ativas = [h for h in listar() if h["ativa"]]
    if not ativas:
        return ""
    linhas = ["# HABILIDADES DISPONIVEIS", "",
              "Voce tem manuais especializados. Quando o pedido do Fred cair em um",
              "destes assuntos, chame usar_habilidade ANTES de responder:", ""]
    for h in ativas:
        gatilhos = (" (assuntos: %s)" % h["quando"]) if h["quando"] else ""
        linhas.append('- %s: "%s"%s' % (h["id"], h["nome"], gatilhos))
    linhas.append("")
    linhas.append("Nao invente habilidade que nao esteja nesta lista.")
    return "\n".join(linhas)


def criar(nome, quando="", conteudo=""):
    """Cria uma habilidade nova pela interface."""
    ident = re.sub(r"[^a-z0-9]+", "-", (nome or "").lower()).strip("-")[:50]
    if not ident:
        return {"ok": False, "msg": "nome invalido"}
    destino = PASTA / ident
    if destino.exists():
        return {"ok": False, "msg": "ja existe uma habilidade com esse nome"}
    destino.mkdir(parents=True, exist_ok=True)
    texto = ("---\nnome: %s\nquando: %s\nativa: sim\n---\n\n%s\n"
             % (nome, quando, conteudo or "Escreva aqui as instrucoes detalhadas."))
    (destino / "HABILIDADE.md").write_text(texto, encoding="utf-8")
    return {"ok": True, "id": ident}


def salvar(ident, texto):
    arquivo = PASTA / ident / "HABILIDADE.md"
    if not arquivo.parent.exists():
        return {"ok": False, "msg": "habilidade nao existe"}
    arquivo.write_text(texto, encoding="utf-8")
    return {"ok": True}


def texto_bruto(ident):
    arquivo = PASTA / ident / "HABILIDADE.md"
    try:
        return arquivo.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return ""


def apagar(ident):
    import shutil
    destino = PASTA / ident
    if destino.exists():
        shutil.rmtree(destino)
        return {"ok": True}
    return {"ok": False}
