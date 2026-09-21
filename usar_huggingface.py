"""LIGAR O BIGODE NO HUGGING FACE
Venure · venure.com.br · 17/09/2026

Rode NO SEU WINDOWS, na pasta do Cerebro:

    python usar_huggingface.py

Ele pede o token, conversa de verdade com o modelo, CONFERE QUE A CHAMADA
DE FERRAMENTA VOLTA, e so entao grava.

POR QUE TESTAR A FERRAMENTA, E NAO SO O TEXTO
    Ate 17/09 esta rota devolvia texto e jogava a chamada de ferramenta no
    lixo. O Bigode conversava normalmente e nao conseguia abrir um arquivo,
    buscar na web nem mexer no navegador -- e nada na tela dizia isso.

    Um teste que so pede "diga oi" teria passado. Entao aqui o teste PEDE
    uma ferramenta e falha se ela nao voltar.

PARA DESCOBRIR QUAIS MODELOS FAZEM FERRAMENTA

    python usar_huggingface.py --procurar

    O roteador do Hugging Face escolhe o provedor, e nem todo provedor
    aceita `tools` para todo modelo. O mesmo modelo pode CONVERSAR e nao
    fazer ferramenta -- e o erro que volta e um 404 seco, que parece dizer
    que o modelo nao existe.

    Esse modo testa uma lista de candidatos e diz, com resultado, quais
    funcionam na SUA conta. E medicao, nao opiniao: o que serve aqui
    depende de quais provedores a sua conta alcanca hoje.

PARA DESLIGAR

    python usar_huggingface.py --remover
"""

import getpass
import json
import sys
from pathlib import Path

import ferramentas
import huggingface_cliente

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


# CANDIDATOS A MOTOR DO BIGODE
#
#   Todos sao modelos de instrucao treinados para chamada de ferramenta e
#   servidos por mais de um provedor no roteador do Hugging Face -- o que
#   aumenta a chance de a SUA conta alcancar pelo menos um.
#
#   A ordem nao e por tamanho: e por quanto o modelo costuma acertar o
#   formato da chamada, que e o que importa aqui. Modelo que conversa bem e
#   erra o JSON da ferramenta e inutil para o Bigode.
CANDIDATOS = [
    ("meta-llama/Llama-3.3-70B-Instruct", "forte em ferramenta, varios provedores"),
    ("Qwen/Qwen2.5-72B-Instruct", "mesma familia do seu motor local, porte grande"),
    ("Qwen/Qwen3-32B", "geracao nova da Qwen"),
    ("mistralai/Mistral-Small-24B-Instruct-2501", "leve e rapido"),
    ("meta-llama/Llama-3.1-70B-Instruct", "anterior, muito disponivel"),
    ("Qwen/Qwen2.5-Coder-32B-Instruct", "o que voce tentou: bom em codigo"),
]


def procurar(esquema):
    """Testa cada candidato e diz, com resultado, quais fazem ferramenta."""
    print()
    print("=" * 68)
    print("  QUAIS MODELOS DA SUA CONTA FAZEM FERRAMENTA")
    print("=" * 68)
    print()
    if not huggingface_cliente.configurado():
        raise SystemExit(
            "  Sem token gravado. Rode primeiro: python usar_huggingface.py\n")
    print("  Vou pedir a hora a cada um, com as ferramentas na mesa.")
    print("  Passa quem DEVOLVER a chamada. Leva alguns segundos por modelo.")
    print()

    bons = []
    for nome, nota in CANDIDATOS:
        print("  %-46s " % nome[:46], end="", flush=True)
        try:
            _t, chamada = huggingface_cliente.conversar(
                [{"role": "user",
                  "content": "Que horas sao agora? Use a ferramenta."}],
                model=nome, temperature=0.1, max_tokens=160,
                tools=esquema, fluxo=False)
        except Exception as erro:
            texto = str(erro)
            if "NAO aceita chamada de ferramenta" in texto:
                print("conversa, mas sem ferramenta")
            elif "404" in texto or "Nenhum provedor" in texto:
                print("nenhum provedor na sua conta")
            elif "402" in texto or "credito" in texto:
                print("credito de inferencia acabou")
                break          # o resto vai falhar igual; nao insiste
            elif "401" in texto:
                print("token recusado")
                break
            else:
                print("falhou: %s" % texto[:60])
            continue

        if chamada:
            print("SIM  ->  pediu %s" % chamada[0])
            bons.append((nome, nota))
        else:
            print("respondeu texto, ignorou a ferramenta")

    print()
    print("  " + "-" * 64)
    if not bons:
        print("  Nenhum dos candidatos fez ferramenta nesta conta.")
        print()
        print("  Duas saidas:")
        print("    . conta PRO do Hugging Face alcanca mais provedores;")
        print("    . ou fique no motor local para ferramenta, e use o")
        print("      Hugging Face so para conversa longa.")
    else:
        print("  FUNCIONAM na sua conta:")
        for nome, nota in bons:
            print("    %-46s %s" % (nome, nota))
        print()
        print("  Para usar o primeiro:")
        print("    python usar_huggingface.py")
        print("    e cole este modelo no passo 2:")
        print("    %s" % bons[0][0])
    print("=" * 68)
    print()


def remover():
    dados = _ler()
    hf = dict(dados.get("huggingface") or {})
    hf["token"] = ""
    dados["huggingface"] = hf
    if dados.get("modelo_provedor") == "huggingface":
        dados["modelo_provedor"] = "local"
    _gravar(dados)
    print("\n  Pronto. O Bigode volta ao motor local.\n")


def main():
    if "--remover" in sys.argv:
        return remover()
    if "--procurar" in sys.argv:
        return procurar(ferramentas.esquema_openai())

    print()
    print("=" * 68)
    print("  LIGAR O BIGODE NO HUGGING FACE")
    print("=" * 68)
    print()
    print("  O Hugging Face nao aluga placa: ele encaminha a sua conversa")
    print("  para quem tem GPU e cobra por TOKEN. Pausa nao custa nada --")
    print("  e por isso ele e mais barato que a Modal para conversar.")
    print()
    print("  1. Crie um token em https://huggingface.co/settings/tokens")
    print()
    print("     ATENCAO: se o token for do tipo 'Fine-grained', LER NAO BASTA.")
    print("     Marque tambem:  Make calls to Inference Providers")
    print("     Sem essa caixa o roteador recusa tudo com 401.")
    print()

    # O TOKEN NAO APARECE NA TELA                               (17/09)
    #   getpass nao ecoa. Nao e paranoia: o Fred colou dois tokens do
    #   Hugging Face em conversa nesta semana, e os dois tiveram de ser
    #   revogados. O que nao aparece na tela nao vai para o print.
    token = getpass.getpass("  token (nao aparece ao digitar) > ").strip()
    if not token:
        raise SystemExit("\n  Sem token nao da.\n")
    if not token.startswith("hf_"):
        print("\n  AVISO: token do Hugging Face normalmente comeca com 'hf_'.")
        print("  Vou testar de qualquer jeito.\n")

    # SO O MODELO QUE PASSOU NO TESTE PODE SER PADRAO           (17/09)
    #
    #   Minha versao anterior oferecia "o que estava gravado no
    #   config.json". Parecia respeitar a decisao anterior -- mas o arquivo
    #   e escrito ANTES do teste, para o cliente poder ler o token. Entao
    #   uma tentativa FRACASSADA ficava gravada e virava o padrao.
    #
    #   Resultado: o script passou a sugerir justamente o modelo que a
    #   medicao tinha reprovado, e o Fred apertou Enter confiando nele.
    #   Meu conserto piorou o que ele consertava.
    #
    #   Agora existe a marca `ferramenta_ok`, escrita SO depois de o teste
    #   (b) passar. Sem ela, o padrao geral ganha.
    hf_antes = _ler().get("huggingface") or {}
    ja_provado = (str(hf_antes.get("texto_modelo") or "")
                  if hf_antes.get("ferramenta_ok") else "")
    sugestao = ja_provado or huggingface_cliente.MODELO_PADRAO

    print()
    print("  2. Modelo. Enter aceita:")
    print("     %s" % sugestao)
    if ja_provado:
        print("     (ja passou no teste de ferramenta nesta conta)")
    else:
        print("     (padrao; o --procurar mostra o que funciona aqui)")
    print()
    modelo = input("  modelo > ").strip() or sugestao

    # Grava ANTES de testar, porque o cliente le o token do config.json.
    # Se o teste falhar, apagamos -- configuracao quebrada gravada e pior
    # do que nenhuma, porque o Bigode tentaria usar e falharia toda vez.
    dados = _ler()
    antes = dict(dados.get("huggingface") or {})
    provedor_antes = dados.get("modelo_provedor", "local")

    hf = dict(antes)
    hf["token"] = token
    hf["texto_modelo"] = modelo
    # Desmarca ANTES de testar. A marca so volta se o teste (b) passar --
    # senao esta gravacao provisoria viraria o padrao da proxima vez.
    hf["ferramenta_ok"] = False
    dados["huggingface"] = hf
    _gravar(dados)

    def desfazer():
        d = _ler()
        d["huggingface"] = antes
        d["modelo_provedor"] = provedor_antes
        _gravar(d)

    print()
    print("  Testando de verdade. Duas coisas:")
    print("    a) ele responde?")
    print("    b) ele consegue PEDIR uma ferramenta?")
    print()

    # ---- a) responde? ------------------------------------------------
    # SEM FLUXO AQUI, DE PROPOSITO                              (17/09)
    #   Com fluxo, uma recusa do roteador chega como "the stream has been
    #   closed" e o codigo HTTP se perde. Sem fluxo, a excecao traz o 401,
    #   402 ou 404 -- e o cliente traduz cada um numa acao diferente.
    try:
        texto, _ = huggingface_cliente.conversar(
            [{"role": "user", "content": "Responda apenas: pronto."}],
            model=modelo, temperature=0.1, max_tokens=24, fluxo=False)
    except Exception as erro:
        desfazer()
        print("  NAO GRAVEI NADA")
        print()
        for linha in str(erro).split(". "):
            if linha.strip():
                print("  " + linha.strip().rstrip(".") + ".")
        print()
        print("=" * 68)
        print()
        return

    print("    a) respondeu: %s" % (texto.strip()[:60] or "(vazio)"))

    # ---- b) pede ferramenta? -----------------------------------------
    esquema = ferramentas.esquema_openai()
    try:
        _texto2, chamada = huggingface_cliente.conversar(
            [{"role": "user",
              "content": "Que horas sao agora? Use a ferramenta."}],
            model=modelo, temperature=0.1, max_tokens=160, tools=esquema,
            fluxo=False)
    except Exception as erro:
        # O TOKEN FICA, PORQUE ELE ESTA CERTO                   (17/09)
        #
        #   Antes isto chamava desfazer(), que apagava o token. Mas o teste
        #   (a) acabou de passar -- o token e valido e o modelo responde.
        #   Quem nao serve e a COMBINACAO modelo + ferramenta.
        #
        #   Apagar o token ai obrigava a colar tudo de novo, e pior: o
        #   `--procurar`, que existe exatamente para resolver este caso,
        #   ficava sem token e nao rodava.
        #
        #   Entao: guarda o token, NAO troca o provedor, e manda procurar.
        dados = _ler()
        dados["modelo_provedor"] = provedor_antes
        _gravar(dados)

        print("    b) FALHOU ao pedir ferramenta.")
        print()
        for linha in str(erro).split(". "):
            if linha.strip():
                print("  " + linha.strip().rstrip(".") + ".")
        print()
        print("  O TOKEN FICOU GRAVADO -- ele esta certo, o teste (a) passou.")
        print("  O Bigode continua no motor local por enquanto.")
        print()
        print("  Agora descubra quais modelos da sua conta fazem ferramenta:")
        print("      python usar_huggingface.py --procurar")
        print("=" * 68)
        print()
        return

    if not chamada:
        print("    b) ele NAO pediu ferramenta nenhuma.")
        print()
        print("  Gravei o token, mas NAO troquei o provedor.")
        print()
        print("  Este modelo respondeu texto e ignorou as ferramentas. Sem")
        print("  ferramenta o Bigode nao le arquivo, nao busca na web e nao")
        print("  mexe no navegador -- viraria so um chat.")
        print()
        print("  O token ja esta gravado, entao agora da para procurar:")
        print("      python usar_huggingface.py --procurar")
        print("=" * 68)
        print()
        return

    print("    b) pediu a ferramenta: %s" % chamada[0])

    dados = _ler()
    dados["modelo_provedor"] = "huggingface"
    # Agora sim: este modelo, nesta conta, fez chamada de ferramenta.
    hf_ok = dict(dados.get("huggingface") or {})
    hf_ok["ferramenta_ok"] = True
    dados["huggingface"] = hf_ok
    _gravar(dados)

    print()
    print("  FUNCIONOU. O Bigode passa a usar o Hugging Face.")
    print()
    print("    modelo ....... %s" % modelo)
    print("    ferramentas .. %d no esquema" % len(esquema or []))
    print()
    print("  Abra o BIGODE.bat. Ele nao vai mais subir motor local.")
    print()
    print("  Para voltar ao local:  python usar_huggingface.py --remover")
    print("=" * 68)
    print()


if __name__ == "__main__":
    main()
