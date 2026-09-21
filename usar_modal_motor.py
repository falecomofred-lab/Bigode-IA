"""APONTAR O BIGODE PARA O MOTOR DA MODAL

Rode NO SEU WINDOWS, na pasta do Cerebro:

    python usar_modal_motor.py

Ele pede o endereco que o `modal deploy modal_motor.py` imprimiu e o token
que voce criou, conversa de verdade com o modelo, e so grava se responder.

POR QUE TESTAR CONVERSANDO, E NAO COM UM PING
    Um ping nao prova nada aqui -- foi a licao do endpoint de teste, que
    respondia 200 dizendo "Processamento simulado com sucesso" e nao tinha
    modelo nenhum atras. E foi a licao da Pipi na Modal, que ficou um dia
    inteiro publicada, com endereco vivo respondendo 405, e em crash-loop
    por baixo: o roteador da Modal responde MESMO quando o container morre.

    A unica prova que serve e receber texto escrito pelo modelo.

O TESTE USA O CLIENTE DE VERDADE
    Ele nao monta um pedido proprio: chama o modal_cliente.gerar, o mesmo
    que o cerebro.py usa. Se o formato do pedido nao servir ao llama-server,
    a falha aparece AGORA, e nao no meio de uma conversa sua.

PARA DESLIGAR

    python usar_modal_motor.py --remover

Venure - venure.com.br
"""

import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import modal_cliente

BASE = Path(__file__).resolve().parent
ARQUIVO = BASE / "config.json"


def _ler():
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8-sig") or "{}")
    except Exception:
        return {}


def _gravar(dados):
    ARQUIVO.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                       encoding="utf-8")


def remover():
    dados = _ler()
    dados["modal"] = {"ativo": False, "url": "", "health_url": "", "token": ""}
    # Nao basta desligar o "ativo": se o provedor continuar "modal", o
    # cerebro.py cai no caminho local por sorte, nao por decisao.
    if dados.get("modelo_provedor") == "modal":
        dados["modelo_provedor"] = "local"
    _gravar(dados)
    print("\n  Pronto. O Bigode volta ao motor local.\n")


def main():
    if "--remover" in sys.argv:
        return remover()

    print()
    print("=" * 68)
    print("  USAR O MOTOR DA MODAL")
    print("=" * 68)
    print()
    print("  1. Cole o endereco que o `modal deploy modal_motor.py` imprimiu.")
    print("     Ele termina em .modal.run e NAO muda mais.")
    print()
    base = input("  endereco > ").strip().rstrip("/")
    if not base.startswith("http"):
        raise SystemExit("\n  Isso nao e um endereco. Comece com https://\n")

    # O llama-server publica a API compativel com a OpenAI em
    # /v1/chat/completions e a saude em /health. Se a pessoa colar o
    # endereco ja com o caminho, nao duplicamos.
    if base.endswith("/v1/chat/completions"):
        base = base[: -len("/v1/chat/completions")]
    url = base + "/v1/chat/completions"
    saude = base + "/health"

    print()
    print("  2. Cole o token do `modal secret create bigode-token`.")
    print()
    # O TOKEN NAO APARECE NA TELA                               (17/09)
    #   Com input() ele fica escrito no terminal, e dali vai para print de
    #   tela, para conversa com assistente, para captura. Tres tokens do
    #   Fred tiveram de ser revogados nesta semana por esse caminho.
    #   getpass nao ecoa: o que nao aparece nao vaza.
    token = getpass.getpass("  token (nao aparece ao digitar) > ").strip()
    if not token:
        raise SystemExit(
            "\n  Sem token nao da: o endereco e publico e o credito e seu.\n")

    print()
    print("  Acordando a placa. O container frio leva de 30s a 2 min.")
    print()

    # ── GRAVA TAMBEM DENTRO DO PERFIL ───────────────────────── (18/09)
    #
    #   Ha dois motores na Modal: `bigode-motor` (Qwen, ferramenta nativa)
    #   e `bigode-coder` (DeepSeek, melhor em codigo). Antes este arquivo
    #   so escrevia nos campos soltos -- entao configurar o segundo APAGAVA
    #   o primeiro, e voltar significava colar o endereco de novo.
    #
    #   Agora cada endereco fica guardado com o nome do seu perfil, e os
    #   campos soltos passam a ser uma COPIA do que esta em uso. O resto do
    #   Bigode continua lendo so os campos soltos, sem saber que ha perfis
    #   -- foi assim que os dois motores couberam sem mexer em mais nada.
    #
    #   Qual perfil esta sendo configurado vem da variavel BIGODE_PERFIL,
    #   a mesma que o `modal deploy` ja usa. Sem ela, "conversa".
    perfil = (os.environ.get("BIGODE_PERFIL") or "conversa").strip().lower()
    if perfil not in ("conversa", "codigo"):
        perfil = "conversa"

    cfg = dict(_ler())
    antigo = dict(cfg.get("modal") or {})
    perfis = dict(antigo.get("perfis") or {})
    # Configuracao antiga, de quando havia um motor so: vira "conversa".
    if not perfis and str(antigo.get("url") or "").strip():
        perfis["conversa"] = {"url": antigo.get("url", ""),
                              "health_url": antigo.get("health_url", ""),
                              "token": antigo.get("token", "")}
    perfis[perfil] = {"url": url, "health_url": saude, "token": token}

    cfg["modal"] = {"ativo": True, "url": url, "health_url": saude,
                    "token": token, "perfil": perfil, "perfis": perfis}

    # ---- 1) ESPERAR o servidor ficar pronto -------------------------
    #
    # 503 NAO E FALHA, E TAMBEM NAO E PRONTO                    (17/09)
    #
    #   A versao anterior pedia /health, via 503, escrevia "carregando" --
    #   e mandava a conversa em seguida. Que levava o mesmo 503, agora
    #   apresentado como erro:
    #
    #       saude .... HTTP 503 (carregando)
    #       NAO GRAVEI NADA
    #       Modal HTTP 503: {"message":"Loading model"}
    #
    #   Reconhecer que o motor esta carregando e nao esperar por ele e
    #   pior do que nao reconhecer: a mensagem diz que sabe o que esta
    #   acontecendo e falha do mesmo jeito.
    #
    #   Carregar 4,7 GB do Volume para a placa leva de 30 a 90 segundos no
    #   container frio. Aqui ele espera ate 5 minutos, mostrando ponto.
    # QUANTOS PONTOS APARECEM DIZ QUAL CONTEINER RESPONDEU     (17/09)
    #
    #   Zero pontos = um conteiner JA ESTAVA quente, e ele carrega o
    #   segredo de quando nasceu. Se o token acabou de mudar, esse e
    #   justamente o que vai recusar.
    #
    #   Com pontos = nasceu agora, com o segredo atual.
    #
    #   Isso nao e curiosidade: foi o que separou "digitei errado" de
    #   "respondeu o conteiner velho" depois de meia hora tentando.
    print("    esperando o motor carregar", end="", flush=True)
    pronto = False
    esperou = False
    limite = time.time() + 300
    while time.time() < limite:
        try:
            with urllib.request.urlopen(saude, timeout=20) as r:
                if 200 <= r.status < 300:
                    pronto = True
                    break
        except urllib.error.HTTPError as e:
            if e.code != 503:           # 503 = ainda carregando; o resto, nao
                print("\n    saude .... HTTP %s" % e.code)
                break
        except Exception:
            pass                        # container ainda nem subiu
        esperou = True
        print(".", end="", flush=True)
        time.sleep(5)

    print()
    if pronto and not esperou:
        print("    motor .... pronto NA HORA (conteiner que ja estava de pe)")
        print("               se o token der 401, e porque este conteiner")
        print("               nasceu com o segredo antigo")
    elif pronto:
        print("    motor .... pronto (conteiner novo)")
    else:
        print("    motor .... nao ficou pronto em 5 min; vou tentar mesmo assim")
        print("               (se falhar, veja modal.com/apps -> bigode-motor -> Logs)")

    # ---- 2) ele CONVERSA? -------------------------------------------
    mensagens = [
        {"role": "user",
         "content": "Responda apenas, exatamente: motor no ar."},
    ]
    try:
        resposta = modal_cliente.gerar(cfg, mensagens, temperatura=0.1,
                                       max_tokens=32, timeout=600)
    except Exception as erro:
        # Configuracao quebrada gravada e pior do que nenhuma: o Bigode
        # tentaria usar e falharia a cada mensagem.
        texto = str(erro)
        print("  NAO GRAVEI NADA")
        print()
        print("  " + texto[:600])
        print()
        if "401" in texto or "Unauthorized" in texto or "Invalid API Key" in texto:
            # O 401 AQUI TEM DUAS CAUSAS, E A SEGUNDA ENGANA    (17/09)
            #
            #   A obvia: o que foi digitado nao e o valor do segredo.
            #
            #   A que engana: a Modal injeta o segredo quando o CONTEINER
            #   NASCE. Se voce acabou de rodar `secret create --force`, o
            #   conteiner que esta de pe -- e que acabou de carregar o
            #   modelo, como o "motor .... pronto" acima mostra -- ainda
            #   carrega o valor VELHO. O token certo leva 401 mesmo assim.
            #
            #   Isso ja custou quase uma hora na Pipi. Aqui o aviso vem
            #   junto do erro, nao depois.
            print("  O motor subiu, mas recusou o token. Duas causas:")
            print()
            print("  1. O valor digitado nao e o do segredo. Confira com:")
            print("       python -m modal secret list")
            print()
            print("  2. O CONTEINER DE PE AINDA TEM O SEGREDO ANTIGO.")
            print()
            print("     A Modal poe o segredo no conteiner quando ele NASCE.")
            print("     E `modal deploy` publica a versao nova SEM matar o")
            print("     que ja esta rodando -- ele so morre quando o tempo de")
            print("     ocioso acaba, o que aqui leva 5 minutos.")
            print()
            print("     Se la em cima apareceu 'motor pronto' SEM os pontos,")
            print("     foi isto: respondeu um conteiner velho.")
            print()
            print("     Para matar na hora e nascer com o segredo novo:")
            print()
            print("       python -m modal app stop bigode-motor")
            print("       python -m modal deploy modal_motor.py")
            print("       python usar_modal_motor.py")
            print()
        print("=" * 68)
        print()
        return

    texto = (resposta.get("texto") or "").strip()
    if not texto:
        print("  NAO GRAVEI NADA")
        print()
        print("  O endereco respondeu, mas sem texto. Resposta crua:")
        print("  " + json.dumps(resposta.get("raw"), ensure_ascii=False)[:400])
        print()
        print("  Veja os registros em modal.com/apps -> bigode-motor -> Logs.")
        print("=" * 68)
        print()
        return

    cfg["modelo_provedor"] = "modal"
    _gravar(cfg)

    print("  FUNCIONOU.")
    print()
    print("    ele disse ... %s" % texto[:120])
    print()
    print("  O Bigode passa a usar a Modal como motor.")
    print()
    print("  COM FERRAMENTAS, texto palavra por palavra e cache de prompt.")
    print("  O llama-server da Modal e o mesmo do motor local, entao o")
    print("  Bigode trata os dois pelo mesmo caminho -- ele le arquivo,")
    print("  busca na web e mexe no navegador por aqui tambem.")
    print()
    print("  Feche e abra o BIGODE.bat para o novo endereco valer.")
    print()
    print("  Para voltar ao local:  python usar_modal_motor.py --remover")
    print("=" * 68)
    print()


if __name__ == "__main__":
    main()
