#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIARIO DE BORDO — a memoria do Bigode entre uma sessao e outra

O PROBLEMA QUE ISTO RESOLVE

As conversas ficam em `conversas/*.json`, dentro da pasta do Bigode. Isso
funciona enquanto ele mora sempre no mesmo lugar. Desde 09/09 ele roda
tambem no Colab -- e la a maquina e nova a cada sessao: tudo o que foi
conversado morre junto com o runtime.

Pior que perder o historico e perder o FIO. O Fred trabalha em cima do que
ficou pendente da vez anterior, e comecar do zero a cada sessao transforma
um consultor em um atendente que nunca lembra de nada.

COMO FUNCIONA

Ao fim de cada resposta, uma linha e acrescentada a um arquivo Markdown no
Google Drive -- que sobrevive ao pendrive, ao Colab e a troca de maquina.
Ao comecar uma conversa nova, o Bigode le as ultimas anotacoes e ja sabe
onde vocês pararam.

    G:\\Meu Drive\\projetos\\Cerebro\\Historico\\
        2026-09-09.md        um arquivo por dia
        ONDE-PARAMOS.md      so o essencial, sempre atualizado

Markdown de proposito: o Fred abre e le sem precisar do Bigode. Um .json
seria melhor para a maquina e pior para ele -- e a memoria e dele.

SEM GASTAR IA

Nada aqui chama o modelo. O resumo e montado com o que ja se sabe: a
pergunta, os arquivos abertos, as ferramentas usadas, o comeco da resposta.
Chamar o modelo para resumir custaria 75 segundos por mensagem.

Venure - venure.com.br
"""

import datetime
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Onde procurar o Drive, na ordem. O primeiro que existir ganha.
#
# No Windows do Fred o Drive e G:. No Colab ele e montado em
# /content/drive/MyDrive. Descobrir sozinho evita configuracao manual toda
# vez que ele troca de casa.
LUGARES = [
    Path(r"G:\Meu Drive\projetos\Cerebro\Historico"),
    Path("/content/drive/MyDrive/projetos/Cerebro/Historico"),
]

QUANTAS_LEMBRAR = 12      # ultimas anotacoes que entram no prompt
TETO_DO_PROMPT = 1200     # caracteres; acima disso corta pelas mais antigas


def pasta(config=None):
    """Onde o diario mora. Config manda; senao, o primeiro lugar que existir."""
    escolhido = None
    try:
        if config:
            do_config = (config() if callable(config) else config).get("pasta_historico")
            if do_config:
                escolhido = Path(do_config)
    except Exception:
        pass

    if escolhido is None:
        for lugar in LUGARES:
            if lugar.parent.exists():      # o Drive esta montado?
                escolhido = lugar
                break

    # Sem Drive nenhum (pendrive solto, maquina emprestada): guarda em casa.
    # Melhor um historico local do que historico nenhum.
    if escolhido is None:
        escolhido = BASE / "historico"

    try:
        escolhido.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None
    return escolhido


def _limpo(texto, tamanho=160):
    """Uma linha, sem quebra e sem marcacao que estrague a tabela."""
    t = re.sub(r"\s+", " ", str(texto or "")).strip()
    t = t.replace("|", "/")
    return (t[:tamanho] + "…") if len(t) > tamanho else t


# ==========================================================================
# Escrever
# ==========================================================================

def anotar(pergunta, resposta, lidos=(), projeto="", especialista="",
           segundos=0, modelo="", config=None):
    """Guarda uma linha do que aconteceu. Nunca levanta erro.

    Falha de diario nao pode derrubar uma conversa: se o Drive estiver fora
    do ar ou a pasta somir, a resposta do Fred continua chegando.
    """
    destino = pasta(config)
    if not destino:
        return
    try:
        agora = datetime.datetime.now()
        arquivo = destino / (agora.strftime("%Y-%m-%d") + ".md")

        if not arquivo.exists():
            arquivo.write_text(
                "# Diario do Bigode — %s\n\n"
                "*Escrito sozinho ao fim de cada resposta. "
                "Voce pode editar: o que estiver aqui, ele le na proxima vez.*\n"
                % agora.strftime("%d/%m/%Y"),
                encoding="utf-8")

        partes = ["\n---\n\n### %s" % agora.strftime("%H:%M")]
        if projeto:
            partes.append("**Projeto:** %s" % _limpo(projeto, 60))
        if especialista:
            partes.append("**Especialista:** %s" % _limpo(especialista, 40))

        partes.append("**Voce pediu:** %s" % _limpo(pergunta, 220))
        if lidos:
            vistos = []
            for x in lidos:
                x = _limpo(x, 70)
                if x and x not in vistos:
                    vistos.append(x)
            partes.append("**Ele abriu:** %s" % ", ".join(vistos[:6]))
        partes.append("**Respondeu:** %s" % _limpo(resposta, 400))

        rodape = []
        if segundos:
            rodape.append("%.0fs" % segundos)
        if modelo:
            rodape.append(_limpo(modelo, 40))
        if rodape:
            partes.append("*%s*" % " · ".join(rodape))

        with arquivo.open("a", encoding="utf-8") as f:
            f.write("\n".join(partes) + "\n")

        _atualizar_resumo(destino)
    except Exception:
        pass          # diario e conforto, nao funcionalidade


def _atualizar_resumo(destino):
    """Reescreve o ONDE-PARAMOS.md com as ultimas anotacoes.

    Um arquivo so, sempre no mesmo lugar, e o que o Fred abre no celular
    para lembrar do que estava fazendo. E e o que o Bigode le primeiro.
    """
    try:
        dias = sorted(destino.glob("20*.md"), reverse=True)[:3]
        blocos = []
        for dia in dias:
            texto = dia.read_text(encoding="utf-8", errors="ignore")
            trechos = texto.split("\n---\n")[1:]
            for t in reversed(trechos):
                blocos.append((dia.stem, t.strip()))
                if len(blocos) >= QUANTAS_LEMBRAR:
                    break
            if len(blocos) >= QUANTAS_LEMBRAR:
                break

        linhas = ["# Onde paramos",
                  "",
                  "*Atualizado sozinho. As %d ultimas coisas que fizemos, "
                  "da mais recente para a mais antiga.*" % len(blocos),
                  ""]
        dia_anterior = None
        for dia, bloco in blocos:
            if dia != dia_anterior:
                linhas.append("\n## %s" % dia)
                dia_anterior = dia
            linhas.append("\n" + bloco)

        (destino / "ONDE-PARAMOS.md").write_text(
            "\n".join(linhas) + "\n", encoding="utf-8")
    except Exception:
        pass


# ==========================================================================
# Ler
# ==========================================================================

def retomar(config=None):
    """O texto que entra no prompt quando a conversa e nova.

    Devolve string vazia quando nao ha nada — assim o prompt nao carrega um
    cabecalho vazio de graça.
    """
    destino = pasta(config)
    if not destino:
        return ""
    try:
        resumo = destino / "ONDE-PARAMOS.md"
        if not resumo.exists():
            return ""
        texto = resumo.read_text(encoding="utf-8", errors="ignore")

        # So os blocos, sem o cabecalho explicativo.
        pedacos = [p.strip() for p in texto.split("###")[1:]]
        if not pedacos:
            return ""

        juntos, tamanho = [], 0
        for p in pedacos:                       # ja vem do mais recente
            p = "### " + p
            if tamanho + len(p) > TETO_DO_PROMPT:
                break
            juntos.append(p)
            tamanho += len(p)

        if not juntos:
            return ""

        return ("# ONDE VOCES PARARAM\n\n"
                "Isto e o que voce e o Fred fizeram nas ultimas conversas, da\n"
                "mais recente para a mais antiga. Use para dar continuidade —\n"
                "mas nao repita o que ja foi dito, e nao trate como se tivesse\n"
                "acabado de acontecer. Se ele retomar um assunto daqui, voce\n"
                "ja sabe do que se trata.\n\n" + "\n\n".join(juntos))
    except Exception:
        return ""


def onde_esta(config=None):
    """Para a tela mostrar onde o diario mora."""
    destino = pasta(config)
    return str(destino) if destino else "(sem lugar para guardar)"
