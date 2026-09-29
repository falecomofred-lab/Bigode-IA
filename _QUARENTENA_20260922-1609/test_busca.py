"""TESTE — a busca na web funciona?

09/09/2026. O Bigode afirmou que Corisco era um canabinoide extraido da
Corynanthe yohimbe. Invencao completa: Corisco era o cangaceiro, braco
direito de Lampiao.

O Fred pediu para pesquisar. A busca respondeu:

    "a pagina de resultados veio num formato que nao sei ler"

O DuckDuckGo tinha mudado o HTML -- de novo, poucos dias depois da correcao
anterior. Raspar HTML de buscador e uma corrida que nunca se ganha.

O conserto foi em tres camadas:
  1. POST em vez de GET no DuckDuckGo (o formulario deles sempre foi POST)
  2. Mojeek como segundo buscador
  3. Wikipedia como fundo de poco -- API de verdade, estavel, devolve JSON

Este teste vai a internet DE VERDADE. Sem rede, ele avisa em vez de mentir.

    python test_busca.py

Nao altera nada.

Venure - venure.com.br
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ferramentas as F


def falhou(saida):
    return saida.lower().startswith("nao consegui")


def main():
    print()
    print("=" * 66)
    print("  A BUSCA NA WEB FUNCIONA?")
    print("=" * 66)
    print()

    # ---- 1. o caso real ----
    print("  1. O caso de 09/09: 'quem foi Corisco no cangaco'")
    print("  " + "-" * 62)
    saida = F.web_buscar("quem foi Corisco no cangaco")
    for linha in saida.splitlines()[:10]:
        print("     " + linha[:74])
    print()

    ok_busca = not falhou(saida)
    # A prova de que achou o certo: cangaco/Lampiao aparecem no resultado.
    achou_certo = any(p in saida.lower()
                      for p in ("cangac", "cangaç", "lampi", "virgulino"))

    print("  %-6s a busca respondeu" % ("[ok]" if ok_busca else "[ERRO]"))
    print("  %-6s achou o cangaceiro (e nao a planta)"
          % ("[ok]" if achou_certo else "[ERRO]"))
    print()

    # ---- 2. a Wikipedia sozinha ----
    print("  2. O fundo de poco (Wikipedia) responde sozinho?")
    print("  " + "-" * 62)
    try:
        itens = F._wikipedia("Corisco cangaceiro")
        ok_wiki = bool(itens)
        for link, titulo, trecho in itens[:3]:
            print("     - %s" % titulo)
            print("       %s" % link)
    except Exception as erro:
        ok_wiki = False
        print("     falhou: %s" % erro)
    print()
    print("  %-6s Wikipedia respondeu" % ("[ok]" if ok_wiki else "[ERRO]"))
    print()

    # ---- 3. consulta vazia nao pode explodir ----
    vazio = F.web_buscar("")
    ok_vazio = "preciso saber" in vazio.lower()
    print("  %-6s consulta vazia avisa em vez de quebrar"
          % ("[ok]" if ok_vazio else "[ERRO]"))

    print()
    print("=" * 66)
    if ok_busca and achou_certo and ok_wiki and ok_vazio:
        print("  TUDO CERTO.")
        print()
        print("  Agora o Bigode consegue descobrir quem foi Corisco em vez")
        print("  de inventar. Pergunte a ele e confira o selo VERIFICADO.")
    elif not ok_busca and not ok_wiki:
        print("  NADA RESPONDEU.")
        print()
        print("  Ou este computador esta sem internet, ou os tres caminhos")
        print("  cairam ao mesmo tempo. Confira a rede antes de mexer no")
        print("  codigo -- o teste vai a internet de verdade.")
    else:
        print("  FALHA PARCIAL. Veja acima qual linha deu [ERRO].")
    print("=" * 66)
    print()
    return 0 if (ok_busca and ok_wiki and ok_vazio) else 1


if __name__ == "__main__":
    raise SystemExit(main())
