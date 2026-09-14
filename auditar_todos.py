"""AUDITAR TODOS — Bigode IA

Uma passada por TODAS as IAs instaladas: liga cada uma, mede velocidade,
aplica a prova de qualidade, testa o selo de evidencia, desliga e vai para
a proxima. No fim, uma tabela unica.

Por que existe: os outros scripts medem UM modelo -- o que estiver ligado.
Comparar exigia trocar na mao, esperar, rodar, anotar. Tres modelos viravam
uma tarde. Aqui voce roda uma vez e vai fazer outra coisa.

    python auditar_todos.py                 mostra a tabela do que ja foi medido
    python auditar_todos.py --rodar         mede tudo o que falta
    python auditar_todos.py --rodar --tudo  refaz do zero, inclusive o ja medido
    python auditar_todos.py --rodar --incluir-pesados
                                            inclui os que nao cabem na memoria

DUAS REGRAS QUE ESTE SCRIPT NAO QUEBRA:

1. Nao inventa nota. Faltou medir? A celula fica vazia e o modelo fica fora
   da classificacao. Ranking com buraco preenchido por media parece decisao
   informada e nao e.

2. Nao insiste em modelo que nao cabe. A medicao do Qwen3-14B mostrou 843s
   de leitura e 2,7 GB de RAM livre: o Windows passa a usar o disco como
   memoria e a maquina para. Modelo maior que a folga de memoria e pulado,
   com o motivo escrito.

Venure — venure.com.br · tecnologia propria
"""

import argparse
import datetime
import json
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "auditoria"
BIGODE = "http://localhost:7000"
PROPS = "http://localhost:8082/props"

# Folga de memoria exigida alem do tamanho do arquivo. O modelo ocupa mais que
# o .gguf: contexto, cache de atencao e o proprio Windows precisam caber.
FOLGA_GB = 3.0


# ==========================================================================
# Conversa com o Bigode
# ==========================================================================

class PrecisaEntrar(Exception):
    """O Bigode respondeu, mas com a tela de login em vez de dados."""


def pegar(rota, token=None, teto=15):
    """Le uma rota do Bigode.

    Quase tudo aqui exige login. Sem cracha, o servidor NAO devolve erro:
    devolve a pagina de login em HTML, e o json.loads morre com
    "Expecting value: line 1 column 1". Essa mensagem nao diz nada para
    quem esta lendo o terminal, entao a gente traduz.
    """
    cab = {"Accept": "application/json"}
    if token:
        cab["X-Cerebro-Sessao"] = token
    req = urllib.request.Request(BIGODE + rota, headers=cab)
    with urllib.request.urlopen(req, timeout=teto) as r:
        bruto = r.read().decode("utf-8", "replace")
        tipo = (r.headers.get("Content-Type") or "").lower()
        virou_login = ("/login" in r.geturl()) or ("html" in tipo)
    if virou_login or bruto.lstrip()[:1] not in ("{", "["):
        raise PrecisaEntrar()
    return json.loads(bruto)


def mandar(rota, corpo, token=None, teto=60):
    cab = {"Content-Type": "application/json"}
    if token:
        cab["X-Cerebro-Sessao"] = token
    req = urllib.request.Request(BIGODE + rota,
                                 data=json.dumps(corpo).encode("utf-8"),
                                 headers=cab)
    with urllib.request.urlopen(req, timeout=teto) as r:
        return json.loads(r.read().decode("utf-8"))


def ram_livre_gb():
    """Quanta memoria sobra agora. Sem psutil instalado, devolve None e o
    script diz isso em vez de chutar."""
    try:
        import ctypes

        class M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = M(); m.dwLength = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullAvailPhys / (1024 ** 3), 1)
    except Exception:
        pass
    try:
        import psutil
        return round(psutil.virtual_memory().available / (1024 ** 3), 1)
    except Exception:
        return None


def esperar_carregar(minutos):
    """Espera o motor responder. Devolve (carregou, segundos, motivo).

    Nao mente sobre o que falta: se estourou o tempo, diz que estourou.
    """
    t0 = time.time()
    limite = t0 + minutos * 60
    pontos = 0
    while time.time() < limite:
        try:
            with urllib.request.urlopen(PROPS, timeout=8) as r:
                json.loads(r.read().decode("utf-8"))
            print(" pronto em %dmin%02ds." % divmod(int(time.time() - t0), 60))
            return True, round(time.time() - t0, 1), ""
        except urllib.error.HTTPError as e:
            if e.code != 503:
                return False, round(time.time() - t0, 1), "HTTP %d" % e.code
        except Exception:
            pass
        pontos += 1
        if pontos % 6 == 0:
            print(".", end="", flush=True)
        time.sleep(5)
    return (False, round(time.time() - t0, 1),
            "nao carregou em %d min — provavelmente nao cabe na memoria" % minutos)


# ==========================================================================
# Leitura do que ja foi medido
# ==========================================================================

def curto(caminho):
    return str(caminho).replace("\\", "/").split("/")[-1].replace(".gguf", "")


def medidos():
    """{nome_curto: {'velocidade':d, 'qualidade':d, 'selo':d}} — sempre o mais
    recente de cada tipo."""
    fora = {}
    if not SAIDA.is_dir():
        return fora
    for arq in sorted(SAIDA.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except Exception:
            continue
        # A TABELA-*.json e a saida DESTE script. Lida de volta, ela nao tem
        # campo "modelo" e virava uma linha fantasma chamada "?" no relatorio.
        if arq.name.startswith("TABELA-"):
            continue
        if arq.name.startswith("SELO-"):
            alvo = curto(d.get("modelo", ""))
            if alvo:
                fora.setdefault(alvo, {})["selo"] = d
            continue
        nome = curto(d.get("modelo") or
                     d.get("ambiente", {}).get("modelo_carregado", ""))
        if not nome or nome == "?":
            continue
        m = fora.setdefault(nome, {})
        m["qualidade" if arq.name.startswith("QUALIDADE-") else "velocidade"] = d
        m.setdefault("arquivos", []).append(arq.name)
    return fora


def resumir(m):
    """Uma linha de tabela a partir dos arquivos brutos."""
    v, q = m.get("velocidade"), m.get("qualidade")
    linha = {k: None for k in ("escrita", "leitura", "primeiro", "pior_primeiro",
                               "ram_livre", "raciocinio", "programacao",
                                                  "instrucoes", "confianca", "selo")}
    s = m.get("selo")
    if s and s.get("total"):
        linha["selo"] = "%d/%d" % (s["passaram"], s["total"])
    if v:
        testes = [t for t in v.get("testes", []) if not t.get("erro")]
        taxas = [t["tok_por_s"] for t in testes if t.get("tok_por_s")]
        leit = [t.get("leitura_tok_por_s") for t in testes
                if t.get("leitura_tok_por_s")]
        prim = [t["primeiro_token_s"] for t in testes if t.get("primeiro_token_s")]
        if taxas: linha["escrita"] = round(statistics.median(taxas), 2)
        if leit:  linha["leitura"] = round(statistics.median(leit), 1)
        if prim:
            linha["primeiro"] = round(statistics.median(prim), 1)
            linha["pior_primeiro"] = round(max(prim), 1)
        linha["ram_livre"] = v.get("ambiente", {}).get("ram_livre_gb")
        linha["estimado"] = any("contagem_de_tokens" not in t or
                                "ESTIMADA" in str(t.get("contagem_de_tokens", ""))
                                for t in testes)
    if q:
        n = q.get("notas") or {}
        for a, k in (("raciocinio", "raciocinio"), ("programacao", "programacao"),
                     ("instrucoes", "instrucoes"), ("alucinacao", "confianca")):
            linha[k] = n.get(a, {}).get("nota")
    return linha


# ==========================================================================
# Tabela
# ==========================================================================

def num(x, f="%6.1f"):
    return (f % x) if isinstance(x, (int, float)) else "     —"


def tabela(instalados, dados):
    print()
    print("=" * 92)
    print("  TODAS AS IAs DO BIGODE")
    print("=" * 92)

    print("\n  VELOCIDADE  (quanto maior a escrita, melhor;"
          " quanto menor o 1º token, melhor)\n")
    print("  %-30s %7s %7s %7s %8s" %
          ("IA", "escreve", "lê", "1ºtoken", "pior 1º"))
    print("  " + "-" * 88)
    for nome, l in dados:
        print("  %-30s %s %s %s %s%s" % (
            nome[:30], num(l["escrita"], "%7.2f"), num(l["leitura"], "%7.1f"),
            num(l["primeiro"], "%7.1f"), num(l["pior_primeiro"], "%8.1f"),
            "  *" if l.get("estimado") else ""))
    print("\n  escreve/lê = palavras por segundo · 1ºtoken = segundos de espera")

    print("\n  QUALIDADE  (nota de 0 a 10)\n")
    print("  %-30s %10s %8s %8s %11s %9s" %
          ("IA", "raciocínio", "código", "obedece", "IA sozinha", "com selo"))
    print("  " + "-" * 88)
    for nome, l in dados:
        print("  %-30s %s %s %s %s %9s" % (
            nome[:30], num(l["raciocinio"], "%10.1f"), num(l["programacao"], "%8.1f"),
            num(l["instrucoes"], "%8.1f"), num(l["confianca"], "%11.1f"),
            l.get("selo") or "—"))
    print("\n  IA sozinha = nota de não inventar falando direto com o motor")
    print("  com selo   = as MESMAS 5 perguntas passando pelo Bigode")

    if any(l.get("estimado") for _, l in dados):
        print("\n  * medido pela versão antiga, que contava por caractere e")
        print("    errava ~40% para cima. Rode de novo para o número real.")

    # ---- quem nao tem nota nenhuma ----
    nunca = [n for n in instalados if n not in [d[0] for d in dados]]
    if nunca:
        print("\n  NUNCA MEDIDOS (instalados, sem nenhum número):")
        for n in nunca:
            print("    %s" % n[:60])

    # ---- classificacao ----
    print("\n" + "=" * 92)
    print("  QUAL USAR")
    print("=" * 92)

    chaves = ("escrita", "raciocinio", "programacao", "instrucoes", "confianca")
    completos = [(n, l) for n, l in dados
                 if all(isinstance(l[k], (int, float)) for k in chaves)]

    if not completos:
        if not dados:
            print("\n  Nenhuma IA foi medida ainda — a tabela está vazia porque")
            print("  não há um único número, não porque deu erro.")
        else:
            print("\n  NENHUMA IA tem os cinco números. Sem inventar, não dá")
            print("  para classificar. Falta em cada uma:\n")
            for n, l in dados:
                f = [k for k in chaves if not isinstance(l[k], (int, float))]
                if f:
                    print("    %-32s falta: %s" % (n[:32], ", ".join(f)))
        print("\n  Rode:  python auditar_todos.py --rodar\n")
        return

    # Velocidade normalizada contra a mais rápida da lista; qualidade em nota.
    vmax = max(l["escrita"] for _, l in completos) or 1
    for _, l in completos:
        l["pontos"] = round(
            statistics.mean([l["raciocinio"], l["instrucoes"]]) * 10 * 0.30 +
            (l["escrita"] / vmax) * 100 * 0.25 +
            l["programacao"] * 10 * 0.15 +
            l["confianca"] * 10 * 0.30, 1)

    print()
    for i, (n, l) in enumerate(sorted(completos, key=lambda x: -x[1]["pontos"]), 1):
        print("  %dº  %-34s %5.1f pontos" % (i, n[:34], l["pontos"]))

    print("\n  Pesos: raciocínio+obediência 30% · velocidade 25% ·")
    print("         código 15% · NÃO INVENTAR 30%.")
    print("  Não inventar pesa igual a raciocínio de propósito: resposta")
    print("  errada com segurança custa mais caro que resposta lenta.")

    fora = [n for n, l in dados if (n, l) not in completos]
    if fora:
        print("\n  Fora da classificação por falta de número: %s"
              % ", ".join(x[:24] for x in fora))
    print()


# ==========================================================================
# Rodar tudo
# ==========================================================================

def rodar(modelos, args, token):
    py = sys.executable
    total = len(modelos)
    print("\n  Vou medir %d IA(s). Cada uma leva de 20 a 40 minutos." % total)
    print("  Pode deixar rodando e usar o computador para outra coisa.\n")

    feitos = []
    for i, mo in enumerate(modelos, 1):
        # "nome" e o apelido bonito (Venure Rapido); para casar com os arquivos
        # de auditoria vale o nome do arquivo.
        nome = mo.get("arquivo") or curto(mo.get("id", "?"))
        apelido = mo.get("nome") or nome
        gb = mo.get("gb") or 0
        print("=" * 76)
        print("  [%d/%d] %s   %s · %.1f GB" % (i, total, apelido, nome, gb))
        print("=" * 76)

        livre = ram_livre_gb()
        if livre is not None and gb and (livre - gb) < FOLGA_GB \
                and not args.incluir_pesados:
            print("  PULADO: sobram %.1f GB de memória e o arquivo tem %.1f GB."
                  % (livre, gb))
            print("  Sem %.0f GB de folga o Windows usa o disco como memória e"
                  % FOLGA_GB)
            print("  a máquina trava. Use --incluir-pesados para forçar.\n")
            feitos.append({"modelo": nome, "pulado": "não cabe na memória",
                           "ram_livre_gb": livre, "arquivo_gb": gb})
            continue

        print("  Ligando…", end="", flush=True)
        try:
            mandar("/api/modelo", {"caminho": mo["id"]}, token, teto=90)
        except Exception as e:
            print("  não consegui trocar: %s\n" % e)
            feitos.append({"modelo": nome, "erro": str(e)})
            continue

        ok, seg, motivo = esperar_carregar(args.espera)
        if not ok:
            print("\n  FALHOU: %s" % motivo)
            print("  Isso É um resultado: esta IA não serve nesta máquina.\n")
            feitos.append({"modelo": nome, "nao_carregou": motivo,
                           "esperou_s": seg})
            continue

        for script, rotulo in (("auditar_motor.py", "velocidade"),
                               ("auditar_qualidade.py", "qualidade")):
            print("\n  → %s" % rotulo)
            r = subprocess.run([py, str(BASE / script)], cwd=str(BASE))
            if r.returncode:
                print("  (%s terminou com erro %d)" % (script, r.returncode))

        if token and not args.sem_selo:
            print("\n  → selo de evidência")
            try:
                import auditar_selo as selo
                inventou, detalhe = 0, []
                for cod, pergunta in selo.PERGUNTAS:
                    # 6 min por pergunta. O que passa disso nao e resposta
                    # lenta, e o agente preso em algum passo.
                    texto, selos, s = selo.perguntar(BIGODE, token, pergunta,
                                                     teto=360)
                    passou = selo.admitiu(texto) or "nao_verificado" in selos
                    if not passou:
                        inventou += 1
                    detalhe.append({"codigo": cod, "passou": passou,
                                    "segundos": s, "resposta": texto})
                    print("    %s %s (%ds)" % (cod, "ok" if passou else "INVENTOU", s))
                total_s = len(selo.PERGUNTAS)
                print("    selo: %d de %d sem invenção" % (total_s - inventou, total_s))
                # Gravado COM o nome do modelo: sem isso o resultado do selo
                # nao voltava para a tabela e a coluna ficava vazia.
                SAIDA.mkdir(exist_ok=True)
                (SAIDA / ("SELO-%s-%s.json" % (
                    nome[:40], datetime.datetime.now().strftime("%Y%m%d-%H%M")))
                 ).write_text(json.dumps({
                    "modelo": nome, "quando": datetime.datetime.now().isoformat(
                        timespec="seconds"),
                    "passaram": total_s - inventou, "total": total_s,
                    "detalhe": detalhe,
                 }, ensure_ascii=False, indent=2), encoding="utf-8")
                feitos.append({"modelo": nome, "selo_inventou": inventou})
            except Exception as e:
                print("    (não deu para testar o selo: %s)" % e)
        print()

    return feitos


def contas_locais():
    """Os e-mails cadastrados neste Bigode.

    Le o usuarios.json que esta ao lado deste script -- mesma maquina, mesmo
    dono. So o e-mail e usado; a senha guardada ali e um hash e nao serve
    para entrar. Isso existe porque "E-mail ou senha incorretos" nao diz
    QUAL e-mail o Bigode conhece, e adivinhar conta e perda de tempo.
    """
    arq = BASE / "usuarios.json"
    if not arq.is_file():
        return []
    try:
        d = json.loads(arq.read_text(encoding="utf-8"))
    except Exception:
        return []
    lista = d.get("usuarios", d) if isinstance(d, dict) else d
    return [(u.get("email", ""), u.get("nome", ""), bool(u.get("dono")))
            for u in lista if isinstance(u, dict) and u.get("email")]


def escolher_conta(args):
    """Devolve o e-mail. Com uma conta so, nem pergunta."""
    if (args.email or "").strip():
        return args.email.strip()

    contas = contas_locais()
    if not contas:
        return input("  E-mail: ").strip()
    if len(contas) == 1:
        print("  Conta: %s" % contas[0][0])
        return contas[0][0]

    print("\n  Contas cadastradas neste Bigode:")
    for i, (email, nome, dono) in enumerate(contas, 1):
        print("    %d) %-34s %s%s" % (i, email, nome,
                                      "  (dono)" if dono else ""))
    esc = input("\n  Número da conta (ou digite o e-mail): ").strip()
    if esc.isdigit() and 1 <= int(esc) <= len(contas):
        return contas[int(esc) - 1][0]
    return esc


def entrar_agora(args):
    """Pede e-mail e senha uma unica vez e devolve o cracha da sessao.

    A senha e lida com getpass (nao aparece na tela), usada na hora e
    descartada. Nao vai para arquivo, nem para variavel de ambiente, nem
    para a linha de comando -- onde ficaria no historico do PowerShell.
    """
    import getpass
    try:
        import auditar_selo as selo
    except Exception as e:
        print("  Não achei o auditar_selo.py ao lado deste script (%s)." % e)
        return None

    print()
    print("  O Bigode pede login para listar as IAs.")
    for tentativa in (1, 2, 3):
        email = escolher_conta(args)
        if not email:
            return None
        senha = getpass.getpass("  Senha (não aparece enquanto digita): ")
        try:
            token = selo.entrar(BIGODE, email, senha)
            print("  Entrei.\n")
            return token
        except SystemExit as e:
            print("  %s" % e)
            if tentativa == 1:
                donos = [c[0] for c in contas_locais() if c[2]]
                if donos and email not in donos:
                    print("  Dica: a conta de dono deste Bigode é %s."
                          % ", ".join(donos))
                    print("  Cada conta tem a SUA senha — a do dono não abre a outra.")
        except Exception as e:
            print("  Não deu: %s" % e)
        finally:
            senha = None
        args.email = ""                       # erra uma vez, pergunta de novo
        if tentativa == 3:
            print("  Três tentativas. Confira a senha na tela do Bigode.\n")
    return None


# ==========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rodar", action="store_true",
                    help="mede de verdade, em vez de só mostrar a tabela")
    ap.add_argument("--tudo", action="store_true",
                    help="refaz inclusive o que já tem número")
    ap.add_argument("--incluir-pesados", action="store_true",
                    help="não pula os que não cabem na memória")
    ap.add_argument("--espera", type=int, default=20,
                    help="minutos de espera para carregar cada IA")
    ap.add_argument("--email", default="",
                    help="para não digitar o e-mail toda vez")
    ap.add_argument("--sem-selo", action="store_true",
                    help="não testa o selo de evidência")
    args = ap.parse_args()

    # ---- o Bigode esta no ar? ----
    try:
        pegar("/api/login/estado")
    except PrecisaEntrar:
        pass                                   # no ar, so pediu login
    except Exception as e:
        print("\n  O Bigode não respondeu em %s (%s)" % (BIGODE, e))
        print("  Abra o Bigode no notebook e rode de novo.\n")
        return 1

    # ---- entrar ----
    # Listar as IAs ja exige login. Por isso o cracha vem ANTES de tudo,
    # e nao so quando chega a hora de testar o selo.
    token = entrar_agora(args)

    try:
        instalados = pegar("/api/modelos", token).get("modelos", [])
    except PrecisaEntrar:
        print("\n  Continuo sem acesso. E-mail ou senha não conferem.\n")
        return 1
    except Exception as e:
        print("\n  Não consegui listar as IAs: %s\n" % e)
        return 1

    if not instalados:
        print("\n  Nenhuma IA instalada. Baixe uma com:")
        print("  powershell -File baixar-modelo.ps1\n")
        return 1

    instalados = [m for m in instalados if not m.get("incompleto")]
    nomes = [m.get("arquivo") or curto(m.get("id", "")) for m in instalados]
    ja = medidos()

    if args.rodar:
        if not args.tudo:
            fila = [m for m in instalados
                    if not (ja.get(m.get("arquivo") or curto(m.get("id",""))) or {}).get("qualidade")]
            if not fila:
                print("\n  Todas já foram medidas. Use --tudo para refazer.\n")
        else:
            fila = list(instalados)

        if fila:
            rodar(fila, args, token)
            ja = medidos()          # relê o que acabou de ser gravado

    dados = [(n, resumir(m)) for n, m in sorted(ja.items())
             if not n.startswith("_")]
    tabela(nomes, dados)

    if not args.rodar:
        print("  Para medir o que falta:  python auditar_todos.py --rodar\n")

    SAIDA.mkdir(exist_ok=True)
    destino = SAIDA / ("TABELA-%s.json"
                       % datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    destino.write_text(
        json.dumps({"quando": datetime.datetime.now().isoformat(timespec="seconds"),
                    "instalados": nomes,
                    "linhas": {n: l for n, l in dados}},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    # Ctrl+C e uma forma legitima de sair. Despejar 15 linhas de traceback
    # na cara de quem so quis desistir parece que o programa quebrou.
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n\n  Cancelado. Nada foi alterado.\n")
        raise SystemExit(130)
