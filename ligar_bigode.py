"""LIGAR O BIGODE   -   celula 7

Sobe o cerebro.py na porta 7000 e ajusta a configuracao para o Linux.

O AJUSTE NAO E DETALHE
    O config.json que veio do Drive e o do Windows: aponta o motor para D:\\
    e os projetos para G:\\. Subir sem reaplicar isso significa um Bigode que
    procura um motor que nao existe -- e a mensagem que aparece na tela nao
    diz nada disso.

    Por isso o ajuste mora AQUI, junto de quem liga, e nao numa celula
    separada que da para esquecer de rodar.

DEPENDE DE
    Nada. Se a celula 3 nao rodou, avisa e para -- porque sem o codigo
    copiado nao ha o que ligar.

Venure - venure.com.br
"""

import os
import subprocess
import time
import urllib.request
from pathlib import Path

CASA = Path("/content/bigode")
PORTA = 7000
RAIZ_DRIVE = Path("/content/drive/MyDrive")
CATALOGO_PY = RAIZ_DRIVE / "projetos/Cerebro/catalogo_ia.py"


def _no_ar():
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/api/login/estado" % PORTA,
                               timeout=3)
        return True
    except Exception:
        return False


print()
print("=" * 66)
print("  LIGANDO O BIGODE")
print("=" * 66)

if not (CASA / "cerebro.py").is_file():
    raise SystemExit(
        "Nao ha codigo em %s. Rode a celula 3 (trazer o Bigode)." % CASA)

# ---- adaptar para Linux ---------------------------------------------------
#
# A adaptacao mora no adaptar.py, e nao aqui dentro. Ela precisa acontecer
# em tres momentos -- celula 5, aqui, e ao atualizar o codigo -- e o mesmo
# trecho copiado em tres lugares e como se cria diferenca entre eles: alguem
# conserta um e esquece os outros.
_ADAPTAR = (RAIZ_DRIVE / "projetos/Cerebro/adaptar.py")
if not _ADAPTAR.is_file():
    raise SystemExit("Nao achei %s. Rode o sincronizar-bigode.ps1."
                     % _ADAPTAR)
_ADAPTAR_CALADO = True     # quem fala com voce aqui sou eu, nao ele
exec(_ADAPTAR.read_text(encoding="utf-8"), globals())

print("\n  janela ..... %d" % JANELA)                         # noqa: F821
print("  IAs em ..... %s" % PASTA_GGUF)                       # noqa: F821
print("  terminal ... desligado (maquina emprestada)")
print("  navegador .. ligado")

# ---- ligar ----------------------------------------------------------------
subprocess.run("pkill -f cerebro.py", shell=True) if os.name != "nt" else None
time.sleep(2)

_amb = dict(os.environ)
_amb["PYTHONUNBUFFERED"] = "1"      # sem isto o log so aparece no fim
_log = open("/content/bigode.log", "w")
proc_bigode = subprocess.Popen(["python3", "cerebro.py"], cwd=str(CASA),
                               stdout=_log, stderr=subprocess.STDOUT,
                               env=_amb)

print("\n  Subindo", end="")
_vivo = False
for _i in range(45):
    time.sleep(2)
    if _no_ar():
        _vivo = True
        break
    print(".", end="")

print()
print("=" * 66)
if _vivo:
    print("  BIGODE DE PE na porta %d." % PORTA)
    print("  Falta so o tunel -- proxima celula.")
else:
    print("  NAO SUBIU. O que ele disse:")
    print(open("/content/bigode.log").read()[-2500:])
print("=" * 66)
print()
