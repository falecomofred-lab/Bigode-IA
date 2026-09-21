"""TESTE — o carimbo aparece quando tem de aparecer?

09/09/2026. Numa unica conversa, o Bigode afirmou com toda a confianca:

  · Corisco e um canabinoide da Corynanthe yohimbe
        (Corisco era o cangaceiro, braco direito de Lampiao)
  · Lampiao se chamava Manuel Antonio Alves e nasceu em Minas Gerais
        (era Virgulino Ferreira da Silva, de Pernambuco)
  · Nelson Piquet foi campeao em 1978 pela McLaren-Honda
        (foi 1981, 83 e 87, e o carro era Brabham)

O Fred colou a pagina do Google mostrando o erro. Ele repetiu a invencao.

NENHUMA levou carimbo. O selo so aparecia quando a pergunta batia numa lista
de palavras -- e "me fale sobre cannabis" nao batia, nem "quem eh lampiao"
(a lista tinha "quem e", ele escreveu "eh").

Este teste guarda esses casos exatos. Se algum dia o carimbo parar de
aparecer neles de novo, ele acusa.

    python test_selo.py

Nao altera nada. So confere.

Venure - venure.com.br
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cerebro as C

LONGA = ("Corisco e um principio ativo derivado da planta Corynanthe yohimbe. "
         "Ele pertence ao grupo de compostos canabinoides, mas nao contem THC. "
         "Principais usos medicos: tratamento de dor cronica, gerenciamento de "
         "nauseas e vomitos, sindrome do intestino irritavel. A Anvisa autoriza "
         "o uso apenas para procedimentos definidos por protocolos clinicos.")

CURTA = "Ola! Como posso ajudar voce hoje?"

CASOS = [
    # (pergunta, resposta, deve carimbar?)

    # ---- os tres casos reais de 09/09 ----
    ("quem e corisco",                LONGA, True),
    ("quem eh lampiao?",              LONGA, True),
    ("me fale sobre cannabis",        LONGA, True),
    ("me fale sobre nelson piquet",   LONGA, True),
    ("e corisco?",                    LONGA, True),
    ("tem certeza ?",                 LONGA, True),
    ("corisco na historia de lampiao, quem e?", LONGA, True),

    # ---- conversa: nao ha o que verificar ----
    ("oi",                            CURTA, False),
    ("obrigado",                      CURTA, False),
    ("bom dia",                       CURTA, False),

    # ---- pedido de acao ou criacao, nao de fato ----
    ("escreva um codigo que soma dois numeros", LONGA, False),
    ("o que voce acha desse nome para a empresa?", LONGA, False),
    ("sugira um nome para o projeto", LONGA, False),
    ("traduza este texto para o ingles", LONGA, False),

    # ---- sobre o proprio Bigode ----
    ("quem e voce?",                  LONGA, False),

    # ---- resposta curta demais para conter invencao perigosa ----
    ("quem e corisco",                "Nao encontrei essa informacao.", False),
]


def main():
    print()
    print("=" * 66)
    print("  O CARIMBO APARECE QUANDO TEM DE APARECER?")
    print("=" * 66)
    print()

    falhas = 0
    for pergunta, resposta, esperado in CASOS:
        obtido = C.merece_carimbo(pergunta, resposta)
        ok = obtido == esperado
        if not ok:
            falhas += 1
        print("  %-6s %-42s carimba=%-5s"
              % ("[ok]" if ok else "[ERRO]", pergunta[:42], obtido))
        if not ok:
            print("         esperava carimba=%s" % esperado)

    # A trava antiga tambem tem de continuar pegando o que ja pegava.
    print()
    print("  A TRAVA ANTIGA CONTINUA DE PE")
    print("  " + "-" * 62)
    antigos = [
        ("qual foi o faturamento da Venure em 2024?", True),
        ("qual artigo da lei trata disso?", True),
        ("quantos arquivos tem nessa pasta?", True),
        ("oi", False),
    ]
    for pergunta, esperado in antigos:
        obtido = C.precisa_fonte(pergunta)
        ok = obtido == esperado
        if not ok:
            falhas += 1
        print("  %-6s %-42s fonte=%s"
              % ("[ok]" if ok else "[ERRO]", pergunta[:42], obtido))

    print()
    print("=" * 66)
    if falhas:
        print("  %d FALHA(S). NAO envie assim." % falhas)
    else:
        print("  TUDO CERTO — %d casos." % (len(CASOS) + len(antigos)))
        print()
        print("  Depois de enviar, refaca a pergunta sobre Corisco.")
        print("  A resposta tem de vir com ATENCAO - NAO CONFERI.")
    print("=" * 66)
    print()
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
