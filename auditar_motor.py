#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUDITAR O MOTOR — mede o que a auditoria pede, sem chutar nada.

Roda os cinco testes de velocidade (A a E), coleta RAM e CPU durante a
geração, e grava tudo em auditoria/<modelo>-<data>.json + um resumo em texto.

Uso, com o motor JÁ LIGADO no Bigode:

    python auditar_motor.py                    # testa o motor que está no ar
    python auditar_motor.py --rapido           # só os testes A, B e D

Depois troque o modelo na tela do Bigode e rode de novo: os arquivos ficam
lado a lado e dá para comparar.

Este script NÃO julga qualidade de resposta — ele mede tempo, memória e
tokens. Qualidade precisa de gabarito humano, e inventar nota seria pior
que não ter nota.

Venure — venure.com.br
"""

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "auditoria"
MOTOR = "http://localhost:8082/v1/chat/completions"
PROPS = "http://localhost:8082/props"


# --------------------------------------------------------------------------
# Ambiente: só o que dá para ler de verdade
# --------------------------------------------------------------------------

def ambiente():
    """Coleta o que o sistema informa. O que não der, fica marcado."""
    amb = {}

    try:
        amb["cpu_nucleos_logicos"] = os.cpu_count()
    except Exception:
        amb["cpu_nucleos_logicos"] = "INFORMAÇÃO NÃO DISPONÍVEL"

    # RAM: psutil é opcional de propósito. Sem ela, diz que não sabe em vez
    # de estimar — estimativa de memória é justamente o tipo de número que
    # não serve para decidir configuração.
    try:
        import psutil
        vm = psutil.virtual_memory()
        amb["ram_total_gb"] = round(vm.total / 1e9, 1)
        amb["ram_livre_gb"] = round(vm.available / 1e9, 1)
        amb["cpu_modelo"] = psutil.cpu_freq() and "ver /proc/cpuinfo ou msinfo32"
    except ImportError:
        amb["ram_total_gb"] = "INFORMAÇÃO NÃO DISPONÍVEL — instale psutil " \
                              "(pip install psutil) para medir"
        amb["ram_livre_gb"] = "INFORMAÇÃO NÃO DISPONÍVEL"

    amb["gpu"] = "INFORMAÇÃO NÃO DISPONÍVEL — informe manualmente se houver"
    amb["vram"] = "INFORMAÇÃO NÃO DISPONÍVEL"

    # O que o próprio motor diz de si: é a fonte mais confiável para
    # contexto, modelo carregado e parâmetros efetivos.
    try:
        with urllib.request.urlopen(PROPS, timeout=8) as r:
            p = json.loads(r.read().decode("utf-8"))
        amb["motor_props"] = p
        amb["modelo_carregado"] = (p.get("model_path") or
                                   p.get("default_generation_settings", {})
                                    .get("model") or "?")
        amb["contexto_motor"] = (p.get("default_generation_settings", {})
                                  .get("n_ctx") or p.get("n_ctx") or "?")
    except Exception as e:
        amb["motor_props"] = "INFORMAÇÃO NÃO DISPONÍVEL — /props não respondeu (%s)" % e
        amb["modelo_carregado"] = "INFORMAÇÃO NÃO DISPONÍVEL"
        amb["contexto_motor"] = "INFORMAÇÃO NÃO DISPONÍVEL"

    # A configuração que o Bigode manda
    try:
        cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
        amb["config_bigode"] = {k: cfg.get(k) for k in
            ("modelo_atual", "contexto", "threads", "threads_leitura",
             "temperatura", "max_tokens", "max_passos", "usar_mmap")}
    except Exception:
        amb["config_bigode"] = "INFORMAÇÃO NÃO DISPONÍVEL"

    return amb


def esperar_motor(minutos=20):
    """Espera o modelo terminar de carregar, em vez de desistir na hora.

    Sao tres estados diferentes e eles pedem respostas diferentes:
      conexao recusada -> o motor nem subiu; nao adianta esperar
      HTTP 503        -> subiu e esta CARREGANDO; vale esperar
      200             -> pronto

    Antes o script tratava os tres como "ligue um modelo", e a pessoa ficava
    rodando de novo a cada minuto para descobrir se ja tinha carregado.
    Carregar 19 GB de um pendrive leva minutos.
    """
    limite = time.time() + minutos * 60
    avisou = False
    while time.time() < limite:
        try:
            with urllib.request.urlopen(PROPS, timeout=8) as r:
                json.loads(r.read().decode("utf-8"))
            if avisou:
                print(" pronto.")
            return True
        except urllib.error.HTTPError as e:
            if e.code == 503:                       # carregando
                if not avisou:
                    print("\n  O modelo está carregando. Esperando (até %d min)"
                          % minutos, end="", flush=True)
                    avisou = True
                print(".", end="", flush=True)
                time.sleep(10)
                continue
            print("\n  O motor respondeu %s em %s" % (e.code, PROPS))
            return False
        except Exception:
            if avisou:                              # estava carregando e caiu
                print("\n  O motor sumiu no meio do carregamento.")
                return False
            print("\n  O motor não está no ar em %s" % PROPS)
            print("  Abra o Bigode IA e escolha um modelo. Esperar não ajuda:")
            print("  a conexão foi recusada, ou seja, não há nada escutando ali.")
            return False
    print("\n  Passaram %d minutos e ele não terminou de carregar." % minutos)
    return False


def ram_agora():
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1e6, 1), \
               round(psutil.virtual_memory().used / 1e9, 2)
    except Exception:
        return None, None


# --------------------------------------------------------------------------
# Um teste
# --------------------------------------------------------------------------

def rodar(nome, prompt, teto_tokens, temperatura=0.45):
    """Manda um prompt e cronometra. Devolve os números, não opinião."""
    # A primeira versao deste script CONTAVA TOKENS POR CARACTERE, e errou
    # 41% para cima: dizia 4,8 tok/s onde o motor reportava 3,4. Estimativa
    # de token por caractere nao serve para auditoria -- pede-se o numero ao
    # motor. seed fixo torna duas execucoes comparaveis.
    corpo = json.dumps({
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperatura,
        "max_tokens": teto_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "seed": 42,
    }).encode("utf-8")

    req = urllib.request.Request(MOTOR, data=corpo,
                                 headers={"Content-Type": "application/json"})

    comeco = time.time()
    primeiro = None
    pedacos = 0
    texto = []
    ram_pico = 0
    uso = {}

    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            for linha in r:
                linha = linha.decode("utf-8", "ignore").strip()
                if not linha.startswith("data: "):
                    continue
                if linha == "data: [DONE]":
                    break
                try:
                    ev = json.loads(linha[6:])
                except Exception:
                    continue
                if ev.get("usage"):
                    uso = ev["usage"]           # contagem real, do motor
                delta = (ev.get("choices") or [{}])[0].get("delta") or {}
                if delta.get("content"):
                    if primeiro is None:
                        primeiro = time.time()
                    pedacos += 1
                    texto.append(delta["content"])
                    if pedacos % 40 == 0:
                        _, usada = ram_agora()
                        if usada:
                            ram_pico = max(ram_pico, usada)
    except Exception as e:
        return {"teste": nome, "erro": str(e)}

    fim = time.time()
    saida = "".join(texto)
    prefill = (primeiro - comeco) if primeiro else (fim - comeco)
    decode = (fim - primeiro) if primeiro else 0.0

    tok_saida = uso.get("completion_tokens")
    tok_entrada = uso.get("prompt_tokens")
    contagem = "motor"
    if not tok_saida:
        tok_saida = max(1, int(len(saida) / 3.6))
        tok_entrada = int(len(prompt) / 3.6)
        contagem = "ESTIMADA por caractere — o motor não devolveu usage"

    # Resposta curta demais nao produz taxa confiavel: 3 tokens em 2 s dao
    # "1,5 tok/s" que so mede a latencia da conexao. Melhor nao dar numero.
    confiavel = tok_saida >= 40 and decode > 3

    return {
        "teste": nome,
        "prompt_chars": len(prompt),
        "prompt_tokens": tok_entrada,
        "primeiro_token_s": round(prefill, 2),
        "leitura_tok_por_s": (round(tok_entrada / prefill, 1)
                              if tok_entrada and prefill > 0.5 else None),
        "escrita_s": round(decode, 2),
        "total_s": round(fim - comeco, 2),
        "tokens_saida": tok_saida,
        "tok_por_s": round(tok_saida / decode, 2) if confiavel else None,
        "taxa_confiavel": confiavel,
        "contagem_de_tokens": contagem,
        "ram_usada_pico_gb": ram_pico or "INFORMAÇÃO NÃO DISPONÍVEL",
        "resposta_inicio": saida[:180],
        "resposta_chars": len(saida),
    }


# --------------------------------------------------------------------------
# Os cinco testes da auditoria
# --------------------------------------------------------------------------

def testes(rapido=False):
    curto = "Diga apenas: pronto."

    medio = ("Explique em um parágrafo o que é uma função em Python, "
             "para quem nunca programou.")

    # Prompt longo de verdade, sem depender de arquivo externo.
    longo = ("Leia o texto abaixo e responda em uma frase qual é o assunto.\n\n"
             + ("Uma nota fiscal eletrônica é um documento digital emitido "
                "para registrar uma operação de venda de mercadoria ou "
                "prestação de serviço, com validade jurídica garantida pela "
                "assinatura digital do emitente. ") * 60)

    lista = [
        ("A · prompt curto",  curto, 60),
        ("B · prompt médio",  medio, 300),
        ("D · resposta ~500 tokens",
         "Escreva um texto de aproximadamente 500 palavras explicando como "
         "funciona o sistema de notas fiscais eletrônicas no Brasil.", 700),
    ]
    if not rapido:
        lista.insert(2, ("C · prompt longo", longo, 200))
        lista.append(("E · resposta ~2000 tokens",
             "Escreva um manual detalhado, de aproximadamente 2000 palavras, "
             "ensinando um iniciante a organizar as finanças de uma pequena "
             "empresa. Use seções e exemplos.", 2600))
    return lista


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true",
                    help="só os testes A, B e D (o E leva muitos minutos)")
    args = ap.parse_args()

    print("=" * 66)
    print("  AUDITORIA DO MOTOR — Bigode IA")
    print("=" * 66)

    if not esperar_motor():
        print()
        return 1

    amb = ambiente()
    print("\n  AMBIENTE")
    print("  " + "-" * 62)
    for k in ("modelo_carregado", "contexto_motor", "cpu_nucleos_logicos",
              "ram_total_gb", "ram_livre_gb", "gpu", "vram"):
        v = amb.get(k)
        print("  %-22s %s" % (k, str(v)[:80]))

    if "NÃO DISPONÍVEL" in str(amb.get("modelo_carregado")):
        print("\n  PARANDO: o motor não respondeu em %s" % PROPS)
        print("  Ligue um modelo no Bigode e rode de novo.\n")
        return 1

    resultados = []
    for nome, prompt, teto in testes(args.rapido):
        print("\n  %s ..." % nome, end="", flush=True)
        r = rodar(nome, prompt, teto)
        resultados.append(r)
        if r.get("erro"):
            print(" FALHOU: %s" % r["erro"])
        else:
            print(" %.1fs até o 1º token · %s tok/s · %.1fs total" % (
                r["primeiro_token_s"], r["tok_por_s"] or "?", r["total_s"]))

    # ---- resumo ----
    vals = [r["tok_por_s"] for r in resultados if r.get("tok_por_s")]
    prim = [r["primeiro_token_s"] for r in resultados if not r.get("erro")]

    print("\n" + "=" * 66)
    print("  RESUMO")
    print("=" * 66)
    if vals:
        print("  tokens/s        mediana %.2f   min %.2f   max %.2f"
              % (statistics.median(vals), min(vals), max(vals)))
    if prim:
        print("  1º token (s)    mediana %.2f   min %.2f   max %.2f"
              % (statistics.median(prim), min(prim), max(prim)))

    # Leitura de prompt: e onde o tempo vai na primeira mensagem.
    leituras = [r["leitura_tok_por_s"] for r in resultados
                if r.get("leitura_tok_por_s")]
    if leituras:
        print("  leitura (tok/s)  mediana %.1f   min %.1f   max %.1f"
              % (statistics.median(leituras), min(leituras), max(leituras)))

    # A primeira requisicao paga o cache frio. Comparar a primeira com as
    # demais mostra QUANTO custa esse aquecimento -- foi o achado que mais
    # importou nesta maquina.
    ok = [r for r in resultados if not r.get("erro")]
    if len(ok) >= 2:
        primeira = ok[0]["primeiro_token_s"]
        resto = statistics.median([r["primeiro_token_s"] for r in ok[1:]])
        if resto > 0.2:
            print("  1ª requisição custou %.1fx o tempo das seguintes "
                  "(%.1fs contra %.1fs)" % (primeira / resto, primeira, resto))

    # Degradacao SO entre testes com taxa confiavel.
    longos = [r for r in resultados if r.get("tok_por_s") and r["tokens_saida"] > 400]
    curtos = [r for r in resultados
              if r.get("tok_por_s") and 40 <= r["tokens_saida"] <= 400]
    if longos and curtos:
        q = statistics.median([r["tok_por_s"] for r in longos]) / \
            statistics.median([r["tok_por_s"] for r in curtos])
        print("  resposta longa roda a %.0f%% da velocidade da curta" % (q * 100))

    ignorados = [r["teste"] for r in resultados
                 if not r.get("erro") and not r.get("taxa_confiavel")]
    if ignorados:
        print("  (sem taxa: %s — resposta curta demais para medir)"
              % ", ".join(ignorados))

    SAIDA.mkdir(exist_ok=True)
    nome_arq = "%s-%s.json" % (
        str(amb.get("modelo_carregado", "modelo")).replace("\\", "/")
           .split("/")[-1][:40].replace(".gguf", ""),
        datetime.now().strftime("%Y%m%d-%H%M"))
    destino = SAIDA / nome_arq
    destino.write_text(json.dumps(
        {"quando": datetime.now().isoformat(timespec="seconds"),
         "ambiente": amb, "testes": resultados},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n  gravado em: %s" % destino)
    print("\n  O QUE ESTE SCRIPT NÃO MEDE (precisa de você):")
    print("    qualidade de raciocínio, programação, alucinação")
    print("    -> exigem gabarito humano; nota inventada é pior que nota nenhuma")
    print("    uso de GPU/VRAM -> informe o modelo da placa, se houver")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
