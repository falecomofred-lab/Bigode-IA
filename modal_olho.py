"""O BIGODE ENXERGANDO — print, foto e documento fotografado
Venure · venure.com.br · 20/09/2026

PARA QUE SERVE

    Hoje, quando algo aparece errado na sua tela, você precisa traduzir a
    imagem em palavras antes de pedir ajuda -- e a tradução já perde metade
    do que importa. Com isto, você cola o print e ele vê.

    Serve também para o que está fora da memória por ser foto: apólice
    velha escaneada, contrato fotografado no celular, tabela num PDF que é
    imagem. Ele lê e devolve texto, e texto entra no ChromaDB.

O MODELO

    Qwen/Qwen2.5-VL-7B-Instruct · Apache 2.0

    A licença foi o critério de desempate, como no resto do projeto. Na
    família Qwen2.5-VL, o 7B é Apache; o 3B e o 72B têm licença própria,
    com restrições. Este pode ir para dentro de produto que você vende.

    E o português dele é bom -- ele responde sobre a imagem em português
    sem precisar de tradução no meio.

POR QUE L4 E NÃO L40S

    O modelo em bfloat16 ocupa ~16,5 GB. Numa L4 de 24 sobram ~7,5 GB, o
    que é suficiente DESDE QUE a imagem não chegue gigante: um print de
    4K vira dezenas de milhares de pedaços de imagem e estoura a memória.

    Por isso o `max_pixels` abaixo. Ele é o que permite usar a placa de
    US$ 0,80/hora em vez da de US$ 1,95 -- e a diferença de qualidade num
    print de tela é nenhuma: o texto continua legível.

    Sem esse teto, o container subiria, funcionaria com imagem pequena e
    morreria com imagem grande. Defeito intermitente, dependente do que o
    usuário colou. É o pior tipo, e foi evitado de propósito.

O QUE CUSTA

    L4, $0.000222/s. Uma pergunta sobre um print: ~4 s -> menos de 0,1
    centavo. Container frio: ~40 s (os pesos vêm no Volume, prontos).
    `scaledown_window=180`: 3 minutos sem imagem e a placa desliga.

COMO PUBLICAR

    python -m modal secret create bigode-token BIGODE_TOKEN=<a-mesma-senha>
    python -m modal deploy modal_olho.py

    Sai um endereço terminado em `-olhar.modal.run`. Guarde com:

        python usar_modal_olho.py

    Ele manda uma imagem desenhada na hora e confere se o Bigode descreveu
    o que realmente está nela -- e não só se respondeu alguma coisa.
"""

import os

import modal

APP = "bigode-olho"
MODELO = "Qwen/Qwen2.5-VL-7B-Instruct"
PLACA = "L4"
PESOS = "/pesos"

# O TETO DA IMAGEM, EM "PEDAÇOS DE 28x28"
#
#   O Qwen-VL corta a imagem em blocos de 28x28 pixels e trata cada bloco
#   como um token. 1280 blocos ≈ uma imagem de 1000x1000. Um print de
#   monitor 4K, sem teto, daria ~10.000 blocos -- e aí não é lentidão, é
#   falta de memória na placa no meio da resposta.
#
#   O processador redimensiona sozinho para caber. Ver o cabeçalho.
MAX_PIXELS = 1280 * 28 * 28
MIN_PIXELS = 256 * 28 * 28

PERGUNTA_PADRAO = (
    "Descreva o que está nesta imagem em português do Brasil. "
    "Se houver texto, transcreva-o exatamente como aparece. "
    "Se for uma tela de erro, diga qual é o erro e onde ele aparece. "
    "Seja objetivo: não invente nada que não esteja na imagem."
)

app = modal.App(APP)

# Volume e não imagem: são ~16 GB de pesos. Dentro da imagem, cada `modal
# deploy` reconstruiria e reenviaria tudo. No Volume eles ficam, e o deploy
# seguinte é rápido.
volume = modal.Volume.from_name("bigode-olho-pesos", create_if_missing=True)


def _baixar():
    """Traz os pesos para o Volume na CONSTRUÇÃO, não no primeiro pedido.

    Função com nome, no topo do arquivo -- lambda morre com
    `Image.run_function does not support lambda functions`.
    """
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=MODELO, local_dir=PESOS,
                      # Os .bin são a versão antiga dos mesmos pesos que os
                      # .safetensors. Sem este filtro o download dobra.
                      ignore_patterns=["*.bin", "*.pth", "*.msgpack"])


imagem = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # O Qwen2.5-VL só existe a partir do transformers 4.49. Preso porque
        # esta família muda o nome das classes com frequência: já foi
        # Qwen2VLForConditionalGeneration, hoje é Qwen2_5_VL..., e um
        # AttributeError no deploy apontaria para o meu código em vez de
        # para a atualização que o causou.
        "torch==2.5.1",
        "torchvision==0.20.1",
        "transformers==4.49.0",
        "accelerate==1.4.0",
        "pillow",
        "huggingface_hub[hf_transfer]==0.28.1",
        "fastapi[standard]",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .run_function(_baixar, volumes={PESOS: volume})
)


@app.cls(
    image=imagem,
    gpu=PLACA,
    volumes={PESOS: volume},
    secrets=[modal.Secret.from_name("bigode-token")],
    scaledown_window=180,
    max_containers=1,
)
@modal.concurrent(max_inputs=2)
class Olho:

    @modal.enter()
    def carregar(self):
        """Carrega o modelo UMA vez por container.

        A falha fica guardada em vez de derrubar o container: app que morre
        no `enter` entra em crash-loop e a Modal reinicia e cobra sem dizer
        o motivo. Foi o que a Pipi passou um dia inteiro fazendo com o FLUX.
        """
        self.modelo = None
        self.processador = None
        self.erro = ""
        try:
            import torch
            from transformers import (Qwen2_5_VLForConditionalGeneration,
                                      AutoProcessor)
            self.modelo = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                PESOS, torch_dtype=torch.bfloat16, device_map="cuda")
            self.processador = AutoProcessor.from_pretrained(
                PESOS, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS)
        except Exception as exc:
            self.erro = "%s: %s" % (type(exc).__name__, str(exc)[:300])

    @modal.fastapi_endpoint(method="POST", docs=False)
    def olhar(self, item: dict):
        """Imagem em base64 entra, texto sai.

        Espera {"token": ..., "imagem": "<base64 sem o data:>",
                "pergunta": "opcional"}.
        """
        import base64
        import io
        import time

        esperado = (os.environ.get("BIGODE_TOKEN") or "").strip()
        recebido = str(item.get("token") or "").strip()
        if not esperado:
            return {"ok": False, "erro": "O segredo bigode-token nao chegou "
                                         "no conteiner."}
        if recebido != esperado:
            return {"ok": False,
                    "erro": ("Token invalido. Recebi %d caracteres e esperava "
                             "%d. Se os numeros batem, rode "
                             "`modal app stop %s` e tente de novo."
                             % (len(recebido), len(esperado), APP))}

        if self.modelo is None:
            return {"ok": False, "erro": "O modelo nao carregou. " + self.erro}

        bruto = str(item.get("imagem") or "")
        # Aceita com ou sem o prefixo `data:image/png;base64,`. O navegador
        # manda com; um script manda sem. Recusar um dos dois seria criar um
        # erro que só aparece no caminho que ninguém testou.
        if bruto.startswith("data:"):
            _, _, bruto = bruto.partition(",")
        try:
            dados = base64.b64decode(bruto)
        except Exception:
            return {"ok": False, "erro": "A imagem nao veio em base64."}
        if len(dados) < 200:
            return {"ok": False, "erro": "Imagem vazia ou pequena demais."}
        if len(dados) > 20_000_000:
            return {"ok": False, "erro": "Imagem grande demais (limite ~20 MB)."}

        try:
            from PIL import Image
            figura = Image.open(io.BytesIO(dados)).convert("RGB")
        except Exception as exc:
            return {"ok": False,
                    "erro": "Nao consegui abrir a imagem: %s" % str(exc)[:200]}

        pergunta = str(item.get("pergunta") or "").strip() or PERGUNTA_PADRAO

        inicio = time.time()
        try:
            mensagens = [{"role": "user", "content": [
                {"type": "image"},
                {"type": "text", "text": pergunta},
            ]}]
            texto = self.processador.apply_chat_template(
                mensagens, tokenize=False, add_generation_prompt=True)
            entradas = self.processador(text=[texto], images=[figura],
                                        return_tensors="pt").to("cuda")
            # `limite` opcional (28/09): a lista de pecas para o Blender
            # precisa de mais espaco que uma descricao. Teto em 1600 para a
            # L4 nao ficar presa num pedido so.
            try:
                limite = max(64, min(1600, int(item.get("limite") or 700)))
            except (TypeError, ValueError):
                limite = 700
            saida = self.modelo.generate(**entradas, max_new_tokens=limite,
                                         do_sample=False)
            # Corta o que entrou: o generate devolve pergunta + resposta
            # coladas, e sem este recorte o Bigode repetiria a própria
            # instrução antes de responder.
            recorte = saida[0][entradas.input_ids.shape[1]:]
            resposta = self.processador.decode(
                recorte, skip_special_tokens=True).strip()
        except Exception as exc:
            return {"ok": False,
                    "erro": "%s: %s" % (type(exc).__name__, str(exc)[:300])}

        return {"ok": True, "texto": resposta, "modelo": MODELO,
                "tamanho": "%dx%d" % figura.size,
                "segundos": round(time.time() - inicio, 2)}
