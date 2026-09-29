"""
Gerador 3D LOCAL do Bigode (plano B do modo Detalhado).

Quando o TRELLIS.2 do Hugging Face nao responde (cota de GPU acabou, site
fora do ar), o Bigode transforma a imagem em modelo 3D AQUI NO SEU PC, com o
TripoSR (licenca MIT, Stability AI + Tripo). Roda so com o processador: sem
cota, sem limite por dia. A qualidade e menor que a do TRELLIS, mas e um
objeto 3D de verdade, com cor.

Tudo fica numa pasta separada, FORA do Google Drive (sao ~3 GB):
    %LOCALAPPDATA%\\bigode_3d
      libs\\          pacotes do gerador (separados dos pacotes do Bigode)
      TripoSR-main\\  codigo do TripoSR
      rodar.py       script que gera o .glb
      pronto.txt     marca que a instalacao terminou

A instalacao e automatica e acontece UMA vez, em segundo plano (10 a 20 min,
depende da internet). Enquanto instala, o Bigode continua funcionando.
"""

import io
import os
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

PASTA = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache") / "bigode_3d"
# O Bigode roda num Python "embutido" (pasta python\ do Pen IA), que NAO tem
# o modulo venv. Por isso os pacotes vao para uma pasta propria (pip --target)
# e o script de geracao poe essa pasta na frente do caminho de busca.
LIBS = PASTA / "libs"
PY = Path(sys.executable)
CODIGO = PASTA / "TripoSR-main"
RODAR = PASTA / "rodar.py"
PRONTO = PASTA / "pronto.txt"
LOG = PASTA / "instalacao.log"
TRAVA_ARQ = PASTA / "instalando.lock"      # outro processo ja esta instalando
ZIP_TRIPOSR = "https://codeload.github.com/VAST-AI-Research/TripoSR/zip/refs/heads/main"

PACOTES = ["omegaconf", "einops", "transformers<4.50", "trimesh", "rembg",
           "onnxruntime", "huggingface-hub", "Pillow", "numpy", "xatlas"]

_TRAVA = threading.Lock()
_INSTALANDO = {"ativo": False, "etapa": "", "erro": ""}
_SEM_JANELA = 0x08000000 if os.name == "nt" else 0   # nao abrir console preto no Windows


# O TripoSR usa o "torchmcubes", que no Windows precisa de compilador C++.
# Este substituto faz a mesma coisa com o PyMCubes (que ja vem pronto).
SUBSTITUTO_MCUBES = '''import numpy as np, torch
def marching_cubes(level, thr=0.0):
    vol = level.detach().cpu().numpy().astype(np.float64)
    try:
        import mcubes
        v, f = mcubes.marching_cubes(vol, thr)
    except ImportError:                     # plano B: scikit-image
        from skimage.measure import marching_cubes as mc
        v, f, _n, _val = mc(vol, level=thr)
        f = f[:, ::-1]                      # mesma orientacao das faces do mcubes
    v = v[:, ::-1].copy()
    return torch.from_numpy(v.astype(np.float32)), torch.from_numpy(np.ascontiguousarray(f).astype(np.int64))
'''

SCRIPT_RODAR = r'''
import sys, os, time
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "libs"))
sys.path.insert(0, os.path.join(AQUI, "TripoSR-main"))
sys.path.insert(0, os.path.join(AQUI, "shim"))
import numpy as np, torch
from PIL import Image
torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
from tsr.system import TSR
from tsr.utils import remove_background, resize_foreground

modelo = TSR.from_pretrained("stabilityai/TripoSR", config_name="config.yaml", weight_name="model.ckpt")
modelo.renderer.set_chunk_size(8192)
if len(sys.argv) < 3:
    print("modelo ok"); sys.exit(0)

entrada, saida = sys.argv[1], sys.argv[2]
resolucao = int(sys.argv[3]) if len(sys.argv) > 3 else 320
tam_textura = int(sys.argv[4]) if len(sys.argv) > 4 else 1024


def rasterizar_posicoes(uvs, faces, pos, N):
    """Para cada pixel da textura, a posicao 3D do ponto da malha que cai nele.
    Feito com numpy (sem OpenGL), em lotes de triangulos."""
    tex = np.zeros((N, N, 3), np.float32)
    ocup = np.zeros((N, N), bool)
    uv = uvs * (N - 1)
    T = uv[faces]                                     # (F,3,2)
    P = pos[faces]                                    # (F,3,3)
    mn = np.floor(T.min(1)).astype(int)
    mx = np.ceil(T.max(1)).astype(int)
    tam = (mx - mn).max(1) + 1
    S = 12
    lotes = [np.where(tam <= S)[0], np.where(tam > S)[0]]
    grade = np.stack(np.meshgrid(np.arange(S), np.arange(S), indexing="xy"), -1).reshape(-1, 2)
    for idx in np.array_split(lotes[0], max(1, len(lotes[0]) // 20000)):
        if not len(idx):
            continue
        pts = mn[idx][:, None, :] + grade[None]       # (B,S*S,2)
        a, b, c = T[idx, 0][:, None], T[idx, 1][:, None], T[idx, 2][:, None]
        v0, v1, v2 = b - a, c - a, pts + 0.0 - a
        d00 = (v0 * v0).sum(-1); d01 = (v0 * v1).sum(-1); d11 = (v1 * v1).sum(-1)
        d20 = (v2 * v0).sum(-1); d21 = (v2 * v1).sum(-1)
        den = d00 * d11 - d01 * d01
        den = np.where(np.abs(den) < 1e-12, 1e-12, den)
        w1 = (d11 * d20 - d01 * d21) / den
        w2 = (d00 * d21 - d01 * d20) / den
        w0 = 1 - w1 - w2
        dentro = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        dentro &= (pts[..., 0] >= 0) & (pts[..., 0] < N) & (pts[..., 1] >= 0) & (pts[..., 1] < N)
        bb, kk = np.nonzero(dentro)
        p3 = (w0[bb, kk, None] * P[idx][bb, 0] + w1[bb, kk, None] * P[idx][bb, 1]
              + w2[bb, kk, None] * P[idx][bb, 2])
        xs, ys = pts[bb, kk, 0], pts[bb, kk, 1]
        tex[ys, xs] = p3
        ocup[ys, xs] = True
    for f in lotes[1]:
        x0, y0 = mn[f]; x1, y1 = mx[f]
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        pts = np.stack([xs.ravel(), ys.ravel()], -1).astype(np.float64)
        a, b, c = T[f]
        v0, v1, v2 = b - a, c - a, pts - a
        d00 = v0 @ v0; d01 = v0 @ v1; d11 = v1 @ v1
        d20 = v2 @ v0; d21 = v2 @ v1
        den = d00 * d11 - d01 * d01 or 1e-12
        w1 = (d11 * d20 - d01 * d21) / den; w2 = (d00 * d21 - d01 * d20) / den; w0 = 1 - w1 - w2
        m = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02) & (pts[:, 0] < N) & (pts[:, 1] < N) & (pts[:, 0] >= 0) & (pts[:, 1] >= 0)
        p3 = w0[m, None] * P[f, 0] + w1[m, None] * P[f, 1] + w2[m, None] * P[f, 2]
        xi, yi = pts[m, 0].astype(int), pts[m, 1].astype(int)
        tex[yi, xi] = p3; ocup[yi, xi] = True
    return tex, ocup


def dilatar(img, ocup, passos=4):
    """Espalha a cor para os pixels vizinhos vazios (evita costura escura)."""
    for _ in range(passos):
        novo = img.copy(); nocup = ocup.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            viz = np.roll(np.roll(ocup, dy, 0), dx, 1)
            cor = np.roll(np.roll(img, dy, 0), dx, 1)
            m = viz & ~nocup
            novo[m] = cor[m]; nocup |= m
        img, ocup = novo, nocup
    return img


t0 = time.time()
img = Image.open(entrada)
if not (img.mode == "RGBA" and img.getextrema()[3][0] < 250):
    import rembg
    img = remove_background(img.convert("RGB"), rembg.new_session("u2net"))
img = resize_foreground(img, 0.85)
a = np.array(img).astype(np.float32) / 255.0
a = a[:, :, :3] * a[:, :, 3:4] + (1 - a[:, :, 3:4]) * 0.5
img = Image.fromarray((a * 255.0).astype(np.uint8))

with torch.no_grad():
    codigos = modelo([img], device="cpu")
    malha = modelo.extract_mesh(codigos, False, resolution=resolucao)[0]
print("malha", round(time.time() - t0), malha.vertices.shape, flush=True)

import trimesh
try:
    import xatlas
except ImportError:
    xatlas = None
if xatlas is None:                 # sem xatlas: jeito antigo (cor por vertice)
    malha = modelo.extract_mesh(codigos, True, resolution=resolucao)[0]
    malha.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
    malha.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))
    malha.export(saida); print("ok (cor por vertice)", saida); sys.exit(0)
# textura de verdade (em vez de cor por vertice): muito mais nitida
vmap, faces, uvs = xatlas.parametrize(malha.vertices.astype(np.float32), malha.faces.astype(np.uint32))
pos = malha.vertices[vmap].astype(np.float64)
tex_pos, ocup = rasterizar_posicoes(uvs.astype(np.float64), faces.astype(np.int64), pos, tam_textura)
cores = np.zeros((tam_textura, tam_textura, 3), np.float32)
pontos = torch.tensor(tex_pos[ocup], dtype=torch.float32)
with torch.no_grad():
    saidas = []
    for pedaco in torch.split(pontos, 200000):
        saidas.append(modelo.renderer.query_triplane(modelo.decoder, pedaco, codigos[0])["color"])
    cores[ocup] = torch.cat(saidas).numpy()
cores = dilatar(cores, ocup)
textura = Image.fromarray((np.clip(cores, 0, 1) * 255).astype(np.uint8)).transpose(Image.FLIP_TOP_BOTTOM)
print("textura", round(time.time() - t0), flush=True)

final = trimesh.Trimesh(vertices=pos, faces=faces, process=False,
                        visual=trimesh.visual.TextureVisuals(
                            uv=uvs, material=trimesh.visual.material.PBRMaterial(
                                baseColorTexture=textura, roughnessFactor=0.7, metallicFactor=0.0)))
final.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))
final.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]))
final.export(saida)
print("ok", saida, round(time.time() - t0))
'''


def pronto():
    return PRONTO.exists() and LIBS.exists() and RODAR.exists()


def _outro_instalando():
    try:
        return TRAVA_ARQ.exists() and time.time() - TRAVA_ARQ.stat().st_mtime < 7200
    except Exception:
        return False


def _ultima_etapa():
    try:
        return LOG.read_text(encoding="utf-8").strip().splitlines()[-1][9:]
    except Exception:
        return ""


def estado():
    if pronto():
        return "instalado"
    if _INSTALANDO["ativo"]:
        return "instalando: " + _INSTALANDO["etapa"]
    if _outro_instalando():
        return "instalando: " + (_ultima_etapa() or "em andamento")
    if _INSTALANDO["erro"]:
        return "falhou: " + _INSTALANDO["erro"]
    return "nao instalado"


def _anotar(texto):
    _INSTALANDO["etapa"] = texto
    try:
        if TRAVA_ARQ.exists():
            os.utime(TRAVA_ARQ, None)      # mostra que a instalacao continua viva
        PASTA.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + texto + "\n")
    except Exception:
        pass


def _rodar(cmd, limite=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=limite,
                       creationflags=_SEM_JANELA)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "")[-600:])
    return r.stdout


def _instalar():
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        TRAVA_ARQ.write_text(str(os.getpid()), encoding="utf-8")
        LIBS.mkdir(parents=True, exist_ok=True)
        # O Python embutido do Bigode nao deixa o pip montar o "ambiente
        # isolado" de compilacao, e o omegaconf depende do antlr4, que so
        # existe como codigo-fonte. Erro visto no PC do Fred (28/09):
        #   BackendUnavailable: Cannot import 'setuptools.build_meta'
        # Solucao: setuptools/wheel no proprio Python e --no-build-isolation.
        _anotar("preparando o instalador (setuptools)")
        _rodar([str(PY), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                "setuptools", "wheel"])
        base = [str(PY), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                "--upgrade", "--no-build-isolation", "--target", str(LIBS)]
        # uma chamada so: com --target o pip nao enxerga o que ja foi
        # instalado antes, e duas chamadas podiam trocar versoes entre si.
        _anotar("instalando o PyTorch (CPU) e os complementos (~1 GB)")
        # No Windows o torch do PyPI ja e a versao so-CPU (~200 MB). O indice
        # proprio do PyTorch so e preciso no Linux -- e no PC do Fred ele
        # derrubou a conexao (erro SSL em 28/09), entao nem tentamos la.
        extra = [] if os.name == "nt" else ["--extra-index-url", "https://download.pytorch.org/whl/cpu"]
        for tentativa in (1, 2, 3):
            try:
                _rodar(base + ["--retries", "10", "--timeout", "120", "torch"] + PACOTES + extra,
                       limite=5400)
                break
            except Exception as erro_pip:
                if tentativa == 3 or "BackendUnavailable" in str(erro_pip):
                    raise
                _anotar("falhou (%s); tentando de novo (%d/3)"
                        % (str(erro_pip).strip().splitlines()[-1][:200] if str(erro_pip).strip() else "?",
                           tentativa + 1))
                time.sleep(20)
        try:                    # opcional: sem ele o scikit-image (vem com o rembg) faz o servico
            _rodar(base + ["--no-deps", "PyMCubes"])
        except Exception:
            _anotar("PyMCubes nao instalou; vou usar o scikit-image")
        if not (CODIGO / "tsr").exists():
            _anotar("baixando o codigo do TripoSR")
            try:
                pedido = urllib.request.Request(ZIP_TRIPOSR, headers={"User-Agent": "Bigode"})
                with urllib.request.urlopen(pedido, timeout=180) as r:
                    zipfile.ZipFile(io.BytesIO(r.read())).extractall(PASTA)
            except Exception:
                # plano B: git (se estiver instalado)
                _rodar(["git", "clone", "--depth", "1",
                        "https://github.com/VAST-AI-Research/TripoSR.git", str(CODIGO)])
        (PASTA / "shim").mkdir(exist_ok=True)
        (PASTA / "shim" / "torchmcubes.py").write_text(SUBSTITUTO_MCUBES, encoding="utf-8")
        RODAR.write_text(SCRIPT_RODAR, encoding="utf-8")
        _anotar("baixando o modelo TripoSR (~1,7 GB)")
        _rodar([str(PY), str(RODAR)], limite=5400)
        PRONTO.write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
        _anotar("pronto")
        _INSTALANDO["erro"] = ""
    except Exception as erro:
        _INSTALANDO["erro"] = str(erro)[-300:]
        _anotar("ERRO: " + str(erro)[-300:])
    finally:
        _INSTALANDO["ativo"] = False
        try:
            TRAVA_ARQ.unlink()
        except Exception:
            pass


def instalar_em_segundo_plano():
    """Comeca a instalacao sem travar o Bigode. Devolve texto para o Fred."""
    with _TRAVA:
        if pronto():
            return "O gerador 3D local ja esta instalado."
        if _INSTALANDO["ativo"] or _outro_instalando():
            return "O gerador 3D local ja esta sendo instalado (%s)." % (
                _INSTALANDO["etapa"] or _ultima_etapa())
        _INSTALANDO.update(ativo=True, erro="", etapa="comecando")
        threading.Thread(target=_instalar, daemon=True).start()
    return ("Comecei a instalar o gerador 3D LOCAL (roda no seu PC, sem limite por dia). "
            "Leva de 10 a 20 minutos, uma vez so, em segundo plano. "
            "Depois disso, quando o Hugging Face falhar, ele assume sozinho.")


# QUALIDADE (28/09, testado com a foto do gato Bigode):
#   cor por vertice (antes) -> manchas lavadas, preto virava cinza
#   textura 1024 + malha 256 -> cores nitidas, ~1 min a mais no PC
#   malha 384 -> um pouco mais de forma, mas 2,5x mais lento e mais ruido
QUALIDADES = {"normal": ("256", "1024"), "maxima": ("320", "2048")}


def _atualizar():
    """Instalacao antiga: poe o script novo e o xatlas sem reinstalar tudo."""
    try:
        if RODAR.read_text(encoding="utf-8") != SCRIPT_RODAR:
            RODAR.write_text(SCRIPT_RODAR, encoding="utf-8")
    except Exception:
        RODAR.write_text(SCRIPT_RODAR, encoding="utf-8")
    if not (LIBS / "xatlas").exists() and not list(LIBS.glob("xatlas*")):
        try:
            _rodar([str(PY), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                    "--no-deps", "--target", str(LIBS), "xatlas"], limite=600)
        except Exception:
            pass                 # sem xatlas o script cai no jeito antigo


def gerar(caminho_imagem, destino, qualidade="normal"):
    """Imagem -> .glb no proprio PC. Devolve (caminho_glb, erro)."""
    if not pronto():
        return None, "gerador local nao instalado"
    try:
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        _atualizar()
        res, tex = QUALIDADES.get(qualidade, QUALIDADES["normal"])
        _rodar([str(PY), str(RODAR), str(caminho_imagem), str(destino), res, tex], limite=1500)
        if not Path(destino).exists():
            return None, "o gerador local nao criou o arquivo"
        return Path(destino), None
    except subprocess.TimeoutExpired:
        return None, "o gerador local passou de 15 minutos"
    except Exception as erro:
        return None, "o gerador local falhou: %s" % str(erro)[-250:]
