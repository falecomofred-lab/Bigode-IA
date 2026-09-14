"""MEDIR FLUIDEZ — Bigode IA

Por que conversar pelo motor direto parece mais solto do que pelo Bigode?

A janela do llama.cpp manda a sua frase e mais NADA: sem instrucoes, sem
ferramentas, sem trava. O Bigode manda 2.500 tokens de instrucao, o catalogo
de ferramentas, e ainda pode DESCARTAR a resposta que ja comecou a aparecer
para obrigar o modelo a pesquisar antes.

Essa trava existe por um bom motivo -- foi ela que levou a invencao de 5/5
para 1/5. Mas ela dispara por PALAVRA, e a lista de palavras inclui coisas
comuns: "quando", "quantos", "compare", "atualmente", "valor de", "data".

Uma frase do dia a dia como "compare essas duas opcoes" aciona a trava. O
texto comeca a sair, some da tela, e o modelo e mandado pesquisar. Nao e
lentidao: e o fluxo sendo interrompido.

Este script mede isso. Para cada frase, mostra:

    motor    segundos ate a primeira letra falando DIRETO com o motor
    bigode   o mesmo, passando pelo Bigode
    trava    se a resposta foi descartada e recomecada
    palavra  qual palavra da lista acionou a trava

    python medir_fluidez.py

Ele NAO altera nada. So mede.

Venure — venure.com.br · tecnologia propria
"""

import json
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
MOTOR = "http://localhost:8082/v1/chat/completions"
BIGODE = "http://localhost:7000"

# Frases de conversa normal. Nenhuma delas pede arquivo nem fato do mundo --
# sao o tipo de coisa que voce escreve o dia inteiro.
FRASES = [
    "Me explique com suas palavras o que é uma função em Python.",
    "Compare duas formas de organizar uma pasta de projeto.",
    "Quantos passos você costuma dar antes de responder?",
    "Atualmente, qual é o seu jeito de trabalhar comigo?",
    "Escreva um texto curto de apresentação para a Venure.",
    "Bom dia! Como você está hoje?",
]


def falar_com_motor(frase, teto=180):
    """Sem instrucao nenhuma: e assim que a janela do llama.cpp conversa."""
    corpo = json.dumps({"messages": [{"role": "user", "content": frase}],
                        "max_tokens": 40, "temperature": 0.3, "stream": True})
    req = urllib.request.Request(
        MOTOR, data=corpo.encode("utf-8"),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=teto) as r:
            for linha in r:
                if b'"content"' in linha:
                    return round(time.time() - t0, 1)
    except Exception:
        return None
    return None


def falar_com_bigode(token, frase, teto=420):
    """Pelo caminho de verdade. Conta tambem se a resposta foi descartada."""
    corpo = json.dumps({"mensagens": [{"role": "user", "content": frase}]})
    req = urllib.request.Request(
        BIGODE + "/api/chat", data=corpo.encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "X-Cerebro-Sessao": token, "Accept": "text/event-stream"})
    t0 = time.time()
    primeiro, descartes, acoes, total = None, 0, 0, None
    try:
        with urllib.request.urlopen(req, timeout=teto) as r:
            for linha in r:
                if time.time() - t0 > teto:
                    break
                linha = linha.decode("utf-8", "replace").strip()
                if not linha.startswith("data:"):
                    continue
                try:
                    ev = json.loads(linha[5:].strip())
                except Exception:
                    continue
                tipo = ev.get("tipo")
                if tipo == "texto" and primeiro is None:
                    primeiro = round(time.time() - t0, 1)
                elif tipo == "descartar":
                    descartes += 1
                    primeiro = None        # a contagem recomeca: era isso que sumia
                elif tipo == "acao":
                    acoes += 1
                elif tipo == "fim":
                    total = round(time.time() - t0, 1)
                    break
    except Exception:
        pass
    return primeiro, descartes, acoes, (total or round(time.time() - t0, 1))


def fotografar_travamento(frase):
    """Pergunta ao Bigode onde ele parou, AGORA.

    Travamento nao deixa rastro: nada quebra, nada e registrado. A unica
    forma de ver por dentro e tirar a foto no instante em que acontece --
    e esperar a pessoa correr ate o navegador nao funciona.
    """
    from datetime import datetime
    try:
        req = urllib.request.Request(BIGODE + "/api/diagnostico",
                                     headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return ("(não consegui o diagnóstico: %s — o Bigode pode ter CAÍDO, "
                "não travado. Veja o erros.log.)" % e)

    destino = BASE / ("TRAVAMENTO-%s.json"
                      % datetime.now().strftime("%Y%m%d-%H%M%S"))
    d["frase_que_travou"] = frase
    destino.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return destino


def main():
    import getpass
    import sys
    try:
        import auditar_selo as selo
        import cerebro
    except Exception as e:
        print("\n  Preciso rodar de dentro da pasta do Bigode (%s)\n" % e)
        return 1

    print()
    print("=" * 74)
    print("  POR QUE O BIGODE PARECE MENOS SOLTO QUE O MOTOR DIRETO")
    print("=" * 74)

    try:
        with urllib.request.urlopen(BIGODE + "/api/login/estado", timeout=8) as r:
            json.loads(r.read().decode("utf-8"))
    except Exception:
        print("\n  O Bigode não está aberto em %s.\n" % BIGODE)
        return 1

    email = input("\n  E-mail: ").strip()
    if not email:
        return 0
    senha = getpass.getpass("  Senha (não aparece): ")
    try:
        token = selo.entrar(BIGODE, email, senha)
    except Exception as e:
        print("  %s\n" % e)
        return 1
    finally:
        senha = None

    print("\n  Cada frase vai pelos dois caminhos. Leva alguns minutos.\n")
    print("  %-44s %6s %7s %6s %5s" %
          ("FRASE", "motor", "bigode", "trava", "passos"))
    print("  " + "-" * 72)

    travadas, travou_de_vez = [], []
    for frase in FRASES:
        sys.stdout.write("  %-44s " % frase[:44])
        sys.stdout.flush()

        direto = falar_com_motor(frase)
        primeiro, descartes, acoes, total = falar_com_bigode(token, frase)

        # Qual palavra da lista acionou? Sem isso, "a trava disparou" nao
        # ajuda ninguem a decidir o que mudar.
        gatilho = next((g for g in cerebro.GATILHOS_FONTE
                        if g in frase.lower()), "")
        if not gatilho:
            gatilho = next((g for g in cerebro.GATILHOS
                            if g in frase.lower()), "")

        print("%6s %7s %6s %6d" % (
            ("%.1fs" % direto) if direto else "—",
            ("%.1fs" % primeiro) if primeiro else "—",
            ("sim" if descartes else "não"),
            acoes))

        # Nada voltou E nenhum passo comecou: nao e lentidao, e travamento.
        # A foto tem de ser tirada agora, nao depois.
        if primeiro is None and acoes == 0:
            foto = fotografar_travamento(frase)
            print("      >> TRAVOU. Foto do estado interno guardada em:")
            print("         %s" % foto)
            travou_de_vez.append(str(foto))

        if descartes or gatilho:
            travadas.append((frase, gatilho, descartes))

    print()
    print("=" * 74)
    print("  O QUE ISSO QUER DIZER")
    print("=" * 74)

    if travou_de_vez:
        print()
        print("  O BIGODE PAROU DE RESPONDER durante o teste.")
        print("  Isso e mais grave que falta de fluidez, e vem primeiro.")
        print()
        print("  O estado interno foi fotografado em:")
        for f in travou_de_vez:
            print("    %s" % f)
        print()
        print("  Mande esse arquivo. Ele mostra em que linha do codigo cada")
        print("  parte do Bigode ficou parada -- e a unica forma de saber a")
        print("  causa sem adivinhar.")
        print()
        return

    if travadas:
        print("\n  Frases de conversa normal que acionaram a trava de evidência:\n")
        for frase, gatilho, d in travadas:
            print("    %s" % frase[:64])
            print("      palavra: \"%s\"%s" %
                  (gatilho or "(nenhuma — foi o assunto grudado da conversa)",
                   "   · resposta DESCARTADA e recomeçada" if d else ""))
        print()
        print("  A trava é o que faz o Bigode inventar 1 em 5 em vez de 5 em 5.")
        print("  Mas ela dispara por PALAVRA, não por intenção. Frase comum com")
        print("  \"compare\", \"quantos\" ou \"atualmente\" cai nela sem precisar.")
        print()
        print("  DUAS SAÍDAS, e as duas têm preço:")
        print()
        print("  1. Enxugar a lista de palavras — tirar as mais comuns.")
        print("     Ganha fluidez. Pode deixar passar invenção.")
        print("     MEÇA DEPOIS:  python auditar_selo.py")
        print()
        print("  2. Criar um Especialista de rigor 'livre' para bate-papo,")
        print("     e deixar a trava apertada só no trabalho sério.")
        print("     Não perde nada — mas exige você escolher o modo.")
    else:
        print("\n  Nenhuma frase comum acionou a trava. Se ainda assim o Bigode")
        print("  parece travado, a diferença está no tamanho do prompt e no")
        print("  catálogo de ferramentas, não na trava de evidência.")
    print()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n\n  Cancelado.\n")
        raise SystemExit(130)
