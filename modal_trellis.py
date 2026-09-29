"""GERADOR 3D DE ALTA QUALIDADE DO BIGODE -- TRELLIS na sua conta Modal
Venure · venure.com.br · 28/09/2026

PARA QUE SERVE

    Foto (ou 2 a 4 fotos do MESMO objeto) -> modelo 3D com textura (.glb).
    E o mesmo TRELLIS da Microsoft que o Bigode usava pelo Hugging Face,
    agora rodando na SUA conta Modal: sem a cota gratis de 5 min/dia do
    Hugging Face, sem fila de desconhecidos.

    Com varias fotos (frente, lado, costas) a forma sai muito mais fiel:
    o modelo nao precisa inventar o lado que nao viu.

O MODELO

    microsoft/TRELLIS-image-large · licenca MIT.
    Codigo e rodas pre-compiladas: Space oficial JeffreyXiang/TRELLIS.

O QUE CUSTA

    A100 40 GB, US$ 0,000583/s (~US$ 2,10/hora ligada).
    Um modelo: ~40-90 s de GPU -> ~US$ 0,03 a 0,05.
    Container frio: ~1-2 min a mais (os pesos ficam no Volume).
    `scaledown_window=120`: 2 minutos sem pedido e a placa desliga.
    Os US$ 30/mes de credito do plano Starter cobrem centenas de modelos.

COMO PUBLICAR (uma vez)

    python -m modal deploy modal_trellis.py
    python usar_modal_trellis.py

    O segundo comando testa com uma imagem e grava o endereco no
    config.json (trellis_modal). Usa o mesmo segredo `bigode-token` da
    visao do Bigode.
"""

import modal

APP = "bigode-trellis"
PLACA = "A100"
PESOS = "/pesos"
SPACE = "https://huggingface.co/spaces/JeffreyXiang/TRELLIS/resolve/main"

app = modal.App(APP)
volume = modal.Volume.from_name("bigode-trellis-pesos", create_if_missing=True)


def _baixar():
    """Pesos no Volume na CONSTRUCAO, nao no primeiro pedido."""
    import os
    from huggingface_hub import snapshot_download
    snapshot_download(repo_id="microsoft/TRELLIS-image-large", local_dir=PESOS + "/trellis")
    # o TRELLIS baixa o DINOv2 do GitHub toda vez que liga; guardamos no Volume
    os.environ["TORCH_HOME"] = PESOS + "/torch"
    import torch
    torch.hub.load("facebookresearch/dinov2", "dinov2_vitl14_reg", pretrained=True)


imagem = (
    modal.Image.from_registry("nvidia/cuda:12.1.1-devel-ubuntu22.04", add_python="3.10")
    .apt_install("git", "git-lfs", "libgl1", "libglib2.0-0", "libxrender1", "libxext6",
                 "libsm6", "ffmpeg", "build-essential", "ninja-build")
    .pip_install("torch==2.4.0", "torchvision==0.19.0",
                 index_url="https://download.pytorch.org/whl/cu121")
    .pip_install(
        "numpy==1.26.4", "pillow==10.4.0", "imageio==2.36.1", "imageio-ffmpeg==0.5.1", "tqdm==4.67.1",
        "easydict==1.13", "opencv-python-headless==4.10.0.84", "scipy==1.14.1",
        "rembg==2.0.60", "onnxruntime==1.20.1", "trimesh==4.5.3", "xatlas==0.0.9",
        "pyvista==0.44.2", "pymeshfix==0.17.0", "igraph==0.11.8",
        "xformers==0.0.27.post2", "spconv-cu120==2.3.6", "transformers==4.46.3",
        "huggingface_hub[hf_transfer]==0.26.5", "fastapi[standard]",
        "git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8",
        extra_index_url="https://download.pytorch.org/whl/cu121",
    )
    .pip_install(
        SPACE + "/wheels/diff_gaussian_rasterization-0.0.0-cp310-cp310-linux_x86_64.whl?download=true",
        SPACE + "/wheels/nvdiffrast-0.3.3-cp310-cp310-linux_x86_64.whl?download=true",
    )
    .run_commands(
        "GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 https://huggingface.co/spaces/JeffreyXiang/TRELLIS /trellis_app",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "0", "SPCONV_ALGO": "native",
          "ATTN_BACKEND": "xformers", "PYTHONPATH": "/trellis_app",
          "TORCH_HOME": PESOS + "/torch"})
    .run_function(_baixar, volumes={PESOS: volume})
)


@app.cls(
    image=imagem,
    gpu=PLACA,
    volumes={PESOS: volume},
    secrets=[modal.Secret.from_name("bigode-token")],
    scaledown_window=120,
    max_containers=1,
    timeout=900,
)
class Trellis:

    @modal.enter()
    def carregar(self):
        """Carrega uma vez por container. Falha fica guardada (sem crash-loop)."""
        self.pipeline = None
        self.erro = ""
        try:
            from trellis.pipelines import TrellisImageTo3DPipeline
            self.pipeline = TrellisImageTo3DPipeline.from_pretrained(PESOS + "/trellis")
            self.pipeline.cuda()
        except Exception as exc:
            import traceback
            self.erro = "%s: %s\n%s" % (type(exc).__name__, str(exc)[:300], traceback.format_exc()[-1500:])

    def _mascara(self, original, preparada, n=64):
        """Contorno do objeto (64x64, texto 0/1) para o Bigode deixar o modelo
        em pe do mesmo jeito que na foto. (28/09)"""
        try:
            from PIL import Image
            alfa = None
            if original.mode in ("RGBA", "LA") and original.getextrema()[-1][0] < 250:
                alfa = original.convert("RGBA").split()[3]
            elif getattr(self.pipeline, "rembg_session", None) is not None:
                import rembg
                alfa = rembg.remove(original.convert("RGB"), session=self.pipeline.rembg_session).split()[3]
            if alfa is None:                      # fundo preto da imagem preparada
                alfa = preparada.convert("L").point(lambda v: 255 if v > 8 else 0)
            caixa = alfa.point(lambda v: 255 if v > 128 else 0).getbbox()
            if not caixa:
                return ""
            r = alfa.crop(caixa); w, h = r.size; k = n / float(max(w, h))
            nw, nh = max(1, min(n, round(w * k))), max(1, min(n, round(h * k)))
            r = r.resize((nw, nh))
            tela = Image.new("L", (n, n), 0); tela.paste(r, ((n - nw) // 2, (n - nh) // 2))
            return "".join("1" if v > 128 else "0" for v in tela.getdata())
        except Exception:
            return ""

    # O decorador fica COLADO no gerar. (28/09: o _mascara entrou entre os
    # dois, virou endpoint no lugar do gerar e o TRELLIS no Modal saiu do ar.)
    @modal.fastapi_endpoint(method="POST", docs=False)
    def gerar(self, item: dict):
        """{"token", "imagens": [base64, ...], "seed", "textura", "simplificar"}
        -> {"ok": true, "glb": base64, "segundos": n}"""
        import base64, io, os, time, tempfile
        if item.get("token") != os.environ.get("BIGODE_TOKEN"):
            return {"ok": False, "erro": "token invalido"}
        if self.pipeline is None:
            return {"ok": False, "erro": "o modelo nao carregou: " + self.erro}
        inicio = time.time()
        try:
            from PIL import Image
            from trellis.utils import postprocessing_utils
            fotos = []
            for b64 in (item.get("imagens") or [])[:4]:
                b64 = str(b64)
                if b64.startswith("data:"):
                    b64 = b64.partition(",")[2]
                fotos.append(Image.open(io.BytesIO(base64.b64decode(b64))))
            if not fotos:
                return {"ok": False, "erro": "nenhuma imagem"}
            seed = int(item.get("seed") or 1)
            originais = list(fotos)
            fotos = [self.pipeline.preprocess_image(f) for f in fotos]
            mascara = self._mascara(originais[0], fotos[0])
            # padrao do modelo (25 passos): mais lento que o Space (12), mais fiel
            passos = {}
            passos2 = {}
            if len(fotos) == 1:
                saida = self.pipeline.run(fotos[0], seed=seed, formats=["gaussian", "mesh"],
                                          preprocess_image=False,
                                          sparse_structure_sampler_params=passos,
                                          slat_sampler_params=passos2)
            else:
                saida = self.pipeline.run_multi_image(fotos, seed=seed, formats=["gaussian", "mesh"],
                                                      preprocess_image=False,
                                                      sparse_structure_sampler_params=passos,
                                                      slat_sampler_params=passos2,
                                                      mode="stochastic")
            glb = postprocessing_utils.to_glb(
                saida["gaussian"][0], saida["mesh"][0],
                simplify=float(item.get("simplificar") or 0.95),
                texture_size=int(item.get("textura") or 1024), verbose=False)
            caminho = tempfile.mktemp(suffix=".glb")
            glb.export(caminho)
            dados = open(caminho, "rb").read()
            return {"ok": True, "glb": base64.b64encode(dados).decode("ascii"),
                    "fotos": len(fotos), "segundos": round(time.time() - inicio, 1),
                    "mascara": mascara}
        except Exception as exc:
            import traceback
            return {"ok": False, "erro": "%s: %s" % (type(exc).__name__, str(exc)[:300]),
                    "detalhe": traceback.format_exc()[-1500:]}
