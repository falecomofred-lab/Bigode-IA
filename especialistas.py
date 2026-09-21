#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESPECIALISTAS — versões do Bigode treinadas para um assunto só.

Um Especialista é o Bigode com quatro coisas amarradas:

  instruções   como ele deve pensar e responder naquele assunto
  documentos   o que ele consulta como base (a apostila, a norma, o contrato)
  ferramentas  o que ele pode usar — e, por consequência, o que NÃO pode
  rigor        quanto ele precisa provar antes de afirmar

O rigor é a parte que importa. São três níveis, e a diferença entre eles não
é de estilo, é de arquitetura:

  livre     conversa e cria. Brainstorm, nome de produto, rascunho.
            Não carimba nada, porque não está afirmando fato.

  fonte     não afirma nada sobre o mundo sem ter consultado algo fora.
            Jurídico, fiscal, saúde, qualquer coisa com data e número.
            A memória do modelo não conta como fonte.

  arquivo   não fala do seu código sem ter aberto o arquivo.
            Programação, auditoria, revisão.

Cada especialista mora num .md com cabeçalho — dá para editar no bloco de
notas, versionar no Git e mandar por e-mail. Nada de banco de dados para
guardar meia dúzia de arquivos de texto.

Venure — venure.com.br
"""

import json
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
PASTA = BASE / "memoria" / "especialistas"

RIGORES = {
    "livre": {
        "rotulo": "Livre",
        "explica": "conversa e cria; não precisa provar nada",
        "exige": "",
    },
    "fonte": {
        "rotulo": "Exige fonte",
        "explica": "não afirma nada sobre o mundo sem consultar",
        "exige": "fonte externa",
    },
    "arquivo": {
        "rotulo": "Exige ler o arquivo",
        "explica": "não fala do seu código sem abrir o arquivo",
        "exige": "leitura de arquivo",
    },
}


def _id(nome):
    """'Consultor Fiscal' -> 'consultor-fiscal'. Serve de nome de arquivo."""
    limpo = unicodedata.normalize("NFD", nome or "")
    limpo = "".join(c for c in limpo if unicodedata.category(c) != "Mn")
    limpo = re.sub(r"[^a-zA-Z0-9]+", "-", limpo).strip("-").lower()
    return limpo[:48] or "especialista"


# --------------------------------------------------------------------------
# Ler e gravar
# --------------------------------------------------------------------------

def _ler_arquivo(caminho):
    """Separa o cabeçalho entre --- do corpo do texto."""
    try:
        bruto = caminho.read_text(encoding="utf-8")
    except Exception:
        return None

    cabeca, corpo = {}, bruto
    if bruto.startswith("---"):
        partes = bruto.split("---", 2)
        if len(partes) >= 3:
            corpo = partes[2].lstrip("\n")
            for linha in partes[1].strip().splitlines():
                if ":" not in linha:
                    continue
                chave, valor = linha.split(":", 1)
                chave, valor = chave.strip().lower(), valor.strip()
                if valor.startswith("["):
                    try:
                        valor = json.loads(valor)
                    except Exception:
                        valor = [v.strip() for v in valor.strip("[]").split(",")
                                 if v.strip()]
                cabeca[chave] = valor

    rigor = str(cabeca.get("rigor", "fonte")).lower()
    if rigor not in RIGORES:
        rigor = "fonte"

    return {
        "id": caminho.stem,
        "nome": cabeca.get("nome") or caminho.stem,
        "descricao": cabeca.get("descricao", ""),
        "rigor": rigor,
        "rigor_rotulo": RIGORES[rigor]["rotulo"],
        "pasta": cabeca.get("pasta", ""),
        "documentos": cabeca.get("documentos") or [],
        "ferramentas": cabeca.get("ferramentas") or [],
        "navegador": str(cabeca.get("navegador", "")).lower() in ("sim", "true", "1"),
        "ativo": str(cabeca.get("ativo", "sim")).lower() not in ("nao", "não", "0"),
        "instrucoes": corpo.strip(),
    }


def listar():
    if not PASTA.exists():
        return []
    saida = []
    for arq in sorted(PASTA.glob("*.md")):
        item = _ler_arquivo(arq)
        if item:
            saida.append(item)
    return saida


def abrir(ident):
    if not ident:
        return None
    alvo = PASTA / ("%s.md" % _id(ident))
    return _ler_arquivo(alvo) if alvo.exists() else None


def salvar(dados):
    nome = (dados.get("nome") or "").strip()
    if not nome:
        return {"ok": False, "erro": "dê um nome ao especialista"}
    instrucoes = (dados.get("instrucoes") or "").strip()
    if not instrucoes:
        return {"ok": False, "erro": "escreva o que ele deve fazer"}

    rigor = str(dados.get("rigor") or "fonte").lower()
    if rigor not in RIGORES:
        rigor = "fonte"

    ident = _id(dados.get("id") or nome)
    PASTA.mkdir(parents=True, exist_ok=True)

    cabeca = [
        "---",
        "nome: %s" % nome,
        "descricao: %s" % (dados.get("descricao") or "").strip(),
        "rigor: %s" % rigor,
        "pasta: %s" % (dados.get("pasta") or "").strip(),
        "documentos: %s" % json.dumps(dados.get("documentos") or [],
                                      ensure_ascii=False),
        "ferramentas: %s" % json.dumps(dados.get("ferramentas") or [],
                                       ensure_ascii=False),
        "navegador: %s" % ("sim" if dados.get("navegador") else "nao"),
        "ativo: %s" % ("sim" if dados.get("ativo", True) else "nao"),
        "---",
        "",
    ]
    (PASTA / ("%s.md" % ident)).write_text(
        "\n".join(cabeca) + instrucoes + "\n", encoding="utf-8")
    return {"ok": True, "id": ident}


def apagar(ident):
    alvo = PASTA / ("%s.md" % _id(ident))
    if alvo.exists():
        alvo.unlink()
        return {"ok": True}
    return {"ok": False, "erro": "não encontrei"}


# --------------------------------------------------------------------------
# O que entra no prompt
# --------------------------------------------------------------------------

def montar(ident):
    """Devolve o texto que o especialista acrescenta ao system, e as regras.

    Importante: isto vai no FIM do system, nunca no começo. Qualquer mudança
    no início do prompt obriga o motor a reprocessar tudo do zero e joga o
    cache fora — que é justamente o que faz a primeira mensagem levar minutos.
    """
    esp = abrir(ident)
    if not esp or not esp["ativo"]:
        return "", {}

    partes = ["\n\n# ESPECIALISTA: %s\n" % esp["nome"]]
    if esp["descricao"]:
        partes.append(esp["descricao"] + "\n")
    partes.append("\n" + esp["instrucoes"] + "\n")

    if esp["pasta"]:
        partes.append("\nSua pasta de trabalho é `%s`. Quando o Fred falar de "
                      "arquivo sem dizer onde, procure ali primeiro.\n"
                      % esp["pasta"])

    if esp["documentos"]:
        partes.append("\n## Sua base de referência\n\n"
                      "Estes documentos são sua fonte neste assunto. Leia com "
                      "`ler_arquivo` antes de responder — não confie na "
                      "memória sobre o que está escrito neles:\n")
        for doc in esp["documentos"]:
            partes.append("- `%s`\n" % doc)

    if esp["rigor"] == "fonte":
        partes.append("\n## Regra deste especialista\n\n"
                      "Você NÃO afirma data, número, lei, preço ou fato sem "
                      "ter consultado uma fonte nesta conversa. Sua memória "
                      "não é fonte. Cite de onde veio cada afirmação. Quando "
                      "não conseguir confirmar, escreva \"não confirmei\" e "
                      "siga — não preencha com texto que soa bem.\n")
    elif esp["rigor"] == "arquivo":
        partes.append("\n## Regra deste especialista\n\n"
                      "Você NÃO fala de código, arquivo ou estrutura sem ter "
                      "aberto o arquivo nesta conversa. Nada de código "
                      "\"parecido com o que deve estar lá\".\n")

    if esp["navegador"]:
        partes.append("\n## Navegador\n\n"
                      "Você pode operar o Chrome como uma pessoa: abrir "
                      "página, clicar, preencher campo, ler o que apareceu. "
                      "Descreva cada passo antes de dar. Nunca envie "
                      "formulário, compre, publique nem aceite termo sem o "
                      "Fred autorizar na hora.\n")

    return "".join(partes), {
        "id": esp["id"],
        "nome": esp["nome"],
        "rigor": esp["rigor"],
        "ferramentas": esp["ferramentas"],
        "navegador": esp["navegador"],
        "pasta": esp["pasta"],
    }


def exige_fonte(regras):
    return (regras or {}).get("rigor") == "fonte"


def exige_arquivo(regras):
    return (regras or {}).get("rigor") == "arquivo"


# --------------------------------------------------------------------------
# Modelos prontos, para não começar do zero
# --------------------------------------------------------------------------

PRONTOS = [
    {
        "nome": "Programador Python",
        "descricao": "Escreve e revisa Python nos seus projetos",
        "rigor": "arquivo",
        "instrucoes": (
            "Você programa em Python para o Fred, que não é desenvolvedor.\n\n"
            "- Entregue o arquivo COMPLETO, nunca trecho solto.\n"
            "- Diga exatamente em qual arquivo o código vai.\n"
            "- Antes de alterar, leia o arquivo atual e mostre o que muda.\n"
            "- Prefira a solução mais simples e estável; nada de refatoração "
            "grande sem necessidade.\n"
            "- Explique o que quebrou e o que isso causa na prática, em "
            "português comum."
        ),
    },
    {
        "nome": "Consultor Fiscal",
        "descricao": "Impostos, obrigações e prazos — sempre com a norma na mão",
        "rigor": "fonte",
        "instrucoes": (
            "Você orienta o Fred sobre obrigações fiscais no Brasil.\n\n"
            "- Toda resposta cita a norma: lei, IN, decreto, com número e ano.\n"
            "- Regra fiscal muda todo ano: confirme a vigência antes de "
            "afirmar. Alíquota que você lembra pode ser de dois anos atrás.\n"
            "- Diga com todas as letras que você não é contador e que decisão "
            "de valor deve passar pelo contador dele."
        ),
    },
    {
        "nome": "Redator Venure",
        "descricao": "Textos no tom da casa, com os fatos conferidos",
        "rigor": "fonte",
        "instrucoes": (
            "Você escreve para a Venure: direto, sem enrolação, sem palavra "
            "difícil por enfeite.\n\n"
            "- Todo fato citado tem fonte. Sem fonte, o dado não entra.\n"
            "- Frase curta. Corte advérbio e adjetivo que não trabalham.\n"
            "- Nada de conclusão que repete o que já foi dito.\n"
            "- Quando faltar um dado, marque `[FALTA: ...]` em vez de "
            "preencher com parágrafo genérico."
        ),
    },
    {
        "nome": "Parceiro de Ideias",
        "descricao": "Brainstorm sem trava — para pensar, não para afirmar",
        "rigor": "livre",
        "instrucoes": (
            "Você ajuda o Fred a pensar. Aqui pode especular, propor caminho "
            "improvável e discordar.\n\n"
            "- Dê 3 a 5 opções, não uma só.\n"
            "- Aponte o ponto fraco de cada uma.\n"
            "- Quando algo for chute, diga que é chute.\n"
            "- Pergunte quando a ideia estiver vaga demais para avançar."
        ),
    },
]
