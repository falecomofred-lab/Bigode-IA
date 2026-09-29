"""O BIGODE FALANDO — o caminho de volta da voz
Venure · venure.com.br · 20/09/2026

O QUE FALTAVA

    O `modal_voz.py` já faz a ida: você fala, o Whisper escreve. A volta
    nunca existiu -- a resposta dele sempre foi um bloco de texto para ler.

    Este arquivo fecha o par: texto entra, áudio em português sai.

ESTE É O ÚNICO APP DA MODAL AQUI QUE NÃO USA PLACA

    E é de propósito. O Piper roda em processador e sintetiza mais rápido
    que tempo real: uma resposta de 30 segundos de fala sai em ~2 s de CPU.
    Pedir uma T4 para isso seria reservar uma placa de vídeo para esperar.

    Custo de CPU na Modal é uma fração do de GPU. Falando o dia inteiro,
    isto não chega a alguns centavos por mês.

POR QUE PIPER, E NÃO O MAIS FAMOSO

    O XTTS da Coqui soa melhor e clona voz -- e a licença dele (CPML)
    proíbe uso comercial. Você vende serviço sob a marca Venure; um modelo
    que não pode ir junto é um modelo que não serve, por melhor que seja.

    O Piper é MIT: usa, embute, vende, sem pedir nada a ninguém. A voz
    `pt_BR-faber-medium` é brasileira, masculina, clara e sem sotaque de
    robô de central telefônica.

    Trocar de voz é trocar uma linha -- a lista está em
    huggingface.co/rhasspy/piper-voices, pasta pt/pt_BR.

A VERSÃO ESTÁ PRESA, E POR UM MOTIVO CONCRETO

    O piper-tts 1.2 tem `voice.synthesize(texto, arquivo_wav)`. O 1.3
    renomeou para `synthesize_wav` e mudou o que devolve. Sem o pino, o
    primeiro `modal deploy` de um dia qualquer do futuro quebraria com
    AttributeError -- e o erro apontaria para o meu código, não para a
    atualização que o causou.

COMO PUBLICAR

    python -m modal secret create bigode-token BIGODE_TOKEN=<a-mesma-senha>
    python -m modal deploy modal_fala.py

    Sai um endereço terminado em `-falar.modal.run`. Guarde com:

        python usar_modal_fala.py

    Ele fala uma frase de teste e só grava no config.json se voltar áudio.
"""

import os

import modal

APP = "bigode-fala"

# A voz. pt_BR, masculina, qualidade "medium" -- a alta (`high`) existe, é
# ~3x maior e a diferença só aparece em fone bom.
VOZ = "pt_BR-faber-medium"
CAMINHO_VOZ = "pt/pt_BR/faber/medium"
REPO_VOZES = "rhasspy/piper-voices"

# Teto de texto por chamada. Uma resposta longa do Bigode passa fácil disso,
# e a tela quebra em pedaços antes de mandar -- ver o comentário do endpoint.
LIMITE = 4000

app = modal.App(APP)


def _baixar_voz():
    """Traz os dois arquivos da voz DURANTE a construção da imagem.

    Função com nome, no topo do arquivo -- a Modal precisa achar o módulo e
    o nome dela na máquina de build. Lambda morre com:

        InvalidError: Image.run_function does not support lambda functions.
    """
    from huggingface_hub import hf_hub_download

    for sufixo in (".onnx", ".onnx.json"):
        hf_hub_download(repo_id=REPO_VOZES,
                        filename="%s/%s%s" % (CAMINHO_VOZ, VOZ, sufixo),
                        local_dir="/voz")


imagem = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # Ver o cabeçalho: o 1.3 renomeou o método que este arquivo chama.
        "piper-tts==1.2.0",
        "huggingface_hub==0.25.2",
        "fastapi[standard]",
    )
    .run_function(_baixar_voz)
)


@app.cls(
    image=imagem,
    # SEM gpu= DE PROPÓSITO. Ver o cabeçalho.
    secrets=[modal.Secret.from_name("bigode-token")],
    scaledown_window=120,
    max_containers=1,
)
@modal.concurrent(max_inputs=8)
class Fala:

    @modal.enter()
    def carregar(self):
        """Carrega a voz UMA vez por container.

        A falha fica guardada em vez de derrubar o container: app que morre
        no `enter` entra em crash-loop, e a Modal reinicia e cobra sem nunca
        dizer o motivo.
        """
        self.voz = None
        self.erro = ""
        try:
            from piper.voice import PiperVoice
            base = "/voz/%s/%s" % (CAMINHO_VOZ, VOZ)
            self.voz = PiperVoice.load(base + ".onnx", base + ".onnx.json")
        except Exception as exc:
            self.erro = "%s: %s" % (type(exc).__name__, str(exc)[:300])

    @modal.fastapi_endpoint(method="POST", docs=False)
    def falar(self, item: dict):
        """Texto entra, um WAV em base64 sai.

        Espera {"token": ..., "texto": "...", "velocidade": 1.0}.

        WAV e não MP3: o navegador toca WAV direto, e converter exigiria
        ffmpeg na imagem e mais um passo que pode falhar. O arquivo fica
        maior, e fica no ar por dois segundos -- não é o gargalo de nada.
        """
        import base64
        import io
        import time
        import wave

        esperado = (os.environ.get("BIGODE_TOKEN") or "").strip()
        recebido = str(item.get("token") or "").strip()
        if not esperado:
            return {"ok": False, "erro": "O segredo bigode-token nao chegou "
                                         "no conteiner."}
        if recebido != esperado:
            # A contagem poupa meia hora: quase sempre é container quente com
            # o segredo antigo, e aí os números batem mas a senha não.
            return {"ok": False,
                    "erro": ("Token invalido. Recebi %d caracteres e esperava "
                             "%d. Se os numeros batem, rode "
                             "`modal app stop %s` e tente de novo."
                             % (len(recebido), len(esperado), APP))}

        if self.voz is None:
            return {"ok": False, "erro": "A voz nao carregou. " + self.erro}

        texto = str(item.get("texto") or "").strip()
        if not texto:
            return {"ok": False, "erro": "Mande algum texto."}
        if len(texto) > LIMITE:
            # CORTAR E AVISAR, EM VEZ DE CORTAR CALADO
            #
            #   O escritor.py da Pipi já ensinou isto do jeito caro: ele
            #   truncava o prompt em silêncio e o resultado saía diferente do
            #   pedido, sem nada na tela explicando por quê.
            return {"ok": False,
                    "erro": "Texto de %d caracteres; o limite e %d. Quebre em "
                            "pedacos antes de mandar." % (len(texto), LIMITE)}

        try:
            velocidade = float(item.get("velocidade") or 1.0)
        except Exception:
            velocidade = 1.0
        # length_scale é o inverso da velocidade: 0.9 fala mais rápido.
        escala = max(0.5, min(2.0, 1.0 / max(0.25, velocidade)))

        inicio = time.time()
        try:
            memoria = io.BytesIO()
            with wave.open(memoria, "wb") as arquivo:
                self.voz.synthesize(texto, arquivo, length_scale=escala)
            dados = memoria.getvalue()
        except Exception as exc:
            return {"ok": False,
                    "erro": "%s: %s" % (type(exc).__name__, str(exc)[:300])}

        # Um WAV de 16 bits a 22.050 Hz: 44 bytes de cabeçalho + 2 por
        # amostra. Dá para saber a duração sem abrir o arquivo de novo.
        segundos_audio = max(0.0, (len(dados) - 44) / 2 / 22050.0)

        return {"ok": True,
                "wav": base64.b64encode(dados).decode("ascii"),
                "voz": VOZ,
                "caracteres": len(texto),
                "duracao": round(segundos_audio, 1),
                "segundos": round(time.time() - inicio, 2)}
