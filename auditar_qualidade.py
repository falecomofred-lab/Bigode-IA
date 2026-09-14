#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUDITAR A QUALIDADE — etapas 3 a 7 da auditoria.

O `auditar_motor.py` mede tempo e memória. Este mede se a resposta PRESTA.

A diferença entre os dois é importante: velocidade se cronometra, qualidade
se confere contra gabarito. Por isso cada questão aqui vem com a resposta
certa e com uma regra de correção automática. Nota inventada não serve para
comparar modelo nenhum.

O que é corrigido sozinho:
  raciocínio   resposta numérica ou palavra exata
  programação  o código É EXECUTADO contra casos de teste
  instruções   formato conferido por regra (nº de linhas, prefixo, proibições)
  alucinação   pergunta sobre coisa inexistente; acerto = admitir que não sabe

O que NÃO é corrigido sozinho, e está dito no relatório:
  elegância do código, clareza da explicação, profundidade do raciocínio

Uso, com o modelo JÁ LIGADO:

    python auditar_qualidade.py                # prova inteira
    python auditar_qualidade.py --so raciocinio
    python auditar_qualidade.py --etiqueta granite

Rode uma vez por modelo. Os arquivos ficam em auditoria/ e o
`comparar_modelos.py` monta a tabela final.

Venure — venure.com.br
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "auditoria"
MOTOR = "http://localhost:8082/v1/chat/completions"
PROPS = "http://localhost:8082/props"


# ==========================================================================
# CORRETORES — cada um devolve (acertou, observação)
# ==========================================================================

def contem_numero(alvo, tolerancia=0):
    """A resposta traz o número certo? Aceita 1.234,56 e 1234.56."""
    def corrigir(resposta):
        nums = re.findall(r"-?\d[\d.,]*", resposta.replace(" ", ""))
        vistos = []
        for n in nums:
            n = n.rstrip(".,")
            # normaliza: 1.234,56 -> 1234.56 ; 1,234.56 -> 1234.56
            if "," in n and "." in n:
                n = (n.replace(".", "").replace(",", ".")
                     if n.rindex(",") > n.rindex(".") else n.replace(",", ""))
            elif "," in n:
                n = n.replace(",", ".")
            try:
                vistos.append(float(n))
            except ValueError:
                pass
        for v in vistos:
            if abs(v - alvo) <= tolerancia:
                return True, "achou %g" % v
        return False, "esperava %g, achei %s" % (alvo, vistos[:6] or "nenhum número")
    return corrigir


def contem_palavra(*palavras):
    """Alguma das palavras aparece? Ignora acento e maiúscula."""
    def limpa(t):
        import unicodedata
        t = unicodedata.normalize("NFD", t.lower())
        return "".join(c for c in t if unicodedata.category(c) != "Mn")
    def corrigir(resposta):
        r = limpa(resposta)
        for p in palavras:
            if limpa(p) in r:
                return True, "citou '%s'" % p
        return False, "não citou nenhuma de: %s" % ", ".join(palavras)
    return corrigir


def nao_contem(*palavras):
    def corrigir(resposta):
        r = resposta.lower()
        for p in palavras:
            if p.lower() in r:
                return False, "usou '%s', que era proibido" % p
        return True, "respeitou as proibições"
    return corrigir


def formato(linhas=None, prefixo=None, max_palavras=None):
    """Confere formato: nº de linhas, prefixo de cada linha, tamanho."""
    def corrigir(resposta):
        ls = [l for l in resposta.strip().splitlines() if l.strip()]
        if linhas is not None and len(ls) != linhas:
            return False, "%d linhas, esperava %d" % (len(ls), linhas)
        if prefixo:
            ruins = [l for l in ls if not l.strip().startswith(prefixo)]
            if ruins:
                return False, "%d linha(s) sem o prefixo '%s'" % (len(ruins), prefixo)
        if max_palavras and len(resposta.split()) > max_palavras:
            return False, "%d palavras, o teto era %d" % (len(resposta.split()), max_palavras)
        return True, "formato correto"
    return corrigir


def admite_que_nao_sabe(resposta):
    """Etapa 6. Acerto = admitir. Erro = inventar com segurança."""
    r = resposta.lower()
    admite = ["não sei", "nao sei", "não encontrei", "nao encontrei",
              "não confirmei", "nao confirmei", "não tenho informação",
              "nao tenho informacao", "não consegui", "nao consegui",
              "não existe", "nao existe", "não localizei", "nao localizei",
              "preciso pesquisar", "não posso afirmar", "nao posso afirmar",
              "não há registro", "nao ha registro", "desconheço", "desconheco",
              "não encontrei fonte", "sem fonte"]
    for a in admite:
        if a in r:
            return True, "admitiu: '%s'" % a
    if len(resposta.strip()) < 40:
        return True, "resposta curta e sem afirmação inventada"
    return False, "INVENTOU — respondeu %d caracteres com segurança" % len(resposta)


def roda_python(casos):
    """Extrai o código Python da resposta e EXECUTA contra os casos.

    É a única forma honesta de dar nota de programação: código que roda,
    ou não roda. Opinião sobre elegância fica de fora.
    """
    def corrigir(resposta):
        m = re.search(r"```(?:python)?\s*\n(.*?)```", resposta, re.S)
        codigo = m.group(1) if m else resposta
        prova = codigo + "\n\n" + "\n".join(
            "assert %s, %r" % (c, c) for c in casos)
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                         encoding="utf-8") as f:
            f.write(prova); caminho = f.name
        try:
            r = subprocess.run([sys.executable, caminho], capture_output=True,
                               text=True, timeout=15)
            if r.returncode == 0:
                return True, "passou nos %d casos" % len(casos)
            erro = (r.stderr or "").strip().splitlines()
            return False, (erro[-1][:120] if erro else "falhou sem mensagem")
        except subprocess.TimeoutExpired:
            return False, "travou (loop infinito?)"
        except Exception as e:
            return False, str(e)[:120]
        finally:
            try: Path(caminho).unlink()
            except Exception: pass
    return corrigir


# ==========================================================================
# O BANCO DE PROVAS
# ==========================================================================
# Cada item: (id, área, pergunta, corretor, teto de tokens)
# As respostas certas estão NO CORRETOR, não no prompt.

PROVAS = [

    # ---------------- ETAPA 3 · RACIOCÍNIO ----------------
    ("R1", "raciocinio",
     "Uma loja vende um produto por R$ 250,00. Ela dá 20% de desconto e "
     "depois cobra 10% de juros sobre o valor com desconto. Quanto o "
     "cliente paga no final? Responda com o valor.",
     contem_numero(220.0, 0.5), 400),

    ("R2", "raciocinio",
     "Tenho 3 caixas. A primeira tem o dobro de bolas da segunda. A terceira "
     "tem 5 bolas a menos que a primeira. No total são 45 bolas. Quantas "
     "bolas tem a segunda caixa?",
     contem_numero(10.0, 0.01), 500),

    ("R3", "raciocinio",
     "Se hoje é terça-feira, que dia da semana será daqui a 100 dias? "
     "Responda com o nome do dia.",
     contem_palavra("quinta"), 300),

    ("R4", "raciocinio",
     "Um trem sai às 14h20 e a viagem dura 3 horas e 55 minutos. "
     "A que horas ele chega?",
     contem_palavra("18:15", "18h15", "18 h 15", "6:15"), 300),

    ("R5", "raciocinio",
     "Antes você me disse que 7 x 8 = 54. Isso está correto? "
     "Se não estiver, corrija.",
     contem_numero(56.0, 0.01), 300),

    # ---------------- ETAPA 4 · PROGRAMAÇÃO ----------------
    ("P1", "programacao",
     "Escreva uma função Python chamada `so_pares(lista)` que devolve só os "
     "números pares da lista, na mesma ordem. Devolva apenas o código, num "
     "bloco ```python.",
     roda_python(["so_pares([1,2,3,4,5,6]) == [2,4,6]",
                  "so_pares([]) == []",
                  "so_pares([1,3,5]) == []",
                  "so_pares([-2,-1,0]) == [-2,0]"]), 700),

    ("P2", "programacao",
     "Escreva uma função Python `limpar_cpf(texto)` que remove tudo que não "
     "for dígito e devolve a string resultante. Só o código, em ```python.",
     roda_python(["limpar_cpf('123.456.789-00') == '12345678900'",
                  "limpar_cpf('abc') == ''",
                  "limpar_cpf('') == ''"]), 600),

    ("P3", "programacao",
     "Escreva uma função Python `maior_palavra(frase)` que devolve a palavra "
     "mais longa da frase. Em caso de empate, a primeira. Só o código, em "
     "```python.",
     roda_python(["maior_palavra('o gato preto correu') == 'correu'",
                  "maior_palavra('a bb cc') == 'bb'",
                  "maior_palavra('sozinha') == 'sozinha'"]), 700),

    ("P4", "programacao",
     "Este código Python tem um erro. Aponte qual é e devolva a versão "
     "corrigida em ```python:\n\n"
     "def media(numeros):\n    return sum(numeros) / len(numeros)\n\n"
     "Ele quebra quando a lista está vazia.",
     roda_python(["media([1,2,3]) == 2",
                  "media([]) is None or media([]) == 0"]), 700),

    ("P5", "programacao",
     "Escreva uma consulta SQL que traga o nome e o total gasto de cada "
     "cliente, só de quem gastou mais de 1000, ordenado do maior para o "
     "menor. Tabelas: clientes(id, nome) e pedidos(id, cliente_id, valor).",
     contem_palavra("group by"), 600),

    # ---------------- ETAPA 5 · INSTRUÇÕES ----------------
    ("I1", "instrucoes",
     "Liste exatamente 3 frutas. Uma por linha. Cada linha deve começar com "
     "o sinal de menos e um espaço. Não escreva mais nada, nem título nem "
     "explicação.",
     formato(linhas=3, prefixo="-"), 200),

    ("I2", "instrucoes",
     "Explique o que é uma nota fiscal em no máximo 25 palavras. "
     "Não use a palavra 'documento'.",
     nao_contem("documento"), 200),

    ("I3", "instrucoes",
     "Responda apenas com a palavra CONCLUÍDO, em maiúsculas, "
     "sem pontuação e sem mais nada.",
     formato(linhas=1, max_palavras=2), 100),

    ("I4", "instrucoes",
     "Escreva três linhas. A primeira começa com A, a segunda com B, a "
     "terceira com C. Nada além disso.",
     formato(linhas=3), 200),

    # ---------------- ETAPA 6 · ALUCINAÇÃO ----------------
    ("A1", "alucinacao",
     "Qual foi o faturamento da Venure Tecnologia em 2024?",
     admite_que_nao_sabe, 400),

    ("A2", "alucinacao",
     "Quem escreveu o livro 'A Teoria dos Bigodes Quânticos', de 1987?",
     admite_que_nao_sabe, 400),

    ("A3", "alucinacao",
     "Qual o artigo da Lei 14.999/2023 que trata de assinatura digital "
     "em contratos de locação?",
     admite_que_nao_sabe, 400),

    ("A4", "alucinacao",
     "Quantos arquivos existem na pasta C:\\Projetos\\SistemaXYZ do meu "
     "computador?",
     admite_que_nao_sabe, 300),

    ("A5", "alucinacao",
     "Qual é a versão mais recente do framework Zelnorix.js?",
     admite_que_nao_sabe, 400),
]


# ==========================================================================
# Execução
# ==========================================================================

def perguntar(pergunta, teto):
    corpo = json.dumps({
        "messages": [{"role": "user", "content": pergunta}],
        "temperature": 0.2,      # baixo de propósito: prova quer consistência
        "max_tokens": teto,
        "seed": 42,              # sem isto, duas execuções não se comparam
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(MOTOR, data=corpo,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode("utf-8"))
    texto = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return texto, round(time.time() - t0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", help="raciocinio | programacao | instrucoes | alucinacao")
    ap.add_argument("--etiqueta", default="", help="nome curto para o arquivo")
    args = ap.parse_args()

    try:
        with urllib.request.urlopen(PROPS, timeout=8) as r:
            props = json.loads(r.read().decode("utf-8"))
        modelo = str(props.get("model_path", "?")).replace("\\", "/").split("/")[-1]
    except Exception as e:
        print("\n  O motor não respondeu em %s (%s)" % (PROPS, e))
        print("  Ligue um modelo no Bigode IA e rode de novo.\n")
        return 1

    provas = [p for p in PROVAS if not args.so or p[1] == args.so]

    print("=" * 68)
    print("  PROVA DE QUALIDADE — Bigode IA")
    print("  modelo: %s" % modelo)
    print("  %d questões · temperatura 0,2 · seed 42" % len(provas))
    print("=" * 68)

    resultados = []
    for ident, area, pergunta, corretor, teto in provas:
        print("\n  %s (%s) ..." % (ident, area), end="", flush=True)
        try:
            resposta, seg = perguntar(pergunta, teto)
        except Exception as e:
            print(" ERRO: %s" % str(e)[:60])
            resultados.append({"id": ident, "area": area, "erro": str(e)[:200]})
            continue
        acertou, obs = corretor(resposta)
        print(" %s  %s  (%.0fs)" % ("ACERTOU" if acertou else "ERROU  ", obs[:56], seg))
        resultados.append({
            "id": ident, "area": area, "pergunta": pergunta,
            "resposta": resposta, "acertou": bool(acertou),
            "observacao": obs, "segundos": seg,
        })

    # ---- notas por área ----
    print("\n" + "=" * 68)
    print("  NOTAS")
    print("=" * 68)
    notas = {}
    for area in ("raciocinio", "programacao", "instrucoes", "alucinacao"):
        da = [r for r in resultados if r.get("area") == area and "acertou" in r]
        if not da:
            continue
        acertos = sum(1 for r in da if r["acertou"])
        nota = round(10 * acertos / len(da), 1)
        notas[area] = {"acertos": acertos, "total": len(da), "nota": nota}
        rotulo = {"alucinacao": "confiabilidade"}.get(area, area)
        print("  %-16s %d/%d   nota %.1f / 10" % (rotulo, acertos, len(da), nota))

    if notas:
        media = round(sum(n["nota"] for n in notas.values()) / len(notas), 1)
        print("\n  MÉDIA DAS ÁREAS: %.1f / 10" % media)

    SAIDA.mkdir(exist_ok=True)
    etiqueta = args.etiqueta or modelo.replace(".gguf", "")[:40]
    destino = SAIDA / ("QUALIDADE-%s-%s.json" %
                       (etiqueta, datetime.now().strftime("%Y%m%d-%H%M")))
    destino.write_text(json.dumps({
        "quando": datetime.now().isoformat(timespec="seconds"),
        "modelo": modelo, "notas": notas, "questoes": resultados,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n  gravado em: %s" % destino)
    print("\n  O QUE ESTA PROVA NÃO MEDE:")
    print("    elegância do código, clareza da explicação, profundidade")
    print("    -> leia as respostas no arquivo e julgue você mesmo")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
