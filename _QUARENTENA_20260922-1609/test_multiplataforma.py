"""AUDITORIA — o Bigode roda no Windows E no Linux?

Desde 09/09 ele tem duas casas: o pendrive do Fred (Windows) e uma maquina
do Colab (Linux, com GPU). O mesmo codigo, dois sistemas.

Este teste caça o que so funciona num deles. Cada item aqui ja quebrou, ou
quebraria em silencio -- que e pior.

    python test_multiplataforma.py

Nao altera nada. So confere.

Venure - venure.com.br
"""

import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

falhas = []
avisos = []


def conferir(rotulo, ok, detalhe=""):
    print("  %-6s %s" % ("[ok]" if ok else "[ERRO]", rotulo))
    if detalhe:
        print("         " + detalhe)
    if not ok:
        falhas.append(rotulo)


def avisar(rotulo, detalhe=""):
    print("  %-6s %s" % ("[!]", rotulo))
    if detalhe:
        print("         " + detalhe)
    avisos.append(rotulo)


print()
print("=" * 68)
print("  O BIGODE RODA NOS DOIS SISTEMAS?")
print("  rodando agora em: %s" % ("Windows" if os.name == "nt" else "Linux"))
print("=" * 68)
print()

# ---------------------------------------------------------------------------
print("  1. COMANDOS QUE SO EXISTEM NUM SISTEMA")
print("  " + "-" * 64)

PROIBIDOS = {
    "taskkill": "so existe no Windows",
    "os.startfile": "so existe no Windows",
    "CREATE_NO_WINDOW": "so existe no Windows",
    "/dev/null": "so existe em Linux",
    "pkill": "so existe em Linux",
}
for arquivo in sorted(BASE.glob("*.py")):
    if arquivo.name.startswith("test_"):
        continue
    try:
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for termo, porque in PROIBIDOS.items():
        if termo not in texto:
            continue
        # Vale se estiver protegido por uma checagem de sistema.
        protegido = ('os.name == "nt"' in texto or "os.name != 'nt'" in texto
                     or "os.name != \"nt\"" in texto or "platform" in texto)
        if protegido:
            continue
        conferir("%s usa %s sem checar o sistema" % (arquivo.name, termo),
                 False, porque)
if not falhas:
    conferir("nenhum comando preso a um sistema so", True)
print()

# ---------------------------------------------------------------------------
print("  2. CAMINHOS")
print("  " + "-" * 64)
try:
    import ferramentas as F
    # A cauda tem de usar a barra do sistema, nao a do Windows sempre.
    fonte = (BASE / "ferramentas.py").read_text(encoding="utf-8")
    conferir("arrumar_caminho respeita a barra do sistema",
             'os.name != "nt"' in fonte and "cauda" in fonte)
    conferir("letra de unidade (G:\\) so e tentada no Windows",
             'if os.name == "nt":' in fonte)
except Exception as erro:
    conferir("ferramentas.py carrega", False, str(erro))

try:
    import cerebro as C
    # Caminho do Colab tem de virar nome legivel, nao "content > drive > ..."
    bonito = C._lugar("/content/drive/MyDrive/projetos/lucas_garage/app.py")
    conferir("caminho do Colab vira nome legivel", "content" not in bonito,
             "resultado: %s" % bonito)
    bonito_win = C._lugar(r"G:\Meu Drive\projetos\lucas_garage\app.py")
    conferir("caminho do Windows continua legivel", "Drive" in bonito_win,
             "resultado: %s" % bonito_win)
except Exception as erro:
    conferir("cerebro.py carrega", False, str(erro))
print()

# ---------------------------------------------------------------------------
print("  3. O MOTOR")
print("  " + "-" * 64)
try:
    fonte_m = (BASE / "modelos.py").read_text(encoding="utf-8")
    conferir("descarregar() trata Windows e Linux",
             "pkill" in fonte_m and "taskkill" in fonte_m)
    conferir("subir o motor trata Windows e Linux",
             'os.name == "nt"' in fonte_m and "start \"Motor Bigode\"" in fonte_m)
    conferir("modelos.py importa os", re.search(r"^import os$", fonte_m, re.M) is not None)
except Exception as erro:
    conferir("modelos.py legivel", False, str(erro))
print()

# ---------------------------------------------------------------------------
print("  4. O DIARIO ACHA O DRIVE NOS DOIS")
print("  " + "-" * 64)
try:
    import diario
    # Normaliza a barra: no Windows, Path("/content/x") vira "\content\x".
    # Comparar com barra crua daria falso alarme -- e um teste que grita sem
    # motivo ensina a ignorar teste.
    lugares = [str(l).replace("\\", "/") for l in diario.LUGARES]
    conferir("conhece o Drive do Windows",
             any("Meu Drive" in l for l in lugares))
    conferir("conhece o Drive do Colab",
             any("/content/drive" in l for l in lugares),
             "lugares: %s" % lugares)
    conferir("respeita pasta_historico do config",
             "pasta_historico" in (BASE / "diario.py").read_text(encoding="utf-8"))
except Exception as erro:
    conferir("diario.py carrega", False, str(erro))
print()

# ---------------------------------------------------------------------------
print("  5. TUDO COMPILA")
print("  " + "-" * 64)
import py_compile
for arquivo in sorted(BASE.glob("*.py")):
    try:
        py_compile.compile(str(arquivo), doraise=True)
    except Exception as erro:
        conferir("%s compila" % arquivo.name, False, str(erro)[:120])
conferir("todos os .py compilam", not any("compila" in f for f in falhas))
print()

# ---------------------------------------------------------------------------
print("=" * 68)
if falhas:
    print("  %d PROBLEMA(S):" % len(falhas))
    for f in falhas:
        print("    - " + f)
else:
    print("  TUDO ADERENTE. O mesmo codigo roda no pendrive e no Colab.")
if avisos:
    print()
    print("  %d aviso(s) — nao impedem, mas vale olhar." % len(avisos))
print("=" * 68)
print()
raise SystemExit(1 if falhas else 0)
