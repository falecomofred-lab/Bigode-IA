"""A MAQUINA AGUENTA? — Bigode IA

A auditoria mostrou o motor levando 127 segundos so para dizer "Oi", com o
prompt mais curto possivel e limite de 12 palavras. Isso nao e o Bigode: e o
motor sozinho, sem instrucao nenhuma.

Duas explicacoes, e elas pedem decisoes opostas:

  PRIMEIRA VEZ CARA, DEPOIS RAPIDO
      normal. O modelo acabou de carregar e a primeira conta e sempre a mais
      lenta. Nao ha nada para consertar.

  TODAS AS VEZES CARAS
      a maquina nao da conta deste modelo. Nenhum ajuste de prompt, cache ou
      janela muda isso -- so um modelo menor.

Com UMA medicao nao da para saber qual. Este script pergunta "oi" tres vezes
seguidas e mostra as tres.

    python medir_maquina.py

Nao altera nada.

Venure — venure.com.br · tecnologia propria
"""

import json
import time
import urllib.request

MOTOR = "http://localhost:8082/v1/chat/completions"


def perguntar_oi(teto=300):
    corpo = json.dumps({
        "messages": [{"role": "user", "content": "Diga apenas: oi"}],
        "max_tokens": 12, "temperature": 0.2, "stream": False,
        "cache_prompt": True,
    })
    req = urllib.request.Request(
        MOTOR, data=corpo.encode("utf-8"),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=teto) as r:
            r.read()
        return round(time.time() - t0, 1)
    except Exception:
        return None


def main():
    print()
    print("=" * 66)
    print("  A MAQUINA AGUENTA ESTE MODELO?")
    print("=" * 66)
    print("\n  Tres perguntas identicas, a mais simples possivel.\n")

    tempos = []
    for i in (1, 2, 3):
        print("   %d de 3 ..." % i, end="", flush=True)
        seg = perguntar_oi()
        tempos.append(seg)
        print("  %s" % ("%.1fs" % seg if seg else "sem resposta"))

    validos = [t for t in tempos if t]
    print()
    print("=" * 66)
    if len(validos) < 2:
        print("  O motor nao respondeu. Ele esta ligado?\n")
        return 1

    primeira, resto = validos[0], validos[1:]
    tipico = min(resto)

    print("  O QUE ISSO QUER DIZER")
    print("=" * 66)
    print()
    if primeira > tipico * 4:
        print("  A primeira custou %.0fs e as seguintes ~%.0fs." % (primeira, tipico))
        print("  Isso e NORMAL: e o custo de o modelo acordar. Voce paga uma")
        print("  vez por sessao, nao a cada pergunta.")
        print()
        print("  Nao ha nada para consertar aqui.")
    elif tipico > 30:
        print("  Todas levaram mais de 30 segundos (%s)."
              % ", ".join("%.0fs" % t for t in validos))
        print()
        print("  ISTO E A MAQUINA, NAO O BIGODE.")
        print()
        print("  O motor esta sozinho aqui: sem instrucoes, sem ferramentas,")
        print("  sem trava. Se ele leva meio minuto para dizer 'oi', nenhum")
        print("  ajuste no Bigode vai deixar a conversa fluida.")
        print()
        print("  O QUE MUDA DE VERDADE, em ordem:")
        print()
        print("   1. Um modelo MENOR. De 7 bilhoes de parametros para 3 ou 1.")
        print("      python baixar-modelo.ps1  ->  procure por 3B ou 1.5B.")
        print("      Erra mais. Mas responde. Hoje voce tem o contrario.")
        print()
        print("   2. Copiar o modelo do pendrive para o disco do computador.")
        print("      Ler 4 GB pelo USB e mais lento que pelo disco interno.")
        print()
        print("   3. Fechar o que estiver pesando na maquina enquanto usa.")
    elif tipico > 8:
        print("  Tipico de %.0fs. Nao e rapido, mas da para conversar." % tipico)
        print("  Vale tentar o Granite 7B Q4, que foi medido 2,5x mais rapido")
        print("  que o Qwen nesta maquina.")
    else:
        print("  Tipico de %.1fs. O motor esta saudavel." % tipico)
        print("  Se a conversa ainda parece lenta, o custo esta no Bigode --")
        print("  rode:  python auditar_tudo.py")
    print()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n  Cancelado.\n")
        raise SystemExit(130)
