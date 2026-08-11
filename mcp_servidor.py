#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PONTE MCP - expoe o Cerebro para o Claude

Servidor MCP por stdio. O Claude executa este arquivo e ganha tres ferramentas
para conversar com o Cerebro rodando no pendrive.

Configuracao no Claude (arquivo de configuracao de conectores):

  {
    "mcpServers": {
      "cerebro": {
        "command": "python",
        "args": ["D:\\\\Cerebro\\\\mcp_servidor.py"]
      }
    }
  }

Requer o Cerebro ligado (CEREBRO.bat).

Venure - venure.com.br
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = Path(__file__).resolve().parent


def porta():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8")).get("porta", 7000)
    except Exception:
        return 7000


API = "http://localhost:%d" % porta()


def chamar(caminho, corpo, timeout=1800):
    pedido = urllib.request.Request(
        API + caminho,
        data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


FERRAMENTAS = [
    {
        "name": "cerebro_perguntar",
        "description": ("Faz uma pergunta ao Cerebro (IA local do Fred, roda no pendrive). "
                        "Ele tem acesso as pastas de projeto do Fred e pode ler arquivos "
                        "para responder. Use para consultar o que existe nos projetos."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pergunta": {"type": "string", "description": "O que voce quer saber"},
            },
            "required": ["pergunta"],
        },
    },
    {
        "name": "cerebro_codificar",
        "description": ("Passa uma tarefa de programacao para o Cerebro executar localmente. "
                        "Ele le os arquivos do projeto e devolve o codigo pronto em texto. "
                        "Nao altera nada em disco - use para gerar codigo sem gastar tokens."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tarefa": {"type": "string", "description": "O que deve ser codificado"},
                "contexto": {"type": "string", "description": "Projeto, caminho ou codigo de apoio"},
            },
            "required": ["tarefa"],
        },
    },
    {
        "name": "cerebro_memoria",
        "description": ("Consulta a memoria do Cerebro sobre os projetos do Fred: "
                        "estrutura de pastas, tecnologias, arquivos principais."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Nome do projeto ou assunto"},
            },
            "required": ["consulta"],
        },
    },
]


def executar(nome, args):
    if nome == "cerebro_perguntar":
        dados = chamar("/api/tarefa", {"pergunta": args.get("pergunta", "")})
    elif nome == "cerebro_codificar":
        dados = chamar("/api/tarefa", {
            "pergunta": args.get("tarefa", ""),
            "contexto": args.get("contexto", ""),
        })
    elif nome == "cerebro_memoria":
        dados = chamar("/api/tarefa", {
            "pergunta": "Consulte a memoria e descreva: " + args.get("consulta", ""),
        })
    else:
        return "Ferramenta desconhecida: %s" % nome

    texto = dados.get("texto") or "(sem resposta)"
    acoes = dados.get("acoes") or []
    if acoes:
        texto += "\n\n---\nAcoes do Cerebro: " + " | ".join(acoes)
    return texto


def responder(id_pedido, resultado=None, erro=None):
    msg = {"jsonrpc": "2.0", "id": id_pedido}
    if erro:
        msg["error"] = {"code": -32000, "message": erro}
    else:
        msg["result"] = resultado
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        try:
            pedido = json.loads(linha)
        except Exception:
            continue

        metodo = pedido.get("method")
        id_pedido = pedido.get("id")

        if metodo == "initialize":
            responder(id_pedido, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "cerebro", "version": "1.0.0"},
            })

        elif metodo == "tools/list":
            responder(id_pedido, {"tools": FERRAMENTAS})

        elif metodo == "tools/call":
            params = pedido.get("params", {})
            try:
                texto = executar(params.get("name"), params.get("arguments") or {})
                responder(id_pedido, {"content": [{"type": "text", "text": texto}]})
            except urllib.error.URLError:
                responder(id_pedido, {"content": [{"type": "text", "text":
                          "O Cerebro nao esta rodando. Peca ao Fred para abrir o CEREBRO.bat "
                          "no pendrive."}], "isError": True})
            except Exception as erro:
                responder(id_pedido, {"content": [{"type": "text",
                          "text": "Falha: %s" % erro}], "isError": True})

        elif metodo in ("notifications/initialized", "initialized"):
            continue

        elif id_pedido is not None:
            responder(id_pedido, {})


if __name__ == "__main__":
    main()
