#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTENTICACAO - quem pode usar o Cerebro

Contas ficam em usuarios.json, no proprio pendrive. Senha nunca e guardada:
so o hash PBKDF2 com sal unico por usuario.

Entrar por Google e GitHub e opcional e exige cadastrar um aplicativo (ver
LEIAME). Sem isso, funciona o login por e-mail e senha, que nao depende de
internet nenhuma.

Venure - venure.com.br
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARQUIVO = BASE / "usuarios.json"

SESSOES = {}                 # token -> {"email", "nome", "expira"}
ESTADOS_OAUTH = {}           # state -> criado_em
TRAVA = threading.Lock()

DIAS_SESSAO = 30
ITERACOES = 120_000


# ==========================================================================
# Armazenamento
# ==========================================================================

def _ler():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"usuarios": []}


def _gravar(dados):
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                       encoding="utf-8")


def existe_alguem():
    return bool(_ler().get("usuarios"))


def buscar(email):
    alvo = (email or "").strip().lower()
    for u in _ler().get("usuarios", []):
        if u.get("email", "").lower() == alvo:
            return u
    return None


# ==========================================================================
# Senha
# ==========================================================================

def _hash(senha, sal):
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"),
                               bytes.fromhex(sal), ITERACOES).hex()


def criar_conta(nome, email, senha, provedor="local", foto=""):
    email = (email or "").strip().lower()
    nome = (nome or "").strip() or email.split("@")[0]

    if not email or "@" not in email:
        return {"ok": False, "erro": "Informe um e-mail válido."}
    if provedor == "local" and len(senha or "") < 6:
        return {"ok": False, "erro": "A senha precisa de pelo menos 6 caracteres."}
    if buscar(email):
        return {"ok": False, "erro": "Já existe uma conta com esse e-mail."}

    dados = _ler()
    sal = secrets.token_hex(16)
    dados.setdefault("usuarios", []).append({
        "email": email,
        "nome": nome,
        "foto": foto,
        "provedor": provedor,
        "sal": sal,
        "senha": _hash(senha, sal) if provedor == "local" else "",
        "dono": not dados.get("usuarios"),          # o primeiro e o dono
        "criado": datetime.now().isoformat(timespec="seconds"),
    })
    _gravar(dados)
    return {"ok": True, "email": email, "nome": nome}


def conferir(email, senha):
    u = buscar(email)
    if not u:
        return {"ok": False, "erro": "E-mail ou senha incorretos."}
    if u.get("provedor") != "local":
        return {"ok": False,
                "erro": "Essa conta entra pelo %s." % u.get("provedor", "").title()}
    if not hmac.compare_digest(u.get("senha", ""), _hash(senha or "", u["sal"])):
        return {"ok": False, "erro": "E-mail ou senha incorretos."}
    return {"ok": True, "email": u["email"], "nome": u["nome"], "foto": u.get("foto", "")}


def trocar_senha(email, atual, nova):
    u = buscar(email)
    if not u:
        return {"ok": False, "erro": "Conta não encontrada."}
    if u.get("provedor") == "local":
        if not hmac.compare_digest(u.get("senha", ""), _hash(atual or "", u["sal"])):
            return {"ok": False, "erro": "Senha atual incorreta."}
    if len(nova or "") < 6:
        return {"ok": False, "erro": "A nova senha precisa de 6 caracteres."}

    dados = _ler()
    for item in dados["usuarios"]:
        if item["email"] == u["email"]:
            item["sal"] = secrets.token_hex(16)
            item["senha"] = _hash(nova, item["sal"])
            item["provedor"] = "local"
    _gravar(dados)
    return {"ok": True}


# ==========================================================================
# Sessao
# ==========================================================================

def abrir_sessao(email, nome, foto=""):
    token = secrets.token_urlsafe(32)
    with TRAVA:
        SESSOES[token] = {"email": email, "nome": nome, "foto": foto,
                          "expira": time.time() + DIAS_SESSAO * 86400}
    return token


def sessao_de(cookie):
    if not cookie:
        return None
    for parte in cookie.split(";"):
        if "=" not in parte:
            continue
        chave, valor = parte.strip().split("=", 1)
        if chave != "sessao":
            continue
        with TRAVA:
            s = SESSOES.get(valor)
            if not s:
                return None
            if s["expira"] < time.time():
                SESSOES.pop(valor, None)
                return None
            return s
    return None


def fechar_sessao(cookie):
    if not cookie:
        return
    for parte in cookie.split(";"):
        if "sessao=" in parte:
            with TRAVA:
                SESSOES.pop(parte.strip().split("=", 1)[1], None)


# ==========================================================================
# Entrar com Google / GitHub
# ==========================================================================

PROVEDORES = {
    "google": {
        "nome": "Google",
        "autorizar": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "perfil": "https://www.googleapis.com/oauth2/v2/userinfo",
        "escopo": "openid email profile",
    },
    "github": {
        "nome": "GitHub",
        "autorizar": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "perfil": "https://api.github.com/user",
        "escopo": "read:user user:email",
    },
}


def _credenciais(config, provedor):
    dados = (config.get("login_social") or {}).get(provedor) or {}
    return dados.get("client_id", "").strip(), dados.get("client_secret", "").strip()


def disponiveis(config):
    """Quais botoes sociais mostrar na tela de login."""
    saida = {}
    for chave, p in PROVEDORES.items():
        cid, seg = _credenciais(config, chave)
        saida[chave] = {"nome": p["nome"], "pronto": bool(cid and seg)}
    saida["apple"] = {"nome": "Apple", "pronto": False,
                      "motivo": "Entrar com Apple exige domínio HTTPS público e "
                                "conta paga de desenvolvedor. Não funciona em "
                                "aplicativo local."}
    return saida


def url_autorizacao(config, provedor, base_url):
    p = PROVEDORES.get(provedor)
    cid, _ = _credenciais(config, provedor)
    if not p or not cid:
        return None

    estado = secrets.token_urlsafe(24)
    with TRAVA:
        ESTADOS_OAUTH[estado] = time.time()
        for k, v in list(ESTADOS_OAUTH.items()):
            if time.time() - v > 600:
                ESTADOS_OAUTH.pop(k, None)

    parametros = {
        "client_id": cid,
        "redirect_uri": base_url + "/auth/" + provedor + "/retorno",
        "response_type": "code",
        "scope": p["escopo"],
        "state": estado,
    }
    if provedor == "google":
        parametros["access_type"] = "online"
        parametros["prompt"] = "select_account"
    return p["autorizar"] + "?" + urllib.parse.urlencode(parametros)


def _post_json(url, dados, cabecalhos=None):
    corpo = urllib.parse.urlencode(dados).encode("utf-8")
    cab = {"Accept": "application/json",
           "Content-Type": "application/x-www-form-urlencoded",
           "User-Agent": "Cerebro-Venure"}
    cab.update(cabecalhos or {})
    pedido = urllib.request.Request(url, data=corpo, headers=cab)
    with urllib.request.urlopen(pedido, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _get_json(url, token):
    pedido = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "User-Agent": "Cerebro-Venure"})
    with urllib.request.urlopen(pedido, timeout=25) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def concluir_login(config, provedor, codigo, estado, base_url):
    with TRAVA:
        if estado not in ESTADOS_OAUTH:
            return {"ok": False, "erro": "Pedido expirado. Tente de novo."}
        ESTADOS_OAUTH.pop(estado, None)

    p = PROVEDORES.get(provedor)
    cid, seg = _credenciais(config, provedor)
    if not p or not cid:
        return {"ok": False, "erro": "Provedor não configurado."}

    try:
        resposta = _post_json(p["token"], {
            "client_id": cid, "client_secret": seg, "code": codigo,
            "redirect_uri": base_url + "/auth/" + provedor + "/retorno",
            "grant_type": "authorization_code",
        })
        acesso = resposta.get("access_token")
        if not acesso:
            return {"ok": False, "erro": "Não recebi autorização do %s." % p["nome"]}

        perfil = _get_json(p["perfil"], acesso)
        if provedor == "google":
            email = perfil.get("email", "")
            nome = perfil.get("name", "")
            foto = perfil.get("picture", "")
        else:
            email = perfil.get("email") or ""
            nome = perfil.get("name") or perfil.get("login", "")
            foto = perfil.get("avatar_url", "")
            if not email:
                try:
                    emails = _get_json("https://api.github.com/user/emails", acesso)
                    principal = [e for e in emails if e.get("primary")]
                    email = (principal or emails or [{}])[0].get("email", "")
                except Exception:
                    pass

        if not email:
            return {"ok": False, "erro": "Não consegui obter seu e-mail."}

        u = buscar(email)
        if not u:
            criar_conta(nome, email, "", provedor=provedor, foto=foto)
            u = buscar(email)
        return {"ok": True, "email": u["email"], "nome": u["nome"],
                "foto": u.get("foto", foto)}

    except urllib.error.HTTPError as erro:
        return {"ok": False, "erro": "%s respondeu %s." % (p["nome"], erro.code)}
    except Exception as erro:
        return {"ok": False, "erro": "Falha ao entrar: %s" % erro}


def listar_usuarios():
    return [{"email": u["email"], "nome": u["nome"], "provedor": u.get("provedor"),
             "dono": u.get("dono", False), "criado": u.get("criado", "")}
            for u in _ler().get("usuarios", [])]


def remover(email):
    dados = _ler()
    antes = len(dados.get("usuarios", []))
    dados["usuarios"] = [u for u in dados.get("usuarios", [])
                         if u["email"] != (email or "").lower() or u.get("dono")]
    _gravar(dados)
    return {"ok": len(dados["usuarios"]) < antes}
