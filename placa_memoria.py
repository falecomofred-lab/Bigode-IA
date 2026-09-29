# -*- coding: utf-8 -*-
"""O LADO DE CÁ DA MEMÓRIA NA PLACA — só urllib, nenhuma biblioteca nova
Venure · venure.com.br · 20/09/2026

POR QUE ESTE ARQUIVO NÃO IMPORTA NADA

    A lição do `perfis_modal.py`, que já custou uma tarde: o Bigode roda no
    Python portátil do projeto, onde quase nada está instalado. Qualquer
    `import` que falhe aqui dentro vira memória desligada SEM AVISO -- e
    "desligado em silêncio" é indistinguível de "não existe".

    Então: urllib e json, que vêm com o Python. Mais nada.

O QUE ELE FAZ

    embutir(textos)          texto  ->  números          (para indexar)
    embutir_consulta(texto)  pergunta -> números         (para procurar)
    ranquear(consulta, trechos, quantos)  ->  os melhores, na ordem

    Todas as três devolvem None quando a placa não está configurada ou não
    respondeu. None quer dizer "siga sem mim" -- quem chama continua com o
    jeito antigo. A memória é um ACRÉSCIMO: se ela falhar, o Bigode responde
    como respondia antes de ela existir.

O QUE ELE NUNCA FAZ

    Não levanta exceção para cima. Não escreve no prompt do modelo. Não
    trava esperando. O `contexto_relevante` do chroma_memoria.py já aprendeu
    na marra que erro de infraestrutura no meio da conversa mata o pedido e
    a tela culpa o motor errado.

ONDE FICAM O ENDEREÇO E A SENHA

    No config.json, escritos pelo `usar_modal_memoria.py`:

        "memoria_placa": {
          "embutir":  "https://...-embutir.modal.run",
          "ranquear": "https://...-ranquear.modal.run",
          "token":    "<a mesma senha do bigode-token>",
          "ligada":   true
        }
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Uma chamada de indexação carrega 64 blocos e pode demorar; uma pergunta
# tem de voltar depressa ou o Fred sente. Por isso dois tempos diferentes.
ESPERA_EMBUTIR = 120
ESPERA_RANQUEAR = 20

# QUANTOS CANDIDATOS BUSCAR ANTES DE FILTRAR
#
#   O reranker só pode escolher entre o que recebe. Buscar 5 e ranquear 5
#   não melhora nada -- são os mesmos 5, em outra ordem. O ganho vem de
#   buscar largo e cortar fino: 20 entram, 5 saem.
#
#   20 e não 50 porque o custo do reranker cresce com a lista e o retorno
#   cai: o bloco certo quase nunca está em 34º lugar.
CANDIDATOS = 20

_ULTIMO_ERRO = {"texto": ""}


def _config() -> dict:
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _ajustes() -> dict:
    d = _config().get("memoria_placa") or {}
    return d if isinstance(d, dict) else {}


def ligada() -> bool:
    """True só quando há endereço, senha e ninguém desligou na mão."""
    a = _ajustes()
    if not a.get("ligada", True):
        return False
    return bool(str(a.get("embutir") or "").strip()
                and str(a.get("token") or "").strip())


def ranqueador_ligado() -> bool:
    a = _ajustes()
    if not a.get("ligada", True):
        return False
    return bool(str(a.get("ranquear") or "").strip()
                and str(a.get("token") or "").strip())


def ultimo_erro() -> str:
    """O motivo da última falha, para o log e para a tela de situação.

    Existe porque `return None` sozinho não diz se a placa está desligada,
    fora do ar ou com a senha errada -- e sem essa diferença o conserto vira
    adivinhação.
    """
    return _ULTIMO_ERRO["texto"]


def _chamar(url: str, corpo: dict, espera: int):
    if not url:
        return None
    dados = json.dumps(corpo).encode("utf-8")
    pedido = urllib.request.Request(
        url, data=dados, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=espera) as r:
            resposta = json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as erro:
        _ULTIMO_ERRO["texto"] = "HTTP %s em %s" % (erro.code, url[:60])
        return None
    except Exception as erro:
        _ULTIMO_ERRO["texto"] = "%s: %s" % (type(erro).__name__, str(erro)[:200])
        return None

    if not isinstance(resposta, dict) or not resposta.get("ok"):
        # A placa respondeu e disse não. Isso é informação boa -- token
        # errado e modelo que não carregou chegam por aqui, com texto.
        _ULTIMO_ERRO["texto"] = str((resposta or {}).get("erro") or
                                    "resposta sem 'ok'")[:300]
        return None

    _ULTIMO_ERRO["texto"] = ""
    return resposta


def embutir(textos, consulta: bool = False):
    """Lista de textos -> lista de vetores. None se não deu.

    Quebra em lotes de 128 sozinho: o endpoint recusa acima de 256, e um
    lote menor também segura melhor o tempo de resposta.
    """
    if not ligada():
        _ULTIMO_ERRO["texto"] = "memoria_placa nao configurada no config.json"
        return None
    textos = [str(t or "") for t in (textos or [])]
    if not textos:
        return []

    a = _ajustes()
    url = str(a.get("embutir") or "").strip()
    token = str(a.get("token") or "").strip()

    saida = []
    for i in range(0, len(textos), 128):
        lote = textos[i:i + 128]
        r = _chamar(url, {"token": token, "textos": lote,
                          "consulta": bool(consulta)}, ESPERA_EMBUTIR)
        if r is None:
            # Meio lote embutido não serve para nada: devolver parcial faria
            # a coleção nascer com buracos, e buraco em índice não dá erro,
            # dá resultado errado.
            return None
        vetores = r.get("vetores") or []
        if len(vetores) != len(lote):
            _ULTIMO_ERRO["texto"] = ("a placa devolveu %d vetores para %d "
                                     "textos" % (len(vetores), len(lote)))
            return None
        saida.extend(vetores)
    return saida


def embutir_consulta(texto: str):
    """Um texto só, do lado da pergunta. None se não deu."""
    r = embutir([texto], consulta=True)
    return r[0] if r else None


def ranquear(consulta: str, trechos, quantos: int = 5):
    """Devolve [(indice, nota), ...] em ordem de quem mais responde.

    None quando a placa não respondeu -- e aí quem chamou fica com a ordem
    que já tinha, que é o comportamento de antes.
    """
    if not ranqueador_ligado():
        _ULTIMO_ERRO["texto"] = "ranquear nao configurado no config.json"
        return None
    trechos = [str(t or "") for t in (trechos or [])]
    consulta = str(consulta or "").strip()
    if not consulta or not trechos:
        return None

    a = _ajustes()
    r = _chamar(str(a.get("ranquear") or "").strip(),
                {"token": str(a.get("token") or "").strip(),
                 "consulta": consulta,
                 "trechos": trechos[:100],
                 "quantos": int(quantos)},
                ESPERA_RANQUEAR)
    if r is None:
        return None
    melhores = r.get("melhores") or []
    try:
        return [(int(m["i"]), float(m["nota"])) for m in melhores]
    except Exception:
        _ULTIMO_ERRO["texto"] = "resposta do ranquear em formato inesperado"
        return None


def situacao() -> dict:
    """O que a tela mostra, sem chamar a placa."""
    a = _ajustes()
    return {
        "ligada": ligada(),
        "ranqueador": ranqueador_ligado(),
        "tem_embutir": bool(str(a.get("embutir") or "").strip()),
        "tem_ranquear": bool(str(a.get("ranquear") or "").strip()),
        "tem_token": bool(str(a.get("token") or "").strip()),
        "desligada_na_mao": not a.get("ligada", True),
        "ultimo_erro": ultimo_erro(),
    }
