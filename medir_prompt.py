"""MEDIR O PROMPT — Bigode IA

Toda pergunta que voce faz carrega junto um texto fixo de instrucoes: quem o
Bigode e, como deve se comportar, quais ferramentas existem, quais pastas
pode abrir. Esse texto e LIDO pelo modelo antes de escrever a primeira letra
-- e ler custa tempo.

LICAO DE 19/08/2026: cuidado ao comparar motor frio com motor aquecido.

Este script mediu 7,0s numa conversa nova e eu anunciei que o problema
estava resolvido. Nao estava: aquele motor ja tinha lido as instrucoes em
rodadas anteriores. Com o motor recem-aberto, a mesma conversa nova custou
70,2s.

Por isso agora sao TRES medicoes: duas conversas novas e uma segunda
mensagem. Se a 2a conversa nova for rapida, o texto fixo esta sendo
reaproveitado entre conversas e so a primeira da sessao paga caro.

Este script quebra o texto fixo em pedacos, conta os tokens de CADA UM
perguntando ao proprio motor (nao estimando por caractere, que errava 40%
para cima), e mostra quantos segundos cada pedaco custa na velocidade
medida da IA que esta ligada.

Assim a decisao de cortar deixa de ser palpite: voce ve que o bloco X custa
9 segundos por pergunta e decide se vale.

    python medir_prompt.py

Ele NAO altera nada. So mede.

Venure — venure.com.br · tecnologia propria
"""

import json
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
MOTOR = "http://localhost:8082"
BIGODE = "http://localhost:7000"


def _motor_de_verdade():
    """Onde o motor esta AGORA: nesta maquina ou na placa.

    20/09: este arquivo falava so com `localhost:8082`. Com o motor na
    Modal, `/tokenize` nao responde ali -- e a funcao abaixo caia calada
    para a estimativa por caractere, que ja errou 40% uma vez. A medicao
    continuaria saindo, com numero inventado e sem dizer que era inventado.

    O mesmo config que o cerebro.py le decide aqui tambem. Uma verdade so
    sobre qual motor esta valendo.
    """
    try:
        cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return MOTOR, {}
    if str(cfg.get("modelo_provedor") or "local").lower() != "modal":
        return MOTOR, {}
    m = cfg.get("modal") or {}
    url = str(m.get("url") or "").strip()
    if not url:
        return MOTOR, {}
    base = url.rstrip("/")
    if base.endswith("/v1/chat/completions"):
        base = base[: -len("/v1/chat/completions")]
    cab = {"Content-Type": "application/json"}
    if m.get("token"):
        cab["Authorization"] = "Bearer " + str(m["token"]).strip()
    return base, cab


def tokenizar(texto):
    """Quantos tokens tem este texto, segundo o proprio motor.

    Devolve (quantidade, exato). Se o motor nao souber tokenizar, cai para a
    estimativa por caractere -- mas marcada como estimativa, porque essa conta
    ja nos enganou uma vez.
    """
    base, cab = _motor_de_verdade()
    try:
        req = urllib.request.Request(
            base + "/tokenize",
            data=json.dumps({"content": texto}).encode("utf-8"),
            headers=cab or {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode("utf-8"))
        return len(d.get("tokens", [])), True
    except Exception:
        return int(len(texto) / 3.6), False


def velocidade_de_leitura():
    """Tokens por segundo na LEITURA, da ultima auditoria desta IA.

    Sem esse numero nao da para dizer quanto tempo um bloco custa -- e um
    tempo inventado seria pior que nenhum.
    """
    saida = BASE / "auditoria"
    if not saida.is_dir():
        return None, ""
    arqs = sorted((a for a in saida.glob("*.json")
                   if not a.name.startswith(("QUALIDADE-", "SELO-", "TABELA-"))),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    for a in arqs:
        try:
            d = json.loads(a.read_text(encoding="utf-8"))
        except Exception:
            continue
        taxas = [t.get("leitura_tok_por_s") for t in d.get("testes", [])
                 if t.get("leitura_tok_por_s")]
        if taxas:
            # A leitura do prompt LONGO e a que importa: e o caso real.
            return min(taxas), a.name
    return None, ""


def primeiro_token(token, mensagens, teto=600):
    """Segundos ate a primeira letra aparecer, pelo caminho REAL (/api/chat).

    Isto NAO e o mesmo que o auditar_motor.py mede. Aquele fala direto com o
    motor, sem as instrucoes do Bigode. Aqui vai tudo junto, como quando voce
    digita na tela.
    """
    corpo = json.dumps({"mensagens": mensagens})
    req = urllib.request.Request(
        BIGODE + "/api/chat", data=corpo.encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "X-Cerebro-Sessao": token, "Accept": "text/event-stream"})
    import time
    t0 = time.time()
    primeiro, resposta = None, ""
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
            if ev.get("tipo") == "texto":
                if primeiro is None:
                    primeiro = round(time.time() - t0, 1)
                resposta += ev.get("texto", "")
            elif ev.get("tipo") == "fim":
                break
    return primeiro, resposta.strip()


def medir_de_verdade():
    """Compara conversa NOVA (cache frio) com a segunda mensagem (cache quente).

    Sem esta medicao, os 308s da tabela sao teoria: talvez o motor guarde o
    texto fixo e voce nunca pague. Melhor descobrir antes de cortar instrucao
    que segura invencao.
    """
    import getpass
    try:
        import auditar_selo as selo
    except Exception as e:
        print("  Preciso do auditar_selo.py ao lado (%s)\n" % e)
        return

    print("\n" + "=" * 70)
    print("  AGORA NO CAMINHO REAL")
    print("=" * 70)

    # Conferir ANTES de pedir a senha. Fazer alguem digitar e-mail e senha
    # para so entao descobrir que o servidor esta fechado e desrespeitoso --
    # e foi o que este script fez na primeira versao.
    try:
        with urllib.request.urlopen(BIGODE + "/api/login/estado", timeout=8) as r:
            json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("\n  O Bigode nao esta aberto em %s." % BIGODE)
        print("  (o MOTOR esta ligado — os tokens acima vieram dele — mas a")
        print("   janela do Bigode, nao. Sao dois programas.)")
        print("\n  Abra assim, em outra janela do PowerShell:")
        print('     Set-Location "D:\\Cerebro"; & "D:\\Cerebro\\python\\python.exe" cerebro.py')
        print("\n  Depois rode:  python medir_prompt.py --real\n")
        return

    # ---- o Bigode no ar e o mesmo codigo que esta no disco? ----
    # Sem esta checagem da para passar a noite medindo o efeito de uma
    # correcao que nunca entrou em execucao.
    try:
        with urllib.request.urlopen(BIGODE + "/api/status", timeout=8) as r:
            st = json.loads(r.read().decode("utf-8"))
        inicio, codigo = st.get("iniciado_em") or 0, st.get("codigo_de") or 0
        if not inicio:
            print("\n  (este Bigode e anterior a esta checagem — se voce")
            print("   acabou de copiar arquivos, feche e abra antes de medir)")
        elif codigo > inicio:
            import datetime as dt
            print("\n  ATENCAO: o Bigode que esta rodando e MAIS VELHO que o")
            print("  cerebro.py do disco.")
            print("    aberto em .......... %s"
                  % dt.datetime.fromtimestamp(inicio).strftime("%d/%m %H:%M:%S"))
            print("    codigo alterado em . %s"
                  % dt.datetime.fromtimestamp(codigo).strftime("%d/%m %H:%M:%S"))
            print("\n  O que voce medir agora e do codigo ANTIGO. Feche a janela")
            print("  do Bigode, abra de novo e repita.\n")
            if input("  Medir assim mesmo? (s/N) ").strip().lower() != "s":
                return
    except Exception:
        pass

    email = input("\n  E-mail: ").strip()
    if not email:
        return
    senha = getpass.getpass("  Senha (nao aparece): ")
    try:
        tok = selo.entrar(BIGODE, email, senha)
    except Exception as e:
        print("  %s\n" % e)
        return
    finally:
        senha = None

    P1 = "Escreva apenas a palavra: pronto"
    P2 = "Escreva apenas a palavra: certo"

    # TRES medicoes, nao duas. Com duas eu tirei a conclusao errada:
    # medi uma conversa nova num motor que JA tinha lido as instrucoes antes,
    # vi 7 segundos e anunciei que o problema estava resolvido. Nao estava --
    # so estava aquecido. A pergunta certa e se a SEGUNDA conversa nova
    # aproveita o que a primeira leu.
    print("\n  1ª conversa nova…", end="", flush=True)
    frio, r1 = primeiro_token(tok, [{"role": "user", "content": P1}])
    print(" %s" % ("%.1fs" % frio if frio else "sem resposta"))

    print("  2ª conversa nova (outra do zero)…", end="", flush=True)
    frio2, _ = primeiro_token(tok, [{"role": "user", "content": P2}])
    print(" %s" % ("%.1fs" % frio2 if frio2 else "sem resposta"))

    print("  Segunda mensagem na MESMA conversa…", end="", flush=True)
    quente, _ = primeiro_token(tok, [{"role": "user", "content": P1},
                                     {"role": "assistant", "content": r1 or "pronto"},
                                     {"role": "user", "content": P2}])
    print(" %s" % ("%.1fs" % quente if quente else "sem resposta"))

    print()
    if frio and frio2 and quente:
        if frio2 <= quente * 3:
            print("  FUNCIONANDO: conversa nova custa o mesmo que continuar uma")
            print("  conversa (%.1fs, %.1fs, %.1fs). O texto fixo esta sendo"
                  % (frio, frio2, quente))
            print("  reaproveitado entre conversas.")
            print()
            print("  NAO HA O QUE CORTAR. Cortar instrucao economizaria uns")
            print("  poucos segundos e levaria junto as regras que seguram a")
            print("  invencao.")
            print()
            print("  Observacao honesta: este script nao sabe se o motor estava")
            print("  frio ou ja aquecido. A espera longa (70 a 90s) so aparece")
            print("  logo depois de o motor carregar o modelo. Para ver o pior")
            print("  caso, feche o motor, abra, espere ficar pronto e rode isto")
            print("  como primeira coisa.")
        else:
            print("  O texto fixo NAO esta sendo aproveitado entre conversas:")
            print("    1ª conversa nova ..... %.1fs" % frio)
            print("    2ª conversa nova ..... %.1fs" % frio2)
            print("    2ª msg da mesma ...... %.1fs" % quente)
            print("  Se as duas conversas novas custam parecido e muito mais que")
            print("  a segunda mensagem, o motor guarda so dentro da conversa.")
            print("  Confira se ha \"cache_prompt\": True no payload do cerebro.py")
            print("  e se o motor foi reaberto depois da mudanca.")
        print()
        return
    if frio and quente:
        if frio > quente * 3:
            print("  O motor NAO esta guardando o texto fixo: a primeira")
            print("  mensagem custou %.0fx a segunda." % (frio / quente))
            print()
            print("  ANTES de cortar instrucao, confira se o Bigode esta")
            print("  pedindo o cache ao motor. Em cerebro.py, no payload que")
            print("  vai para o motor, tem de haver:")
            print('      "cache_prompt": True')
            print("  Sem isso o motor joga fora o que leu e nenhum corte de")
            print("  texto resolve o problema de raiz.")
        else:
            print("  O motor ESTA guardando o texto fixo: %.1fs contra %.1fs."
                  % (frio, quente))
            print("  Voce paga isso uma vez por conversa, nao a cada mensagem.")
            print("  Cortar instrucao renderia pouco e custaria confiabilidade.")
    print()


def main():
    print()
    print("=" * 70)
    print("  QUANTO CUSTA O TEXTO FIXO DE INSTRUCOES")
    print("=" * 70)

    try:
        import cerebro
    except Exception as e:
        print("\n  Nao consegui ler o cerebro.py (%s)\n" % e)
        return 1

    # Os blocos, na ordem em que entram no prompt.
    ler = cerebro.ler
    M = cerebro.MEMORIA
    cfg = cerebro.config()
    catalogo = cerebro.ferramentas.ativas()

    blocos = [
        ("regra do idioma", "Responda SEMPRE em portugues do Brasil."),
        ("identidade.md", ler(M / "identidade.md")),
        ("temperamento.md", ler(M / "temperamento.md")),
        ("sua personalidade", cerebro.bloco_personalidade()),
        ("jeito_de_trabalhar.md", ler(M / "jeito_de_trabalhar.md")),
    ]
    if catalogo:
        if not cerebro.usar_nativas(cfg):
            blocos.append(("lista de ferramentas", cerebro.PROTOCOLO_TEXTO.format(
                lista=cerebro.ferramentas.descrever(catalogo))))
        blocos.append(("como usar ferramentas",
                       cerebro.PROTOCOLO_CURTO if cerebro.prompt_pequeno()
                       else cerebro.PROTOCOLO))
        blocos.append(("pastas liberadas", "\n".join(
            cfg.get("pastas_liberadas", []))))
        blocos.append(("seus manuais", cerebro.habilidades.resumo_para_prompt()))

    tok_s, arquivo = velocidade_de_leitura()
    exato_geral = True
    linhas, total = [], 0
    for nome, texto in blocos:
        texto = (texto or "").strip()
        if not texto:
            continue
        n, exato = tokenizar(texto)
        exato_geral = exato_geral and exato
        total += n
        linhas.append((nome, n, texto))

    print("\n  %-26s %8s %9s" % ("BLOCO", "tokens", "segundos"))
    print("  " + "-" * 66)
    for nome, n, _ in sorted(linhas, key=lambda x: -x[1]):
        seg = ("%8.1fs" % (n / tok_s)) if tok_s else "       —"
        print("  %-26s %8d %9s" % (nome[:26], n, seg))
    print("  " + "-" * 66)
    seg_total = ("%8.1fs" % (total / tok_s)) if tok_s else "       —"
    print("  %-26s %8d %9s" % ("TOTAL", total, seg_total))

    if not exato_geral:
        print("\n  * o motor nao respondeu /tokenize: os numeros sao ESTIMADOS")
        print("    por caractere, conta que ja errou 40% para cima. Ligue uma")
        print("    IA no Bigode e rode de novo para ter o valor real.")
    if tok_s:
        print("\n  Segundos calculados a %.1f tokens/s — a velocidade de leitura"
              % tok_s)
        print("  mais LENTA medida em %s." % arquivo)
        print("  E a velocidade do caso ruim, que e o caso que incomoda.")
    else:
        print("\n  Sem auditoria de velocidade ainda, nao da para converter em")
        print("  segundos. Rode antes:  python auditar_motor.py")

    print("\n  O QUE ISTO SIGNIFICA")
    print("  " + "-" * 66)
    if tok_s and total:
        print("  Esse tempo e pago em TODA pergunta em que o motor nao")
        print("  reaproveita o cache — conversa nova, troca de projeto,")
        print("  troca de especialista.")
    print("  Cortar um bloco economiza o tempo da linha dele. Mas cortar")
    print("  instrucao tambem muda o comportamento: o temperamento.md e o")
    print("  que segura a invencao, e o selo tirou 0/5 para 4/5 por causa")
    print("  dele. Antes de cortar, rode o auditar_selo.py e compare.")
    print()

    import sys
    if "--real" in sys.argv:
        medir_de_verdade()
    else:
        print("  Os segundos acima sao o PIOR caso: motor lendo tudo do zero.")
        print("  Para saber se voce paga isso de verdade:")
        print("      python medir_prompt.py --real")
        print()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n  Cancelado.\n")
        raise SystemExit(130)
