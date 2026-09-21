"""PIPI NO COLAB — sobe o ComfyUI e publica, sem o Bigode no meio

Celula unica do notebook da Pipi.

POR QUE UM ARQUIVO SO PARA ISTO
    Ate hoje, usar o ComfyUI do Colab exigia rodar as celulas 1 a 7 do
    notebook do Bigode -- baixar um .gguf de TEXTO de 4 GB, instalar o
    llama.cpp, subir o cerebro -- para so entao chegar na celula 10.

    Nada disso tem a ver com desenhar. Sao uns seis minutos e uns 5 GB
    de download para ligar uma coisa que nao depende de nenhum deles.

    Aqui a Pipi tem o proprio caminho: instala o ComfyUI, baixa as
    quatro pecas do FLUX e publica. So isso.

O QUE ELE REAPROVEITA
    O `desenhista.py` e o `tuneis.py` do Cerebro, que ja existem e ja
    foram consertados. Copiar o codigo para ca criaria duas versoes que
    divergem no primeiro conserto.

Venure - venure.com.br
"""

import sys
import urllib.request
from pathlib import Path

CEREBRO = Path("/content/drive/MyDrive/projetos/Cerebro")
PORTA = 8188

for _onde in (str(CEREBRO), "/content/bigode"):
    if _onde not in sys.path:
        sys.path.insert(0, _onde)

print()
print("=" * 70)
print("  PIPI IA  --  o desenhista no Colab")
print("=" * 70)

if not CEREBRO.is_dir():
    raise SystemExit(
        "\n  Nao achei %s.\n"
        "  O Drive foi montado? Rode a celula 1.\n" % CEREBRO)


def _no_ar():
    try:
        urllib.request.urlopen(
            "http://127.0.0.1:%d/system_stats" % PORTA, timeout=4)
        return True
    except Exception:
        return False


# ---- 1. o desenhista --------------------------------------------------
# O desenhista.py ja confere se esta no ar antes de instalar de novo, e
# ja sabe baixar as quatro pecas com espelho quando o repositorio oficial
# fecha. Nao ha por que repetir nada disso aqui.
if _no_ar():
    print("\n  O ComfyUI ja esta de pe. Pulando a instalacao.")
else:
    print("\n  Instalando e subindo o ComfyUI...")
    exec((CEREBRO / "desenhista.py").read_text(encoding="utf-8"), globals())

if not _no_ar():
    raise SystemExit(
        "\n  O ComfyUI nao subiu. O motivo esta na saida acima.\n")

# ---- 2. publicar ------------------------------------------------------
import tuneis                                                # noqa: E402

print()
LINK = tuneis.abrir(PORTA, "o desenhista")

print()
print("=" * 70)

if not LINK:
    raise SystemExit("  Sem link. O motivo esta acima.\n")

print()
print("  A PIPI JA PODE DESENHAR DAQUI:")
print()
print("      " + LINK)
print()
print("  " + "-" * 66)
print("  NO SEU WINDOWS, na pasta da Pipi IA:")
print()
print("    python usar_desenhista_do_colab.py")
print()
print("  Cole o endereco acima. Ele testa e mostra qual placa respondeu")
print("  -- se aparecer Tesla T4, chegou no lugar certo.")
print()
print("  Depois:  pipi.bat")
print("  " + "-" * 66)
print()
print("  O ComfyUI NAO TEM SENHA. Enquanto este link estiver de pe, quem")
print("  tiver o endereco desenha na sua placa e ve as suas imagens.")
print("  Nao compartilhe, e rode a ultima celula ao terminar.")
print()
print("  Mexa na aba de vez em quando: 90 min parado e o Colab desliga.")
print("=" * 70)
print()
