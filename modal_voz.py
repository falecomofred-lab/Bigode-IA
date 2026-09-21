"""A VOZ DO BIGODE NA MODAL — Whisper large-v3 numa placa
Venure · venure.com.br · 17/09/2026

POR QUE ESTE ARQUIVO EXISTE

    O botao de microfone nunca chegou a usar a captacao boa. O caminho era:

        alternarVoz()  ->  if (window.Voz && VOZ.disponivel) Voz.alternar()
                       ->  senao, ditado do proprio Chrome

    e `VOZ.disponivel` vem do voz.py, que responde `True` so quando acha um
    `whisper-cli.exe` e um `ggml-*.bin` no disco. Nao ha nenhum dos dois
    nesta maquina -- procurei em projetos\\voz, Cerebro\\voz, projetos e
    Cerebro. Logo `disponivel` sempre foi False, e TODA gravacao caiu no
    ditado do Chrome, que dentro da barra lateral da extensao falha.

    Ou seja: o problema nunca foi a captacao, e sim que nao havia para onde
    mandar o audio. Escrever um capturador melhor nao resolveria -- e o tipo
    de conserto que se faz por hipotese, olhando o codigo que a gente acabou
    de escrever em vez de olhar por que ele nao roda.

POR QUE NA MODAL, E NAO INSTALANDO O whisper.cpp AQUI

    A conta da Modal ja esta de pe, paga e testada -- o motor de texto ja
    roda nela. Instalar whisper.cpp no Windows pede binario compilado, um
    modelo de ~1,5 GB e um caminho fixo no disco. E mais uma peca para
    manter, num projeto que hoje roda de qualquer maquina.

    E ha o ponto que decide: o large-v3 na placa entende portugues falado
    depressa, com sotaque e com ruido de fundo. O `small` que caberia no
    processador erra nome proprio e numero -- justo o que voce dita.

O QUE CUSTA

    T4, $0.000164/s. Uma frase de 10 s transcreve em ~1,5 s.
    Container frio: ~20 s (o modelo vem pronto na imagem, nao baixa na hora).
    `scaledown_window=120`: depois de 2 min sem falar, a placa desliga.

    Ditando o dia inteiro, 200 frases, da menos de 10 centavos de dolar.

COMO PUBLICAR

    python -m modal secret create bigode-token BIGODE_TOKEN=<a-mesma-senha>
    python -m modal deploy modal_voz.py

    Sai um endereco terminado em `-transcrever.modal.run`. Cole em
    config.json:

        "voz_modal": {
          "url":   "https://...-transcrever.modal.run",
          "token": "<a-mesma-senha>"
        }

    Confira com:  python usar_modal_voz.py
"""

import os

import modal

APP = "bigode-voz"
MODELO = "large-v3"
PLACA = "T4"

app = modal.App(APP)

def _baixar_modelo():
    """Puxa os pesos DURANTE a construcao da imagem, nao no primeiro pedido.

    Precisa ser uma funcao com nome, no topo do arquivo. Eu tinha escrito
    como lambda e o deploy morreu na hora:

        InvalidError: Image.run_function does not support lambda functions.

    A Modal envia esta funcao para a maquina de build, e para isso precisa
    achar o modulo e o nome dela. Lambda nao tem nome -- nao ha o que
    procurar do outro lado.
    """
    from faster_whisper import WhisperModel
    # device="cpu" de proposito: aqui so se baixa arquivo. Reservar uma
    # placa para esperar a rede seria pagar T4 por minuto de download.
    WhisperModel(MODELO, device="cpu", compute_type="int8")


# O modelo entra NA IMAGEM, nao num Volume.
#
# Sao ~1,5 GB, e baixar na hora do primeiro pedido somaria uns 40 s a uma
# espera que ja e a pior (container frio). Na imagem, ele ja esta no disco
# quando o conteiner nasce -- custa alguns GB de armazenamento de imagem,
# que a Modal nao cobra como Volume.
imagem = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    # POR QUE TRES VERSOES ESTAO PRESAS AQUI                    (17/09)
    #
    # Sem os pinos, a construcao morreu assim:
    #
    #     File ".../faster_whisper/utils.py", line 8, in <module>
    #         import requests
    #     ModuleNotFoundError: No module named 'requests'
    #
    # O faster-whisper 1.0.3 USA requests mas nao o DECLARA -- ele vinha de
    # carona no huggingface_hub, que na epoca dependia de requests. O hub
    # 1.x trocou para httpx e parou de trazer. Pacote de 2024 caindo numa
    # dependencia de 2026.
    #
    # `faster-whisper==1.0.3` sozinho nao protege de nada: o pino prende a
    # versao dele, e as das dependencias sobem sozinhas. Quem quebra e
    # sempre a que voce nao escreveu.
    #
    # Entao: o hub volta para a faixa com que o faster-whisper 1.0.3 foi
    # testado, e requests fica escrito -- explicito, para nao depender de
    # novo da boa vontade de outro pacote.
    .pip_install(
        "faster-whisper==1.0.3",
        "huggingface_hub==0.25.2",
        "requests",
        "fastapi[standard]",
    )
    .run_function(_baixar_modelo)
)


@app.cls(
    image=imagem,
    gpu=PLACA,
    secrets=[modal.Secret.from_name("bigode-token")],
    scaledown_window=120,
    max_containers=1,
)
@modal.concurrent(max_inputs=4)
class Voz:

    @modal.enter()
    def carregar(self):
        """Carrega o modelo UMA vez por conteiner, nao por pedido.

        Sem isto, cada frase ditada pagaria os ~8 s de carga do large-v3 --
        mais tempo do que a transcricao em si.

        A falha fica guardada em vez de derrubar o conteiner: um app que
        morre no `enter` entra em crash-loop e a Modal fica reiniciando,
        cobrando, sem nunca dizer o motivo. Foi o que a Pipi passou um dia
        inteiro fazendo com o FLUX.
        """
        self.modelo = None
        self.erro = ""
        try:
            from faster_whisper import WhisperModel
            self.modelo = WhisperModel(MODELO, device="cuda",
                                       compute_type="float16")
        except Exception as exc:
            self.erro = "%s: %s" % (type(exc).__name__, str(exc)[:300])

    @modal.fastapi_endpoint(method="POST", docs=False)
    def transcrever(self, item: dict):
        import base64
        import tempfile
        import time

        esperado = (os.environ.get("BIGODE_TOKEN") or "").strip()
        recebido = str(item.get("token") or "").strip()
        if not esperado:
            return {"ok": False, "erro": "O segredo bigode-token nao chegou "
                                         "no conteiner."}
        if recebido != esperado:
            # Contar os caracteres poupa meia hora de adivinhacao: quase
            # sempre e conteiner quente com o segredo antigo, e ai os
            # numeros batem mas a senha nao. `modal app stop bigode-voz`
            # mata o conteiner e forca um novo, com o segredo de agora.
            return {"ok": False,
                    "erro": ("Token invalido. Recebi %d caracteres e esperava "
                             "%d. Se os numeros batem, o conteiner ainda esta "
                             "com o segredo antigo: rode "
                             "`modal app stop %s` e tente de novo."
                             % (len(recebido), len(esperado), APP))}

        if self.modelo is None:
            return {"ok": False, "erro": "O modelo nao carregou. " + self.erro}

        bruto = item.get("wav") or ""
        try:
            audio = base64.b64decode(bruto)
        except Exception:
            return {"ok": False, "erro": "O audio nao veio em base64."}
        if len(audio) < 2000:
            return {"ok": False, "erro": "Audio curto demais."}
        if len(audio) > 30_000_000:
            return {"ok": False, "erro": "Audio grande demais (limite ~30 MB)."}

        inicio = time.time()
        caminho = tempfile.mktemp(suffix=".wav")
        try:
            with open(caminho, "wb") as f:
                f.write(audio)
            partes, info = self.modelo.transcribe(
                caminho,
                language=str(item.get("idioma") or "pt"),
                beam_size=5,
                # Corta o silencio antes de transcrever. Sem isto o Whisper
                # "ouve" frase em trecho mudo e inventa texto -- o defeito
                # mais conhecido dele, e o mais constrangedor num produto.
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 400},
                condition_on_previous_text=False,
            )
            texto = " ".join(p.text.strip() for p in partes).strip()
        except Exception as exc:
            return {"ok": False,
                    "erro": "%s: %s" % (type(exc).__name__, str(exc)[:300])}
        finally:
            try:
                os.unlink(caminho)
            except Exception:
                pass

        return {"ok": True, "texto": texto, "modelo": MODELO,
                "segundos": round(time.time() - inicio, 2),
                "confianca": round(float(getattr(info, "language_probability",
                                                 0) or 0), 2)}
