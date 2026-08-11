#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STORAGE - persistencia local de conversas e projetos

Tudo em disco, dentro da propria unidade do aplicativo. Nada sai daqui.

Venure - venure.com.br
"""

import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
CONVERSAS = APP_ROOT / "conversas"
PROJETOS = APP_ROOT / "projetos"


def _garantir():
    CONVERSAS.mkdir(exist_ok=True)
    PROJETOS.mkdir(exist_ok=True)


def _ler(caminho, padrao=None):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8-sig"))
    except Exception:
        return padrao


def _gravar(caminho, dados):
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                             encoding="utf-8")


# ==========================================================================
# Conversas
# ==========================================================================

def titulo_de(mensagens):
    for m in mensagens:
        if m.get("role") == "user":
            texto = re.sub(r"\s+", " ", m.get("content", "")).strip()
            return (texto[:58] + "…") if len(texto) > 58 else (texto or "Sem título")
    return "Nova conversa"


def salvar_conversa(dados):
    _garantir()
    ident = dados.get("id") or uuid.uuid4().hex[:12]
    mensagens = dados.get("mensagens") or []
    if not mensagens:
        return {"id": ident}

    existente = _caminho_conversa(ident)
    criada = (_ler(existente, {}) or {}).get("criada") if existente else None

    registro = {
        "id": ident,
        "titulo": dados.get("titulo") or titulo_de(mensagens),
        "criada": criada or datetime.now().isoformat(timespec="seconds"),
        "atualizada": datetime.now().isoformat(timespec="seconds"),
        "modelo": dados.get("modelo", ""),
        "projeto": dados.get("projeto", ""),
        "ferramentas": dados.get("ferramentas", []),
        "mensagens": mensagens,
    }
    dia = registro["criada"][:10]
    _gravar(CONVERSAS / dia / (ident + ".json"), registro)
    return {"id": ident, "titulo": registro["titulo"]}


def _caminho_conversa(ident):
    for arquivo in CONVERSAS.rglob(ident + ".json"):
        return arquivo
    return None


def listar_conversas(busca="", limite=80):
    _garantir()
    itens = []
    for arquivo in CONVERSAS.rglob("*.json"):
        dados = _ler(arquivo)
        if not dados:
            continue
        if busca:
            alvo = (dados.get("titulo", "") + " " + " ".join(
                m.get("content", "") for m in dados.get("mensagens", []))).lower()
            if busca.lower() not in alvo:
                continue
        itens.append({
            "id": dados.get("id"),
            "titulo": dados.get("titulo", "Sem título"),
            "atualizada": dados.get("atualizada", ""),
            "modelo": dados.get("modelo", ""),
            "projeto": dados.get("projeto", ""),
            "mensagens": len(dados.get("mensagens", [])),
        })
    itens.sort(key=lambda x: x["atualizada"], reverse=True)
    return itens[:limite]


def abrir_conversa(ident):
    arquivo = _caminho_conversa(ident)
    return _ler(arquivo, {}) if arquivo else {}


def apagar_conversa(ident):
    arquivo = _caminho_conversa(ident)
    if arquivo:
        try:
            arquivo.unlink()
            return True
        except Exception:
            pass
    return False


# ==========================================================================
# Projetos
# ==========================================================================

def listar_projetos():
    _garantir()
    itens = []
    for arquivo in sorted(PROJETOS.glob("*.json")):
        dados = _ler(arquivo)
        if dados:
            itens.append(dados)
    itens.sort(key=lambda p: p.get("nome", "").lower())
    return itens


def salvar_projeto(dados):
    _garantir()
    ident = dados.get("id") or uuid.uuid4().hex[:10]
    registro = {
        "id": ident,
        "nome": (dados.get("nome") or "Projeto sem nome").strip(),
        "diretorio": (dados.get("diretorio") or "").strip(),
        "instrucoes": (dados.get("instrucoes") or "").strip(),
        "modelo": dados.get("modelo", ""),
        "conexoes": dados.get("conexoes", []),
        "criado": dados.get("criado") or datetime.now().isoformat(timespec="seconds"),
    }
    _gravar(PROJETOS / (ident + ".json"), registro)
    return registro


def abrir_projeto(ident):
    return _ler(PROJETOS / (ident + ".json"), {})


def apagar_projeto(ident):
    arquivo = PROJETOS / (ident + ".json")
    if arquivo.exists():
        arquivo.unlink()
        return True
    return False
