"""O BIGODE PEDINDO IMAGEM A PIPI
Venure · venure.com.br · 17/09/2026

Você diz "crie uma imagem de um café ao amanhecer" na tela do Bigode. Ele
reconhece que é pedido de desenho, chama a Pipi, espera ela desenhar, e
mostra a imagem ali mesmo.

POR QUE PASSAR PELA PIPI, E NAO IR DIRETO NA MODAL
    Seria tentador: o Bigode tem o endereco e o token na mao, e um POST
    resolveria. Mas ai existiriam DOIS lugares que sabem desenhar -- e
    cada melhoria feita num nao chegaria no outro.

    Concretamente, indo direto na Modal o Bigode perderia: a escolha de
    motor que a Pipi faz, o corte de formato, a gravacao em producao\\, o
    mosaico, o historico com semente, e o custo por imagem. Tudo isso ja
    existe do outro lado.

    E e exatamente o erro que custou o dia de ontem no motor de texto:
    havia tres caminhos fazendo a mesma coisa, e os consertos de um nunca
    chegavam nos outros.

    Entao: a Pipi desenha. O Bigode pede.

COMO ELE PROVA QUE E ELE
    Le o segredo do `ponte.txt`, que a Pipi cria na pasta dela, e manda no
    cabecalho X-Venure-Ponte. A Pipi confere isso E confere que a conexao
    veio de 127.0.0.1.

    A segunda prova nao e redundancia: uma aba qualquer do seu navegador
    consegue mandar POST para 127.0.0.1, mas nao consegue ler arquivo do
    seu disco. O segredo e o que separa o Bigode de um site qualquer.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CABECALHO = "X-Venure-Ponte"


def _pasta_da_pipi():
    """Onde mora a Pipi. Mesma busca que o venure.css ja usa."""
    for base in (os.environ.get("PIPI_PASTA", "").strip(),
                 str(RAIZ.parent / "Pipi IA"),
                 str(Path.home() / "Downloads" / "Pipi IA")):
        if base and (Path(base) / "pipi_server.py").is_file():
            return Path(base)
    return None


def _segredo():
    pasta = _pasta_da_pipi()
    if not pasta:
        return ""
    try:
        return (pasta / "ponte.txt").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _endereco():
    porta = os.environ.get("PIPI_PORT", "7300")
    return "http://127.0.0.1:%s/api/ponte/imagem" % porta


def disponivel():
    """Da para pedir imagem a Pipi agora?

    Nao faz chamada de rede: so confere que a pasta e o segredo existem.
    Se a Pipi estiver fechada, quem descobre e a chamada -- e a mensagem
    de erro diz para abrir.
    """
    return bool(_pasta_da_pipi() and _segredo())


def desenhar(descricao, formato="", semente=0, timeout=660):
    """Pede a imagem e devolve o texto que vai para a tela do Bigode."""
    descricao = (descricao or "").strip()
    if not descricao:
        return "Diga o que voce quer ver na imagem."

    pasta = _pasta_da_pipi()
    if not pasta:
        return ("Nao achei a pasta da Pipi IA. Ela deveria estar ao lado do "
                "Cerebro. Se voce a moveu, defina PIPI_PASTA com o caminho.")

    segredo = _segredo()
    if not segredo:
        return ("A Pipi existe, mas o ponte.txt ainda nao foi criado. Abra a "
                "Pipi uma vez (pipi.bat) -- ela cria o arquivo sozinha na "
                "primeira vez -- e peca de novo.")

    corpo = json.dumps({
        "descricao": descricao,
        "formato": (formato or "quadrado"),
        "semente": int(semente or 0),
    }, ensure_ascii=False).encode("utf-8")

    pedido = urllib.request.Request(
        _endereco(), data=corpo, method="POST",
        headers={"Content-Type": "application/json", CABECALHO: segredo})

    try:
        # O timeout e longo de proposito: a primeira imagem do dia acorda a
        # placa na Modal, e isso leva ate um minuto. Cortar cedo faria o
        # Bigode desistir de um pedido que ia dar certo.
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            dados = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:200]
        if e.code == 403:
            return ("A Pipi recusou a ponte: %s. Se voce apagou o ponte.txt, "
                    "feche e abra a Pipi para ela criar outro." % detalhe)
        return "A Pipi respondeu %s: %s" % (e.code, detalhe)
    except Exception:
        return ("A Pipi nao esta aberta. Abra o pipi.bat -- ela e quem "
                "desenha -- e peca de novo. (Procurei em %s)" % _endereco())

    if not dados.get("ok"):
        return "A Pipi nao conseguiu desenhar: %s" % dados.get("erro", "sem motivo")

    # O QUE VOLTA E TEXTO, E A TELA DO BIGODE E QUEM VIRA IMAGEM
    #
    #   Devolver a URL numa linha sozinha basta: o renderizador do
    #   index.html tem uma regra que troca endereco de imagem por <img>.
    #   Nao precisa de rota nova nem de base64 atravessando o chat.
    #
    #   18/09: ontem este comentario dizia a mesma coisa e era FALSO -- a
    #   regra nao existia, e a resposta mostrava a URL escrita. Afirmei um
    #   comportamento sem procurar por ele. Hoje a regra foi escrita, e o
    #   comentario passou a descrever o que existe.
    partes = ["Pronto. A Pipi desenhou:", "", str(dados.get("url") or "")]
    ficha = []
    if dados.get("segundos") is not None:
        ficha.append("%ss na placa" % dados["segundos"])
    if dados.get("custo_usd") is not None:
        ficha.append("US$ %.4f" % float(dados["custo_usd"]))
    if dados.get("arquivo"):
        ficha.append("salva em %s" % dados["arquivo"])
    if ficha:
        partes += ["", " · ".join(ficha)]
    if dados.get("licenca"):
        partes += ["", dados["licenca"]]
    return "\n".join(partes)
