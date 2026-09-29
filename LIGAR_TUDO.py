#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LIGAR TUDO DE UMA VEZ — sem perguntar nada
Venure · venure.com.br · 20/09/2026

    LIGAR_TUDO.bat          (ou)    python LIGAR_TUDO.py

POR QUE ESTE ARQUIVO EXISTE

    Os conferidores (usar_modal_fala.py, usar_modal_olho.py,
    usar_modal_memoria.py) fazem três perguntas cada um: endereço, senha,
    e às vezes uma confirmação. São nove respostas que ninguém tem como
    adivinhar, e todas elas JÁ ESTÃO no computador:

      . a senha está gravada no config.json, de quando a voz foi ligada
      . os endereços seguem um padrão fixo da Modal, a partir do nome da
        sua conta -- que também está no config.json

    Pedir ao usuário uma informação que o programa já tem é defeito de
    projeto, não é "segurança". Este arquivo descobre tudo sozinho, testa
    cada peça de verdade e grava só o que passou.

O QUE ELE NUNCA FAZ

    Não imprime a senha na tela. Não inventa endereço: se o app não estiver
    publicado, o teste falha e ele DIZ qual `modal deploy` está faltando,
    em vez de gravar um endereço morto.

O QUE ELE TESTA, PEÇA POR PEÇA

    memória   manda 3 frases e confere se ele entende português
              manda 4 trechos e confere se acha o que responde
    voz       manda uma frase e confere se voltou áudio com duração certa
    visão     manda uma imagem com palavra escondida e confere se ele leu

    Quem conversa com você -- Qwen 7B ou DeepSeek -- NÃO é mexido aqui.
    Isso é escolha sua, no cartão da tela de Configurações.

    Um endpoint que responde 200 não prova nada -- a Pipi ficou um dia
    inteiro no ar, respondendo, e em crash-loop por baixo.
"""

import base64
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
CONFIG = BASE / "config.json"

VERDE = "  [ok] "
VERM = "  [x]  "
AMAR = "  [!]  "


# ----------------------------------------------------------------------
def ler_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8-sig") or "{}")
    except Exception:
        return {}


def gravar_config(dados):
    CONFIG.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                      encoding="utf-8")


def achar_senha(cfg):
    """A senha do bigode-token, procurada em todo lugar onde ela já mora.

    Ordem: voz primeiro (foi a última a ser configurada por completo),
    depois o motor, depois qualquer perfil. Todas são a MESMA senha -- é
    um único `modal secret` servindo todos os apps.
    """
    tentativas = [
        (cfg.get("voz_modal") or {}).get("token"),
        (cfg.get("modal") or {}).get("token"),
        (cfg.get("memoria_placa") or {}).get("token"),
        (cfg.get("fala_modal") or {}).get("token"),
    ]
    for p in ((cfg.get("modal") or {}).get("perfis") or {}).values():
        if isinstance(p, dict):
            tentativas.append(p.get("token"))
    for t in tentativas:
        t = str(t or "").strip()
        if t:
            return t
    return ""


def achar_conta(cfg):
    """O apelido da sua conta na Modal, tirado de um endereço já gravado.

    Os endereços da Modal têm a forma:

        https://<conta>--<app>-<classe>-<rota>.modal.run

    Então qualquer endereço que já funcione entrega o nome da conta, e daí
    saem todos os outros. Melhor do que escrever "falecomofred-lab" no
    código: no dia em que a conta mudar, o código mentiria.
    """
    candidatos = [
        (cfg.get("voz_modal") or {}).get("url"),
        (cfg.get("modal") or {}).get("url"),
        (cfg.get("fala_modal") or {}).get("url"),
        (cfg.get("olho_modal") or {}).get("url"),
        (cfg.get("memoria_placa") or {}).get("embutir"),
    ]
    for p in ((cfg.get("modal") or {}).get("perfis") or {}).values():
        if isinstance(p, dict):
            candidatos.append(p.get("url"))
    for u in candidatos:
        m = re.search(r"https://([^-.]+(?:-[^-.]+)*?)--", str(u or ""))
        if m:
            return m.group(1)
    return ""


def chamar(url, corpo, espera=300):
    dados = json.dumps(corpo).encode("utf-8")
    pedido = urllib.request.Request(
        url, data=dados, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=espera) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def perto(a, b):
    """Quanto dois vetores apontam para o mesmo lado. 1 = idênticos.

    À mão, com soma e multiplicação: este arquivo roda no Python portátil
    do projeto, e um `import numpy` que falhasse viraria "o teste não
    rodou" disfarçado de erro.
    """
    soma = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return soma / (na * nb) if na and nb else 0.0


# ----------------------------------------------------------------------
def testar_memoria(conta, senha):
    u1 = "https://%s--bigode-memoria-memoria-embutir.modal.run" % conta
    u2 = "https://%s--bigode-memoria-memoria-ranquear.modal.run" % conta

    frases = [
        "A apólice cobre roubo do veículo em todo o território nacional.",
        "O seguro do carro protege contra furto em qualquer estado do país.",
        "Receita de bolo de fubá com goiabada para o café da tarde.",
    ]
    r = chamar(u1, {"token": senha, "textos": frases})
    if not r.get("ok"):
        return None, r.get("erro", "(sem motivo)")
    v = r.get("vetores") or []
    if len(v) != 3:
        return None, "esperava 3 vetores, vieram %d" % len(v)

    iguais, diferentes = perto(v[0], v[1]), perto(v[0], v[2])
    print("       os dois de seguro: %.3f   ·   seguro x bolo: %.3f"
          % (iguais, diferentes))
    if iguais <= diferentes:
        return None, ("ele achou o bolo de fubá tão parecido com o seguro "
                      "quanto o outro seguro — não entende português")

    pergunta = "Quantos dias tenho para avisar o sinistro?"
    trechos = [
        "A cobertura de vidros é opcional e tem franquia reduzida.",
        "O aviso de sinistro deve ser feito em até 5 dias úteis da ocorrência.",
        "A vistoria prévia é dispensada para veículos zero quilômetro.",
        "O prêmio pode ser parcelado em até 10 vezes sem juros.",
    ]
    r2 = chamar(u2, {"token": senha, "consulta": pergunta,
                     "trechos": trechos, "quantos": 2})
    if not r2.get("ok"):
        return None, r2.get("erro", "(sem motivo)")
    melhores = r2.get("melhores") or []
    if not melhores or int(melhores[0]["i"]) != 1:
        return None, "não pôs o trecho certo em primeiro lugar"

    print("       achou a resposta certa entre 4 trechos parecidos")
    return {"embutir": u1, "ranquear": u2, "token": senha, "ligada": True}, ""


def testar_fala(conta, senha):
    url = "https://%s--bigode-fala-fala-falar.modal.run" % conta
    frase = ("Olá, Fred. Aqui é o Bigode. A partir de agora eu posso "
             "responder falando, em vez de você ter que ler tudo.")
    r = chamar(url, {"token": senha, "texto": frase})
    if not r.get("ok"):
        return None, r.get("erro", "(sem motivo)")

    duracao = float(r.get("duracao") or 0)
    print("       voz %s · %.1fs de fala" % (r.get("voz", "?"), duracao))
    # 118 caracteres dão uns 8 s. Menos de 3 é voz que não carregou direito:
    # o endpoint responderia 200 do mesmo jeito.
    if duracao < 3.0:
        return None, "áudio curto demais (%.1fs) para esta frase" % duracao

    try:
        destino = BASE / "teste_da_voz.wav"
        destino.write_bytes(base64.b64decode(r["wav"]))
        print("       gravei %s — abra para ouvir" % destino.name)
    except Exception:
        pass
    return {"url": url, "token": senha, "ligada": True}, ""


def imagem_com_palavra(palavra):
    """Um PNG branco com a palavra em preto, grande. (base64, None) ou (None, motivo)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None, ("o Pillow não está neste Python — sem ele não dá para "
                      "montar a imagem de teste")
    figura = Image.new("RGB", (900, 320), (255, 255, 255))
    pequena = Image.new("RGB", (225, 80), (255, 255, 255))
    ImageDraw.Draw(pequena).text((12, 30), palavra, fill=(0, 0, 0))
    figura.paste(pequena.resize((900, 320), Image.LANCZOS), (0, 0))
    ImageDraw.Draw(figura).rectangle([(0, 0), (899, 319)],
                                     outline=(0, 0, 0), width=4)
    memoria = io.BytesIO()
    figura.save(memoria, "PNG")
    return base64.b64encode(memoria.getvalue()).decode("ascii"), None


def png_metades(lado=240):
    """Um PNG preto em cima, branco embaixo — sem biblioteca nenhuma.

    Existe porque o Pillow pode não estar no Python portátil, e sem ele o
    teste da visão simplesmente não rodaria. "Não consegui testar" não é
    aprovação: um modelo de visão quebrado devolve uma descrição plausível
    em vez de um erro, então pular o teste seria ligar no escuro.

    PNG na mão é só isto: assinatura, cabeçalho, os pixels comprimidos com
    zlib, e o fim. Tudo da biblioteca padrão do Python.
    """
    import struct
    import zlib

    linhas = b""
    for y in range(lado):
        cor = b"\x00\x00\x00" if y < lado // 2 else b"\xff\xff\xff"
        linhas += b"\x00" + cor * lado        # o \x00 é o filtro da linha

    def bloco(tipo, dados):
        corpo = tipo + dados
        return (struct.pack(">I", len(dados)) + corpo
                + struct.pack(">I", zlib.crc32(corpo) & 0xFFFFFFFF))

    cabecalho = struct.pack(">IIBBBBB", lado, lado, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + bloco(b"IHDR", cabecalho)
           + bloco(b"IDAT", zlib.compress(linhas, 9))
           + bloco(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


def testar_olho(conta, senha):
    url = "https://%s--bigode-olho-olho-olhar.modal.run" % conta

    # TESTE BOM: a palavra escondida. Só um modelo que realmente LÊ a
    # imagem consegue citá-la.
    segredo = "JABUTICABA"
    figura, _ = imagem_com_palavra(segredo)
    if figura is not None:
        r = chamar(url, {"token": senha, "imagem": figura,
                         "pergunta": "Que palavra está escrita nesta imagem? "
                                     "Responda em português."})
        if not r.get("ok"):
            return None, r.get("erro", "(sem motivo)")
        resposta = str(r.get("texto") or "")
        print("       ele disse: %r" % resposta[:90])
        if segredo.lower() not in resposta.lower():
            # Modelo de visão quebrado não dá erro: dá descrição plausível.
            return None, ("não citou a palavra que estava na imagem — ou não "
                          "enxerga, ou está inventando")
        print("       leu a palavra escondida: está enxergando de verdade")
        return {"url": url, "token": senha, "ligada": True}, ""

    # TESTE DE RESERVA: sem Pillow não dá para desenhar texto, mas dá para
    # fazer metade preta e metade branca. Ele tem de dizer QUAL está em
    # cima -- chutar acerta metade das vezes, e é por isso que este é o
    # teste pior dos dois. Melhor que nenhum.
    print("       (sem Pillow aqui: usando o teste de reserva, mais fraco)")
    r = chamar(url, {"token": senha, "imagem": png_metades(),
                     "pergunta": "Esta imagem tem duas metades de cores "
                                 "diferentes. Qual é a cor da metade DE CIMA? "
                                 "Responda com uma palavra só, em português."})
    if not r.get("ok"):
        return None, r.get("erro", "(sem motivo)")

    resposta = str(r.get("texto") or "").lower()
    print("       ele disse: %r" % resposta[:80])

    pos_preto = min([p for p in (resposta.find("preto"), resposta.find("black"))
                     if p >= 0] or [10 ** 6])
    pos_branco = min([p for p in (resposta.find("branc"), resposta.find("white"))
                      if p >= 0] or [10 ** 6])
    if pos_preto >= pos_branco:
        return None, ("a metade de cima é preta e ele não disse isso — "
                      "não está enxergando")
    print("       acertou a metade de cima")
    return {"url": url, "token": senha, "ligada": True}, ""


# ----------------------------------------------------------------------
# O GURU SAIU DAQUI                                        (22/09/2026)
#
#   Havia um `testar_guru` e uma quarta linha nesta lista. Foram embora
#   junto com o perfil, no perfis_modal.py.
#
#   O guru era sugestão minha, não pedido do Fred -- a prioridade dele
#   sempre foi o Qwen 7B e o DeepSeek, que já funcionavam. Tirar da tabela
#   e esquecer aqui é o tipo de meia-remoção que deixa a tela dizendo uma
#   coisa e o script dizendo outra.
#
#   As três peças abaixo são as que ele pediu e usa: ouvir, falar, ver.
PECAS = [
    ("memória (indexar + ranquear)", "memoria", testar_memoria,
     "python -m modal deploy modal_memoria.py"),
    ("voz (o Bigode falando)", "fala", testar_fala,
     "python -m modal deploy modal_fala.py"),
    ("visão (ler print e foto)", "olho", testar_olho,
     "python -m modal deploy modal_olho.py"),
]


def main():
    print()
    print("=" * 70)
    print("  LIGANDO TUDO — sem perguntas")
    print("=" * 70)

    cfg = ler_config()

    senha = achar_senha(cfg)
    if not senha:
        print()
        print(VERM + "Não achei a senha do bigode-token no config.json.")
        print("       Ela é gravada quando você liga o primeiro app.")
        print("       Rode uma vez:  python usar_modal_voz.py")
        print()
        return 1

    conta = achar_conta(cfg)
    if not conta:
        print()
        print(VERM + "Não achei o nome da sua conta da Modal no config.json.")
        print("       Ele sai de qualquer endereço já gravado lá.")
        print()
        return 1

    print()
    print("  conta na Modal ...: %s" % conta)
    print("  senha ............: achei no config.json (%d caracteres)"
          % len(senha))
    print("  (a senha não é impressa, e não precisa ser digitada)")

    novos = {}
    falhas = []

    for rotulo, chave, teste, comando in PECAS:
        print()
        print("  " + "-" * 66)
        print("  %s" % rotulo)
        print("  " + "-" * 66)
        print("       acordando a placa… (container frio: até 2 min)")
        inicio = time.time()
        codigo = 0
        try:
            resultado, motivo = teste(conta, senha)
        except urllib.error.HTTPError as erro:
            codigo = int(getattr(erro, "code", 0) or 0)
            resultado, motivo = None, "HTTP %d" % codigo
        except Exception as erro:
            resultado, motivo = None, "%s: %s" % (type(erro).__name__,
                                                  str(erro)[:180])
        levou = time.time() - inicio

        if resultado:
            print(VERDE + "passou em %.0fs" % levou)
            novos[chave] = resultado
            continue

        print(VERM + "não passou: %s" % motivo)
        falhas.append(rotulo)

        # O NÚMERO DO ERRO DIZ COISAS DIFERENTES              (20/09)
        #
        #   A primeira versão mandava "falta publicar?" para qualquer falha.
        #   Isso é palpite com cara de diagnóstico, e manda a pessoa para o
        #   lugar errado -- foi exatamente o defeito que a gente passou o dia
        #   caçando em outras peças.
        #
        #   404 = a Modal não conhece este endereço. Aí sim, falta publicar.
        #   503 = o endereço EXISTE e o contêiner não está servindo: ou ainda
        #         está carregando o modelo, ou subiu e morreu.
        if codigo == 404:
            print("       a Modal não conhece este endereço: falta publicar.")
            print("       rode:  %s" % comando)
        elif codigo == 503:
            print("       o endereço existe, mas o contêiner não respondeu.")
            print("       Isso é 'subiu e caiu', não 'não existe'.")
            print()
            print("       MEÇA ANTES DE CONSERTAR:")
            print()
            print("         modal app logs bigode-%s" % chave)
            print()
            print("       O log diz se ele ainda está carregando ou se")
            print("       morreu — e, se morreu, por quê. Consertar sem ler")
            print("       isso é adivinhar.")
        else:
            print("       se ainda não publicou este app, rode:")
            print("       %s" % comando)

    # ---- gravar só o que passou -------------------------------------
    #
    # Gravar um endereço que não respondeu seria plantar um defeito para
    # amanhã: o botão apareceria pronto na tela e falharia no clique.
    if "memoria" in novos:
        cfg["memoria_placa"] = novos["memoria"]
    if "fala" in novos:
        cfg["fala_modal"] = novos["fala"]
    if "olho" in novos:
        cfg["olho_modal"] = novos["olho"]

    # ESTE ARQUIVO NÃO ENCOSTA NO MOTOR DE TEXTO
    #
    #   Ele liga os acréscimos: memória, voz, visão. Qual modelo conversa
    #   com você -- Qwen 7B ou DeepSeek -- é escolha sua, no cartão da tela,
    #   e nada aqui muda isso. É de propósito: trocar o motor de alguém por
    #   baixo, durante um script chamado "ligar tudo", seria a pior surpresa
    #   possível.
    if novos:
        gravar_config(cfg)

    print()
    print("=" * 70)
    if not falhas:
        print("  TUDO LIGADO.")
    else:
        print("  LIGUEI %d de %d. Faltou: %s"
              % (len(novos), len(PECAS), ", ".join(falhas)))
    print("=" * 70)
    print()

    if "memoria" in novos:
        print("  FALTA UM PASSO, E ELE É OBRIGATÓRIO:")
        print()
        print("      reindexar a memória, para os seus blocos passarem a")
        print("      ser lidos pelo modelo novo. Rode:")
        print()
        print("          LIGAR_TUDO.bat indexar")
        print()
    print("  O motor de texto continua o que você escolheu na tela.")
    print("  Recarregue a página do Bigode com Ctrl+F5.")
    print()
    return 0 if not falhas else 1


def resumo():
    """Diz o que está ligado, lendo só o config.json — sem chamar a rede.

    Existe para o BIGODE.bat mostrar na abertura. Não acorda placa nenhuma:
    uma consulta de rede por peça somaria dezenas de segundos à partida, e
    partida lenta foi a queixa que começou tudo isto.

    Isto NÃO prova que funciona, e o texto diz isso. Prova é o LIGAR_TUDO
    inteiro; aqui é só "está configurado".
    """
    cfg = ler_config()

    def liga(bloco, campo="url"):
        d = cfg.get(bloco) or {}
        if not isinstance(d, dict) or not d.get("ligada", True):
            return False
        return bool(str(d.get(campo) or "").strip()
                    and str(d.get("token") or "").strip())

    pecas = [
        ("ouvir voce", liga("voz_modal")),
        ("falar", liga("fala_modal")),
        ("ver print", liga("olho_modal")),
        ("memoria na placa", liga("memoria_placa", "embutir")),
    ]
    prontos = [n for n, ok in pecas if ok]
    faltam = [n for n, ok in pecas if not ok]

    print("  Extras ....: " + (", ".join(prontos) if prontos else "nenhum"))
    if faltam:
        print("               (falta: %s -- rode LIGAR_TUDO.bat)"
              % ", ".join(faltam))
    return 0


def indexar():
    """Reindexa a memória. Separado porque só faz sentido depois de ligar."""
    try:
        import chromadb  # noqa: F401
    except ImportError:
        print()
        print(VERM + "Este Python não tem o ChromaDB: %s" % sys.executable)
        print("       Use o LIGAR_TUDO.bat, que chama o Python certo.")
        print()
        return 1
    import indexar_memoria
    return indexar_memoria.main()


if __name__ == "__main__":
    if "resumo" in sys.argv:
        raise SystemExit(resumo())
    if "indexar" in sys.argv:
        raise SystemExit(indexar())
    raise SystemExit(main())
