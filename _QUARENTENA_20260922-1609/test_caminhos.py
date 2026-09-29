"""TESTE — o Bigode acha a pasta certa nos dois sistemas?

09/09, no Colab. O Fred pediu um jogo de damas e entrou num laco de cinco
mensagens:

    Bigode: "a pasta G:\\Meu Drive\\projetos/jogo-damas esta fora das
             pastas liberadas"
    Fred:   "G:\\Meu Drive\\projetos\\jogo-damas esse eh o correto,
             atencao!!!"
    Bigode: (a mesma recusa, de novo)
    Fred:   "ajuste, voce colocou errado"
    Bigode: (a mesma recusa, de novo)

Os dois estavam certos. No computador do Fred o Drive e `G:`. No Colab o
mesmo Drive fica em /content/drive/MyDrive. As skills e a memoria falam
`G:` -- e do lado de la esse caminho nao existe.

Dois defeitos somados:
  1. nao havia traducao entre os dois enderecos
  2. `arrumar_caminho` so aceitava caminho que JA EXISTE -- e uma pasta que
     esta sendo criada, por definicao, ainda nao existe

    python test_caminhos.py

Nao altera nada. So confere.

Venure - venure.com.br
"""

import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import ferramentas as F

falhas = 0


def diz(ok, rotulo, detalhe=""):
    global falhas
    print("  %-6s %s" % ("[ok]" if ok else "[ERRO]", rotulo))
    if detalhe:
        print("         " + detalhe)
    if not ok:
        falhas += 1


print()
print("=" * 70)
print("  O BIGODE ACHA A PASTA CERTA?")
print("  rodando em: %s" % ("Windows" if os.name == "nt" else "Linux/Colab"))
print("=" * 70)
print()

liberadas = [str(p) for p in F._pastas_liberadas()]
print("  Pastas liberadas agora:")
for l in liberadas:
    print("    - " + l)
print()

# ---------------------------------------------------------------------------
print("  1. UMA PASTA QUE JA EXISTE")
print("  " + "-" * 66)
alvo = liberadas[0] if liberadas else str(BASE)
arrumado = F.arrumar_caminho(alvo)
diz(F._permitido(arrumado), "a propria pasta liberada e aceita",
    "%s -> %s" % (alvo, arrumado))
print()

# ---------------------------------------------------------------------------
print("  2. UMA PASTA QUE AINDA NAO EXISTE  (o caso do jogo-damas)")
print("  " + "-" * 66)
novo = str(Path(alvo) / "pasta-que-ainda-nao-existe-teste")
arrumado = F.arrumar_caminho(novo)
ok = F._permitido(arrumado)
diz(ok, "criar dentro de pasta liberada e aceito",
    "%s -> %s" % (novo, arrumado))
if not ok:
    print("         Este e exatamente o defeito de 09/09: o Bigode recusava")
    print("         criar uma pasta nova dentro de um lugar permitido.")
print()

# ---------------------------------------------------------------------------
print("  3. TRADUCAO ENTRE WINDOWS E COLAB")
print("  " + "-" * 66)
if os.name == "nt":
    print("     (a traducao G: -> /content so age em Linux; aqui apenas")
    print("      conferimos que o caminho do Windows continua funcionando)")
    a = F.arrumar_caminho(r"G:\Meu Drive\projetos")
    diz("Meu Drive" in a or "projetos" in a, "caminho do Drive reconhecido",
        "resultado: %s" % a)
else:
    a = F.arrumar_caminho(r"G:\Meu Drive\projetos")
    diz(a.startswith("/content/drive"),
        "G:\\Meu Drive vira /content/drive/MyDrive", "resultado: %s" % a)
    b = F.arrumar_caminho(r"G:\Meu Drive\projetos\jogo-damas")
    diz(b.startswith("/content/drive"),
        "o caso real do jogo-damas", "resultado: %s" % b)
    diz(F._permitido(b), "e o resultado passa na cerca")
print()

# ---------------------------------------------------------------------------
print("  4. O QUE TEM DE CONTINUAR BARRADO")
print("  " + "-" * 66)
for proibido in ([r"C:\Windows\System32", r"C:\Users\Frederico\AppData"]
                 if os.name == "nt" else ["/etc", "/root", "/usr/bin"]):
    diz(not F._permitido(proibido), "barra %s" % proibido)
print()

print("=" * 70)
if falhas:
    print("  %d FALHA(S)." % falhas)
else:
    print("  TUDO CERTO. Ele acha a pasta e respeita a cerca.")
print("=" * 70)
print()
raise SystemExit(1 if falhas else 0)
