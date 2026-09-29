import modal

imagem = modal.Image.debian_slim().uv_pip_install("fastapi[standard]")

app = modal.App(
    name="cerebro-modal-api",
    image=imagem,
)


@app.function(gpu="T4")
@modal.fastapi_endpoint(
    method="POST",
    docs=True,
)
def gerar_midia(dados: dict) -> dict:
    prompt = dados.get("prompt", "").strip()

    if not prompt:
        return {
            "ok": False,
            "erro": "O campo 'prompt' é obrigatório.",
        }

    return {
        "ok": True,
        "mensagem": "Processamento simulado com sucesso.",
        "prompt_recebido": prompt,
        "gpu": "T4",
        "media_url": "https://exemplo.invalid/pipi-ia/midia-gerada.png",
    }
