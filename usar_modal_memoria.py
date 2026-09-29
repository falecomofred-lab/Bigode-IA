#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIGAR A MEMÓRIA DO BIGODE NA PLACA — e provar que ela pensa
Venure · venure.com.br · 20/09/2026

    python usar_modal_memoria.py

Pergunta os dois endereços e a senha, faz um teste de verdade nos dois e só
grava no config.json se os dois passarem.

O TESTE NÃO É "RESPONDEU"

    Um endpoint que devolve 200 e uma lista de números não prova nada: se os
    números estiverem errados, a busca fica errada em silêncio -- e silêncio
    é o defeito que mais custou tempo neste projeto.

    Então o teste mede o que importa:

      EMBUTIR   manda três frases, duas sobre o mesmo assunto e uma sobre
                outro, e confere se as duas parecidas ficaram mais perto
                entre si do que da estranha. Se não ficaram, o modelo não
                está entendendo português e não adianta seguir.

      RANQUEAR  manda uma pergunta com quatro candidatos e confere se o
                certo subiu para o primeiro lugar.

    Passar nos dois é o que autoriza gravar.

A senha é digitada sem eco. Já houve token vazando neste projeto por
aparecer na tela; uma vez basta.
"""

import getpass
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))       # o Python embutido nao poe o proprio dir
CONFIG = BASE / "config.json"


def ler_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def chamar(url, corpo, espera=240):
    dados = json.dumps(corpo).encode("utf-8")
    pedido = urllib.request.Request(
        url, data=dados, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=espera) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def perto(a, b):
    """Quanto dois vetores apontam para o mesmo lado. 1 = idênticos.

    Escrito à mão, com soma e multiplicação, porque este arquivo roda no
    Python portátil do projeto -- onde numpy não está instalado, e onde um
    import que falha viraria "o teste não rodou" disfarçado de erro.
    """
    soma = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return soma / (na * nb) if na and nb else 0.0


def testar_embutir(url, token):
    print("\n  1. INDEXAÇÃO (bge-m3)")
    print("     mandando três frases…")
    frases = [
        "A apólice cobre roubo do veículo em todo o território nacional.",
        "O seguro do carro protege contra furto em qualquer estado do país.",
        "Receita de bolo de fubá com goiabada para o café da tarde.",
    ]
    inicio = time.time()
    r = chamar(url, {"token": token, "textos": frases})
    levou = time.time() - inicio

    if not r.get("ok"):
        print("     [x] a placa recusou: %s" % r.get("erro", "(sem motivo)"))
        return False

    v = r.get("vetores") or []
    if len(v) != 3:
        print("     [x] esperava 3 vetores, vieram %d" % len(v))
        return False

    iguais = perto(v[0], v[1])
    diferentes = perto(v[0], v[2])
    print("     modelo ......... %s (%d números por bloco)"
          % (r.get("modelo", "?"), r.get("dimensoes", 0)))
    print("     na placa ....... %.2fs   (total %.1fs)"
          % (r.get("segundos", 0), levou))
    print("     as duas de seguro ..... %.3f de semelhança" % iguais)
    print("     seguro x bolo de fubá . %.3f" % diferentes)

    if iguais <= diferentes:
        print("     [x] REPROVADO: ele achou o bolo tão parecido quanto o")
        print("         outro seguro. Não indexe com isto -- a busca sairia")
        print("         aleatória, e sem dar erro.")
        return False
    print("     [ok] entende português.")
    return True


def testar_ranquear(url, token):
    print("\n  2. FILTRO FINAL (bge-reranker-v2-m3)")
    pergunta = "Quantos dias tenho para avisar o sinistro?"
    trechos = [
        "A cobertura de vidros é opcional e tem franquia reduzida.",
        "O aviso de sinistro deve ser feito em até 5 dias úteis da ocorrência.",
        "A vistoria prévia é dispensada para veículos zero quilômetro.",
        "O prêmio pode ser parcelado em até 10 vezes sem juros.",
    ]
    print("     pergunta: %r" % pergunta)
    print("     4 trechos, um só responde (o nº 2)")

    inicio = time.time()
    r = chamar(url, {"token": token, "consulta": pergunta,
                     "trechos": trechos, "quantos": 2})
    levou = time.time() - inicio

    if not r.get("ok"):
        print("     [x] a placa recusou: %s" % r.get("erro", "(sem motivo)"))
        return False

    melhores = r.get("melhores") or []
    if not melhores:
        print("     [x] veio lista vazia")
        return False

    print("     modelo ......... %s" % r.get("modelo", "?"))
    print("     na placa ....... %.2fs   (total %.1fs)"
          % (r.get("segundos", 0), levou))
    for pos, m in enumerate(melhores, 1):
        i = int(m["i"])
        print("     %dº (nota %+.2f) %s" % (pos, m["nota"], trechos[i][:58]))

    if int(melhores[0]["i"]) != 1:
        print("     [x] REPROVADO: ele não pôs o trecho certo em primeiro.")
        return False
    print("     [ok] separa o que responde do que só parece.")
    return True


def main():
    print()
    print("  MEMÓRIA DO BIGODE NA PLACA")
    print("  " + "-" * 62)
    print("  Os dois endereços saem no fim de:")
    print("      python -m modal deploy modal_memoria.py")

    dados = ler_config()
    antes = dados.get("memoria_placa") or {}

    # UM ENDEREÇO SÓ, E EU DEDUZO O OUTRO                      (20/09)
    #
    #   A primeira versão pedia os dois, na ordem indexar → ranquear. A
    #   Modal imprime na ordem inversa (ranquear em cima), e a primeira
    #   coisa que aconteceu na vida real foi colar o de ranquear no campo
    #   de indexar.
    #
    #   A culpa não é de quem colou: os dois endereços são idênticos menos
    #   por uma palavra, saem juntos na tela e em ordem trocada. Pedir os
    #   dois era montar a armadilha e esperar.
    #
    #   Os dois vêm do MESMO app, então deduzir um do outro é seguro.
    bruto = input("\n  Cole QUALQUER um dos dois endereços da memória: ").strip() \
        or str(antes.get("embutir") or "")

    if not bruto.startswith("https://"):
        print("\n  [x] O endereço precisa começar com https://")
        print("      Os dois saem no fim do `modal deploy modal_memoria.py`.")
        return 1

    if "-embutir." in bruto:
        u1, u2 = bruto, bruto.replace("-embutir.", "-ranquear.")
    elif "-ranquear." in bruto:
        u1, u2 = bruto.replace("-ranquear.", "-embutir."), bruto
    else:
        # O MESMO TROPEÇO DO 404 DA VOZ                         (17/09)
        #   Todos os apps do Bigode vivem na mesma conta e os endereços se
        #   parecem. Colar o do motor de texto aqui devolve 404 -- que soa
        #   como "o deploy falhou" e manda procurar no lugar errado.
        print("\n  [x] Este endereço não é da memória.")
        print("      Ele precisa ter `-embutir.` ou `-ranquear.` no meio.")
        print("      O `-servidor.modal.run` é o motor de TEXTO, o")
        print("      `-transcrever.` é a voz e o `-olhar.` é a visão:")
        print("      nenhum deles conhece estas rotas.")
        return 1

    print("\n  indexar  → %s" % u1)
    print("  ranquear → %s" % u2)

    token = getpass.getpass("  Senha (não aparece ao digitar): ").strip() \
        or str(antes.get("token") or "")
    if not token:
        print("\n  [x] Sem senha o endpoint recusa — e deve recusar mesmo.")
        return 1

    print("\n  (o primeiro pedido do dia acorda a placa: até ~60 s)")

    try:
        ok1 = testar_embutir(u1, token)
        ok2 = testar_ranquear(u2, token) if ok1 else False
    except Exception as erro:
        print("\n  [x] Não consegui falar com a Modal.")
        print("      %s" % str(erro)[:240])
        print("\n      Confira se o deploy terminou e se os endereços estão certos.")
        return 1

    if not (ok1 and ok2):
        print("\n  Não gravei nada no config.json.")
        return 1

    dados["memoria_placa"] = {"embutir": u1, "ranquear": u2,
                              "token": token, "ligada": True}
    CONFIG.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                      encoding="utf-8")

    print("\n  " + "=" * 62)
    print("  GRAVADO. A memória do Bigode agora pensa na placa.")
    print("  " + "=" * 62)
    print()
    print("  FALTA UM PASSO, E ELE É OBRIGATÓRIO:")
    print()
    print("      python indexar_memoria.py")
    print()
    print("  Os 8.113 blocos de hoje foram indexados com o modelo antigo.")
    print("  Os números dele e os do bge-m3 não são a mesma língua -- e")
    print("  comparar um com o outro não dá erro, dá resultado aleatório.")
    print()
    print("  Por isso a memória nova nasce em coleções separadas")
    print("  (`seguros__placa`), ao lado das antigas. Nada foi apagado:")
    print("  desligar a placa devolve a memória de antes, inteira.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
