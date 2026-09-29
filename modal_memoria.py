"""A MEMÓRIA DO BIGODE NA PLACA — indexar e ranquear, num container só
Venure · venure.com.br · 20/09/2026

O QUE ESTE ARQUIVO RESOLVE

    Hoje a busca na memória faz uma coisa só: pega a pergunta, procura
    blocos "parecidos" e entrega os primeiros que aparecem. Parecido não é
    certo. Com 8.113 blocos indexados, sempre existem vinte trechos
    parecidos com qualquer pergunta -- e entre eles vai um que responde e
    dezenove que só usam as mesmas palavras.

    O modelo então recebe dezenove distrações e uma resposta, misturadas, e
    escolhe mal. Não é burrice dele: é o material que chegou.

    Este arquivo põe DUAS peças na placa:

        EMBUTIR    transforma texto em números, com um modelo que entende
                   português de verdade (o de hoje é inglês com sotaque)

        RANQUEAR   lê a pergunta JUNTO com cada candidato e diz qual
                   responde. É a diferença entre "parece" e "responde".

POR QUE OS DOIS NO MESMO APP

    São dois modelos de ~2,2 GB cada. Juntos cabem folgados numa T4 de 16
    GB. Separá-los em dois apps significaria dois containers frios, duas
    placas ligando, dois endereços para configurar e dois lugares para
    consertar. A conta não fecha para nada que eles ganhem.

    Um app, dois endereços de entrada, uma placa.

OS MODELOS, E POR QUE ESTES

    BAAI/bge-m3               MIT      · multilíngue de verdade, e o
                                         português dele é bom. 1024 números
                                         por bloco.
    BAAI/bge-reranker-v2-m3   Apache 2 · o companheiro do de cima, feito
                                         para ser o segundo passo.

    Licença importa aqui: os dois permitem uso comercial sem pedir nada a
    ninguém. Não escolhi o mais famoso, escolhi o que você pode vender.

ATENÇÃO — TROCAR O MODELO DE INDEXAÇÃO OBRIGA A REINDEXAR

    Os 8.113 blocos de hoje foram indexados com o modelo pequeno que vem
    dentro do ChromaDB. Os números dele e os do bge-m3 não são a mesma
    língua: comparar um com o outro dá resultado sem sentido, e o pior é
    que dá SEM ERRO -- sai uma lista, só que aleatória.

    Por isso o `chroma_memoria.py` guarda a memória da placa em coleções
    com nome próprio (`seguros__placa`), ao lado das antigas. As duas
    convivem, nada é sobrescrito, e você pode voltar atrás.

O QUE CUSTA

    T4, $0.000164/s.
    Indexar os 8.113 blocos: ~3 minutos de placa  ->  menos de 4 centavos.
    Ranquear 20 candidatos numa pergunta: ~0,3 s  ->  0,005 centavo.
    `scaledown_window=180`: 3 minutos parado e a placa desliga.

    Usando o dia inteiro, isto não chega a 1 dólar por mês.

COMO PUBLICAR

    python -m modal secret create bigode-token BIGODE_TOKEN=<a-mesma-senha>
    python -m modal deploy modal_memoria.py

    Saem DOIS endereços, um terminado em `-embutir.modal.run` e outro em
    `-ranquear.modal.run`. Guarde com:

        python usar_modal_memoria.py

    Ele confere os dois, mede e escreve no config.json sozinho.
"""

import os

import modal

APP = "bigode-memoria"
PLACA = "T4"

MODELO_EMBUTIR = "BAAI/bge-m3"
MODELO_RANQUEAR = "BAAI/bge-reranker-v2-m3"

app = modal.App(APP)


def _baixar_modelos():
    """Traz os pesos DURANTE a construção da imagem.

    Função com nome, no topo do arquivo, e não lambda -- a Modal precisa
    achar o módulo e o nome dela na máquina de build:

        InvalidError: Image.run_function does not support lambda functions.

    device="cpu" de propósito: aqui só se baixa arquivo. Reservar uma placa
    para esperar a rede seria pagar T4 por minuto de download.
    """
    from sentence_transformers import SentenceTransformer, CrossEncoder

    SentenceTransformer(MODELO_EMBUTIR, device="cpu")
    CrossEncoder(MODELO_RANQUEAR, device="cpu")


# AS VERSÕES ESTÃO PRESAS DE PROPÓSITO
#
#   O modal_voz.py já levou uma lição cara nisso: o faster-whisper usava
#   `requests` sem declarar, e o dia em que o huggingface_hub parou de
#   trazer de carona, a construção morreu com um ModuleNotFoundError que não
#   explicava nada.
#
#   Prender só o pacote de cima não protege: as dependências dele sobem
#   sozinhas, e quem quebra é sempre a que você não escreveu. Aqui ficam
#   presos os três que importam.
imagem = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.4.1",
        "transformers==4.44.2",
        "sentence-transformers==3.0.1",
        "fastapi[standard]",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "0"})
    .run_function(_baixar_modelos)
)


def _conferir_token(item):
    """Devolve a mensagem de erro, ou None se a senha bate.

    A contagem de caracteres poupa meia hora de adivinhação: quase sempre é
    container quente com o segredo antigo, e aí os números batem mas a senha
    não. `modal app stop bigode-memoria` força um container novo.
    """
    esperado = (os.environ.get("BIGODE_TOKEN") or "").strip()
    recebido = str(item.get("token") or "").strip()
    if not esperado:
        return "O segredo bigode-token nao chegou no conteiner."
    if recebido != esperado:
        return ("Token invalido. Recebi %d caracteres e esperava %d. Se os "
                "numeros batem, o conteiner ainda esta com o segredo antigo: "
                "rode `modal app stop %s` e tente de novo."
                % (len(recebido), len(esperado), APP))
    return None


@app.cls(
    image=imagem,
    gpu=PLACA,
    secrets=[modal.Secret.from_name("bigode-token")],
    scaledown_window=180,
    max_containers=1,
)
@modal.concurrent(max_inputs=4)
class Memoria:

    @modal.enter()
    def carregar(self):
        """Carrega os dois modelos UMA vez por container.

        A falha fica guardada em vez de derrubar o container: um app que
        morre no `enter` entra em crash-loop, a Modal fica reiniciando e
        cobrando, e nunca diz o motivo. Foi o que a Pipi passou um dia
        inteiro fazendo com o FLUX.
        """
        self.embutidor = None
        self.ranqueador = None
        self.erro = ""
        try:
            from sentence_transformers import SentenceTransformer, CrossEncoder
            self.embutidor = SentenceTransformer(MODELO_EMBUTIR, device="cuda")
            self.ranqueador = CrossEncoder(MODELO_RANQUEAR, device="cuda",
                                           max_length=512)
        except Exception as exc:
            self.erro = "%s: %s" % (type(exc).__name__, str(exc)[:300])

    # ------------------------------------------------------------------
    @modal.fastapi_endpoint(method="POST", docs=False)
    def embutir(self, item: dict):
        """Texto entra, números saem.

        Espera {"token": ..., "textos": ["...", "..."], "consulta": false}.

        `consulta` existe porque o bge-m3 rende mais quando sabe de que lado
        está: o texto guardado e a pergunta que o procura não recebem o
        mesmo tratamento. É uma linha, e melhora a busca de graça.
        """
        import time

        erro = _conferir_token(item)
        if erro:
            return {"ok": False, "erro": erro}
        if self.embutidor is None:
            return {"ok": False, "erro": "O modelo nao carregou. " + self.erro}

        textos = item.get("textos") or []
        if not isinstance(textos, list) or not textos:
            return {"ok": False, "erro": "Mande uma lista em 'textos'."}
        if len(textos) > 256:
            return {"ok": False,
                    "erro": "Maximo 256 textos por chamada (vieram %d). "
                            "Quebre em lotes." % len(textos)}

        textos = [str(t or "")[:8000] for t in textos]
        inicio = time.time()
        try:
            vetores = self.embutidor.encode(
                textos,
                batch_size=16,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            saida = [[float(x) for x in v] for v in vetores]
        except Exception as exc:
            return {"ok": False,
                    "erro": "%s: %s" % (type(exc).__name__, str(exc)[:300])}

        return {"ok": True, "vetores": saida, "modelo": MODELO_EMBUTIR,
                "dimensoes": len(saida[0]) if saida else 0,
                "segundos": round(time.time() - inicio, 2)}

    # ------------------------------------------------------------------
    @modal.fastapi_endpoint(method="POST", docs=False)
    def ranquear(self, item: dict):
        """A pergunta e os candidatos entram; a ordem certa sai.

        Espera {"token": ..., "consulta": "...", "trechos": [...],
                "quantos": 5}.

        Devolve os índices dos melhores, na ordem, com a nota de cada um.
        Índice e não o texto de volta: o texto já está do outro lado, e
        trazê-lo de novo dobraria o tamanho da resposta por nada.
        """
        import time

        erro = _conferir_token(item)
        if erro:
            return {"ok": False, "erro": erro}
        if self.ranqueador is None:
            return {"ok": False, "erro": "O modelo nao carregou. " + self.erro}

        consulta = str(item.get("consulta") or "").strip()
        trechos = item.get("trechos") or []
        if not consulta:
            return {"ok": False, "erro": "Falta a 'consulta'."}
        if not isinstance(trechos, list) or not trechos:
            return {"ok": False, "erro": "Mande uma lista em 'trechos'."}
        if len(trechos) > 100:
            return {"ok": False,
                    "erro": "Maximo 100 trechos por chamada (vieram %d)."
                            % len(trechos)}

        quantos = int(item.get("quantos") or 5)
        quantos = max(1, min(quantos, len(trechos)))

        pares = [[consulta, str(t or "")[:4000]] for t in trechos]
        inicio = time.time()
        try:
            notas = self.ranqueador.predict(pares, batch_size=16,
                                            show_progress_bar=False)
            notas = [float(n) for n in notas]
        except Exception as exc:
            return {"ok": False,
                    "erro": "%s: %s" % (type(exc).__name__, str(exc)[:300])}

        ordem = sorted(range(len(notas)), key=lambda i: notas[i], reverse=True)
        melhores = ordem[:quantos]

        return {"ok": True,
                "melhores": [{"i": i, "nota": round(notas[i], 4)}
                             for i in melhores],
                "modelo": MODELO_RANQUEAR,
                "segundos": round(time.time() - inicio, 2)}
