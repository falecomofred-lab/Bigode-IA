#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""ESCOLHER QUAL MOTOR DA MODAL ESTA VALENDO — sem perguntar nada
Venure · venure.com.br · 18/09/2026

    python motor_perfil.py                 mostra o que esta guardado
    python motor_perfil.py codigo          liga o DeepSeek-Coder-V2-Lite
    python motor_perfil.py conversa        liga o Qwen2.5-Coder 7B
    python motor_perfil.py --acordar       acorda a placa sem trocar nada

POR QUE ESTE ARQUIVO EXISTE

    O `usar_modal_motor.py` e interativo: pergunta endereco e senha, testa,
    grava. Otimo para configurar uma vez -- impossivel de chamar de dentro
    do BIGODE.bat, que precisa decidir sozinho.

    Este aqui nao pergunta nada. Ele le o que o `usar_modal_motor.py` ja
    guardou e so aponta o config.json para o perfil escolhido.

OS DOIS MOTORES CONVIVEM

    Sao dois apps na Modal, cada um com endereco proprio:

        bigode-motor   Qwen2.5-Coder 7B     faz chamada de ferramenta NATIVA
        bigode-coder   DeepSeek-Coder-V2    escreve codigo melhor, SEM nativa

    Os dois dormem sozinhos quando ninguem usa. Ter os dois publicados nao
    custa nada alem do armazenamento do Volume.

    A ressalva do DeepSeek e real e vale repetir: o chat template dele e o
    formato antigo "User:/Assistant:", sem secao de tools. Para ler arquivo
    e mexer no navegador, o perfil "conversa" acerta mais.

ONDE FICA GUARDADO

    config.json:

        "modal": {
          "perfil": "codigo",
          "perfis": {
            "conversa": {"url": "...", "health_url": "...", "token": "..."},
            "codigo":   {"url": "...", "health_url": "...", "token": "..."}
          },
          "url": "...", "health_url": "...", "token": "..."
        }

    Os campos soltos (`url`, `token`) continuam existindo porque e neles
    que o `config()` do cerebro.py e o `modelos.py` olham. Este arquivo so
    copia o perfil escolhido para cima deles -- assim nada mais precisou
    mudar para os dois motores conviverem.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))       # o Python embutido nao poe o proprio dir
CONFIG = BASE / "config.json"

# Os nomes vem da MESMA tabela que o deploy e a tela usam. Escrever a
# lista aqui de novo seria criar um terceiro lugar para esquecer de
# atualizar quando entrar um modelo novo.
try:
    from perfis_modal import PERFIS as _CATALOGO
    PERFIS = tuple(_CATALOGO)
    APELIDO = {n: str(d.get("nota", n)).split(" · ")[0]
               for n, d in _CATALOGO.items()}
except Exception:
    PERFIS = ("conversa", "codigo")
    APELIDO = {"conversa": "Qwen2.5-Coder 7B",
               "codigo": "DeepSeek-Coder-V2-Lite"}


def ler():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8-sig") or "{}")
    except Exception:
        return {}


def gravar(dados):
    CONFIG.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                      encoding="utf-8")


def guardados(cfg):
    """Os perfis salvos. Migra a configuracao antiga de um motor so.

    Quem ja usava o Bigode tem `modal.url` preenchido e nenhum `perfis`.
    Jogar isso fora obrigaria a reconfigurar; entao o endereco antigo vira
    o perfil "conversa", que e o que ele era.
    """
    m = cfg.get("modal") or {}
    perfis = dict(m.get("perfis") or {})
    if not perfis and str(m.get("url") or "").strip():
        perfis["conversa"] = {"url": m.get("url", ""),
                              "health_url": m.get("health_url", ""),
                              "token": m.get("token", "")}
    return perfis


def acordar(url, token, segundos=150):
    """Bate no /health ate a placa responder. Devolve (ok, segundos).

    Existe para o BIGODE.bat: o conteiner frio leva de 20 a 40 segundos
    para subir o modelo. Sem isto, a PRIMEIRA pergunta do dia paga essa
    espera -- e quem esta esperando acha que o Bigode travou.

    Acordar aqui custa os mesmos segundos de placa; a diferenca e que eles
    passam com uma barra na tela em vez de passarem numa caixa de texto
    que nao responde.
    """
    alvo = (url or "").rstrip("/")
    if alvo.endswith("/v1/chat/completions"):
        alvo = alvo[: -len("/v1/chat/completions")]
    alvo += "/health"

    pedido = urllib.request.Request(alvo)
    if token:
        pedido.add_header("Authorization", "Bearer " + token)

    inicio = time.time()
    while time.time() - inicio < segundos:
        try:
            with urllib.request.urlopen(pedido, timeout=20) as r:
                if 200 <= r.status < 300:
                    return True, round(time.time() - inicio, 1)
        except urllib.error.HTTPError as e:
            # 503 = carregando o modelo. 401/403 = de pe, so recusou a
            # chamada sem chave -- e de pe e o que interessa aqui.
            if e.code in (401, 403):
                return True, round(time.time() - inicio, 1)
        except Exception:
            pass
        time.sleep(3)
    return False, round(time.time() - inicio, 1)


def main():
    argumentos = [a for a in sys.argv[1:]]
    so_acordar = "--acordar" in argumentos
    argumentos = [a for a in argumentos if not a.startswith("--")]
    alvo = (argumentos[0].lower() if argumentos else "")

    cfg = ler()
    perfis = guardados(cfg)
    m = dict(cfg.get("modal") or {})
    atual = str(m.get("perfil") or "conversa")

    if not alvo and not so_acordar:
        print()
        print("  MOTORES DA MODAL GUARDADOS")
        print("  " + "-" * 56)
        for nome in PERFIS:
            tem = nome in perfis and str(perfis[nome].get("url") or "").strip()
            marca = "  <= em uso" if nome == atual and tem else ""
            print("  %-10s %-26s %s%s"
                  % (nome, APELIDO[nome],
                     "configurado" if tem else "FALTA CONFIGURAR", marca))
        print()
        print("  Para trocar:   python motor_perfil.py codigo")
        print("  Para configurar um que falta:")
        print("     set BIGODE_PERFIL=codigo")
        print("     python -m modal deploy modal_motor.py")
        print("     python usar_modal_motor.py        (cole o endereco novo)")
        print()
        return 0

    if alvo:
        if alvo not in PERFIS:
            print("\n  [x] Perfil desconhecido: %r. Use: %s\n"
                  % (alvo, " ou ".join(PERFIS)))
            return 1
        dados = perfis.get(alvo) or {}
        url = str(dados.get("url") or "").strip()
        if not url:
            print("\n  [x] O perfil %r ainda nao foi configurado." % alvo)
            print("      set BIGODE_PERFIL=%s" % alvo)
            print("      python -m modal deploy modal_motor.py")
            print("      python usar_modal_motor.py\n")
            return 1

        m["perfil"] = alvo
        m["perfis"] = perfis
        # Copia para os campos soltos: e neles que o resto do Bigode olha.
        m["url"] = url
        m["health_url"] = str(dados.get("health_url") or "")
        m["token"] = str(dados.get("token") or "")
        m["ativo"] = True
        cfg["modal"] = m
        cfg["modelo_provedor"] = "modal"
        gravar(cfg)
        print("  Motor: %s  (%s, na Modal)" % (APELIDO[alvo], alvo))
        atual = alvo

    if so_acordar:
        m = dict(ler().get("modal") or {})
        url, token = str(m.get("url") or ""), str(m.get("token") or "")
        if not url:
            print("  [!] Sem endereco da Modal para acordar.")
            return 0        # nao e motivo para impedir o Bigode de abrir
        print("  Acordando a placa... (ate 40s se ela estiver dormindo)")
        ok, levou = acordar(url, token)
        print("  %s em %.1fs" % ("Placa pronta" if ok else
                                 "Ainda nao respondeu -- vou abrir assim mesmo",
                                 levou))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
