#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# A docstring e "raw" (r""") por causa dos caminhos com barra invertida:
# sem isso, o Python le "\C" de "D:\Cerebro" como sequencia de escape e
# avisa a cada execucao. Aviso repetido que nao significa nada ensina a
# ignorar aviso -- e um dia o que importa passa batido.
r"""
PONTE MCP - expoe o Bigode para o Claude

Servidor MCP por stdio. O Claude executa este arquivo e ganha tres ferramentas
para conversar com o Bigode rodando no pendrive.

Configuracao no Claude (arquivo de configuracao de conectores):

  {
    "mcpServers": {
      "Bigode": {
        "command": "C:\\\\Users\\\\Frederico\\\\Downloads\\\\Cerebro\\\\python\\\\python.exe",
        "args": ["C:\\\\Users\\\\Frederico\\\\Downloads\\\\Cerebro\\\\mcp_servidor.py"]
      }
    }
  }

Com o Bigode no Colab, acrescente o endereco do tunel -- e so isso muda:

  {
    "mcpServers": {
      "Bigode": {
        "command": "C:\\\\Users\\\\Frederico\\\\Downloads\\\\Cerebro\\\\python\\\\python.exe",
        "args": ["C:\\\\Users\\\\Frederico\\\\Downloads\\\\Cerebro\\\\mcp_servidor.py"],
        "env": { "BIGODE_URL": "https://SEU-TUNEL.trycloudflare.com" }
      }
    }
  }

O tunel muda a cada sessao do Colab, entao esse campo precisa ser atualizado
junto com o link. Sem ele, a ponte procura o Bigode em localhost.

O caminho do python vem inteiro de proposito. Dizer so "python" depende de o
Windows ter Python instalado e no PATH -- e o do Fred e o PORTATIL que mora
dentro do pendrive. Com "python" seco, a ponte falha em silencio na maquina
que nao tiver um Python de sistema, que e justamente o caso.

ATENCAO AO CAMINHO DO PYTHON (conferido em 09/09)
    A copia em C:\Users\Frederico\Downloads\Cerebro NAO tem a pasta `python`
    dentro -- o Python portatil so existe no pendrive. Entao, na pratica:

        command: "D:\\\\Cerebro\\\\python\\\\python.exe"     (o do pendrive)
        args:    ["C:\\\\Users\\\\Frederico\\\\Downloads\\\\Cerebro\\\\mcp_servidor.py"]

    O interpretador de um lugar, o script do outro. Funciona: o script usa
    caminho relativo a si mesmo (BASE = Path(__file__).parent), entao ele le
    o config.json da pasta onde ele esta, nao da do python.

No Windows, o arquivo fica em:
  %APPDATA%\Claude\claude_desktop_config.json

Depois de salvar, feche o Claude Desktop PELA BANDEJA (ao lado do relogio,
botao direito, Sair). Fechar so a janela nao recarrega os conectores.

Requer o Bigode ligado (BIGODE.bat).

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


def _config_local():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def porta():
    return _config_local().get("porta", 7000)


def chave():
    return str(_config_local().get("chave_extensao", "")).strip()


def endereco():
    """Onde o Bigode esta agora.

    ATE 09/09 ISTO ERA `http://localhost:PORTA`, FIXO
        Constante de modulo, avaliada uma vez no import. Funcionava enquanto
        o Bigode so morava no pendrive. Depois que ele passou a rodar no
        Colab, a ponte continuou batendo em localhost, tomava URLError e
        respondia "O Bigode nao esta rodando. Peca ao Fred para abrir o
        BIGODE.bat" -- conselho errado, porque o Bigode estava no ar, so que
        do outro lado do tunel.

    A ORDEM DE PROCURA
        1. BIGODE_URL no ambiente     -- para apontar sem editar arquivo
        2. "url_remota" no config     -- o endereco do tunel do dia
        3. localhost:PORTA            -- o de sempre

        O ambiente vem antes do arquivo porque o config.json e sincronizado
        entre as tres copias: um endereco de tunel escrito la viajaria para
        o pendrive e para o Drive, e amanha estaria morto nos tres.
    """
    do_ambiente = os.environ.get("BIGODE_URL", "").strip()
    if do_ambiente:
        return do_ambiente.rstrip("/")
    do_arquivo = str(_config_local().get("url_remota", "")).strip()
    if do_arquivo:
        return do_arquivo.rstrip("/")
    return "http://localhost:%d" % porta()


def chamar(caminho, corpo, timeout=1800):
    cabecalhos = {"Content-Type": "application/json"}
    if chave():
        cabecalhos["X-Cerebro-Chave"] = chave()
    # Lido a cada chamada, nao no import: assim trocar o endereco (ou subir
    # o tunel do dia) passa a valer sem reiniciar o Claude.
    pedido = urllib.request.Request(
        endereco() + caminho,
        data=json.dumps(corpo).encode("utf-8"),
        headers=cabecalhos,
    )
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def _direto(nome, args, timeout=120):
    """Executa uma ferramenta do Bigode sem passar pelo modelo local."""
    dados = chamar("/api/ferramenta", {"nome": nome, "args": args}, timeout)
    if dados.get("ok"):
        return dados.get("resultado", "")
    return "ERRO: " + str(dados.get("erro", "falha desconhecida"))


FERRAMENTAS = [
    # ── acesso direto aos arquivos do Fred ────────────────────────────────
    # Estas quatro NAO passam pelo modelo local: o Claude escolhe, o Bigode
    # executa. Rapido e exato. As regras do Bigode continuam valendo -
    # so as pastas liberadas, e nada de escrita.
    {
        "name": "cerebro_listar",
        "description": ("Lista o conteudo de uma pasta do Fred (Drive ou pendrive). "
                        "Use antes de ler arquivo, para saber o que existe."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "caminho": {"type": "string",
                            "description": r"Ex: G:\Meu Drive\projetos\carteira2026"},
            },
            "required": ["caminho"],
        },
    },
    {
        "name": "cerebro_ler",
        "description": "Le um arquivo do Fred e devolve o conteudo em texto.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "caminho": {"type": "string", "description": "Caminho completo do arquivo"},
            },
            "required": ["caminho"],
        },
    },
    {
        "name": "cerebro_raio_x",
        "description": ("Inventario completo e real de um projeto: todos os arquivos "
                        "com tamanho e numero de linhas. Use SEMPRE antes de auditar "
                        "ou analisar um projeto - garante que nenhum arquivo e inventado."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "caminho": {"type": "string", "description": "Pasta do projeto"},
            },
            "required": ["caminho"],
        },
    },
    {
        "name": "cerebro_procurar",
        "description": "Procura um termo dentro dos arquivos das pastas liberadas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string", "description": "O que procurar"},
                "pasta": {"type": "string", "description": "Onde procurar (opcional)"},
            },
            "required": ["termo"],
        },
    },

    # ── quando vale usar o modelo local ───────────────────────────────────
    {
        "name": "cerebro_perguntar",
        "description": ("Faz uma pergunta ao Bigode (IA local do Fred, roda no pendrive). "
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
        "description": ("Passa uma tarefa de programacao para o Bigode executar localmente. "
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
        "description": ("Consulta a memoria do Bigode sobre os projetos do Fred: "
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


DIRETAS = {
    "cerebro_listar":   ("listar_pasta", lambda a: {"caminho": a.get("caminho", "")}),
    "cerebro_ler":      ("ler_arquivo",  lambda a: {"caminho": a.get("caminho", "")}),
    "cerebro_raio_x":   ("raio_x",       lambda a: {"caminho": a.get("caminho", "")}),
    "cerebro_procurar": ("buscar",       lambda a: {"termo": a.get("termo", ""),
                                                    "pasta": a.get("pasta", "")}),
}


def executar(nome, args):
    if nome in DIRETAS:
        ferramenta, montar = DIRETAS[nome]
        return _direto(ferramenta, montar(args))

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
        texto += "\n\n---\nAcoes do Bigode: " + " | ".join(acoes)
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
                "serverInfo": {"name": "Bigode", "version": "1.0.0"},
            })

        elif metodo == "tools/list":
            responder(id_pedido, {"tools": FERRAMENTAS})

        elif metodo == "tools/call":
            params = pedido.get("params", {})
            try:
                texto = executar(params.get("name"), params.get("arguments") or {})
                responder(id_pedido, {"content": [{"type": "text", "text": texto}]})
            except urllib.error.URLError:
                # Dizer PARA ONDE se tentou ir. A mensagem antiga mandava
                # abrir o BIGODE.bat sempre -- conselho errado quando o
                # endereco e um tunel do Colab que ja expirou.
                onde = endereco()
                if "localhost" in onde or "127.0.0.1" in onde:
                    conserto = ("Abra o BIGODE.bat. Se ele esta no Colab, "
                                "aponte a ponte para o tunel: coloque o link "
                                "em BIGODE_URL no ambiente, ou em "
                                "\"url_remota\" no config.json.")
                else:
                    conserto = ("Esse endereco de tunel provavelmente expirou "
                                "-- o Colab gera um novo a cada sessao. Rode a "
                                "celula do link e atualize BIGODE_URL.")
                responder(id_pedido, {"content": [{"type": "text", "text":
                          "Nao alcancei o Bigode em %s. %s" % (onde, conserto)}],
                          "isError": True})
            except Exception as erro:
                responder(id_pedido, {"content": [{"type": "text",
                          "text": "Falha: %s" % erro}], "isError": True})

        elif metodo in ("notifications/initialized", "initialized"):
            continue

        elif id_pedido is not None:
            responder(id_pedido, {})


if __name__ == "__main__":
    main()
