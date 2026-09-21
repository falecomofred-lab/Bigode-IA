"""IMAGENS - o Bigode desenha

Fala com o ComfyUI pela porta 8188 e devolve o caminho do arquivo pronto.

POR QUE UM SEGUNDO MOTOR, E NAO UM .gguf NA CELULA 1
    O formato e o mesmo -- GGUF -- mas quem le e outro. O `llama.cpp`, que
    move o Bigode hoje, so entende modelo de texto. Modelo de imagem e uma
    arquitetura diferente (difusao, nao previsao da proxima palavra) e quem
    roda e o ComfyUI com a extensao ComfyUI-GGUF.

    Por isso ele fica SEPARADO: processo proprio, porta propria. Se o
    ComfyUI cair, o Bigode continua pensando. Se voce trocar a IA de texto,
    o desenho nao muda. Sao duas ferramentas na mesma bancada, nao uma
    ferramenta com dois modos.

QUAL MODELO, E POR QUE
    FLUX.1-schnell, quantizado em GGUF pelo city96.

    A escolha nao foi por qualidade pura -- o FLUX.1-dev desenha um pouco
    melhor. Foi pela LICENCA: o schnell e Apache 2.0, uso comercial
    liberado. O dev tem licenca nao-comercial. Como isto aqui e da Venure e
    as imagens podem virar anuncio, o dev esta fora de discussao.

    Bonus: o schnell resolve em 4 passos, contra ~20 do dev. Numa T4, que e
    placa de 2018, isso e a diferenca entre esperar 20 segundos e esperar
    dois minutos.

    Nenhum dos dois carimba marca d'agua na imagem.

A CONTA DE MEMORIA (o que faz isto falhar)
    A T4 tem 15 GB e o motor de TEXTO ja esta la dentro. Somando:

        granite     ~5,5 GB   sobra ~9,5   -> cabe com folga
        qwen-coder  ~6,0 GB   sobra ~9,0   -> cabe
        deepseek   ~12,5 GB   sobra ~2,5   -> NAO cabe

    O ComfyUI sobe com `--lowvram`, que carrega um pedaco por vez (primeiro
    o codificador de texto, depois o desenhista) em vez de tudo junto. E o
    que faz caber. Mesmo assim, com o deepseek carregado nao ha espaco.

    Por isso `conferir()` mede a placa ANTES e diz o que fazer, em vez de
    deixar o ComfyUI morrer sem memoria no meio -- falha que aparece na tela
    como "nao respondeu", sem dizer por que.

Venure - venure.com.br
"""

import json
import os
import random
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent

COMFY = "http://127.0.0.1:8188"

# ---------------------------------------------------------- onde estao elas
#
# As IAs de imagem moram numa pasta SEPARADA das de texto, de proposito:
#
#     Pen IA/              -> .gguf de conversa, lidos pelo llama.cpp
#     Pen IA/IA Imagem/    -> .gguf de difusao, lidos pelo ComfyUI
#
# Sao formatos com o mesmo sobrenome e familias diferentes. Misturar as duas
# pastas faz o Bigode oferecer um modelo de desenho como se fosse de
# conversa -- e ele falha na carga, com uma mensagem que nao ajuda ninguem.
PASTAS_IMAGEM = [
    str(BASE / "IA Imagem"),
    str(BASE / "modelos" / "imagem"),
    "/content/IA Imagem",
    r"G:\Outros computadores\USB e dispositivos externos\Pen IA\IA Imagem",
    "/content/drive/Othercomputers/USB e dispositivos externos/Pen IA/IA Imagem",
]


def pasta_imagem():
    """A primeira pasta de IA de imagem que existe nesta máquina.

    A pasta local do projeto vem primeiro para que os arquivos anexados ao
    Bigode tenham prioridade sobre uma cópia antiga no Drive.
    """
    for p in PASTAS_IMAGEM:
        if Path(p).is_dir():
            return Path(p)
    return None


def modelos_de_imagem():
    """Os .gguf de desenho que voce tem, com tamanho. Vazio se nao houver."""
    pasta = pasta_imagem()
    if not pasta:
        return []
    achados = []
    for a in sorted(pasta.glob("*.gguf")):
        achados.append({"nome": a.stem,
                        "arquivo": a.name,
                        "caminho": str(a),
                        "gb": round(a.stat().st_size / 1e9, 1)})
    return achados


def _nome_configurado(chave, padrao=""):
    """Lê uma escolha de modelo sem tornar o módulo obrigatório no boot."""
    try:
        valor = _config().get(chave, padrao)
        return Path(str(valor)).name if valor else padrao
    except Exception:
        return padrao


def componentes_imagem(modelo_unet=""):
    """Resolve os dois GGUF e os arquivos auxiliares usados pelo workflow.

    Os nomes podem ser definidos no config.json por `imagem_unet` e
    `imagem_t5`. Sem configuração, o primeiro arquivo cujo nome sugere UNet
    e o primeiro cujo nome sugere T5 são escolhidos. Isso permite trocar os
    GGUF sem editar código, mas nunca mistura o GGUF de texto DeepSeek/Qwen
    com o desenhista.
    """
    pasta = pasta_imagem()
    vazio = {"pasta": str(pasta) if pasta else "", "unet": "", "t5": "",
             "clip": "clip_l.safetensors", "vae": "ae.safetensors",
             "faltando": []}
    if not pasta:
        vazio["faltando"] = ["pasta de imagem"]
        return vazio

    arquivos = sorted(pasta.glob("*.gguf"))
    nomes = {a.name.lower(): a.name for a in arquivos}
    unet = _nome_configurado("imagem_unet")
    t5 = _nome_configurado("imagem_t5")

    def escolher(valor, pistas, fallback=""):
        if valor and valor.lower() in nomes:
            return nomes[valor.lower()]
        for a in arquivos:
            n = a.name.lower()
            if any(p in n for p in pistas):
                return a.name
        return fallback

    # O UNet do FLUX normalmente contém flux/unet/transformer; o T5 contém
    # t5/encoder. Nunca escolher um GGUF só pelo tamanho: modelos de texto
    # também podem ter vários gigabytes.
    vazio["unet"] = escolher(modelo_unet or unet, ("flux", "unet", "transformer"))
    vazio["t5"] = escolher(t5, ("t5", "encoder"))
    vazio["clip"] = _nome_configurado("imagem_clip", vazio["clip"])
    vazio["vae"] = _nome_configurado("imagem_vae", vazio["vae"])
    if not vazio["unet"]:
        vazio["faltando"].append("GGUF UNet/difusão")
    if not vazio["t5"]:
        vazio["faltando"].append("GGUF T5/encoder")
    if not (pasta / vazio["clip"]).is_file():
        vazio["faltando"].append(vazio["clip"])
    if not (pasta / vazio["vae"]).is_file():
        vazio["faltando"].append(vazio["vae"])
    return vazio

# Quanto o desenho precisa na placa, com --lowvram, ja contando o VAE e o
# codificador. Medido, nao chutado: pico observado numa T4 com FLUX schnell
# Q4_K_S e o T5 em Q3.
PRECISA_GB = 7.5


# ---------------------------------------------------------------- formatos
#
# Numeros multiplos de 64 de proposito: o FLUX trabalha em blocos e um lado
# que nao seja multiplo de 64 sai com faixa borrada na borda.
#
# Todos acima de 1 megapixel -- e o ponto em que o FLUX foi treinado. Pedir
# 512x512 nao sai "mais rapido e igual": sai pior, com anatomia errada.
FORMATOS = {
    "quadrado":  (1024, 1024),   # feed, catalogo, avatar
    "retrato":   (832, 1216),    # post vertical
    "paisagem":  (1216, 832),    # capa, banner, thumbnail
    "story":     (768, 1344),    # story, reels, tela de celular
    "capa":      (1344, 768),    # topo de site, cabecalho de e-mail
}

PADRAO = "quadrado"


def _config():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _pasta_saida(pasta_solicitada=""):
    """Onde as imagens caem.

    Vai para a primeira pasta liberada, e nao para uma pasta interna do
    Bigode: assim o arquivo nasce onde voce ja procura os seus projetos, e
    o `ler_arquivo` do proprio Bigode alcanca ele depois.
    """
    liberadas = [Path(p).expanduser().resolve()
                 for p in (_config().get("pastas_liberadas") or [])]
    raiz = Path(pasta_solicitada).expanduser().resolve() if pasta_solicitada else None
    if raiz and not any(raiz == p or p in raiz.parents for p in liberadas):
        return BASE
    if not raiz:
        raiz = liberadas[0] if liberadas else BASE
    destino = raiz / "Pipi IA" / "produção"
    try:
        destino.mkdir(parents=True, exist_ok=True)
        return destino
    except Exception:
        return BASE


def _vram_livre_gb():
    """Quanto sobra na placa AGORA. Zero quando nao ha placa."""
    try:
        saida = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free",
             "--format=csv,noheader,nounits"],
            text=True).strip().splitlines()[0]
        return float(saida) / 1024.0
    except Exception:
        return 0.0


# O resultado do ultimo "esta no ar?", com a hora.
#
# POR QUE O CACHE
#     `ferramentas.ativas()` chama `no_ar()` a CADA mensagem, para decidir
#     se `gerar_imagem` entra no catalogo. Sem cache, com o ComfyUI
#     desligado, toda mensagem do Fred esperava os 3 segundos do timeout
#     antes de o Bigode comecar a pensar. Tres segundos em toda pergunta,
#     para descobrir uma coisa que nao muda de segundo em segundo.
#
#     30s e curto o bastante para a ferramenta aparecer logo depois de voce
#     ligar o desenhista, e longo o bastante para nao pesar.
_ULTIMA_CHECAGEM = [0.0, False]
_VALIDADE = 30.0


def no_ar(forcar=False):
    agora = time.time()
    if not forcar and (agora - _ULTIMA_CHECAGEM[0]) < _VALIDADE:
        return _ULTIMA_CHECAGEM[1]
    try:
        urllib.request.urlopen(COMFY + "/system_stats", timeout=2)
        vivo = True
    except Exception:
        vivo = False
    _ULTIMA_CHECAGEM[0] = agora
    _ULTIMA_CHECAGEM[1] = vivo
    return vivo


def conferir():
    """Da para desenhar agora? Se nao, DIZ O QUE FAZER.

    Devolve "" quando esta tudo certo. Qualquer outra coisa e a explicacao
    que vai para a tela.
    """
    # `forcar=True` aqui: na hora de desenhar de verdade vale gastar os 2
    # segundos e ter a verdade, em vez de confiar num cache de 30s.
    if not no_ar(forcar=True):
        return ("O desenhista (ComfyUI) nao esta ligado. No Colab, rode a "
                "celula 'Ligar o desenhista'. No pendrive, esta funcao ainda "
                "nao esta disponivel -- a placa do notebook nao aguenta.")

    livre = _vram_livre_gb()
    if livre and livre < PRECISA_GB:
        return ("Falta memoria na placa: sobram %.1f GB e o desenho precisa "
                "de ~%.1f GB. O motor de texto grande esta ocupando o espaco. "
                "Troque para o granite (celula 9 do Colab, NOVA = \"granite\") "
                "e peca de novo." % (livre, PRECISA_GB))
    return ""


# ------------------------------------------------------------------ o pedido
#
# Este e o "grafo" que o ComfyUI executa. Cada numero e um no, e cada no diz
# de onde vem a sua entrada. Escrito na mao de proposito: a alternativa e
# exportar um .json gigante da interface do ComfyUI, que ninguem consegue
# ler nem consertar seis meses depois.
def _receita(descricao, largura, altura, semente, unet, t5, clip, vae,
             passos=4, guidance=3.5, negativo=""):
    return {
        # 1. o desenhista, em GGUF
        "1": {"class_type": "UnetLoaderGGUF",
              "inputs": {"unet_name": unet}},

        # 2. os dois leitores de texto. O CLIP entende palavra solta; o T5
        #    entende frase inteira. O FLUX usa os dois juntos -- por isso
        #    descricao longa e em portugues funciona bem aqui.
        "2": {"class_type": "DualCLIPLoaderGGUF",
              "inputs": {"clip_name1": t5,
                         "clip_name2": clip,
                         "type": "flux"}},

        # 3. o VAE: traduz o rascunho interno em pixels de verdade
        "3": {"class_type": "VAELoader",
              "inputs": {"vae_name": vae}},

        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": descricao}},

        # 5. tela em branco no tamanho pedido
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": largura, "height": altura, "batch_size": 1}},

        # 6. o schnell foi destilado para nao usar orientacao negativa:
        #    guidance 3.5 e o valor que os autores publicaram. Mexer aqui
        #    costuma piorar.
        "6": {"class_type": "FluxGuidance",
              "inputs": {"conditioning": ["4", 0], "guidance": guidance}},

        # 7. o schnell nao tem "prompt negativo". Passar um texto vazio nao
        #    e preguica -- e como ele foi treinado.
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": negativo}},

        "8": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0],
                         "positive": ["6", 0],
                         "negative": ["7", 0],
                         "latent_image": ["5", 0],
                         "seed": semente,
                         "steps": passos,
                         "cfg": 1.0,          # schnell: sempre 1.0
                         "sampler_name": "euler",
                         "scheduler": "simple",
                         "denoise": 1.0}},

        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},

        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": "bigode"}},
    }


def _enviar(receita, cliente):
    corpo = json.dumps({"prompt": receita, "client_id": cliente}).encode("utf-8")
    pedido = urllib.request.Request(
        COMFY + "/prompt", data=corpo,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=30) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def _esperar(id_pedido, teto=420):
    """Espera o desenho ficar pronto. Devolve a lista de arquivos gerados.

    O teto de 7 minutos existe porque a primeira imagem da sessao carrega
    ~10 GB de modelo do disco -- as seguintes saem em segundos. Sem teto, um
    erro do ComfyUI deixaria o Bigode pendurado para sempre.
    """
    inicio = time.time()
    while time.time() - inicio < teto:
        time.sleep(2)
        try:
            with urllib.request.urlopen(
                    COMFY + "/history/" + id_pedido, timeout=10) as r:
                historico = json.loads(r.read().decode("utf-8"))
        except Exception:
            continue
        if id_pedido not in historico:
            continue
        entrada = historico[id_pedido]
        estado = (entrada.get("status") or {})
        if estado.get("status_str") == "error" or estado.get("completed") is False:
            return None, _erro_legivel(entrada)
        saidas = []
        for no in (entrada.get("outputs") or {}).values():
            for img in (no.get("images") or []):
                saidas.append(img)
        if saidas:
            return saidas, ""
    return None, ("Passou de %d minutos e o desenho nao ficou pronto. "
                  "Confira o ComfyUI." % (teto // 60))


def _erro_legivel(entrada):
    """A mensagem do ComfyUI vem enterrada em tres niveis de dicionario."""
    try:
        for msg in (entrada.get("status") or {}).get("messages") or []:
            if msg and msg[0] == "execution_error":
                d = msg[1]
                return "%s: %s" % (d.get("node_type", "?"),
                                   str(d.get("exception_message"))[:300])
    except Exception:
        pass
    return "o desenhista recusou o pedido e nao disse por que"


def _baixar(img, destino):
    parametros = urllib.parse.urlencode({
        "filename": img.get("filename", ""),
        "subfolder": img.get("subfolder", ""),
        "type": img.get("type", "output"),
    })
    with urllib.request.urlopen(COMFY + "/view?" + parametros, timeout=120) as r:
        destino.write_bytes(r.read())


# ------------------------------------------------------------------ a porta
def gerar_imagem(descricao="", formato="", nome="", modelo="", negativo="",
                 passos=4, guidance=3.5, semente=0, pasta_saida=""):
    """Desenha uma imagem e devolve onde ela foi salva."""
    descricao = (descricao or "").strip()
    if not descricao:
        return "Preciso da descricao do que desenhar."

    problema = conferir()
    if problema:
        return problema

    formato = (formato or PADRAO).strip().lower()
    if formato not in FORMATOS:
        # Nao recusar por causa de uma palavra: o modelo escreve "vertical"
        # ou "16:9" o tempo todo. Melhor entender do que devolver erro.
        apelidos = {"vertical": "retrato", "horizontal": "paisagem",
                    "9:16": "story", "16:9": "capa", "1:1": "quadrado",
                    "reels": "story", "instagram": "quadrado",
                    "banner": "capa", "thumbnail": "paisagem"}
        formato = apelidos.get(formato, PADRAO)

    largura, altura = FORMATOS[formato]
    componentes = componentes_imagem(modelo)
    if componentes["faltando"]:
        return ("Faltam componentes para desenhar: " +
                ", ".join(componentes["faltando"]) +
                ". Coloque os arquivos na pasta IA Imagem ou configure "
                "imagem_unet/imagem_t5 no config.json.")
    try:
        passos = max(1, min(20, int(passos or 4)))
    except Exception:
        passos = 4
    try:
        guidance = max(0.0, min(20.0, float(guidance or 3.5)))
    except Exception:
        guidance = 3.5
    try:
        semente = int(semente or 0) or random.randint(1, 2 ** 31 - 1)
    except Exception:
        semente = random.randint(1, 2 ** 31 - 1)
    cliente = str(uuid.uuid4())

    try:
        resposta = _enviar(_receita(
            descricao, largura, altura, semente,
            componentes["unet"], componentes["t5"], componentes["clip"],
            componentes["vae"], passos=passos, guidance=guidance,
            negativo=negativo),
                           cliente)
    except urllib.error.HTTPError as erro:
        return ("O desenhista recusou o pedido (%s). Isso quase sempre e "
                "arquivo de modelo faltando -- rode a celula do desenhista "
                "de novo." % erro.code)
    except Exception as erro:
        return "Nao consegui falar com o desenhista: %s" % erro

    id_pedido = resposta.get("prompt_id")
    if not id_pedido:
        return "O desenhista aceitou mas nao devolveu numero de pedido."

    inicio = time.time()
    imagens, erro = _esperar(id_pedido)
    if not imagens:
        return "Nao saiu: " + erro

    pasta = _pasta_saida(pasta_saida)
    base_nome = "".join(c for c in (nome or descricao)[:40]
                        if c.isalnum() or c in " -_").strip() or "criativo"
    base_nome = base_nome.replace(" ", "-").lower()

    salvos = []
    for i, img in enumerate(imagens):
        sufixo = "" if len(imagens) == 1 else "-%d" % (i + 1)
        alvo = pasta / ("%s-%s%s.png" % (base_nome, time.strftime("%H%M%S"),
                                         sufixo))
        try:
            _baixar(img, alvo)
            salvos.append(alvo)
        except Exception as erro:
            return "Desenhou, mas nao consegui trazer o arquivo: %s" % erro

    segundos = time.time() - inicio
    linhas = ["Imagem pronta em %.0fs  (%dx%d, %s)"
              % (segundos, largura, altura, formato)]
    for a in salvos:
        linhas.append("  " + str(a))
    linhas.append("")
    linhas.append("PNG sem marca d'agua, licenca Apache 2.0 (uso comercial "
                  "liberado). Semente %d -- guarde se quiser repetir o mesmo "
                  "resultado." % semente)
    return "\n".join(linhas)
