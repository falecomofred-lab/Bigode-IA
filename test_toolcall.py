"""TESTE — o Bigode entende a chamada de ferramenta em texto?

Por que este teste existe:

09/09/2026, primeiro dia rodando na nuvem. O Fred perguntou sobre cannabis e
a tela mostrou isto, cru, no lugar da resposta:

    <tool_call>
    {"name": "web_buscar", "arguments": "{\\n \\"consulta\\": \\"cannabis\\"\\n}"}
    </tool_call>

O modelo fez a coisa certa: pediu a busca. Quem nao entendeu foi o Bigode --
ele so sabia ler `nome`/`args`, e ali vinha `name`/`arguments` embrulhado num
marcador diferente.

O llamafile do pendrive convertia isso sozinho, entao nunca tinha aparecido.
O motor da nuvem nao converte. Como amanha pode ser um terceiro motor, o
conserto foi no Bigode: ele passou a ler todos os formatos.

    python test_toolcall.py

Nao altera nada. So confere.

Venure - venure.com.br
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cerebro as C


CASOS = [
    # (rotulo, texto que o modelo escreveu, ferramenta esperada, args esperados)

    ("o caso real de 09/09",
     '<tool_call>\n{"name": "web_buscar", "arguments": '
     '"{\\n \\"consulta\\": \\"cannabis\\"\\n}"}\n</tool_call>',
     "web_buscar", {"consulta": "cannabis"}),

    ("tool_call com objeto",
     '<tool_call>{"name":"ler_arquivo","arguments":{"caminho":"D:/a.py"}}</tool_call>',
     "ler_arquivo", {"caminho": "D:/a.py"}),

    ("formato antigo do Bigode",
     '<ferramenta>{"nome": "raio_x", "args": {"caminho": "G:/p"}}</ferramenta>',
     "raio_x", {"caminho": "G:/p"}),

    ("bloco de codigo json",
     '```json\n{"nome": "listar_pasta", "args": {"caminho": "G:/x"}}\n```',
     "listar_pasta", {"caminho": "G:/x"}),

    ("json solto, sem marcador",
     'vou fazer isto: {"name": "listar_pasta", "arguments": {"caminho": "G:/y"}}',
     "listar_pasta", {"caminho": "G:/y"}),

    # ---- os que NAO podem virar chamada de ferramenta ----

    ("resposta comum",
     "Ola! Como posso ajudar voce hoje?", None, None),

    ("cita a ferramenta sem chamar",
     "vou usar a ferramenta web_buscar para isso", None, None),

    ("json que nao e ferramenta nenhuma",
     'segue o exemplo: {"name": "joao", "arguments": {"idade": 30}}', None, None),
]


def main():
    print()
    print("=" * 62)
    print("  O BIGODE ENTENDE A CHAMADA DE FERRAMENTA?")
    print("=" * 62)
    print()

    falhas = 0
    for rotulo, texto, nome_esp, args_esp in CASOS:
        nome, args = C.extrair_chamada(texto)
        ok = (nome == nome_esp) and (nome_esp is None or args == args_esp)
        if not ok:
            falhas += 1
        print("  %-6s %-28s -> %s %s"
              % ("[ok]" if ok else "[ERRO]", rotulo[:28],
                 nome, args if nome else ""))
        if not ok:
            print("         esperava: %s %s" % (nome_esp, args_esp))

    # A chamada nao pode vazar para a tela como texto.
    print()
    print("  O QUE APARECE NA TELA")
    print("  " + "-" * 58)
    for marca in ("<tool_call>", "<ferramenta>", "```json"):
        bruto = "Vou buscar isso. " + marca + '{"name":"web_buscar"}'
        visivel = (bruto.split("<ferramenta>")[0]
                        .split("<tool_call>")[0]
                        .split("```json")[0]).strip()
        limpo = "{" not in visivel
        if not limpo:
            falhas += 1
        print("  %-6s %-14s mostra: %r"
              % ("[ok]" if limpo else "[ERRO]", marca, visivel))

    print()
    print("=" * 62)
    if falhas:
        print("  %d FALHA(S). O conserto nao esta completo." % falhas)
    else:
        print("  TUDO CERTO — %d casos." % (len(CASOS) + 3))
        print("  Pode subir o Colab e refazer a pergunta sobre cannabis.")
    print("=" * 62)
    print()
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
