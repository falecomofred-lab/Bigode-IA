"""CONFERIR TUDO - o autoteste do Bigode e da Pipi

Rode de qualquer lugar, sem internet e sem ligar nada:

    python conferir_tudo.py

Ele nao chuta: abre os arquivos, compila cada um e procura as marcas
exatas das correcoes. No fim diz PASSOU ou o que falta.

POR QUE ESTE ARQUIVO EXISTE
    Tres coisas foram consertadas em 13/09 e cada uma toca arquivos
    diferentes, em duas pastas diferentes (Cerebro e Pipi IA). Conferir na
    mao e onde se esquece um. E uma delas -- a trava do Modal -- so apareceu
    porque alguem foi ler o codigo: ligada, ela nao muda nada visivel;
    faltando, o Bigode mente em silencio.

    Um teste que voce roda em dois segundos vale mais do que a minha
    palavra de que esta tudo certo.

Venure - venure.com.br
"""

import ast
import sys
from pathlib import Path

CEREBRO = Path(__file__).resolve().parent
PIPI = CEREBRO.parent / "Pipi IA"

VERDE, VERMELHO, AMARELO, FIM = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
if sys.platform == "win32":
    # O Prompt de Comando antigo mostra os codigos como lixo na tela.
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        VERDE = VERMELHO = AMARELO = FIM = ""

FALHAS = []
AVISOS = []


def ok(texto):
    print("  %s✓%s %s" % (VERDE, FIM, texto))


def falhou(texto, porque):
    print("  %s✗%s %s" % (VERMELHO, FIM, texto))
    print("      %s" % porque)
    FALHAS.append(texto)


def aviso(texto, porque):
    print("  %s!%s %s" % (AMARELO, FIM, texto))
    print("      %s" % porque)
    AVISOS.append(texto)


def _ler(caminho):
    try:
        return caminho.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return ""


def exige(caminho, marcas, rotulo):
    """Todas as marcas precisam estar no arquivo."""
    if not caminho.is_file():
        falhou(rotulo, "arquivo nao existe: %s" % caminho)
        return
    texto = _ler(caminho)
    faltando = [m for m in marcas if m not in texto]
    if faltando:
        falhou(rotulo, "falta no %s: %s" % (caminho.name, faltando[0]))
    else:
        ok(rotulo)


def proibe(caminho, marca, rotulo, porque):
    if not caminho.is_file():
        return
    if marca in _ler(caminho):
        falhou(rotulo, porque)
    else:
        ok(rotulo)


# ==========================================================================
print()
print("=" * 70)
print("  CONFERINDO O BIGODE E A PIPI")
print("=" * 70)

# ---- 1. tudo compila ------------------------------------------------------
print()
print("  1. Os arquivos compilam?")
print("  " + "-" * 66)

quebrados = 0
for pasta in (CEREBRO, PIPI):
    if not pasta.is_dir():
        continue
    for arq in sorted(pasta.glob("*.py")):
        try:
            ast.parse(_ler(arq), filename=str(arq))
        except SyntaxError as erro:
            falhou("%s/%s" % (pasta.name, arq.name),
                   "linha %s: %s" % (erro.lineno, erro.msg))
            quebrados += 1
if not quebrados:
    ok("todos os .py do Cerebro e da Pipi compilam")

# ---- 2. os tuneis nao se matam --------------------------------------------
print()
print("  2. Os tuneis convivem? (item 1)")
print("  " + "-" * 66)

# PROCURAR CHAMADA, NAO PALAVRA   (13/09, consertando o proprio teste)
#
#     A primeira versao destes dois testes deu vermelho em codigo que estava
#     certo, e por duas razoes bobas:
#
#     1. Ela procurava a palavra "pkill -f cloudflared" no texto cru. Mas
#        essa frase aparece nos COMENTARIOS do tunel_motor.py e do
#        tuneis.py, explicando o defeito antigo. O teste acusava a
#        explicacao do conserto como se fosse o defeito.
#
#     2. Ela procurava `127\.0\.0\.1` com uma barra, e no arquivo estao
#        duas -- porque dentro de uma string Python a barra se escreve
#        dobrada.
#
#     A forma de matar TODOS e sempre `subprocess.run("pkill ...")`, com a
#     linha de comando em UMA string. A forma de matar so um usa lista, e
#     nunca casa com este padrao. Procurar a chamada separa os dois sem
#     depender de como o comentario foi escrito.
MATA_GERAL = ('subprocess.run("pkill', "subprocess.run('pkill")

exige(CEREBRO / "tuneis.py",
      ["def abrir", "def derrubar", "cloudflared.*127"],
      "tuneis.py mata por porta, nao todos")

for nome, porta in (("tunel.py", 7000), ("tunel_motor.py", 8082),
                    ("tunel_desenhista.py", 8188)):
    arq = CEREBRO / nome
    if not arq.is_file():
        falhou(nome, "nao existe")
        continue
    texto = _ler(arq)
    if any(m in texto for m in MATA_GERAL):
        falhou(nome, "ainda chama subprocess.run(\"pkill ...\"), que mata "
                     "TODOS os tuneis")
    elif "import tuneis" not in texto:
        falhou(nome, "nao usa o tuneis.py")
    elif "PORTA = %d" % porta not in texto:
        falhou(nome, "nao aponta para a porta %d" % porta)
    else:
        ok("%s usa o tuneis.py (porta %d)" % (nome, porta))

# ---- 3. a chave do motor --------------------------------------------------
print()
print("  3. O motor tem chave? (item 2)")
print("  " + "-" * 66)

exige(CEREBRO / "cerebro.py",
      ['def cabecalhos_llm', '"llm_chave"', 'headers=cabecalhos_llm'],
      "cerebro.py manda o Bearer quando ha chave")

exige(CEREBRO / "ligar_motor.py",
      ['"--api_key"', "CHAVE_MOTOR", '"0.0.0.0"', 'llm_chave'],
      "ligar_motor.py sobe com chave e grava no config")

exige(CEREBRO / "usar_motor_do_colab.py",
      ["llm_chave", "def testar"],
      "usar_motor_do_colab.py grava so depois de testar")

# ---- 4. a trava do Modal --------------------------------------------------
print()
print("  4. O Modal falso e recusado? (item 3)")
print("  " + "-" * 66)

exige(CEREBRO / "modal_cliente.py",
      ["_e_esqueleto", "prompt_recebido", ".invalid"],
      "modal_cliente.py recusa a resposta simulada")

# A ordem importa: a trava precisa vir ANTES da leitura do texto, senao ela
# nunca e alcancada.
mc = _ler(CEREBRO / "modal_cliente.py")
if "_e_esqueleto" in mc and 'dados.get("mensagem")' in mc:
    if mc.index("if _e_esqueleto") < mc.index('dados.get("mensagem")'):
        ok("a trava vem antes de ler a resposta")
    else:
        falhou("ordem da trava do Modal",
               "ela esta depois da leitura -- nunca sera alcancada")

# ---- 5. a Pipi alcanca o Colab --------------------------------------------
print()
print("  5. A Pipi consegue usar o desenhista do Colab?")
print("  " + "-" * 66)

if not PIPI.is_dir():
    aviso("pasta da Pipi", "nao encontrei %s" % PIPI)
else:
    exige(PIPI / "pipi_server.py",
          ["motor_remoto.txt", "_motor_gravado"],
          "pipi_server.py le o motor gravado em arquivo")

    exige(PIPI / "usar_desenhista_do_colab.py",
          ["system_stats", "motor_remoto.txt"],
          "usar_desenhista_do_colab.py existe e testa antes de gravar")

    bat = PIPI / "pipi.bat"
    if not bat.is_file():
        falhou("pipi.bat", "nao existe")
    else:
        texto = _ler(bat)
        if "PIPI_START" not in texto:
            falhou("pipi.bat", "nao tem o desvio para o motor remoto")
        elif "motor_remoto.txt" not in texto:
            falhou("pipi.bat", "nao le o motor_remoto.txt")
        else:
            ok("pipi.bat usa o motor remoto quando ele responde")

    remoto = PIPI / "motor_remoto.txt"
    if remoto.is_file():
        endereco = _ler(remoto).strip()
        print("      motor remoto gravado: %s" % (endereco or "(vazio)"))

# ---- 6. o que esta configurado agora --------------------------------------
print()
print("  6. Como esta a configuracao agora")
print("  " + "-" * 66)

import json                                              # noqa: E402
cfg_arq = CEREBRO / "config.json"
if not cfg_arq.is_file():
    aviso("config.json", "nao existe nesta pasta")
else:
    try:
        cfg = json.loads(_ler(cfg_arq) or "{}")
    except Exception as erro:
        falhou("config.json", "nao e JSON valido: %s" % erro)
        cfg = {}

    provedor = cfg.get("modelo_provedor", "local")
    print("      motor ......... %s" % cfg.get("llm_url", "(padrao)"))
    print("      chave ......... %s"
          % ("sim" if (cfg.get("llm_chave") or "").strip() else "nao"))
    print("      provedor ...... %s" % provedor)
    print("      janela ........ %s" % cfg.get("contexto", "(padrao)"))

    if provedor == "modal" and (cfg.get("modal") or {}).get("ativo"):
        aviso("provedor Modal ligado",
              "o endpoint publicado ainda e o de teste; a trava vai recusar "
              "as respostas. Volte para \"local\" ate publicar um real.")

    url = str(cfg.get("llm_url", ""))
    tem_chave = bool((cfg.get("llm_chave") or "").strip())
    if url.startswith("https://") and not tem_chave:
        falhou("motor publico sem chave",
               "o llm_url aponta para fora mas nao ha llm_chave -- qualquer "
               "um com o endereco usa a sua placa.")

# ---- veredito -------------------------------------------------------------
print()
print("=" * 70)
if FALHAS:
    print("  %sFALTA CONSERTAR %d:%s" % (VERMELHO, len(FALHAS), FIM))
    for f in FALHAS:
        print("    - %s" % f)
else:
    print("  %sPASSOU.%s As tres correcoes estao no lugar." % (VERDE, FIM))
if AVISOS:
    print()
    print("  Avisos (nao impedem de rodar):")
    for a in AVISOS:
        print("    - %s" % a)
print("=" * 70)
print()

sys.exit(1 if FALHAS else 0)
