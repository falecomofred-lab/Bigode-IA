#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BLENDER RECURSOS - o que faz o Bigode sair das formas simples      (28/09)

    1. Biblioteca Poly Haven (CC0, gratis, sem chave): modelos 3D reais,
       HDRIs (luz de ambiente) e texturas.
    2. Importar arquivo 3D: .glb .gltf .obj .fbx .stl .ply e .svg (SVG vira
       curva com volume: logo, contorno, rotulo).
    3. Referencias ortograficas: frente / lado / topo como fundo no Blender.
    4. Textura ou rotulo (PNG/JPG) aplicado num objeto.
    5. Imagem -> malha 3D de verdade com o TRELLIS.2 (Microsoft, MIT), pelo
       Space gratuito do Hugging Face, usando o token HF do config.json.
    6. Planejador maior: pedidos livres de Blender vao para o Qwen2.5-Coder
       32B do Hugging Face (mesmo token). Se falhar, volta o modelo local.

Tudo que roda DENTRO do Blender passa por blender.executar_codigo.
Tudo que baixa arquivo roda AQUI, no Python do Bigode.

Venure - venure.com.br
"""

import base64
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
PASTA = BASE / "producao_blender"
ATIVOS = PASTA / "ativos"
ENTRADA = PASTA / "entrada"
GERADOS = PASTA / "gerados"

AGENTE = "BigodeIA/1.0 (venure.com.br)"     # a Poly Haven exige User-Agent proprio
EXT_3D = (".glb", ".gltf", ".obj", ".fbx", ".stl", ".ply", ".svg")


def _b():
    import blender
    return blender


def _config():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _token_hf():
    return str((_config().get("huggingface") or {}).get("token") or "").strip()


def _baixar(url, destino=None, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        dados = r.read()
    if destino:
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_bytes(dados)
    return dados


def _ao_lado():
    """Trecho bpy: move a colecao COL para o lado do que ja existe."""
    return r'''
from mathutils import Vector
xs = []
for outro in bpy.context.scene.objects:
    if outro.type in ('MESH', 'CURVE', 'FONT') and outro.name not in COL.objects and outro.name != "Chao":
        xs += [(outro.matrix_world @ Vector(c)).x for c in outro.bound_box]
meus = [o for o in COL.objects if o.type in ('MESH', 'CURVE', 'FONT')]
if xs and meus:
    menor = min((o.matrix_world @ Vector(c)).x for o in meus for c in o.bound_box)
    desloca = max(xs) + 1.5 - menor
    for o in COL.objects:
        if o.parent is None:
            o.location.x += desloca
'''


def _enquadrar():
    return r'''
bpy.ops.object.select_all(action='DESELECT')
for o in COL.objects: o.select_set(True)
if COL.objects:
    bpy.context.view_layer.objects.active = COL.objects[0]
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for s in area.spaces:
            if s.type == 'VIEW_3D':
                s.shading.type = 'MATERIAL'; s.region_3d.view_perspective = 'PERSP'
        regiao = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if regiao:
            try:
                with bpy.context.temp_override(area=area, region=regiao):
                    bpy.ops.view3d.view_selected()
            except Exception:
                pass
'''


# ==========================================================================
# 1. POLY HAVEN
# ==========================================================================

# A busca da Poly Haven e em ingles. O Fred escreve em portugues.
PT_EN = {
    "cadeira": "chair", "mesa": "table", "sofa": "sofa", "cama": "bed", "armario": "cabinet",
    "estante": "shelf", "prateleira": "shelf", "luminaria": "lamp", "lampada": "lamp",
    "abajur": "lamp", "vaso": "vase", "planta": "plant", "arvore": "tree", "pedra": "rock",
    "rocha": "rock", "madeira": "wood", "tijolo": "brick", "concreto": "concrete",
    "metal": "metal", "grama": "grass", "terra": "ground", "chao": "floor", "piso": "floor",
    "parede": "wall", "tecido": "fabric", "couro": "leather", "marmore": "marble",
    "telha": "roof", "asfalto": "asphalt", "areia": "sand", "caixa": "box", "garrafa": "bottle",
    "copo": "glass", "caneca": "mug", "prato": "plate", "livro": "book", "relogio": "clock",
    "banco": "bench", "barril": "barrel", "cesta": "basket", "tapete": "rug",
    "ceu": "sky", "por do sol": "sunset", "noite": "night", "estudio": "studio",
    "praia": "beach", "floresta": "forest", "cidade": "city", "rua": "street",
    "interior": "indoor", "sala": "room", "cozinha": "kitchen", "tronco": "log",
    "cogumelo": "mushroom", "flor": "flower", "folha": "leaf", "fruta": "fruit",
    "maca": "apple", "banana": "banana", "camera": "camera", "ferramenta": "tool",
    "martelo": "hammer", "balde": "bucket", "escada": "ladder", "porta": "door",
    "janela": "window", "carro": "car", "moto": "motorcycle", "bicicleta": "bicycle",
    "estatua": "statue", "cerca": "fence", "poste": "lamp post", "ferro": "iron",
    "ouro": "gold", "tinta": "paint", "azulejo": "tiles", "ceramica": "ceramic",
}


def _sem_acento(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower())
                   if unicodedata.category(c) != "Mn")


def _traduzir(termo):
    t = _sem_acento(termo).strip()
    for pt in sorted(PT_EN, key=len, reverse=True):
        t = re.sub(r"\b%s\b" % re.escape(pt), PT_EN[pt], t)
    return t


_CACHE = {}


def polyhaven_buscar(termo="", tipo="models", limite=8):
    """Lista ativos da Poly Haven que casam com o termo. tipo: models, hdris, textures."""
    tipo = {"modelo": "models", "modelos": "models", "hdri": "hdris", "ceu": "hdris",
            "textura": "textures", "texturas": "textures"}.get(tipo, tipo)
    if tipo not in ("models", "hdris", "textures"):
        tipo = "models"
    if tipo not in _CACHE or time.time() - _CACHE[tipo][0] > 3600:
        _CACHE[tipo] = (time.time(), json.loads(_baixar(
            "https://api.polyhaven.com/assets?type=" + tipo).decode("utf-8")))
    todos = _CACHE[tipo][1]
    palavras = [p for p in re.findall(r"[a-z0-9]+", _traduzir(termo)) if len(p) > 2]
    pontos = []
    for ident, a in todos.items():
        texto = " ".join([ident, a.get("name", "")] + a.get("tags", []) + a.get("categories", [])).lower()
        nota = sum(3 if p in ident else (2 if p in texto.split() else (1 if p in texto else 0))
                   for p in palavras)
        if nota or not palavras:
            pontos.append((nota, a.get("download_count", 0), ident, a.get("name", ident)))
    pontos.sort(reverse=True)
    return [{"id": i, "nome": n} for _, _, i, n in pontos[:limite]]


def _baixar_modelo(ident, resolucao="1k"):
    """Baixa o glTF (com texturas) de um modelo. Devolve o caminho do .gltf."""
    arquivos = json.loads(_baixar("https://api.polyhaven.com/files/" + ident).decode("utf-8"))
    gltf = (arquivos.get("gltf") or {})
    res = gltf.get(resolucao) or next(iter(gltf.values()), None)
    if not res:
        raise ValueError("modelo sem glTF")
    item = res["gltf"]
    pasta = ATIVOS / ident
    principal = pasta / Path(urllib.parse.urlparse(item["url"]).path).name
    if not principal.exists():
        _baixar(item["url"], principal)
        for rel, inc in (item.get("include") or {}).items():
            _baixar(inc["url"], pasta / rel)
    return principal


def _baixar_hdri(ident, resolucao="1k"):
    arquivos = json.loads(_baixar("https://api.polyhaven.com/files/" + ident).decode("utf-8"))
    hdri = arquivos.get("hdri") or {}
    res = hdri.get(resolucao) or next(iter(hdri.values()), None)
    item = res.get("hdr") or next(iter(res.values()))
    destino = ATIVOS / (ident + ".hdr")
    if not destino.exists():
        _baixar(item["url"], destino)
    return destino


def _baixar_textura(ident, resolucao="1k"):
    """Devolve {cor, normal, aspereza} com os caminhos que existirem."""
    arquivos = json.loads(_baixar("https://api.polyhaven.com/files/" + ident).decode("utf-8"))
    mapa = {"cor": ("Diffuse", "diff", "Color"), "normal": ("nor_gl", "Normal"),
            "aspereza": ("Rough", "rough", "Roughness")}
    saida = {}
    for chave, nomes in mapa.items():
        for nome in nomes:
            if nome in arquivos:
                res = arquivos[nome].get(resolucao) or next(iter(arquivos[nome].values()))
                item = res.get("jpg") or res.get("png") or next(iter(res.values()))
                destino = ATIVOS / ident / ("%s_%s%s" % (ident, chave, Path(item["url"]).suffix))
                if not destino.exists():
                    _baixar(item["url"], destino)
                saida[chave] = str(destino)
                break
    return saida


def blender_biblioteca(busca="", tipo="modelo", objeto="", **_):
    """Busca na Poly Haven e coloca no Blender: modelo, ceu (HDRI) ou textura."""
    b = _b()
    tipo_api = {"modelo": "models", "hdri": "hdris", "ceu": "hdris", "luz": "hdris",
                "textura": "textures", "material": "textures"}.get((tipo or "modelo").lower(), "models")
    try:
        achados = polyhaven_buscar(busca, tipo_api, limite=5)
    except Exception as erro:
        return "Nao consegui falar com a Poly Haven: %s" % erro
    if not achados:
        return "A Poly Haven nao tem %s para '%s'. Tente outra palavra." % (tipo, busca)
    escolhido = achados[0]
    try:
        if tipo_api == "models":
            caminho = _baixar_modelo(escolhido["id"])
            texto = blender_importar(str(caminho), nome=escolhido["nome"])
        elif tipo_api == "hdris":
            caminho = _baixar_hdri(escolhido["id"])
            r = b.executar_codigo(_CODIGO_HDRI % str(caminho))
            texto = ("Ceu/luz '%s' aplicado no mundo do Blender." % escolhido["nome"]
                     if r.get("status") == "ok" else b._texto(r))
        else:
            mapas = _baixar_textura(escolhido["id"])
            texto = aplicar_mapas(mapas, objeto, escolhido["nome"])
    except Exception as erro:
        return "Achei '%s' na Poly Haven, mas falhou ao baixar/aplicar: %s" % (escolhido["nome"], erro)
    outros = ", ".join(a["nome"] for a in achados[1:])
    texto += "\nFonte: Poly Haven (polyhaven.com), licenca CC0."
    if outros:
        texto += "\nOutras opcoes: " + outros
    return texto


_CODIGO_HDRI = r'''
import bpy
mundo = bpy.context.scene.world or bpy.data.worlds.new("Mundo")
bpy.context.scene.world = mundo
mundo.use_nodes = True
nos = mundo.node_tree.nodes
fundo = nos.get("Background") or nos.new("ShaderNodeBackground")
env = nos.get("HDRI_Bigode") or nos.new("ShaderNodeTexEnvironment")
env.name = "HDRI_Bigode"
env.image = bpy.data.images.load(%r, check_existing=True)
mundo.node_tree.links.new(env.outputs["Color"], fundo.inputs["Color"])
saida = next((n for n in nos if n.type == 'OUTPUT_WORLD'), None) or nos.new("ShaderNodeOutputWorld")
mundo.node_tree.links.new(fundo.outputs["Background"], saida.inputs["Surface"])
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for s in area.spaces:
            if s.type == 'VIEW_3D':
                s.shading.type = 'RENDERED'
result = {"ok": True}
'''


# ==========================================================================
# 2. IMPORTAR ARQUIVO 3D / SVG
# ==========================================================================

def blender_importar(caminho="", nome="", altura=0, mascara=None, **_):
    """Importa .glb .gltf .obj .fbx .stl .ply .svg para uma colecao propria,
    ao lado do que ja existe. altura (m) opcional redimensiona."""
    b = _b()
    p = Path(str(caminho).strip().strip('"'))
    if not p.exists():
        cand = ENTRADA / p.name
        p = cand if cand.exists() else p
    if not p.exists():
        return "Arquivo nao encontrado: %s" % caminho
    ext = p.suffix.lower()
    if ext not in EXT_3D:
        return "Formato %s nao suportado. Use: %s" % (ext, " ".join(EXT_3D))
    try:
        altura = float(altura or 0)
    except (TypeError, ValueError):
        altura = 0.0
    nome = (nome or p.stem)[:40]
    codigo = (_CODIGO_ORIENTAR + "\nMASCARA = %r\nGIRO = {}\n" % (mascara or "")
              + _CODIGO_IMPORTAR % (repr(str(p)), repr(ext), repr(nome), altura) + _ao_lado() + _enquadrar()
              + "\nresult = {'objetos': len(COL.objects), 'colecao': COL.name, 'giro': GIRO}\n")
    r = b.executar_codigo(codigo)
    if r.get("status") != "ok":
        return b._texto(r)
    res = r.get("result", {})
    extra = ""
    giro = res.get("giro") or {}
    if giro.get("girou"):
        extra = " Girei o modelo para ficar na mesma posicao da foto."
    return "Importei '%s' no Blender: %s objetos na colecao '%s'.%s" % (
        p.name, res.get("objetos"), res.get("colecao"), extra)


# ORIENTACAO PELO CONTORNO DA FOTO                                  (28/09)
#
#   O TRELLIS as vezes devolve o modelo DEITADO ou de lado: ele adivinha
#   onde e "em cima" e erra. Quem sabe a resposta e a propria foto -- ela
#   mostra o objeto de pe, de frente.
#
#   Entao: das 24 posicoes possiveis (girar de 90 em 90 graus nos 3 eixos),
#   o Bigode escolhe aquela cuja SILHUETA vista de frente mais se parece com
#   o contorno da foto (IoU, 64x64). Empate fica com a posicao original.
_CODIGO_ORIENTAR = r'''
def _orientar_pela_foto(V, alvo):
    import numpy as np, itertools
    N = alvo.shape[0]
    def silhueta(P):
        mn = P.min(0); tam = float((P.max(0) - mn).max()) or 1.0
        Q = (P - mn) / tam * (N - 1)
        Q += ((N - 1) - Q.max(0)) / 2.0
        c = np.clip(np.round(Q[:, 0]).astype(int), 0, N - 1)
        l = np.clip(np.round(Q[:, 1]).astype(int), 0, N - 1)
        img = np.zeros((N, N), bool); img[N - 1 - l, c] = True
        for _ in range(2):                       # fecha buracos entre pontos
            d = img.copy()
            d[1:] |= img[:-1]; d[:-1] |= img[1:]; d[:, 1:] |= img[:, :-1]; d[:, :-1] |= img[:, 1:]
            img = d
        for _ in range(1):
            e = img.copy()
            e[1:] &= img[:-1]; e[:-1] &= img[1:]; e[:, 1:] &= img[:, :-1]; e[:, :-1] &= img[:, 1:]
            img = e
        return img
    melhor, nota_melhor = np.eye(3), -1.0
    for perm in itertools.permutations(range(3)):
        for sinais in itertools.product((1, -1), repeat=3):
            R = np.zeros((3, 3))
            for i in range(3):
                R[i, perm[i]] = sinais[i]
            if np.linalg.det(R) < 0.5:
                continue
            P = V @ R.T
            s = silhueta(P[:, [0, 2]])
            nota = (s & alvo).sum() / max((s | alvo).sum(), 1)
            if np.allclose(R, np.eye(3)):
                nota += 0.03                     # na duvida, fica como veio
            elif R[2, 2] == 1:
                nota += 0.015                    # depois, manter o "em cima"
            if nota > nota_melhor:
                melhor, nota_melhor = R, nota
    return melhor, nota_melhor
'''


def mascara_silhueta(caminho, n=64):
    """Contorno do objeto na foto, 64x64, como texto de 0/1 (linha 0 = topo).
    None se a foto nao tiver fundo recortavel."""
    try:
        from PIL import Image
        img = Image.open(str(recortar_fundo(caminho))).convert("RGBA")
        alfa = img.split()[3]
        if alfa.getextrema()[0] > 250:
            return None                          # sem transparencia: nao da para saber o contorno
        caixa = alfa.point(lambda v: 255 if v > 128 else 0).getbbox()
        if not caixa:
            return None
        recorte = alfa.crop(caixa)
        w, h = recorte.size
        k = n / float(max(w, h))
        nw, nh = max(1, min(n, round(w * k))), max(1, min(n, round(h * k)))
        recorte = recorte.resize((nw, nh))
        tela = Image.new("L", (n, n), 0)
        tela.paste(recorte, ((n - nw) // 2, (n - nh) // 2))     # centralizado, igual a silhueta do Blender
        return "".join("1" if v > 128 else "0" for v in tela.getdata())
    except Exception:
        return None


_CODIGO_IMPORTAR = r'''
import bpy
from mathutils import Vector
CAMINHO, EXT, NOME, ALTURA = %s, %s, %s, %r
antes = set(bpy.data.objects)
if EXT in (".glb", ".gltf"):
    bpy.ops.import_scene.gltf(filepath=CAMINHO)
elif EXT == ".obj":
    bpy.ops.wm.obj_import(filepath=CAMINHO)
elif EXT == ".fbx":
    bpy.ops.import_scene.fbx(filepath=CAMINHO)
elif EXT == ".stl":
    bpy.ops.wm.stl_import(filepath=CAMINHO)
elif EXT == ".ply":
    bpy.ops.wm.ply_import(filepath=CAMINHO)
elif EXT == ".svg":
    bpy.ops.import_curve.svg(filepath=CAMINHO)
elif EXT in (".usdz", ".usd", ".usdc", ".usda"):
    # iPhone com LiDAR (RoomPlan, Scaniverse, Polycam): o importador de USD
    # do Blender le a escala (metros) e o eixo "em cima" do proprio arquivo.
    bpy.ops.wm.usd_import(filepath=CAMINHO)
novos = [o for o in bpy.data.objects if o not in antes]
COL = bpy.data.collections.new(NOME)
bpy.context.scene.collection.children.link(COL)
for o in novos:
    for c in list(o.users_collection): c.objects.unlink(o)
    COL.objects.link(o)
if EXT == ".svg":
    # SVG chega minusculo e deitado: vira placa em pe, com espessura
    for o in novos:
        if o.type == 'CURVE':
            o.data.extrude = 0.002
            o.data.dimensions = '2D'
    raiz = bpy.data.objects.new(NOME, None); COL.objects.link(raiz)
    for o in novos:
        if o.parent is None: o.parent = raiz
    raiz.rotation_euler = (1.5708, 0, 0)
    bpy.context.view_layer.update()
    pts = [(o.matrix_world @ Vector(c)) for o in novos for c in o.bound_box]
    if pts:
        larg = max(max(p.x for p in pts) - min(p.x for p in pts), 1e-6)
        k = 1.0 / larg          # 1 metro de largura
        raiz.scale = (k, k, k)
        raiz.empty_display_size = 0.05 / k   # senao o eixo do vazio fica gigante
        for o in novos:
            if o.type == 'CURVE': o.data.extrude = 0.02 / k
# Modelo com cor por vertice e sem textura (gerador local): liga a cor ao material
for o in novos:
    if o.type != 'MESH' or not o.data.color_attributes:
        continue
    tem_imagem = any(n.type == 'TEX_IMAGE' for m in o.data.materials if m and m.use_nodes
                     for n in m.node_tree.nodes)
    if tem_imagem:
        continue
    mat = bpy.data.materials.new(NOME + "_cor"); mat.use_nodes = True
    b = mat.node_tree.nodes.get("Principled BSDF")
    vc = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = o.data.color_attributes[0].name
    mat.node_tree.links.new(vc.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    o.data.materials.clear(); o.data.materials.append(mat)
    for p in o.data.polygons: p.use_smooth = True
bpy.context.view_layer.update()
# Gerado a partir de foto: gira para a posicao que bate com o contorno da foto
if MASCARA:
    try:
        import numpy as np
        from mathutils import Matrix
        N = int(round(len(MASCARA) ** 0.5))
        alvo = (np.frombuffer(MASCARA.encode(), dtype=np.uint8) == 49).reshape(N, N)
        blocos = []
        for o in novos:
            if o.type != 'MESH' or not len(o.data.vertices):
                continue
            co = np.empty(len(o.data.vertices) * 3); o.data.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3)
            if len(co) > 60000:
                co = co[np.random.default_rng(0).choice(len(co), 60000, replace=False)]
            M = np.array(o.matrix_world)
            blocos.append(co @ M[:3, :3].T + M[:3, 3])
        if blocos:
            V = np.concatenate(blocos); V = V - V.mean(0)
            R, nota = _orientar_pela_foto(V, alvo)
            GIRO = {'nota': round(float(nota), 3), 'girou': not np.allclose(R, np.eye(3))}
            if GIRO['girou']:
                R4 = Matrix(((R[0][0], R[0][1], R[0][2], 0), (R[1][0], R[1][1], R[1][2], 0),
                             (R[2][0], R[2][1], R[2][2], 0), (0, 0, 0, 1)))
                for o in [o for o in novos if o.parent is None]:
                    o.matrix_world = R4 @ o.matrix_world
                bpy.context.view_layer.update()
    except Exception as erro_giro:
        GIRO = {'erro': str(erro_giro)[:200]}
# apoia no chao e, se pedido, ajusta a altura
pts = [(o.matrix_world @ Vector(c)) for o in COL.objects if o.type in ('MESH', 'CURVE') for c in o.bound_box]
if pts:
    zmin, zmax = min(p.z for p in pts), max(p.z for p in pts)
    topo = [o for o in COL.objects if o.parent is None]
    if ALTURA and zmax - zmin > 1e-6:
        k = ALTURA / (zmax - zmin)
        for o in topo:
            o.scale = tuple(v * k for v in o.scale)
            o.location = tuple(v * k for v in o.location)
        bpy.context.view_layer.update()
        pts = [(o.matrix_world @ Vector(c)) for o in COL.objects if o.type in ('MESH', 'CURVE') for c in o.bound_box]
        zmin = min(p.z for p in pts)
    for o in topo:
        o.location.z -= zmin
'''


# ==========================================================================
# 3. REFERENCIAS ORTOGRAFICAS
# ==========================================================================

def blender_referencias(frente="", lado="", topo="", altura=2.0, **_):
    """Coloca imagens de frente/lado/topo como fundo para modelar por cima."""
    b = _b()
    vistas = {}
    for chave, cam in (("frente", frente), ("lado", lado), ("topo", topo)):
        cam = str(cam or "").strip().strip('"')
        if cam:
            p = Path(cam)
            if not p.exists() and (ENTRADA / p.name).exists():
                p = ENTRADA / p.name
            if not p.exists():
                return "Imagem de %s nao encontrada: %s" % (chave, cam)
            vistas[chave] = str(p)
    if not vistas:
        return "Mande pelo menos uma imagem (frente, lado ou topo)."
    try:
        altura = float(altura or 2.0)
    except (TypeError, ValueError):
        altura = 2.0
    r = b.executar_codigo(_CODIGO_REFS % (repr(vistas), altura))
    if r.get("status") != "ok":
        return b._texto(r)
    return ("Referencias colocadas no Blender (%s), %.1f m de altura, na colecao 'Referencias'. "
            "Veja pelo numpad: 1 = frente, 3 = lado, 7 = topo." % (", ".join(vistas), altura))


_CODIGO_REFS = r'''
import bpy, math
VISTAS, ALTURA = %s, %r
COL = bpy.data.collections.get("Referencias") or bpy.data.collections.new("Referencias")
if COL.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(COL)
for o in list(COL.objects): bpy.data.objects.remove(o, do_unlink=True)
pose = {"frente": ((0, 3, ALTURA / 2), (math.pi / 2, 0, 0)),
        "lado": ((-3, 0, ALTURA / 2), (math.pi / 2, 0, -math.pi / 2)),
        "topo": ((0, 0, -0.01), (0, 0, 0))}
for chave, caminho in VISTAS.items():
    img = bpy.data.images.load(caminho, check_existing=True)
    o = bpy.data.objects.new("Ref_" + chave, None)
    o.empty_display_type = 'IMAGE'
    o.data = img
    o.empty_display_size = ALTURA
    o.empty_image_depth = 'BACK'
    o.use_empty_image_alpha = True
    o.color[3] = 0.5
    o.location, o.rotation_euler = pose[chave]
    o.hide_select = True
    COL.objects.link(o)
result = {"refs": len(COL.objects)}
'''


# ==========================================================================
# 4. TEXTURA / ROTULO
# ==========================================================================

def aplicar_mapas(mapas, objeto="", nome_material=""):
    b = _b()
    if not mapas.get("cor"):
        return "Nao achei a imagem de cor da textura."
    r = b.executar_codigo(_CODIGO_TEXTURA % (repr(mapas), repr(objeto or ""), repr(nome_material or "Textura")))
    if r.get("status") != "ok":
        return b._texto(r)
    res = r.get("result", {})
    if res.get("erro"):
        return res["erro"]
    return "Textura '%s' aplicada em: %s." % (nome_material, ", ".join(res.get("objetos", [])))


def blender_textura(caminho="", objeto="", **_):
    """Aplica uma imagem (PNG/JPG) como cor/rotulo num objeto (ou nos selecionados)."""
    p = Path(str(caminho).strip().strip('"'))
    if not p.exists() and (ENTRADA / p.name).exists():
        p = ENTRADA / p.name
    if not p.exists():
        return "Imagem nao encontrada: %s" % caminho
    return aplicar_mapas({"cor": str(p)}, objeto, p.stem)


_CODIGO_TEXTURA = r'''
import bpy
MAPAS, ALVO, NOME = %s, %s, %s
# Sem nome de objeto NAO usa a selecao: um rotulo sem destino caiu na
# pele de uma pessoa selecionada (28/09). Selecao so quando pedida.
if ALVO.lower() in ("selecionado", "selecionados", "selecao"):
    alvos = [o for o in bpy.context.selected_objects if o.type == 'MESH']
elif ALVO:
    alvos = [o for o in bpy.data.objects if o.type == 'MESH' and (o.name == ALVO or o.name.lower().startswith(ALVO.lower()))]
else:
    alvos = []
if not alvos:
    # Sem objeto: a imagem vira uma PLACA em pe, na proporcao certa, ao lado
    # da cena. (28/09: "como rotulo no objeto" sem nome dava erro.)
    img = bpy.data.images.load(MAPAS["cor"], check_existing=True)
    larg, alt = (img.size[0] or 1), (img.size[1] or 1)
    bpy.ops.mesh.primitive_plane_add(size=1)
    placa = bpy.context.active_object
    placa.name = "Imagem_" + NOME
    placa.scale = (larg / max(larg, alt), alt / max(larg, alt), 1)
    placa.rotation_euler = (1.5708, 0, 0)
    from mathutils import Vector
    xs = [(o.matrix_world @ Vector(c)).x for o in bpy.context.scene.objects
          if o.type in ('MESH', 'CURVE', 'FONT') and o != placa and o.name != "Chao" for c in o.bound_box]
    placa.location = ((max(xs) + 1.5) if xs else 0, 0, placa.scale[1] / 2)
    alvos = [placa]
if alvos:
    m = bpy.data.materials.new("Mat_" + NOME)
    m.use_nodes = True
    nos, links = m.node_tree.nodes, m.node_tree.links
    bsdf = nos.get("Principled BSDF")
    cor = nos.new("ShaderNodeTexImage"); cor.image = bpy.data.images.load(MAPAS["cor"], check_existing=True)
    links.new(cor.outputs["Color"], bsdf.inputs["Base Color"])
    if MAPAS.get("aspereza"):
        rg = nos.new("ShaderNodeTexImage"); rg.image = bpy.data.images.load(MAPAS["aspereza"], check_existing=True)
        rg.image.colorspace_settings.name = 'Non-Color'
        links.new(rg.outputs["Color"], bsdf.inputs["Roughness"])
    if MAPAS.get("normal"):
        nm = nos.new("ShaderNodeTexImage"); nm.image = bpy.data.images.load(MAPAS["normal"], check_existing=True)
        nm.image.colorspace_settings.name = 'Non-Color'
        mapa = nos.new("ShaderNodeNormalMap")
        links.new(nm.outputs["Color"], mapa.inputs["Color"])
        links.new(mapa.outputs["Normal"], bsdf.inputs["Normal"])
    for o in alvos:
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
        o.data.materials.clear()
        o.data.materials.append(m)
    result = {"objetos": [o.name for o in alvos]}
'''


# ==========================================================================
# 5. IMAGEM -> MALHA 3D (TRELLIS.2 no Hugging Face)
# ==========================================================================

ESPACO_TRELLIS = "microsoft/TRELLIS.2"


def garantir_pacote(modulo, nome_pip=None):
    """Importa o pacote; se faltar, INSTALA sozinho no mesmo Python que roda
    o Bigode (sys.executable). Assim o Fred nao precisa abrir terminal.
    Devolve (ok, mensagem)."""
    import importlib
    import subprocess
    import sys
    try:
        importlib.import_module(modulo)
        return True, ""
    except ImportError:
        pass
    nome_pip = nome_pip or modulo
    for extra in ([], ["--user"]):
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                                "--disable-pip-version-check", nome_pip] + extra,
                               capture_output=True, text=True, timeout=600)
            if r.returncode == 0:
                importlib.invalidate_caches()
                try:
                    importlib.import_module(modulo)
                    return True, ""
                except ImportError:
                    continue
        except Exception:
            continue
    return False, ("Nao consegui instalar sozinho o complemento '%s'. Feche o Bigode e rode, "
                   "na pasta Cerebro:\n    \"%s\" -m pip install %s"
                   % (nome_pip, sys.executable, nome_pip))


def recortar_fundo(caminho, tolerancia=10):
    """Fundo liso (branco, cinza...) vira transparente. O TRELLIS usa a
    transparencia como contorno do objeto; sem ela, as vezes ele modela a
    FOTO INTEIRA como uma placa (foi o que deu no gato de 28/09).
    Devolve o caminho do PNG recortado, ou o original se nao der."""
    garantir_pacote("PIL", "Pillow")
    try:
        from PIL import Image, ImageChops, ImageDraw
        img = Image.open(caminho).convert("RGBA")
        if img.getextrema()[3][0] < 250:          # ja tem transparencia
            return Path(caminho)
        rgb = img.convert("RGB")
        w, h = rgb.size
        cantos = [rgb.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
        fundo = tuple(sum(c[i] for c in cantos) // 4 for i in range(3))
        if max(max(abs(c[i] - fundo[i]) for i in range(3)) for c in cantos) > tolerancia:
            return Path(caminho)                   # fundo nao e liso: deixa o TRELLIS recortar
        dif = ImageChops.difference(rgb, Image.new("RGB", rgb.size, fundo)).convert("L")
        perto = dif.point(lambda v: 255 if v <= tolerancia else 0)
        for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            if perto.getpixel(p) == 255:
                ImageDraw.floodfill(perto, p, 128)
        alfa = perto.point(lambda v: 0 if v == 128 else 255)
        if alfa.getbbox() is None:
            return Path(caminho)
        img.putalpha(alfa)
        destino = Path(caminho).with_name(Path(caminho).stem + "_recorte.png")
        img.save(destino)
        return destino
    except Exception:
        return Path(caminho)


ULTIMO_MOTOR = {"nome": "", "tentativas": []}


def _gerar_trellis_modal(caminhos, seed=1, textura=1024):
    """TRELLIS na conta Modal do Fred (modal_trellis.py). Aceita 1 a 4 fotos
    do MESMO objeto: com frente/lado/costas a forma sai muito mais fiel.
    Devolve (caminho_glb, erro). Sem endereco no config: (None, motivo)."""
    cfg = _config()
    tm = cfg.get("trellis_modal") or {}
    url = str(tm.get("url") or "").strip()
    token = str(tm.get("token") or (cfg.get("olho_modal") or {}).get("token") or "").strip()
    if not url or tm.get("ligada") is False:
        return None, "TRELLIS no Modal ainda nao publicado (python -m modal deploy modal_trellis.py)"
    import base64
    imagens = []
    for c in caminhos[:4]:
        caminho = recortar_fundo(c)
        imagens.append(base64.b64encode(Path(caminho).read_bytes()).decode("ascii"))
    # simplificar = fracao de triangulos REMOVIDOS. 0.95 (padrao) deixa 5%;
    # na qualidade maxima deixamos o dobro (10%) -- mais detalhe na forma.
    corpo = {"token": token, "imagens": imagens, "seed": int(seed or 1), "textura": int(textura),
             "simplificar": 0.90 if int(textura) >= 2048 else 0.95}
    try:
        req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            dados = json.loads(r.read().decode("utf-8"))
    except Exception as erro:
        motivo = str(erro)[:200]
        if "404" in motivo:
            motivo += (" -- o endereco do TRELLIS nao existe no Modal. Republique: "
                       "python -m modal deploy modal_trellis.py")
        return None, "TRELLIS no Modal nao respondeu: %s" % motivo
    if not dados.get("ok"):
        return None, "TRELLIS no Modal: %s" % str(dados.get("erro"))[:300]
    GERADOS.mkdir(parents=True, exist_ok=True)
    destino = GERADOS / ("modal_%s.glb" % time.strftime("%Y%m%d_%H%M%S"))
    destino.write_bytes(base64.b64decode(dados["glb"]))
    ULTIMO_MOTOR["mascara"] = str(dados.get("mascara") or "")   # contorno feito com o rembg do Modal
    return destino, None


def gerar_malha(caminho_imagem, resolucao="1024", extras=(), seed=1, qualidade="normal"):
    """Imagem (ou varias fotos do mesmo objeto) -> .glb, tentando EM ORDEM:
      1) TRELLIS no Modal (sua conta)  -- melhor; aceita varias fotos
      2) TRELLIS.2 no Hugging Face     -- otimo; cota gratis por dia
      3) TripoSR no proprio PC          -- sem cota; qualidade menor
    Devolve (caminho_glb, erro). ULTIMO_MOTOR diz quem fez."""
    ULTIMO_MOTOR.update(nome="", tentativas=[], mascara="")
    fotos = [caminho_imagem] + [e for e in (extras or []) if e]
    glb, erro0 = _gerar_trellis_modal(fotos, seed=seed,
                                      textura=2048 if qualidade == "maxima" else 1024)
    if glb:
        ULTIMO_MOTOR["nome"] = "TRELLIS no Modal (%d foto%s)" % (len(fotos[:4]), "s" if len(fotos) > 1 else "")
        return glb, None
    ULTIMO_MOTOR["tentativas"].append(erro0[:160])
    glb, erro = _gerar_trellis(caminho_imagem, resolucao)
    if glb:
        ULTIMO_MOTOR["nome"] = "TRELLIS.2 (Hugging Face)"
        return glb, None
    ULTIMO_MOTOR["tentativas"].append("TRELLIS.2: " + erro[:160])
    try:
        import gerador_local_3d as local
    except Exception as e:
        return None, erro + " | gerador local indisponivel: %s" % e
    if not local.pronto():
        aviso = local.instalar_em_segundo_plano()
        ULTIMO_MOTOR["tentativas"].append("Gerador local: " + local.estado())
        return None, erro + "\n" + aviso
    GERADOS.mkdir(parents=True, exist_ok=True)
    destino = GERADOS / ("local_%s.glb" % time.strftime("%Y%m%d_%H%M%S"))
    glb2, erro2 = local.gerar(recortar_fundo(caminho_imagem), destino, qualidade=qualidade)
    if glb2:
        ULTIMO_MOTOR["nome"] = "TripoSR no seu PC (plano B, so usa 1 foto)"
        return glb2, None
    ULTIMO_MOTOR["tentativas"].append("Gerador local: " + erro2)
    return None, erro + " | " + erro2


COTA_HF = PASTA / ".cota_hf_acabou"      # quando a cota de GPU do dia acabou


def _cota_acabou_ha_pouco(horas=3):
    """O erros.log mostrou o TRELLIS gastando 3 a 5 MINUTOS na fila so para
    responder "sua cota acabou" (18:43 e 18:53 de 28/09). Depois do primeiro
    aviso, o Bigode pula direto para o gerador do PC por algumas horas."""
    try:
        return COTA_HF.exists() and time.time() - COTA_HF.stat().st_mtime < horas * 3600
    except Exception:
        return False


def _gerar_trellis(caminho_imagem, resolucao="1024"):
    """Imagem -> .glb com o TRELLIS.2. Devolve (caminho_glb, erro)."""
    if _cota_acabou_ha_pouco():
        return None, ("a cota gratis de GPU do Hugging Face acabou ha pouco "
                      "(pulei o TRELLIS para nao esperar na fila a toa)")
    ok, msg = garantir_pacote("gradio_client")
    if not ok:
        return None, msg
    from gradio_client import Client, handle_file
    token = _token_hf()
    if not token:
        return None, ("Falta o token do Hugging Face no config.json (huggingface.token). "
                      "Crie gratis em https://huggingface.co/settings/tokens")
    try:
        try:                        # gradio_client novo usa `token`,
            cliente = Client(ESPACO_TRELLIS, token=token, verbose=False)
        except TypeError:           # o antigo usava `hf_token`
            cliente = Client(ESPACO_TRELLIS, hf_token=token, verbose=False)
        try:
            cliente.predict(api_name="/start_session")
        except Exception:
            pass
        img = cliente.predict(handle_file(str(recortar_fundo(caminho_imagem))),
                              api_name="/preprocess_image")
        img = img if isinstance(img, str) else (img or {}).get("path")
        cliente.predict(handle_file(img), 0, str(resolucao), api_name="/image_to_3d")
        saida = cliente.predict(200000, 1024, api_name="/extract_glb")
    except Exception as erro:
        msg = str(erro)
        if "quota" in msg.lower():
            try:
                PASTA.mkdir(parents=True, exist_ok=True)
                COTA_HF.write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
            except Exception:
                pass
            return None, ("A cota gratuita de GPU do Hugging Face acabou por hoje. "
                          "Ela renova sozinha; tente mais tarde. (%s)" % msg[:160])
        return None, "O TRELLIS.2 falhou: %s" % msg[:300]
    glb = saida[0] if isinstance(saida, (list, tuple)) else saida
    glb = glb if isinstance(glb, str) else (glb or {}).get("path") or (glb or {}).get("value")
    if not glb or not Path(glb).exists():
        return None, "O TRELLIS.2 nao devolveu o arquivo .glb."
    GERADOS.mkdir(parents=True, exist_ok=True)
    destino = GERADOS / ("trellis_%s.glb" % time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy(glb, destino)
    return destino, None


def blender_gerar_3d(caminho="", altura=0, extras=(), variacao=False, qualidade="normal", **_):
    """Transforma uma imagem (ou 2 a 4 fotos do mesmo objeto) num modelo 3D
    de verdade (malha com textura) e importa. `variacao`: outra tentativa
    diferente da anterior (semente nova)."""
    import random
    b = _b()
    p = Path(str(caminho or "").strip().strip('"')) if caminho else b.ULTIMA_IMAGEM
    if not p.exists():
        return "Nao ha imagem. Cole a imagem (Ctrl+V) no Bigode primeiro."
    extras = [str(e) for e in (extras or []) if e and Path(str(e)).exists()]
    inicio = time.time()
    seed = random.randint(2, 999999) if variacao else 1
    glb, erro = gerar_malha(p, extras=extras, seed=seed, qualidade=qualidade)
    if erro:
        return erro
    texto = blender_importar(str(glb), nome="Gerado_3D", altura=altura or 1.0,
                             mascara=ULTIMO_MOTOR.get("mascara") or mascara_silhueta(p))
    if texto.startswith("Importei"):
        try:
            texto += b._conferir_volume("Gerado_3D")
        except Exception:
            pass
    dica = ""
    if ULTIMO_MOTOR.get("tentativas") and "TRELLIS" not in (ULTIMO_MOTOR.get("nome") or ""):
        # Caiu no plano B: dizer POR QUE, senao ninguem descobre que o Modal
        # esta fora do ar (28/09: endpoint 404 e o Fred so via "plano B").
        dica += "\nPor que nao usou o TRELLIS: " + " | ".join(ULTIMO_MOTOR["tentativas"])[:400]
    if not extras:
        dica = ("\nDica: para ficar mais fiel, mande 2 a 4 fotos do MESMO objeto "
                "(frente, lado, costas) juntas.")
    return "%s\nModelo gerado por %s em %.0fs. Arquivo: %s%s\nNao gostou? Peca 'outra variacao'." % (
        texto, ULTIMO_MOTOR["nome"] or "gerador 3D", time.time() - inicio, glb, dica)


# ==========================================================================
# 6. PLANEJADOR MAIOR (Qwen2.5-Coder-32B no Hugging Face)
# ==========================================================================

def planejar_hf(prompt, modelo=""):
    """Pede a lista de pecas a um modelo maior no Hugging Face. None se falhar."""
    token = _token_hf()
    if not token:
        return None
    modelo = modelo or (_config().get("huggingface") or {}).get("texto_modelo") \
        or "Qwen/Qwen2.5-Coder-32B-Instruct"
    corpo = {"model": modelo, "messages": [{"role": "user", "content": prompt}],
             "max_tokens": 2500, "temperature": 0.2}
    try:
        req = urllib.request.Request(
            "https://router.huggingface.co/v1/chat/completions",
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=120) as r:
            dados = json.loads(r.read().decode("utf-8"))
        return dados["choices"][0]["message"]["content"]
    except Exception:
        return None


# ==========================================================================
# ESCANEAMENTO DE AMBIENTE / OBJETO (iPhone com LiDAR)          (29/09)
# ==========================================================================
#
#   O Bigode nao escaneia: quem escaneia e um app no iPhone Pro/iPad Pro
#   (RoomPlan da Apple via apps como o 3d Scanner App, Scaniverse, Polycam).
#   O Bigode RECEBE o arquivo, poe no Blender NA ESCALA REAL (sem esticar)
#   e mede: tamanho total, paredes, portas, janelas e moveis.
#
#   Formatos: .usdz (RoomPlan), .glb/.gltf, .obj, .ply, .fbx, .stl, e .zip
#   (o Polycam gratis exporta GLTF em .zip).
EXT_ESCANEAMENTO = (".usdz", ".usd", ".usdc", ".usda", ".glb", ".gltf", ".obj",
                    ".ply", ".fbx", ".stl", ".zip")
ESCANEAMENTOS = PASTA / "escaneamentos"

_CATEGORIAS = {
    "parede": ("wall", "parede"), "porta": ("door", "porta"),
    "janela": ("window", "janela"), "abertura": ("opening", "abertura"),
    "piso": ("floor", "piso", "chao"),
    "movel": ("sofa", "table", "chair", "bed", "storage", "cabinet", "refrigerator",
              "stove", "oven", "sink", "toilet", "bathtub", "washer", "dryer",
              "dishwasher", "fireplace", "television", "stairs", "mesa", "cadeira",
              "cama", "armario", "geladeira", "fogao", "pia", "vaso", "banheira"),
}

_CODIGO_MEDIR = r"""
import re as _re
def _cat(nome):
    n = nome.lower()
    for cat, chaves in CATEGORIAS.items():
        if any(k in n for k in chaves):
            return cat
    return ""
def _caixa(objs):
    pts = [(o.matrix_world @ Vector(c)) for o in objs for c in o.bound_box]
    if not pts:
        return None
    xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
malhas = [o for o in COL.objects if o.type == 'MESH']
geral = _caixa(malhas) or (0, 0, 0)
itens, contagem = [], {}
for o in malhas:
    cat = _cat(o.name) or _cat(o.parent.name if o.parent else "")
    d = _caixa([o])
    if cat:
        contagem[cat] = contagem.get(cat, 0) + 1
    itens.append({"nome": o.name, "tipo": cat, "l": round(d[0], 3), "p": round(d[1], 3),
                  "a": round(d[2], 3)})
paredes = [i for i in itens if i["tipo"] == "parede"]
perimetro = sum(max(i["l"], i["p"]) for i in paredes)
pe_direito = max((i["a"] for i in paredes), default=0)
MEDIDAS = {"largura": round(geral[0], 3), "profundidade": round(geral[1], 3),
           "altura": round(geral[2], 3), "area_aprox": round(geral[0] * geral[1], 2),
           "perimetro_paredes": round(perimetro, 2), "pe_direito": round(pe_direito, 2),
           "contagem": contagem, "malhas": len(malhas),
           "itens": sorted(itens, key=lambda i: -(i["l"] * i["p"] * max(i["a"], 0.01)))[:40]}
"""

_CODIGO_ENQUADRAR_SEGURO = r"""
tela = getattr(bpy.context, "screen", None)
if tela:
    bpy.ops.object.select_all(action='DESELECT')
    for o in COL.objects: o.select_set(True)
    for area in tela.areas:
        if area.type == 'VIEW_3D':
            regiao = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if regiao:
                try:
                    with bpy.context.temp_override(area=area, region=regiao):
                        bpy.ops.view3d.view_selected()
                except Exception:
                    pass
"""


def _abrir_zip(p):
    """Extrai o .zip e devolve o melhor arquivo 3D de dentro (usdz > glb > gltf > obj...)."""
    import zipfile
    destino = ENTRADA / (p.stem + "_zip")
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p) as z:
        for info in z.infolist():
            alvo = (destino / info.filename).resolve()
            if destino.resolve() not in alvo.parents and alvo != destino.resolve():
                continue                                  # caminho malicioso no zip
            if info.is_dir():
                alvo.mkdir(parents=True, exist_ok=True)
                continue
            alvo.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as origem, open(alvo, "wb") as saida:
                shutil.copyfileobj(origem, saida)
    for ext in (".usdz", ".usd", ".usdc", ".glb", ".gltf", ".obj", ".ply", ".fbx", ".stl"):
        achados = sorted(destino.rglob("*" + ext), key=lambda a: -a.stat().st_size)
        if achados:
            return achados[0]
    return None


def _m(v):
    return ("%.2f" % float(v)).replace(".", ",") + " m"


def blender_escaneamento(caminho="", nome="", **_):
    """Importa um escaneamento (LiDAR/fotogrametria) em escala real e mede."""
    b = _b()
    p = Path(str(caminho).strip().strip('"'))
    if not p.exists():
        cand = ENTRADA / p.name
        p = cand if cand.exists() else p
    if not p.exists():
        return "Arquivo nao encontrado: %s" % caminho
    if p.suffix.lower() not in EXT_ESCANEAMENTO:
        return "Formato %s nao suportado. Use: %s" % (p.suffix, " ".join(EXT_ESCANEAMENTO))
    if p.suffix.lower() == ".zip":
        dentro = _abrir_zip(p)
        if not dentro:
            return "O .zip nao tem nenhum arquivo 3D (usdz, glb, gltf, obj, ply, fbx, stl)."
        p = dentro
    ext = p.suffix.lower()
    nome = re.sub(r"[^\w\- ]", "", (nome or p.stem))[:40] or "Escaneamento"
    codigo = ("from mathutils import Vector\nMASCARA = ''\nGIRO = {}\n"
              + _CODIGO_IMPORTAR % (repr(str(p)), repr(ext), repr(nome), 0.0)
              + "CATEGORIAS = %r\n" % (_CATEGORIAS,)
              + _CODIGO_MEDIR + _CODIGO_ENQUADRAR_SEGURO
              + "\nresult = {'colecao': COL.name, 'medidas': MEDIDAS}\n")
    r = b.executar_codigo(codigo, timeout=300)
    if r.get("status") != "ok":
        return b._texto(r)
    res = r.get("result") or {}
    m = res.get("medidas") or {}
    if not m.get("malhas"):
        return ("Importei '%s', mas nao veio nenhuma malha 3D. Confira se o app exportou o modelo "
                "(e nao so a foto ou a planta)." % p.name)

    # guarda as medidas ao lado, para abrir no Excel/AutoCAD depois
    try:
        ESCANEAMENTOS.mkdir(parents=True, exist_ok=True)
        base = ESCANEAMENTOS / (nome + "_medidas")
        base.with_suffix(".json").write_text(json.dumps(m, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
        linhas = ["nome;tipo;largura_m;profundidade_m;altura_m"]
        linhas += ["%s;%s;%s;%s;%s" % (i["nome"], i["tipo"], str(i["l"]).replace(".", ","),
                                       str(i["p"]).replace(".", ","), str(i["a"]).replace(".", ","))
                   for i in m.get("itens", [])]
        base.with_suffix(".csv").write_text("\n".join(linhas), encoding="utf-8-sig")
        arquivo_medidas = str(base.with_suffix(".csv"))
    except Exception:
        arquivo_medidas = ""

    c = m.get("contagem") or {}
    partes = ["Importei o escaneamento '%s' no Blender em ESCALA REAL (colecao '%s')."
              % (p.name, res.get("colecao")),
              "Tamanho total: %s x %s, altura %s." % (_m(m["largura"]), _m(m["profundidade"]),
                                                      _m(m["altura"]))]
    if c.get("parede"):
        partes.append("Paredes: %d (perimetro ~%s, pe-direito %s). Area do piso ~%s m2 "
                      "(pelo retangulo externo; em comodo em L e menor)."
                      % (c["parede"], _m(m["perimetro_paredes"]), _m(m["pe_direito"]),
                         str(m["area_aprox"]).replace(".", ",")))
    plural = {"porta": "portas", "janela": "janelas", "abertura": "aberturas", "movel": "moveis"}
    extras = ["%d %s" % (c[k], plural[k] if c[k] > 1 else k)
              for k in ("porta", "janela", "abertura", "movel") if c.get(k)]
    if extras:
        partes.append("Encontrei: " + ", ".join(extras) + ".")
    moveis = [i for i in m.get("itens", []) if i["tipo"] == "movel"][:6]
    for i in moveis:
        partes.append("  - %s: %s x %s x %s" % (i["nome"], _m(i["l"]), _m(i["p"]), _m(i["a"])))
    if arquivo_medidas:
        partes.append("Medidas salvas em: %s" % arquivo_medidas)
    partes.append("Para AutoCAD/Unreal: no Blender, File > Export > FBX ou OBJ.")
    return "\n".join(partes)


# ==========================================================================
# ARQUIVO VINDO DA TELA
# ==========================================================================

def receber_arquivo(nome, dados_b64):
    """Salva um arquivo anexado na tela em producao_blender/entrada."""
    nome = re.sub(r"[^\w.\- ]", "_", Path(str(nome or "arquivo")).name)[:80] or "arquivo"
    b64 = str(dados_b64 or "")
    if b64.startswith("data:"):
        b64 = b64.partition(",")[2]
    try:
        bruto = base64.b64decode(b64)
    except Exception:
        return {"ok": False, "erro": "Arquivo nao veio em base64."}
    if len(bruto) > 80_000_000:
        return {"ok": False, "erro": "Arquivo grande demais (limite 80 MB)."}
    ENTRADA.mkdir(parents=True, exist_ok=True)
    destino = ENTRADA / nome
    destino.write_bytes(bruto)
    return {"ok": True, "caminho": str(destino), "nome": nome}
