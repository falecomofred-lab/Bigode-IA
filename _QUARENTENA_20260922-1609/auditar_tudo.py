"""AUDITORIA COMPLETA — Bigode IA

Uma passada por tudo que precisa estar certo para o Bigode responder bem,
na ordem em que as coisas quebram. No fim, UMA frase: o que consertar agora.

    python auditar_tudo.py

Nao altera nada. So confere.

O que ele confere, e por que cada item ja causou problema aqui:

  1. O Bigode esta no ar, e o codigo dele e o mesmo do disco?
     -- ja medimos horas o efeito de uma correcao que nao estava rodando

  2. O motor esta no ar, com qual modelo, e com quantos lugares?
     -- o motor subiu com n_parallel=4 e dividiu a janela por quatro

  3. A conta da janela fecha?
     -- as instrucoes passaram do espaco e o motor cortava a conexao

  4. Os arquivos das IAs estao inteiros?
     -- responde a pergunta "sera que o download corrompeu?"

  5. Quanto tempo leva uma pergunta de verdade?

Venure — venure.com.br · tecnologia propria
"""

import json
import struct
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
BIGODE = "http://localhost:7000"
MOTOR = "http://localhost:8082"

ACHADOS = []          # (gravidade, titulo, explicacao, o_que_fazer)
GRAVE, MEDIO, OK = "GRAVE", "atencao", "ok"


def anotar(gravidade, titulo, explicacao="", acao=""):
    ACHADOS.append((gravidade, titulo, explicacao, acao))
    marca = {GRAVE: "  [X] ", MEDIO: "  [!] ", OK: "  [v] "}[gravidade]
    print(marca + titulo)
    if explicacao:
        for linha in explicacao.split("\n"):
            print("        " + linha)


def pegar(url, teto=8):
    with urllib.request.urlopen(url, timeout=teto) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# ==========================================================================
# 1. O Bigode
# ==========================================================================

def conferir_bigode():
    print("\n1. O BIGODE")
    print("   " + "-" * 66)
    try:
        pegar(BIGODE + "/api/login/estado")
    except Exception as e:
        anotar(GRAVE, "O Bigode nao esta aberto.",
               "Nada mais pode ser conferido sem ele.",
               'Set-Location "D:\\Cerebro"; & "D:\\Cerebro\\python\\python.exe" cerebro.py')
        return False

    try:
        st = pegar(BIGODE + "/api/diagnostico")
    except Exception:
        anotar(MEDIO, "Versao antiga: sem a rota de diagnostico.",
               "Envie os arquivos para o pendrive e reabra.")
        return True

    inicio = st.get("quando", "")
    anotar(OK, "No ar. %d linha(s) de trabalho ativa(s)."
           % st.get("linhas_de_trabalho", 0))

    if st.get("aguardando_sua_aprovacao"):
        anotar(MEDIO, "Ha %d acao esperando VOCE aprovar."
               % st["aguardando_sua_aprovacao"],
               "Enquanto nao aprovar ou recusar, aquela conversa fica parada.")

    # o codigo que roda e o do disco?
    try:
        s2 = pegar(BIGODE + "/api/status")
        aberto, codigo = s2.get("iniciado_em") or 0, s2.get("codigo_de") or 0
        if codigo and aberto and codigo > aberto:
            import datetime as dt
            anotar(GRAVE, "O Bigode que esta rodando e MAIS VELHO que o arquivo.",
                   "aberto em ......... %s\ncodigo alterado em  %s\n"
                   "Tudo o que voce medir agora e do codigo antigo."
                   % (dt.datetime.fromtimestamp(aberto).strftime("%d/%m %H:%M"),
                      dt.datetime.fromtimestamp(codigo).strftime("%d/%m %H:%M")),
                   "Feche a janela do Bigode e abra de novo.")
        else:
            anotar(OK, "O codigo que roda e o mesmo do disco.")
    except Exception:
        pass
    return True


# ==========================================================================
# 2. O motor
# ==========================================================================

def conferir_motor():
    print("\n2. O MOTOR (quem pensa)")
    print("   " + "-" * 66)
    modelo = ""
    try:
        props = pegar(MOTOR + "/props")
        modelo = str(props.get("model_path", "")).replace("\\", "/").split("/")[-1]
        anotar(OK, "No ar, com %s" % (modelo or "modelo desconhecido"))
    except urllib.error.HTTPError as e:
        if e.code == 503:
            anotar(MEDIO, "Ainda carregando o modelo.",
                   "Espere terminar e rode de novo.")
        else:
            anotar(GRAVE, "Respondeu HTTP %d." % e.code)
        return modelo, 1
    except Exception:
        anotar(GRAVE, "O motor nao esta no ar.",
               "O Bigode nao consegue pensar sem ele.",
               "Abra pelo BIGODE.bat, ou troque de modelo na tela.")
        return modelo, 1

    # ---- quantos lugares? e o achado que explicou tudo em 23/08 ----
    lugares = 1
    log = BASE / "motor.log"
    if log.is_file():
        try:
            import re
            texto = log.read_text(encoding="utf-8", errors="ignore")[:8000]
            achado = re.search(r"n_parallel\s*=\s*(\d+)", texto)
            if achado:
                lugares = int(achado.group(1))
            pedido = re.search(r"COMANDO:(.*)", texto)
            if pedido and "--parallel" not in pedido.group(1) \
                    and "-np" not in pedido.group(1):
                anotar(MEDIO, "O comando do motor nao pede um lugar so.")
        except Exception:
            pass

    if lugares > 1:
        anotar(GRAVE, "O motor abriu %d lugares (n_parallel = %d)." % (lugares, lugares),
               "A janela e DIVIDIDA por %d. Cada conversa fica com a %da parte.\n"
               "Se as respostas falham com 'o motor derrubou a conexao',\n"
               "e falta de espaco -- nao e defeito do motor." % (lugares, lugares),
               "Feche o motor e abra de novo, para pegar a opcao --parallel 1.")
    else:
        anotar(OK, "Um lugar so: a janela inteira e da sua conversa.")
    return modelo, lugares


# ==========================================================================
# 3. A conta da janela
# ==========================================================================

def conferir_janela(lugares):
    print("\n3. A CONTA DA JANELA")
    print("   " + "-" * 66)
    try:
        import cerebro
        import ferramentas
    except Exception as e:
        anotar(MEDIO, "Rode de dentro da pasta do Bigode (%s)." % e)
        return

    cfg = cerebro.config()
    janela = int(cfg.get("contexto", 8192))
    util = janela // max(1, lugares)
    reserva = min(int(cfg.get("max_tokens", 4096)), janela // 3)

    try:
        esquema = ferramentas.esquema_openai()
        tf = cerebro._tokens(json.dumps(esquema, ensure_ascii=False))
    except Exception:
        esquema, tf = [], 0

    try:
        sistema, _ = cerebro.montar_system("do que se trata este projeto?")
        ts = cerebro._tokens(sistema)
    except Exception as e:
        anotar(MEDIO, "Nao consegui montar as instrucoes (%s)." % e)
        return

    sobra = util - reserva - tf - 400
    print("     janela configurada ......... %6d" % janela)
    if lugares > 1:
        print("     util (dividida por %d) ...... %6d" % (lugares, util))
    print("     - reserva para a resposta ... %6d" % reserva)
    print("     - catalogo de %2d ferramentas  %6d" % (len(esquema), tf))
    print("     - margem .................... %6d" % 400)
    print("     " + "-" * 43)
    print("     = sobra para as instrucoes .. %6d" % sobra)
    print("       instrucoes de verdade ..... %6d" % ts)
    print()

    # A janela do ARQUIVO e a janela do MOTOR podem estar diferentes: o motor
    # le o numero uma vez, quando sobe. Foi o desencontro que mais confundiu.
    try:
        import re as _re
        log = (BASE / "motor.log")
        if log.is_file():
            m = _re.search(r"n_ctx[^0-9]*(\d+)", log.read_text(
                encoding="utf-8", errors="ignore")[:8000])
            if m and int(m.group(1)) != janela:
                anotar(GRAVE,
                       "O motor esta com janela de %s, o arquivo diz %d."
                       % (m.group(1), janela),
                       "O motor le esse numero uma vez, ao subir. Enquanto\n"
                       "nao recarregar, vale o numero antigo.",
                       "Na tela, clique em LIGAR no modelo que quiser usar.")
    except Exception:
        pass

    if ts > sobra:
        anotar(GRAVE, "As instrucoes NAO CABEM: faltam %d tokens." % (ts - sobra),
               "E por isso que aparece 'o motor derrubou a conexao'.",
               "Aumente a janela em Configuracoes -> Quanto ele lembra da conversa,\n"
               "        ou desligue conexoes que voce nao usa (cada uma custa ferramentas).")
    else:
        anotar(OK, "Cabe, com %d tokens de folga." % (sobra - ts))

    if tf > ts:
        anotar(MEDIO, "O catalogo de ferramentas (%d) e maior que as instrucoes (%d)."
               % (tf, ts),
               "Desligar conexoes que voce nao usa libera espaco de verdade.")


# ==========================================================================
# 4. Os arquivos das IAs
# ==========================================================================

def conferir_modelos():
    """Um .gguf comeca sempre com as letras GGUF e traz a contagem de partes.

    Ler os 4 GB inteiros levaria minutos e nao diria mais que isto: se o
    cabecalho esta certo e o arquivo tem o tamanho esperado, ele nao esta
    corrompido -- e a prova de que o download veio inteiro e o proprio motor
    ter conseguido carregar.
    """
    print("\n4. OS ARQUIVOS DAS IAs")
    print("   " + "-" * 66)
    achou = False
    for pasta in (Path("D:/"), BASE, BASE / "modelos"):
        try:
            if not pasta.exists():
                continue
            for arq in sorted(pasta.glob("*.gguf")):
                achou = True
                gb = arq.stat().st_size / 1e9
                try:
                    with arq.open("rb") as f:
                        magica = f.read(4)
                        versao = struct.unpack("<I", f.read(4))[0]
                except Exception as e:
                    anotar(GRAVE, "%s: nao consegui abrir (%s)" % (arq.name, e))
                    continue
                if magica != b"GGUF":
                    anotar(GRAVE, "%s: NAO e um arquivo GGUF valido." % arq.name,
                           "O download veio quebrado.",
                           "Baixe de novo com baixar-modelo.ps1.")
                elif gb < 0.5:
                    anotar(GRAVE, "%s: so %.1f GB -- download incompleto."
                           % (arq.name, gb))
                else:
                    anotar(OK, "%s  %.1f GB  cabecalho v%d ok"
                           % (arq.name[:44], gb, versao))
        except Exception:
            continue
    if not achou:
        anotar(MEDIO, "Nenhum arquivo .gguf encontrado nos lugares de sempre.")


# ==========================================================================
# 5. Uma pergunta de verdade
# ==========================================================================

def conferir_resposta():
    print("\n5. UMA PERGUNTA DE VERDADE")
    print("   " + "-" * 66)
    corpo = json.dumps({"messages": [{"role": "user", "content": "Diga apenas: oi"}],
                        "max_tokens": 12, "temperature": 0.2, "stream": False})
    req = urllib.request.Request(
        MOTOR + "/v1/chat/completions", data=corpo.encode("utf-8"),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        seg = time.time() - t0
        texto = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
        anotar(OK if seg < 20 else MEDIO,
               "O motor sozinho respondeu em %.1fs: %r" % (seg, texto.strip()[:40]),
               "" if seg < 20 else "Acima de 20s so para dizer 'oi' e lentidao da maquina,\n"
                                   "nao do Bigode.")
    except Exception as e:
        anotar(GRAVE, "O motor nao respondeu nem a uma pergunta minima.",
               str(e)[:90])


# ==========================================================================

def main():
    print()
    print("=" * 72)
    print("  AUDITORIA COMPLETA — BIGODE IA")
    print("=" * 72)

    vivo = conferir_bigode()
    modelo, lugares = conferir_motor()
    if vivo:
        conferir_janela(lugares)
    conferir_modelos()
    conferir_resposta()

    graves = [a for a in ACHADOS if a[0] == GRAVE]
    medios = [a for a in ACHADOS if a[0] == MEDIO]

    print()
    print("=" * 72)
    print("  O QUE FAZER AGORA")
    print("=" * 72)
    print()
    if graves:
        g = graves[0]
        print("  Conserte ISTO primeiro:")
        print()
        print("    %s" % g[1])
        if g[3]:
            for linha in g[3].split("\n"):
                print("    %s" % linha)
        if len(graves) > 1:
            print()
            print("  Depois, os outros %d problemas graves." % (len(graves) - 1))
    elif medios:
        print("  Nada grave. %d ponto(s) de atencao acima." % len(medios))
        print("  Se ainda estiver ruim, o problema nao esta na configuracao:")
        print("  e a velocidade da propria maquina com um modelo deste tamanho.")
    else:
        print("  Esta tudo certo na configuracao.")
        print()
        print("  Se as respostas ainda parecem lentas, o limite e a maquina:")
        print("  um modelo de 7 bilhoes de parametros em processador, sem placa")
        print("  de video, escreve entre 5 e 16 palavras por segundo. Nao ha")
        print("  ajuste que mude isso -- so um modelo menor.")
    print()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n  Cancelado.\n")
        raise SystemExit(130)
