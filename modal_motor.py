"""O MOTOR DO BIGODE NA MODAL — llama.cpp numa placa de verdade
Venure · venure.com.br · 14/09/2026

O QUE ISTO SUBSTITUI
    O unico app do Bigode na Modal era o `modal_api_teste.py`: 32 linhas que
    devolviam {"mensagem": "Processamento simulado com sucesso"} e uma
    media_url apontando para exemplo.invalid. Reservava uma T4 e nao carregava
    modelo nenhum.

    Este aqui sobe o llama.cpp de verdade, com pesos, numa L4.

POR QUE llama.cpp E NAO vLLM
    E o MESMO motor que o Bigode ja usa no seu Windows e no Colab. Mesmo
    servidor, mesma API, mesmo jeito de falhar -- o que voce aprendeu
    depurando um vale para o outro. Trocar de motor so para a nuvem seria
    inventar um segundo conjunto de defeitos para aprender.

    E o modelo Q4_K_M tem 4,7 GB contra os ~15 GB do fp16 que o vLLM pediria.
    Container frio mais curto, e container frio e o que custa caro aqui.

POR QUE ESTE MODELO, E POR QUE ESTE REPOSITORIO
    Qwen2.5-Coder 7B Q4_K_M e o que voce ja mediu: 6,4 tok/s no seu
    processador, com as melhores notas da sua propria auditoria. Numa L4 ele
    anda muitas vezes mais rapido -- mesmas respostas, sem a espera.

    O repositorio foi escolhido a dedo: conferido em 14/09 pela API do
    Hugging Face, ele devolve "gated": false. Isso importa. O gerador da
    Pipi passou um dia inteiro em crash-loop porque o repositorio do FLUX
    exige aceite de licenca e ninguem tinha aceitado. Aqui nao ha formulario
    no caminho: o download funciona numa conta recem-criada.

A CHAVE E A MESMA IDEIA DO MODO HIBRIDO
    O endereco da Modal e publico. O llama-server tem `--api-key`, que exige
    o cabecalho `Authorization: Bearer ...` -- exatamente o que o
    modal_cliente.py do Bigode ja manda. Nao foi preciso mudar uma linha do
    cliente: o contrato ja batia.

    Sem chave, este arquivo SE RECUSA A SUBIR. Um LLM aberto na internet com
    o seu credito atras dele nao e um risco aceitavel por comodidade.

COMO PUBLICAR

    pip install modal
    python -m modal setup                    (uma vez, abre o navegador)

    python -m modal secret create bigode-token BIGODE_TOKEN=<senha-longa>
    python -m modal deploy modal_motor.py

    O `deploy` demora na primeira vez: ele baixa os 4,7 GB do modelo para o
    Volume DURANTE a construcao da imagem, nao na hora do primeiro pedido.
    E de proposito -- ver o comentario do `_baixar` abaixo.

    No fim sai um endereco terminado em `-servidor.modal.run`. Depois:

        python usar_modal_motor.py

CUSTO
    A L4 so roda enquanto ha pedido. O `scaledown_window` de 5 minutos
    mantem o container vivo depois da ultima mensagem: numa conversa, isso
    e a diferenca entre pagar o aquecimento uma vez ou a cada pergunta.

    Armazenamento do Volume continua sendo cobrado mesmo com o spend limit
    em zero -- sao 4,7 GB, pouco, mas nao zero.
"""

import os
import subprocess
from pathlib import Path

import modal

# ----------------------------------------------------------------------
# DOIS MOTORES, UM ARQUIVO                                    (17/09)
# ----------------------------------------------------------------------
# Troque PERFIL, rode `modal deploy modal_motor.py`, e nasce um app novo
# com outro nome e outro endereco. Os dois ficam de pe ao mesmo tempo, cada
# um dormindo sozinho -- voce escolhe qual usar no `usar_modal_motor.py`.
#
# Um arquivo so porque o resto e identico: mesma imagem, mesma placa, mesmo
# llama.cpp, mesmas opcoes. Duplicar o arquivo para trocar duas linhas
# significaria que todo conserto teria de ser feito duas vezes -- e um dia
# seria feito so num.
# O PERFIL VEM DO AMBIENTE, E NAO DE EDITAR ESTE ARQUIVO     (18/09)
#
#   Era uma constante: para publicar o outro motor era preciso abrir o
#   arquivo, trocar a palavra, publicar, e lembrar de voltar. Esquecer de
#   voltar significa que o proximo `modal deploy` sobe o app errado.
#
#   Agora:
#       set BIGODE_PERFIL=codigo  &&  python -m modal deploy modal_motor.py
#
#   O arquivo fica igual no disco, os dois apps convivem, e o BIGODE.bat
#   consegue escolher sozinho.
PERFIL = (os.environ.get("BIGODE_PERFIL") or "conversa").strip().lower()

# A TABELA MORA NO `perfis_modal.py`                          (18/09)
#
#   Ela estava aqui, e a tela do Bigode precisava dela -- mas importar
#   este arquivo traz junto o `import modal`, que nao existe no Python
#   portatil. O import falhava calado e os botoes da placa sumiam da tela.
#
#   Dado num arquivo sem dependencia; biblioteca fica com quem precisa.
from perfis_modal import PERFIS

if PERFIL not in PERFIS:
    raise SystemExit("PERFIL deve ser um destes: %s" % ", ".join(PERFIS))

_P = PERFIS[PERFIL]
APP = _P["app"]
REPO = _P["repo"]
ARQUIVO = _P["arquivo"]

MODELOS = "/modelos"
PORTA = 8000

# O CHAO DE 8192, OUTRA VEZ
#     O prompt de sistema do Bigode mais o esquema das 34 ferramentas dao
#     ~3.835 tokens. Com janela de 4096 a conversa comeca ja cortada. O
#     config() do cerebro.py forca 8192 por isso. Aqui vai o dobro: numa L4
#     de 24 GB com um modelo de 4,7 GB sobra memoria, e sobrar e o ponto.
JANELA = _P["janela"]

# Um Volume POR PERFIL. Compartilhar um so faria os dois modelos morarem
# juntos -- 4,7 GB + 10,4 GB = 15 GB cobrados por mes mesmo quando voce usa
# um deles. Separados, da para apagar o que nao esta em uso:
#
#     python -m modal volume delete bigode-modelos-codigo
volume = modal.Volume.from_name("bigode-modelos-%s" % PERFIL,
                                create_if_missing=True)


def _baixar():
    """Traz o modelo para o Volume na CONSTRUCAO, nao no primeiro pedido.

    Se o download acontecesse no arranque do container, o primeiro pedido
    esperaria 4,7 GB de rede com a placa ja ligada e contando -- e o
    `startup_timeout` do web_server provavelmente estouraria antes, dando
    um erro que nao explica nada.

    Aqui isso acontece uma vez, no `modal deploy`, com voce olhando.
    """
    from huggingface_hub import hf_hub_download

    hf_hub_download(repo_id=REPO, filename=ARQUIVO, local_dir=MODELOS)


imagem = (
    modal.Image.from_registry(
        "ghcr.io/ggml-org/llama.cpp:server-cuda", add_python="3.12")
    # A imagem oficial do llama.cpp tem ENTRYPOINT proprio (/app/llama-server).
    # Sem limpar, o comando do runner da Modal viraria ARGUMENTO do
    # llama-server em vez de rodar -- e o container morreria sem dizer por que.
    .entrypoint([])
    .pip_install("huggingface_hub[hf_transfer]==0.28.1")
    # hf_transfer acelera o download unico da construcao.
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .run_function(_baixar, volumes={MODELOS: volume})
)

app = modal.App(APP, image=imagem)


@app.function(
    gpu="L4",
    volumes={MODELOS: volume},
    secrets=[modal.Secret.from_name("bigode-token")],
    timeout=60 * 60,
    # Cinco minutos vivo apos a ultima mensagem. Conversa e rajada de
    # perguntas curtas: sem isto, cada pergunta pagaria o aquecimento.
    scaledown_window=300,
)
# Um container, varios pedidos. O llama-server aguenta -- e sem isto a Modal
# subiria uma placa nova para cada aba aberta.
@modal.concurrent(max_inputs=8)
@modal.web_server(PORTA, startup_timeout=300)
def servidor():
    chave = (os.environ.get("BIGODE_TOKEN") or "").strip()
    if not chave:
        # Falhar aqui e o comportamento correto. Ver o cabecalho.
        raise RuntimeError(
            "O segredo bigode-token nao chegou. Rode: "
            "modal secret create bigode-token BIGODE_TOKEN=<senha-longa>")

    modelo = Path(MODELOS) / ARQUIVO
    if not modelo.is_file():
        raise RuntimeError(
            "O modelo nao esta no Volume (%s). Rode `modal deploy "
            "modal_motor.py` de novo: o download acontece na construcao."
            % modelo)

    subprocess.Popen([
        "/app/llama-server",
        "--model", str(modelo),
        "--host", "0.0.0.0",
        "--port", str(PORTA),
        # Exige Authorization: Bearer <chave>. O modal_cliente.py do Bigode
        # ja manda esse cabecalho.
        "--api-key", chave,
        # 99 = tudo na placa. O modelo cabe inteiro na L4 com folga.
        "--n-gpu-layers", "99",
        "--ctx-size", str(JANELA),
        # Usa o chat template do proprio modelo, que no Qwen2.5-Coder ja
        # inclui <tool_call>. O Bigode ainda nao pede ferramentas por esta
        # rota, mas quando pedir o servidor ja entende.
        "--jinja",
    ])
    print("Perfil: %s  ->  %s" % (PERFIL, _P["nota"]))
