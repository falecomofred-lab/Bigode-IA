#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BLENDER - o Bigode modelando em 3D

Fala direto com o add-on oficial "MCP" do Blender (Blender Lab), o mesmo
que o Claude usa. O add-on abre um servidor TCP dentro do Blender
(padrao 127.0.0.1:9876) e executa codigo Python com acesso total ao `bpy`.

PROTOCOLO (lido do proprio add-on, mcp_to_blender_server.py)

    pedido  : JSON {"type": "execute", "code": "...", "strict_json": false}
              seguido de um byte nulo (\\0)
    resposta: JSON {"status": "ok"|"error", "result": {...},
                    "message": "...", "stdout": "...", "stderr": "..."}
              seguido de um byte nulo (\\0)

    Uma conexao por pedido: o Blender responde e fecha.
    O codigo devolve dados preenchendo a variavel `result` (tem que ser dict).

Nada aqui depende de pacote externo: so a biblioteca padrao do Python.

Venure - venure.com.br
"""

import json
import re
import shutil
import socket
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent

HOST_PADRAO = "127.0.0.1"   # 127.0.0.1 e nao "localhost": no Windows o
                            # localhost pode cair no IPv6 (::1) e o add-on
                            # escuta so no IPv4.
PORTA_PADRAO = 9876
TIMEOUT_EXECUCAO = 180      # render pode demorar
LIMITE_RESPOSTA = 3500      # mesmo teto do ferramentas.py


def _config():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _endereco():
    cfg = _config()
    host = str(cfg.get("blender_host") or HOST_PADRAO)
    try:
        porta = int(cfg.get("blender_porta") or PORTA_PADRAO)
    except (TypeError, ValueError):
        porta = PORTA_PADRAO
    return host, porta


# ==========================================================================
# Conexao
# ==========================================================================

def no_ar(timeout=0.3):
    """O Blender esta aberto com o servidor MCP ligado?
    Conexao recusada volta na hora, entao isto custa milissegundos."""
    host, porta = _endereco()
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            return True
    except OSError:
        return False


def executar_codigo(codigo, timeout=TIMEOUT_EXECUCAO):
    """Manda codigo Python para o Blender e devolve o dict de resposta."""
    host, porta = _endereco()
    pedido = json.dumps({"type": "execute", "code": codigo,
                         "strict_json": False}) + "\0"
    try:
        with socket.create_connection((host, porta), timeout=5) as conn:
            conn.settimeout(timeout)
            conn.sendall(pedido.encode("utf-8"))
            buffer = bytearray()
            while b"\0" not in buffer:
                pedaco = conn.recv(65536)
                if not pedaco:
                    break
                buffer.extend(pedaco)
    except ConnectionRefusedError:
        return {"status": "error", "message": _MSG_DESLIGADO % (host, porta)}
    except socket.timeout:
        return {"status": "error",
                "message": "O Blender nao respondeu em %d segundos." % timeout}
    except OSError as erro:
        return {"status": "error",
                "message": "Falha ao falar com o Blender (%s)." % erro}

    bruto = bytes(buffer).split(b"\0")[0]
    if not bruto:
        return {"status": "error", "message": "O Blender fechou a conexao sem responder."}
    try:
        return json.loads(bruto.decode("utf-8"))
    except ValueError:
        return {"status": "error", "message": "Resposta invalida do Blender."}


_MSG_DESLIGADO = (
    "Nao consegui falar com o Blender em %s:%d.\n"
    "1. Abra o Blender.\n"
    "2. Edit > Preferences > Add-ons: ative o add-on 'MCP' (Auto Start ligado).\n"
    "3. Confira no cmd: netstat -ano | findstr 9876  (tem que aparecer LISTENING).")


def _texto(resposta):
    """Converte a resposta do Blender em texto curto para o modelo ler."""
    if resposta.get("status") != "ok":
        msg = str(resposta.get("message") or "erro desconhecido")
        # traceback longo: fica so o final, que e onde esta o erro de verdade
        if len(msg) > 1500:
            msg = "..." + msg[-1500:]
        saida = "ERRO no Blender:\n" + msg
    else:
        saida = json.dumps(resposta.get("result", {}), ensure_ascii=False, indent=1)
    extra = (resposta.get("stdout") or "").strip()
    if extra:
        saida += "\n\nSaida (print):\n" + extra[-800:]
    if len(saida) > LIMITE_RESPOSTA:
        saida = saida[:LIMITE_RESPOSTA] + "\n...[cortado]"
    return saida


# ==========================================================================
# Ferramentas (chamadas pelo ferramentas.py)
# ==========================================================================

_CODIGO_CENA = r'''
import bpy
cena = bpy.context.scene
def resumo(col):
    return {"nome": col.name,
            "objetos": [{"nome": o.name, "tipo": o.type,
                         "local": [round(v, 2) for v in o.location]}
                        for o in col.objects],
            "filhas": [resumo(c) for c in col.children]}
ativo = bpy.context.view_layer.objects.active
result = {"arquivo": bpy.data.filepath or "(nao salvo)",
          "cena": cena.name,
          "objeto_ativo": ativo.name if ativo else None,
          "total_objetos": len(cena.objects),
          "colecoes": resumo(cena.collection)}
'''


def blender_cena(**_):
    """Le a cena aberta: colecoes, objetos, tipo e posicao."""
    return _texto(executar_codigo(_CODIGO_CENA, timeout=30))


def blender_executar(codigo="", **_):
    """Executa codigo Python (bpy) dentro do Blender."""
    codigo = (codigo or "").strip()
    if not codigo:
        return "Faltou o codigo Python para executar no Blender."
    # modelos pequenos esquecem o `result`; o add-on exige que seja dict
    if "result" not in codigo:
        codigo += "\nresult = {'ok': True}"
    return _texto(executar_codigo(codigo))


def blender_imagem(nome="", vista="camera", **_):
    """Salva um PNG da vista da camera (render rapido do viewport)."""
    pasta = BASE / "producao_blender"
    pasta.mkdir(exist_ok=True)
    nome = "".join(c for c in (nome or "") if c.isalnum() or c in "-_") \
        or time.strftime("blender_%Y%m%d_%H%M%S")
    destino = str(pasta / (nome + ".png"))
    codigo = r'''
import bpy
cena = bpy.context.scene
cena.render.image_settings.file_format = "PNG"
cena.render.filepath = %r
area = next((a for a in bpy.context.screen.areas if a.type == "VIEW_3D"), None)
if area:
    regiao = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(area=area, region=regiao):
        bpy.ops.render.opengl(write_still=True, view_context=%s)
else:
    bpy.ops.render.render(write_still=True)
result = {"arquivo": %r}
''' % (destino, str(vista).strip().lower() == "tela", destino)
    resposta = executar_codigo(codigo)
    if resposta.get("status") == "ok":
        return "Imagem salva em: %s" % destino
    return _texto(resposta)


CORES = {
    "vermelho": (0.85, 0.05, 0.03), "azul": (0.02, 0.15, 0.85),
    "verde": (0.05, 0.6, 0.1), "amarelo": (0.95, 0.75, 0.02),
    "laranja": (1.0, 0.35, 0.0), "preto": (0.02, 0.02, 0.02),
    "branco": (0.9, 0.9, 0.9), "prata": (0.6, 0.6, 0.62),
    "roxo": (0.35, 0.05, 0.7), "rosa": (0.95, 0.3, 0.55),
    "marrom": (0.30, 0.15, 0.06), "cinza": (0.3, 0.3, 0.3), "bege": (0.85, 0.72, 0.55),
    "pele": (0.85, 0.62, 0.45), "dourado": (0.9, 0.65, 0.15), "ciano": (0.0, 0.7, 0.8),
}


def blender_carrinho(cor="vermelho", **_):
    """Monta o carrinho estilo miniatura hot rod (o mesmo feito pelo Claude)."""
    rgb = CORES.get((cor or "").strip().lower(), CORES["vermelho"])
    codigo = _CODIGO_CARRINHO.replace("__COR__", repr(rgb))
    resposta = executar_codigo(codigo)
    if resposta.get("status") == "ok":
        n = resposta.get("result", {}).get("objetos", "?")
        return ("Carrinho montado no Blender: %s pecas na colecao 'Carrinho', "
                "cor %s. Camera enquadrada e viewport em Material Preview. "
                "O arquivo ainda NAO foi salvo (Ctrl+S no Blender)." % (n, cor or "vermelho"))
    return _texto(resposta)


# Script completo do carrinho. Carroceria hatch, rodas traseiras maiores,
# motor exposto, escapamentos laterais, aerofolio, farois que brilham.
# Recria tudo do zero a cada chamada (limpa a colecao 'Carrinho' antes).
_CODIGO_CARRINHO = r'''
import bpy, math, mathutils

COR = __COR__

cubo = bpy.data.objects.get("Cube")
if cubo:
    bpy.data.objects.remove(cubo, do_unlink=True)

col = bpy.data.collections.get("Carrinho") or bpy.data.collections.new("Carrinho")
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
for o in list(col.objects):
    bpy.data.objects.remove(o, do_unlink=True)

def mat(nome, cor, metal=0.0, rough=0.4, coat=0.0, emit=0.0):
    m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    def s(k, v):
        if b and k in b.inputs:
            try: b.inputs[k].default_value = v
            except Exception: pass
    s("Base Color", (*cor, 1)); s("Metallic", metal); s("Roughness", rough)
    s("Coat Weight", coat)
    if emit:
        s("Emission Color", (*cor, 1)); s("Emission Strength", emit)
    m.diffuse_color = (*cor, 1)
    return m

M_body   = mat("Pintura", COR, metal=0.7, rough=0.25, coat=1.0)
M_glass  = mat("Vidro", (0.02, 0.03, 0.05), rough=0.05, coat=1.0)
M_tire   = mat("Pneu", (0.02, 0.02, 0.02), rough=0.8)
M_chrome = mat("Cromo", (0.9, 0.9, 0.9), metal=1.0, rough=0.08)
M_head   = mat("Farol", (1.0, 0.95, 0.8), emit=3.0)
M_tail   = mat("Lanterna", (1.0, 0.0, 0.0), emit=3.0)
M_black  = mat("Plastico", (0.03, 0.03, 0.03), rough=0.5)

def para_colecao(o):
    for c in o.users_collection: c.objects.unlink(o)
    col.objects.link(o)

def malha(nome, verts, faces, material, bevel=0.06, subsurf=1):
    me = bpy.data.meshes.new(nome)
    me.from_pydata(verts, [], faces); me.update()
    o = bpy.data.objects.new(nome, me); col.objects.link(o)
    o.data.materials.append(material)
    if bevel:
        bm = o.modifiers.new("Bevel", "BEVEL"); bm.width = bevel; bm.segments = 3
    if subsurf:
        ss = o.modifiers.new("Sub", "SUBSURF"); ss.levels = subsurf; ss.render_levels = subsurf
    for p in o.data.polygons: p.use_smooth = True
    return o

def caixa(x0, x1, y, z0, z1, xt0=None, xt1=None, yt=None, zf=None):
    xt0 = x0 if xt0 is None else xt0; xt1 = x1 if xt1 is None else xt1
    yt = y if yt is None else yt
    zfr = z1 if zf is None else zf
    v = [(x0,-y,z0),(x1,-y,z0),(x1,y,z0),(x0,y,z0),
         (xt0,-yt,z1),(xt1,-yt,zfr),(xt1,yt,zfr),(xt0,yt,z1)]
    f = [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    return v, f

v,f = caixa(-2.0, 2.0, 0.9, 0.30, 1.00, zf=0.80);                      malha("Carroceria", v, f, M_body, bevel=0.12)
v,f = caixa(-1.75, 0.75, 0.82, 0.98, 1.55, xt0=-1.6, xt1=-0.05, yt=0.66); malha("Cabine", v, f, M_glass, bevel=0.08)
v,f = caixa(-1.62, -0.03, 0.68, 1.52, 1.62, xt0=-1.55, xt1=-0.15, yt=0.62); malha("Teto", v, f, M_body, bevel=0.04)

def roda(nome, x, y, r, w):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=r, depth=w, location=(x,y,r), rotation=(math.pi/2,0,0))
    t = bpy.context.active_object; t.name = nome; para_colecao(t); t.data.materials.append(M_tire)
    bv = t.modifiers.new("Bevel","BEVEL"); bv.width = r*0.18; bv.segments = 4
    for p in t.data.polygons: p.use_smooth = True
    lado = 1 if y > 0 else -1
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=r*0.62, depth=0.06, location=(x, y+lado*(w/2), r), rotation=(math.pi/2,0,0))
    aro = bpy.context.active_object; aro.name = nome+"_Aro"; para_colecao(aro); aro.data.materials.append(M_chrome)
    for i in range(5):
        a = i*2*math.pi/5
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x+math.cos(a)*r*0.3, y+lado*(w/2+0.035), r+math.sin(a)*r*0.3), rotation=(0,-a,0))
        s = bpy.context.active_object; s.scale = (r*0.55, 0.03, 0.07); s.name = "%s_Raio%d" % (nome, i)
        para_colecao(s); s.data.materials.append(M_black)

roda("Roda_TE", -1.30,  0.92, 0.52, 0.42)
roda("Roda_TD", -1.30, -0.92, 0.52, 0.42)
roda("Roda_DE",  1.30,  0.88, 0.38, 0.30)
roda("Roda_DD",  1.30, -0.88, 0.38, 0.30)

for y in (0.55, -0.55):
    v,f = caixa(1.93, 2.03, 0.18, 0.62, 0.74);  o = malha("Farol", v, f, M_head, bevel=0.02, subsurf=0); o.location.y = y
    v,f = caixa(-2.03, -1.95, 0.2, 0.72, 0.86); o = malha("Lanterna", v, f, M_tail, bevel=0.02, subsurf=0); o.location.y = y

v,f = caixa(1.96, 2.04, 0.35, 0.40, 0.55);   malha("Grade", v, f, M_black, bevel=0.02, subsurf=0)
v,f = caixa(-1.95, -1.45, 0.85, 1.62, 1.68); malha("Aerofolio", v, f, M_black, bevel=0.02, subsurf=0)
for y in (0.55, -0.55):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-1.72, y, 1.35))
    s = bpy.context.active_object; s.scale = (0.08, 0.05, 0.6); s.name = "Suporte_Aerofolio"
    para_colecao(s); s.data.materials.append(M_black)

for y in (0.95, -0.95):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.07, depth=1.6, location=(-0.1, y, 0.36), rotation=(0, math.pi/2, 0))
    e = bpy.context.active_object; e.name = "Escape"; para_colecao(e); e.data.materials.append(M_chrome)

v,f = caixa(0.55, 1.25, 0.35, 0.95, 1.20, xt0=0.6, xt1=1.2, yt=0.3); malha("Motor", v, f, M_chrome, bevel=0.03, subsurf=0)
for i, x in enumerate((0.7, 0.9, 1.1)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.07, depth=0.3, location=(x, 0, 1.3))
    t = bpy.context.active_object; t.name = "Corneta%d" % i; para_colecao(t); t.data.materials.append(M_chrome)

if not bpy.data.objects.get("Chao"):
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0,0,0))
    g = bpy.context.active_object; g.name = "Chao"
    g.data.materials.append(mat("Chao", (0.6,0.6,0.62), rough=0.6))

cam = bpy.data.objects.get("Camera")
if cam is None:
    dados = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", dados)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
cam.location = (6.5, -6.0, 3.2)
cam.rotation_euler = (mathutils.Vector((0,0,0.8)) - cam.location).to_track_quat('-Z','Y').to_euler()

luz = bpy.data.objects.get("Light")
if luz and luz.type == 'LIGHT':
    luz.data.type = 'SUN'; luz.data.energy = 4
    luz.rotation_euler = (math.radians(40), math.radians(15), math.radians(30))

for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for sp in area.spaces:
            if sp.type == 'VIEW_3D':
                sp.shading.type = 'MATERIAL'
                sp.region_3d.view_perspective = 'CAMERA'

bpy.ops.object.select_all(action='DESELECT')
result = {"objetos": len(col.objects)}
'''


FORMAS = {
    # palavra que o Fred usa -> forma
    "macaco": "macaco", "suzanne": "macaco", "cubo": "cubo", "caixa": "cubo",
    "esfera": "esfera", "bola": "esfera", "cilindro": "cilindro",
    "cone": "cone", "rosca": "rosca", "donut": "rosca", "anel": "rosca",
}
ANIMACOES = ("girar", "pular", "tudo", "nenhuma")


def blender_objeto(forma="cubo", cor="", animacao="nenhuma", **_):
    """Cria uma forma basica (macaco, cubo, esfera, cilindro, cone, rosca),
    com cor e animacao opcional (girar, pular, tudo)."""
    forma = FORMAS.get((forma or "").strip().lower(), "cubo")
    nome_cor = (cor or "").strip().lower()
    rgb = CORES.get(nome_cor) or ((0.45, 0.25, 0.1) if forma == "macaco" else CORES["laranja"])
    animacao = (animacao or "nenhuma").strip().lower()
    if animacao not in ANIMACOES:
        animacao = "girar"
    codigo = (_CODIGO_OBJETO.replace("__FORMA__", repr(forma))
              .replace("__COR__", repr(rgb)).replace("__ANIM__", repr(animacao)))
    resposta = executar_codigo(codigo)
    if resposta.get("status") != "ok":
        return _texto(resposta)
    r = resposta.get("result", {})
    texto = "Criei o objeto '%s' no Blender, na colecao 'Objetos Bigode'." % r.get("objeto", forma)
    if animacao != "nenhuma":
        texto += (" Animacao: %s, 120 quadros (5 segundos)." % animacao)
        texto += (" Ja esta tocando no Blender." if r.get("tocando") is True
                  else " Aperte Espaco no Blender para tocar.")
    texto += " O arquivo ainda NAO foi salvo (Ctrl+S no Blender)."
    return texto


_CODIGO_OBJETO = r'''
import bpy, math

FORMA = __FORMA__
COR = __COR__
ANIM = __ANIM__

col = bpy.data.collections.get("Objetos Bigode") or bpy.data.collections.new("Objetos Bigode")
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)

# cada objeto novo vai ao lado do anterior, sem encavalar no carrinho
y = -4.0 - 3.0 * len([o for o in col.objects if o.parent is None])
raio = 1.0
local = (0.0, y, raio)
criar = {
    "macaco":   lambda: bpy.ops.mesh.primitive_monkey_add(size=2, location=local),
    "cubo":     lambda: bpy.ops.mesh.primitive_cube_add(size=2, location=local),
    "esfera":   lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=raio, segments=48, ring_count=24, location=local),
    "cilindro": lambda: bpy.ops.mesh.primitive_cylinder_add(radius=raio, depth=2, vertices=48, location=local),
    "cone":     lambda: bpy.ops.mesh.primitive_cone_add(radius1=raio, depth=2, vertices=48, location=local),
    "rosca":    lambda: bpy.ops.mesh.primitive_torus_add(major_radius=raio, minor_radius=0.35, location=local),
}
criar.get(FORMA, criar["cubo"])()
o = bpy.context.active_object
for c in list(o.users_collection): c.objects.unlink(o)
col.objects.link(o)
o.name = FORMA.capitalize()

if FORMA in ("macaco", "esfera", "rosca"):
    sub = o.modifiers.new("Suave", "SUBSURF"); sub.levels = 2; sub.render_levels = 2
    for p in o.data.polygons: p.use_smooth = True
else:
    bv = o.modifiers.new("Bevel", "BEVEL"); bv.width = 0.05; bv.segments = 3

m = bpy.data.materials.new("Cor_" + o.name)
m.use_nodes = True
b = m.node_tree.nodes.get("Principled BSDF")
if b:
    b.inputs["Base Color"].default_value = (*COR, 1)
    if "Roughness" in b.inputs: b.inputs["Roughness"].default_value = 0.35
m.diffuse_color = (*COR, 1)
o.data.materials.append(m)

cena = bpy.context.scene
if ANIM != "nenhuma":
    cena.frame_start = 1
    cena.frame_end = 120
    if ANIM in ("girar", "tudo"):
        pref = bpy.context.preferences.edit
        antes = pref.keyframe_new_interpolation_type
        pref.keyframe_new_interpolation_type = 'LINEAR'
        try:
            o.rotation_euler = (0, 0, 0)
            o.keyframe_insert("rotation_euler", index=2, frame=1)
            o.rotation_euler[2] = 2 * math.pi
            o.keyframe_insert("rotation_euler", index=2, frame=120)
        finally:
            pref.keyframe_new_interpolation_type = antes
    if ANIM in ("pular", "tudo"):
        for f, z in ((1, raio), (30, raio + 1.5), (60, raio), (90, raio + 1.5), (120, raio)):
            o.location[2] = z
            o.keyframe_insert("location", index=2, frame=f)
    # rotacao em velocidade constante (sem acelerar e frear)
    try:
        for fc in o.animation_data.action.fcurves:
            for k in fc.keyframe_points:
                k.interpolation = 'LINEAR' if fc.data_path == "rotation_euler" else 'BEZIER'
    except Exception:
        pass
    cena.frame_set(1)

bpy.ops.object.select_all(action='DESELECT')
o.select_set(True)
bpy.context.view_layer.objects.active = o

# tira a vista da camera do carrinho e enquadra o objeto novo
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for sp in area.spaces:
            if sp.type == 'VIEW_3D':
                sp.shading.type = 'MATERIAL'
                sp.region_3d.view_perspective = 'PERSP'
        regiao = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if regiao:
            try:
                with bpy.context.temp_override(area=area, region=regiao):
                    bpy.ops.view3d.view_selected()
            except Exception:
                pass

tocando = False
if ANIM != "nenhuma":
    try:
        janela = bpy.context.window_manager.windows[0]
        area = next(a for a in janela.screen.areas if a.type == 'VIEW_3D')
        with bpy.context.temp_override(window=janela, area=area):
            if not bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
        tocando = True
    except Exception:
        tocando = False

result = {"objeto": o.name, "animacao": ANIM, "tocando": tocando}
'''


def blender_mascote(texto="", cor="", animar="sim", pose="em_pe", magro="nao", **_):
    """Macaco cartoon de corpo inteiro (cabeca, tronco com camisa, bracos,
    pernas, rabo), com texto opcional na camisa e animacao de pular e acenar.
    Recria o mascote do zero a cada chamada (colecao 'Mascote')."""
    texto = (texto or "").strip()[:40]
    rgb = CORES.get((cor or "").strip().lower(), (0.1, 0.55, 0.25))
    animar = str(animar).strip().lower() not in ("nao", "não", "false", "0", "nenhuma")
    pose = "meditando" if str(pose).strip().lower() in ("meditando", "sentado", "buda", "lotus") else "em_pe"
    magro = str(magro).strip().lower() in ("sim", "true", "1", "magro")
    codigo = (_CODIGO_MASCOTE.replace("__TEXTO__", repr(texto))
              .replace("__COR__", repr(rgb)).replace("__ANIM__", repr(animar))
              .replace("__POSE__", repr(pose)).replace("__MAGRO__", repr(magro)))
    resposta = executar_codigo(codigo)
    if resposta.get("status") != "ok":
        return _texto(resposta)
    r = resposta.get("result", {})
    msg = "Mascote criado no Blender: macaco cartoon de corpo inteiro, %s pecas na colecao 'Mascote'." % r.get("pecas", "?")
    if texto:
        msg += " Camisa com o texto '%s'." % texto
    if pose == "meditando":
        msg += " Pose: sentado de pernas cruzadas, polegares para cima, flutuando."
    if magro:
        msg += " Corpo magro."
    if animar:
        msg += (" Animacao: flutua subindo e descendo, 96 quadros." if pose == "meditando"
                else " Animacao: pula, 96 quadros.")
        msg += " Ja esta tocando." if r.get("tocando") is True else " Aperte Espaco no Blender para tocar."
    msg += " O arquivo ainda NAO foi salvo (Ctrl+S no Blender)."
    return msg


_CODIGO_MASCOTE = r'''
import bpy, math
from mathutils import Matrix, Vector

TEXTO = __TEXTO__
COR_CAMISA = __COR__
ANIMAR = __ANIM__
POSE = __POSE__        # "em_pe" ou "meditando"
MAGRO = __MAGRO__

# recomeca do zero a cada pedido
col = bpy.data.collections.get("Mascote") or bpy.data.collections.new("Mascote")
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
for o in list(col.objects):
    bpy.data.objects.remove(o, do_unlink=True)

def mat(nome, cor, rough=0.5):
    m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Base Color"].default_value = (*cor, 1)
        if "Roughness" in b.inputs: b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*cor, 1)
    return m

M_pelo   = mat("Mascote_Pelo", (0.30, 0.15, 0.06), 0.8)
M_rosto  = mat("Mascote_Rosto", (0.85, 0.62, 0.45), 0.6)
M_camisa = mat("Mascote_Camisa", COR_CAMISA, 0.6)
M_calca  = mat("Mascote_Calca", (0.08, 0.12, 0.35), 0.7)
M_olho   = mat("Mascote_Olho", (0.95, 0.95, 0.95), 0.2)
M_pupila = mat("Mascote_Pupila", (0.02, 0.02, 0.02), 0.1)
M_texto  = mat("Mascote_Texto", (1.0, 1.0, 1.0), 0.4)

raiz = bpy.data.objects.new("Mascote", None)
col.objects.link(raiz)
raiz.location = (0.0, 6.0, 0.0)
raiz.empty_display_size = 0.5

def pegar(nome, material, pai=raiz):
    o = bpy.context.active_object
    for c in list(o.users_collection): c.objects.unlink(o)
    col.objects.link(o)
    o.name = nome
    if material: o.data.materials.append(material)
    if o.type == 'MESH':
        for p in o.data.polygons: p.use_smooth = True
    o.parent = pai
    return o

def esfera(nome, material, local, escala, pai=raiz):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=32, ring_count=16, location=(0, 0, 0))
    o = pegar(nome, material, pai)
    o.location = local; o.scale = escala
    return o

def membro(nome, material, a, b, raio, pai=raiz):
    """Cilindro de a ate b (coordenadas do mascote), com juntas redondas."""
    a, b = Vector(a), Vector(b)
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=raio, depth=d.length, vertices=24, location=(0, 0, 0))
    o = pegar(nome, material, pai)
    o.location = (a + b) / 2
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    esfera(nome + "_junta", material, tuple(b), (raio, raio, raio), pai)
    return o

k = 0.68 if MAGRO else 1.0          # largura do corpo
rm = 0.085 if MAGRO else 0.12       # grossura de braco
rp = 0.12 if MAGRO else 0.17        # grossura de perna
maos = []

if POSE == "meditando":
    # sentado de pernas cruzadas (lotus)
    z_tronco = 1.1
    esfera("Quadril", M_calca, (0, 0, 0.55), (0.55 * k + 0.1, 0.45, 0.26))
    tronco = esfera("Tronco", M_camisa, (0, 0, z_tronco), (0.66 * k, 0.52 * k, 0.6))
    for lado, s in (("E", 1), ("D", -1)):
        joelho = (0.78 * s, -0.3, 0.32)
        membro("Coxa_" + lado, M_calca, (0.22 * s, -0.05, 0.45), joelho, rp)
        pe = (-0.25 * s, -0.55, 0.36 if s > 0 else 0.3)
        membro("Canela_" + lado, M_calca, joelho, pe, rp * 0.9)
        esfera("Pe_" + lado, M_pelo, pe, (0.13, 0.2, 0.08))
        ombro = (0.66 * k * 0.95 * s, 0, z_tronco + 0.42)
        cotovelo = (0.78 * s, -0.12, z_tronco - 0.2)
        mao = (0.62 * s, -0.5, 0.62)
        membro("Braco_" + lado, M_pelo, ombro, cotovelo, rm)
        membro("Antebraco_" + lado, M_pelo, cotovelo, mao, rm * 0.9)
        maos.append(mao)
    z_cabeca = z_tronco + 0.6 + 0.45
else:
    # em pe
    z_tronco = 1.55
    for lado, s in (("E", 1), ("D", -1)):
        membro("Perna_" + lado, M_calca, (0.28 * k * s, 0, 0.95), (0.28 * k * s, 0, 0.15), rp)
        esfera("Pe_" + lado, M_pelo, (0.28 * k * s, -0.12, 0.1), (0.2, 0.3, 0.1))
    esfera("Quadril", M_calca, (0, 0, 1.0), (0.62 * k, 0.5 * k, 0.35))
    tronco = esfera("Tronco", M_camisa, (0, 0, z_tronco), (0.66 * k, 0.52 * k, 0.62))
    for lado, s in (("E", 1), ("D", -1)):
        ombro = (0.66 * k * 0.95 * s, 0, z_tronco + 0.4)
        if s < 0 and ANIMAR:
            mao = (-1.05 * k - 0.3, -0.1, z_tronco + 1.1)     # acenando
        else:
            mao = ((0.66 * k + 0.35) * s, -0.1, z_tronco - 0.45)
        membro("Braco_" + lado, M_pelo, ombro, mao, rm)
        maos.append(mao)
    z_cabeca = z_tronco + 0.62 + 0.45

esfera("Barriga", M_rosto, (0, -0.52 * k * 0.55, z_tronco - 0.3), (0.4 * k, 0.3 * k, 0.22))

# maos com o polegar para cima (sinal de positivo)
for i, m in enumerate(maos):
    esfera("Mao_%d" % i, M_rosto, m, (0.13, 0.13, 0.13))
    base = Vector(m) + Vector((0, -0.03, 0.08))
    membro("Polegar_%d" % i, M_rosto, tuple(base), tuple(base + Vector((0, 0, 0.17))), 0.045)

# cabeca: a Suzanne do Blender, olhando para frente (-Y)
bpy.ops.mesh.primitive_monkey_add(size=1.5, location=(0, 0, 0))
cabeca = pegar("Cabeca", M_pelo)
cabeca.location = (0, -0.05, z_cabeca)
cabeca.rotation_euler = (math.radians(-8), 0, 0)
sub = cabeca.modifiers.new("Suave", "SUBSURF"); sub.levels = 2; sub.render_levels = 2
esfera("Focinho", M_rosto, (0, -0.52, -0.22), (0.42, 0.25, 0.25), pai=cabeca)
for lado, x in (("E", 0.24), ("D", -0.24)):
    esfera("Olho_" + lado, M_olho, (x, -0.55, 0.12), (0.16, 0.1, 0.19), pai=cabeca)
    esfera("Pupila_" + lado, M_pupila, (x * 1.02, -0.63, 0.1), (0.07, 0.05, 0.08), pai=cabeca)

# rabo em espiral
zq = 0.55 if POSE == "meditando" else 1.0
curva = bpy.data.curves.new("Rabo", "CURVE")
curva.dimensions = '3D'; curva.bevel_depth = 0.06; curva.bevel_resolution = 4
sp = curva.splines.new('BEZIER')
pontos = [(0, 0.4, zq), (0, 0.95, zq + 0.1), (0, 1.2, zq + 0.7), (0, 0.9, zq + 1.0)]
sp.bezier_points.add(len(pontos) - 1)
for bp, p in zip(sp.bezier_points, pontos):
    bp.co = p; bp.handle_left_type = bp.handle_right_type = 'AUTO'
rabo = bpy.data.objects.new("Rabo", curva)
col.objects.link(rabo); rabo.data.materials.append(M_pelo); rabo.parent = raiz

# texto na camisa, acompanhando a curva do tronco
if TEXTO:
    tc = bpy.data.curves.new("Texto_Camisa", "FONT")
    tc.body = TEXTO; tc.align_x = 'CENTER'; tc.align_y = 'CENTER'
    tc.extrude = 0.01
    largura = 1.2 * k
    tc.size = min(0.2, largura / max(1, len(TEXTO) * 0.55))
    txt = bpy.data.objects.new("Texto_Camisa", tc)
    col.objects.link(txt); txt.data.materials.append(M_texto)
    txt.parent = raiz
    txt.location = (0, -0.52 * k - 0.03, z_tronco + 0.08)
    txt.rotation_euler = (math.radians(90), 0, 0)
    try:
        cola = txt.modifiers.new("Na_camisa", "SHRINKWRAP")
        cola.target = tronco; cola.wrap_mode = 'OUTSIDE_SURFACE'; cola.offset = 0.01
    except Exception:
        pass

cena = bpy.context.scene
if POSE == "meditando":
    raiz.location[2] = 0.6       # flutuando acima do chao
if ANIMAR:
    cena.frame_start = 1; cena.frame_end = 96
    if POSE == "meditando":
        # sobe e desce devagar, balancando de leve
        for f, z, giro in ((1, 0.5, -4), (48, 0.9, 4), (96, 0.5, -4)):
            raiz.location[2] = z
            raiz.keyframe_insert("location", index=2, frame=f)
            raiz.rotation_euler[2] = math.radians(giro)
            raiz.keyframe_insert("rotation_euler", index=2, frame=f)
    else:
        for f in range(1, 97, 12):
            subir = (f // 12) % 2 == 1
            raiz.location[2] = 0.25 if subir else 0.0
            raiz.keyframe_insert("location", index=2, frame=f)
    cena.frame_set(1)

# viewport: enquadra o mascote
bpy.ops.object.select_all(action='DESELECT')
for o in col.objects: o.select_set(True)
bpy.context.view_layer.objects.active = raiz
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

tocando = False
if ANIMAR:
    try:
        janela = bpy.context.window_manager.windows[0]
        area = next(a for a in janela.screen.areas if a.type == 'VIEW_3D')
        with bpy.context.temp_override(window=janela, area=area):
            if not bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
        tocando = True
    except Exception:
        tocando = False

result = {"pecas": len(col.objects), "texto": TEXTO, "pose": POSE, "tocando": tocando}
'''


TIPOS_PECA = ("cubo", "esfera", "cilindro", "cone", "rosca", "macaco", "plano",
              "membro", "texto")


def _vetor(v, n=3, padrao=0.0):
    try:
        v = [float(x) for x in (v if isinstance(v, (list, tuple)) else [v] * n)]
    except (TypeError, ValueError):
        return None
    return (v + [padrao] * n)[:n]


def blender_montar(pecas="", projeto="Projeto Bigode", animar="", **_):
    """Monta um projeto 3D a partir de uma lista de pecas em JSON.

    E o jeito do Bigode construir QUALQUER coisa no Blender sem escrever
    codigo Python: ele descreve as pecas (forma, posicao, tamanho, cor) e
    este codigo, que ja foi testado, faz o resto. Modelo pequeno erra
    codigo bpy; lista de pecas ele acerta."""
    if isinstance(pecas, str):
        bruto = pecas.strip()
        if bruto.startswith("```"):
            bruto = bruto.strip("`").split("\n", 1)[-1]
        try:
            pecas = json.loads(bruto) if bruto else []
        except ValueError as erro:
            return ("As pecas precisam ser uma lista JSON valida (%s). Exemplo: "
                    '[{"tipo":"esfera","pos":[0,0,1],"escala":[1,1,1],"cor":"branco"}]' % erro)
    if isinstance(pecas, dict):
        pecas = pecas.get("pecas", [pecas])
    if not isinstance(pecas, list) or not pecas:
        return "Nenhuma peca recebida. Mande uma lista com pelo menos uma peca."
    limpas, avisos = [], []
    for i, p in enumerate(pecas[:200]):
        if not isinstance(p, dict):
            avisos.append("peca %d ignorada: nao e objeto JSON" % i); continue
        tipo = str(p.get("tipo", "")).strip().lower()
        tipo = FORMAS.get(tipo, tipo)
        if tipo not in TIPOS_PECA:
            avisos.append("peca %d: tipo '%s' nao existe (use %s)" % (i, tipo, ", ".join(TIPOS_PECA)))
            continue
        cor = p.get("cor", "branco")
        rgb = CORES.get(str(cor).strip().lower()) if isinstance(cor, str) else _vetor(cor)
        item = {"tipo": tipo, "nome": str(p.get("nome") or "%s_%d" % (tipo, i))[:40],
                "cor": tuple(rgb or CORES["branco"])}
        if tipo == "membro":
            de, ate = _vetor(p.get("de")), _vetor(p.get("ate"))
            if not de or not ate:
                avisos.append("peca %d (membro): precisa de 'de' e 'ate' [x,y,z]" % i); continue
            item.update(de=de, ate=ate, raio=float(p.get("raio", 0.1)))
        else:
            item["pos"] = _vetor(p.get("pos", [0, 0, 0])) or [0, 0, 0]
            item["escala"] = _vetor(p.get("escala", 1), padrao=1.0) or [1, 1, 1]
            if "rot" in p:
                item["rot"] = _vetor(p.get("rot")) or [0, 0, 0]
            if tipo == "texto":
                item["texto"] = str(p.get("texto", ""))[:80]
                item["tamanho"] = float(p.get("tamanho", 0.3))
        limpas.append(item)
    if not limpas:
        return "Nenhuma peca valida.\n" + "\n".join(avisos)
    nome = "".join(c for c in (projeto or "Projeto Bigode") if c.isalnum() or c in " -_")[:40] or "Projeto Bigode"
    anim = str(animar or "").strip().lower()
    codigo = (_CODIGO_MONTAR.replace("__PROJETO__", repr(nome))
              .replace("__PECAS__", repr(limpas)).replace("__ANIMAR__", repr(anim)))
    resposta = executar_codigo(codigo)
    if resposta.get("status") != "ok":
        return _texto(resposta)
    r = resposta.get("result", {})
    msg = "Projeto '%s' montado no Blender: %s pecas." % (nome, r.get("feitas"))
    if anim in ("flutuar", "girar", "pular"):
        msg += " Animacao: %s%s." % (anim, ", ja tocando" if r.get("tocando") else "")
    probs = avisos + list(r.get("erros") or [])
    if probs:
        msg += "\nProblemas:\n- " + "\n- ".join(probs[:10])
    msg += "\nPara corrigir, chame blender_montar de novo com o MESMO projeto: ele recomeca do zero."
    return msg


_CODIGO_MONTAR = r'''
import bpy, math
from mathutils import Vector

PROJETO = __PROJETO__
PECAS = __PECAS__
ANIMAR = __ANIMAR__

col = bpy.data.collections.get(PROJETO) or bpy.data.collections.new(PROJETO)
if col.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(col)
for o in list(col.objects):
    bpy.data.objects.remove(o, do_unlink=True)

raiz = bpy.data.objects.new(PROJETO, None)
col.objects.link(raiz)

# Projeto novo nasce AO LADO do que ja existe na cena, nunca dentro.
# (28/09: o gato nasceu na origem, escondido dentro do carrinho.)
xs = []
for outro in bpy.context.scene.objects:
    if outro.type in ('MESH', 'CURVE', 'FONT') and outro.name not in col.objects and outro.name != "Chao":
        xs += [(outro.matrix_world @ Vector(c)).x for c in outro.bound_box]
raiz.location.x = (max(xs) + 2.0) if xs else 0.0

def material(cor):
    nome = "Bigode_%.2f_%.2f_%.2f" % tuple(cor)
    m = bpy.data.materials.get(nome) or bpy.data.materials.new(nome)
    # a cor e aplicada SEMPRE, nao so na criacao: um material com o mesmo
    # nome vindo de outro teste ficava cinza para sempre.
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    if b: b.inputs["Base Color"].default_value = (*cor, 1)
    m.diffuse_color = (*cor, 1)
    return m

def ajustar(o, p):
    for c in list(o.users_collection): c.objects.unlink(o)
    col.objects.link(o)
    o.name = p.get("nome") or p["tipo"]
    o.parent = raiz
    if o.type in ('MESH', 'CURVE', 'FONT'):
        o.data.materials.append(material(p["cor"]))
    if o.type == 'MESH' and p["tipo"] not in ("cubo",):
        for f in o.data.polygons: f.use_smooth = True
    return o

feitas, erros = [], []
for i, p in enumerate(PECAS):
    try:
        t = p["tipo"]
        pos = p.get("pos", (0, 0, 0))
        if t == "membro":
            a, b = Vector(p["de"]), Vector(p["ate"])
            d = b - a
            bpy.ops.mesh.primitive_cylinder_add(radius=p.get("raio", 0.1), depth=max(d.length, 0.01), vertices=24)
            o = ajustar(bpy.context.active_object, p)
            o.location = (a + b) / 2
            o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        elif t == "texto":
            c = bpy.data.curves.new(p.get("nome") or "texto", "FONT")
            c.body = str(p.get("texto", ""))[:80]; c.align_x = 'CENTER'; c.align_y = 'CENTER'
            c.size = p.get("tamanho", 0.3); c.extrude = 0.02
            o = bpy.data.objects.new(c.name, c)
            bpy.context.scene.collection.objects.link(o)
            o = ajustar(o, p)
            o.location = pos
            o.rotation_euler = [math.radians(v) for v in p.get("rot", (90, 0, 0))]
        else:
            criar = {
                "cubo": lambda: bpy.ops.mesh.primitive_cube_add(size=1),
                "esfera": lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, segments=32, ring_count=16),
                "cilindro": lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=1, vertices=32),
                "cone": lambda: bpy.ops.mesh.primitive_cone_add(radius1=0.5, depth=1, vertices=32),
                "rosca": lambda: bpy.ops.mesh.primitive_torus_add(major_radius=0.5, minor_radius=0.15),
                "macaco": lambda: bpy.ops.mesh.primitive_monkey_add(size=1),
                "plano": lambda: bpy.ops.mesh.primitive_plane_add(size=1),
            }[t]
            criar()
            o = ajustar(bpy.context.active_object, p)
            o.location = pos
            o.scale = p.get("escala", (1, 1, 1))
            o.rotation_euler = [math.radians(v) for v in p.get("rot", (0, 0, 0))]
            if t in ("macaco", "esfera"):
                s = o.modifiers.new("Suave", "SUBSURF"); s.levels = 1; s.render_levels = 2
        feitas.append(o.name)
    except Exception as e:
        erros.append("peca %d (%s): %s" % (i, p.get("tipo"), e))

cena = bpy.context.scene
tipo_anim = (ANIMAR or {}).get("tipo", "") if isinstance(ANIMAR, dict) else str(ANIMAR or "")
if tipo_anim in ("flutuar", "girar", "pular"):
    cena.frame_start = 1; cena.frame_end = 96
    if tipo_anim == "flutuar":
        for f, z in ((1, 0.0), (48, 0.4), (96, 0.0)):
            raiz.location[2] = z; raiz.keyframe_insert("location", index=2, frame=f)
    elif tipo_anim == "pular":
        for f in range(1, 97, 12):
            raiz.location[2] = 0.5 if (f // 12) % 2 else 0.0
            raiz.keyframe_insert("location", index=2, frame=f)
    else:
        # Blender 5 nao tem mais action.fcurves: a velocidade constante
        # vem da preferencia de interpolacao, trocada so durante a chave.
        pref = bpy.context.preferences.edit
        antes = pref.keyframe_new_interpolation_type
        pref.keyframe_new_interpolation_type = 'LINEAR'
        try:
            raiz.rotation_euler[2] = 0; raiz.keyframe_insert("rotation_euler", index=2, frame=1)
            raiz.rotation_euler[2] = 2 * math.pi; raiz.keyframe_insert("rotation_euler", index=2, frame=96)
        finally:
            pref.keyframe_new_interpolation_type = antes
    cena.frame_set(1)

bpy.ops.object.select_all(action='DESELECT')
for o in col.objects: o.select_set(True)
bpy.context.view_layer.objects.active = raiz
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
tocando = False
if tipo_anim in ("flutuar", "girar", "pular"):
    try:
        janela = bpy.context.window_manager.windows[0]
        area = next(a for a in janela.screen.areas if a.type == 'VIEW_3D')
        with bpy.context.temp_override(window=janela, area=area):
            if not bpy.context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
        tocando = True
    except Exception:
        pass

result = {"projeto": PROJETO, "feitas": len(feitas), "erros": erros, "tocando": tocando}
'''


# ==========================================================================
# VISAO: o Bigode olhando imagem e cena                          (28/09)
#
#   Usa o mesmo olho do Bigode (Qwen2.5-VL na Modal, config "olho_modal").
#   Dois caminhos:
#     - referencia_da_imagem: foto de produto / desenho / print -> lista
#       de pecas para o blender_montar. Guardada em producao_blender/
#       ultima_referencia.json ate o Fred mandar montar.
#     - blender_olhar: tira um PNG da cena aberta e pergunta ao olho o
#       que ha nela. E assim que o Bigode "ve" o projeto para continuar.
# ==========================================================================

import base64
import urllib.request

PASTA_SAIDA = BASE / "producao_blender"
REFERENCIA = PASTA_SAIDA / "ultima_referencia.json"

PROMPT_PECAS = """Voce e um modelador 3D. Olhe a imagem e reconstrua o objeto principal com formas simples para o Blender.

Pedido do usuario: %s

Responda SOMENTE com um JSON, sem texto antes ou depois, neste formato:
{"projeto": "nome curto", "descricao": "uma frase do que e o objeto", "pecas": [ ... ]}

Cada peca e um destes:
{"tipo":"cubo|esfera|cilindro|cone|rosca|plano","nome":"...","pos":[x,y,z],"escala":[x,y,z],"rot":[graus_x,graus_y,graus_z],"cor":"..."}
{"tipo":"membro","nome":"...","de":[x,y,z],"ate":[x,y,z],"raio":0.1,"cor":"..."}
{"tipo":"texto","nome":"...","texto":"...","pos":[x,y,z],"tamanho":0.2,"cor":"..."}

Regras:
- Metros. Z para cima, chao em z=0. A frente do objeto olha para -Y. X e a largura.
- pos e o CENTRO da peca. Cubo com escala [1,1,1] mede 1 m; esfera [1,1,1] tem 1 m de diametro; cilindro [1,1,1] tem 1 m de diametro e 1 m de altura.
- Mantenha as proporcoes da imagem. Altura total entre 0.5 e 3 metros.
- Cores: vermelho, azul, verde, amarelo, laranja, preto, branco, prata, roxo, rosa, marrom, cinza, bege, pele, dourado, ciano, ou [r,g,b] de 0 a 1.
- Se houver texto/logo legivel no objeto, use uma peca "texto" na frente (y negativo).
- No maximo 14 pecas. Numeros com no maximo 2 casas decimais."""


def _olho():
    bloco = _config().get("olho_modal") or {}
    if not isinstance(bloco, dict) or not bloco.get("ligada", True):
        return "", ""
    return str(bloco.get("url") or "").strip(), str(bloco.get("token") or "").strip()


def olhar_imagem(imagem_b64, pergunta="", limite=700, timeout=240):
    """Manda uma imagem ao olho do Bigode. Devolve o dict da Modal."""
    url, token = _olho()
    if not url or not token:
        return {"ok": False, "desligado": True,
                "erro": ("A visao do Bigode nao esta publicada. Na pasta do Cerebro:\n"
                         "    python -m modal deploy modal_olho.py\n"
                         "    python usar_modal_olho.py")}
    b64 = (imagem_b64 or "").strip()
    if b64.startswith("data:"):
        b64 = b64.partition(",")[2]
    corpo = {"token": token, "imagem": b64, "pergunta": pergunta or "", "limite": limite}
    try:
        req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as erro:
        return {"ok": False, "erro": "%s: %s" % (type(erro).__name__, str(erro)[:200])}


def extrair_json(texto):
    """Acha o primeiro objeto/lista JSON dentro de uma resposta de modelo."""
    t = (texto or "").strip()
    if "```" in t:
        partes = t.split("```")
        for p in partes[1::2]:
            p = p.split("\n", 1)[1] if p.lower().startswith("json") else p
            try:
                return json.loads(p)
            except ValueError:
                pass
    for abre, fecha in (("{", "}"), ("[", "]")):
        i, j = t.find(abre), t.rfind(fecha)
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except ValueError:
                continue
    return None


def referencia_da_imagem(imagem_b64, pedido=""):
    """Imagem -> pecas para o Blender. Guarda a referencia e devolve o
    texto que vai para a caixa de mensagem do Fred."""
    inicio = time.time()
    r = olhar_imagem(imagem_b64, PROMPT_PECAS % (pedido or "reproduza o objeto da imagem"),
                     limite=1600)
    if not r.get("ok"):
        return r
    dados = extrair_json(r.get("texto"))
    if isinstance(dados, list):
        dados = {"pecas": dados}
    pecas = (dados or {}).get("pecas") if isinstance(dados, dict) else None
    if not pecas:
        return {"ok": True, "segundos": round(time.time() - inicio, 1),
                "texto": ("%s\n\nO olho descreveu a imagem, mas nao devolveu as pecas "
                          "em JSON. Resposta dele:\n```\n%s\n```\n"
                          "Peca: monte isso no blender com blender_montar."
                          % (pedido, (r.get("texto") or "")[:1500]))}
    PASTA_SAIDA.mkdir(exist_ok=True)
    try:
        bruto = base64.b64decode(imagem_b64.partition(",")[2] if imagem_b64.startswith("data:") else imagem_b64)
        (PASTA_SAIDA / "ultima_referencia.png").write_bytes(bruto)
    except Exception:
        pass
    projeto = str(dados.get("projeto") or "Referencia")[:40]
    REFERENCIA.write_text(json.dumps({"projeto": projeto, "pedido": pedido,
                                      "descricao": dados.get("descricao", ""),
                                      "pecas": pecas}, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    texto = ("%s\n\nMonte no blender a referencia da imagem: %s (%d pecas). %s"
             % (pedido.strip(), projeto, len(pecas), dados.get("descricao", ""))).strip()
    return {"ok": True, "texto": texto, "segundos": round(time.time() - inicio, 1)}


def blender_salvar(nome="", **_):
    """Salva o projeto aberto como .blend de verdade (pelo proprio Blender)."""
    PASTA_SAIDA.mkdir(exist_ok=True)
    nome = "".join(c for c in (nome or "") if c.isalnum() or c in "-_") \
        or time.strftime("projeto_%Y%m%d_%H%M%S")
    destino = str(PASTA_SAIDA / (nome + ".blend"))
    r = executar_codigo("import bpy\nbpy.ops.wm.save_as_mainfile(filepath=%r)\n"
                        "result = {'arquivo': bpy.data.filepath}" % destino)
    if r.get("status") == "ok":
        return "Projeto salvo em: %s" % destino
    return _texto(r)


ULTIMA_IMAGEM = PASTA_SAIDA / "ultima_imagem.png"
ULTIMO_3D = PASTA_SAIDA / "ultimo_3d.json"      # para "outra variacao"


def guardar_imagem(imagem_b64):
    """Toda imagem colada no Bigode fica guardada aqui, para "crie isso no
    blender" funcionar mesmo quando o texto vem DEPOIS da imagem."""
    try:
        b64 = imagem_b64.partition(",")[2] if imagem_b64.startswith("data:") else imagem_b64
        PASTA_SAIDA.mkdir(exist_ok=True)
        ULTIMA_IMAGEM.write_bytes(base64.b64decode(b64))
    except Exception:
        pass


def imagem_recente(minutos=60):
    try:
        return ULTIMA_IMAGEM.exists() and (time.time() - ULTIMA_IMAGEM.stat().st_mtime) < minutos * 60
    except OSError:
        return False


FIEL = ("fiel", "realista", "real", "identico", "identica", "igual", "de verdade",
        "trellis", "malha", "exato", "exata", "detalhado", "detalhada")


# Palavras que pedem o jeito ANTIGO (formas simples: esferas, cubos...).
# Sem elas, o Bigode usa o caminho DETALHADO (malha de verdade).
SIMPLES = ("simples", "formas basicas", "formas simples", "com formas", "primitiv",
           "low poly", "lowpoly", "blocos", "rapido", "rascunho", "estilizado")


def quer_simples(texto):
    return any(w in _sem_acento(texto or "") for w in SIMPLES)


PROMPT_INGLES = """Rewrite the request below as ONE short English prompt for an image generator.
Describe only the main object/character, its colors, materials and pose. No background, no text.
Answer with the prompt only, one line, max 40 words.
Request: %s"""

ESTILO_3D = (", single object, full body fully visible, centered, isolated on pure white "
             "background, no shadow, no floor, soft even studio lighting, sharp focus, highly detailed, "
             "high quality 3d render")


def _limpar_pedido(pedido):
    t = re.sub(r"\b(no|na|para o|pro)\s+blender\b", " ", pedido or "", flags=re.I)
    t = re.sub(r"\b(crie|cria|criar|faca|faça|faz|fazer|monte|monta|modele|gere|gera|quero|"
               r"me|um|uma|por favor|3d)\b", " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" .,:;") or pedido


def gerar_conceito(prompt_en, destino):
    """Desenha a imagem-base. 1o o desenhista LOCAL (ComfyUI, sem cota);
    se ele nao estiver ligado, o FLUX no Hugging Face (gasta cota de GPU)."""
    try:
        import imagens
        if imagens.no_ar():
            texto = imagens.gerar_imagem(prompt_en, "quadrado", nome="conceito_3d",
                                         pasta_saida=str(Path(destino).parent))
            achado = re.findall(r"^\s+(\S.*\.png)\s*$", texto or "", re.M)
            if achado and Path(achado[0]).exists():
                return Path(achado[0]), None
    except Exception:
        pass
    caminho, erro = gerar_imagem_flux(prompt_en, destino)
    if caminho:
        return caminho, None
    caminho2, erro2 = gerar_imagem_pollinations(prompt_en, destino)
    if caminho2:
        return caminho2, None
    return None, erro + " | " + erro2


def gerar_imagem_pollinations(prompt_en, destino):
    """Plano C da imagem-base: Pollinations.ai (gratis, sem chave, sem cota
    de GPU sua). Devolve (caminho, erro)."""
    import urllib.parse
    import urllib.request
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt_en[:900])
           + "?width=1024&height=1024&nologo=true&model=flux&seed=%d" % int(time.time()))
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": "Bigode"})
        with urllib.request.urlopen(pedido, timeout=150) as r:
            dados = r.read()
        if len(dados) < 5000:
            return None, "o Pollinations devolveu uma imagem vazia"
        destino = Path(destino).with_suffix(".jpg")
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_bytes(dados)
        return destino, None
    except Exception as erro:
        return None, "o Pollinations nao respondeu: %s" % str(erro)[:150]


def gerar_imagem_flux(prompt_en, destino):
    """Texto (ingles) -> imagem PNG com o FLUX.1-schnell (Space gratis no
    Hugging Face, usa a cota ZeroGPU do token). Devolve (caminho, erro)."""
    import blender_recursos
    if blender_recursos._cota_acabou_ha_pouco():
        return None, "a cota de GPU do Hugging Face acabou ha pouco (pulei o FLUX)"
    ok, msg = blender_recursos.garantir_pacote("gradio_client")
    if not ok:
        return None, msg
    from gradio_client import Client
    token = blender_recursos._token_hf()
    if not token:
        return None, "Falta o token do Hugging Face (huggingface.token no config.json)."
    try:
        try:
            cliente = Client("black-forest-labs/FLUX.1-schnell", token=token, verbose=False)
        except TypeError:
            cliente = Client("black-forest-labs/FLUX.1-schnell", hf_token=token, verbose=False)
        img, _semente = cliente.predict(prompt_en, 0, True, 1024, 1024, 4, api_name="/infer")
        caminho = img.get("path") if isinstance(img, dict) else img
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        try:                                  # webp -> png (o TRELLIS aceita os dois)
            from PIL import Image
            Image.open(caminho).convert("RGB").save(destino)
        except Exception:
            destino = Path(destino).with_suffix(Path(caminho).suffix)
            shutil.copyfile(caminho, destino)
        return Path(destino), None
    except Exception as erro:
        texto = str(erro)
        if "quota" in texto.lower() or "exceeded" in texto.lower():
            try:
                blender_recursos.COTA_HF.write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
            except Exception:
                pass
            texto = "a cota gratis de GPU do Hugging Face acabou por hoje (volta sozinha em algumas horas)"
        return None, "o gerador de imagem nao respondeu: " + texto[:200]


def _conferir_volume(colecao):
    """Avisa se o modelo saiu achatado (uma 'placa' em vez de um objeto)."""
    codigo = ("import bpy, mathutils\n"
              "col = bpy.data.collections.get(%r)\n"
              "pts = [o.matrix_world @ mathutils.Vector(c) for o in (col.all_objects if col else []) "
              "if o.type == 'MESH' for c in o.bound_box]\n"
              "result = {'d': [max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)] if pts else []}"
              % colecao)
    try:
        d = (executar_codigo(codigo, timeout=20).get("result") or {}).get("d") or []
        if d and min(d) < 0.2 * max(d):
            return ("\nATENCAO: o modelo saiu ACHATADO (parece uma placa). Peca de novo: "
                    "cada tentativa sai diferente.")
    except Exception:
        pass
    return ""


def criar_detalhado(pedido, traduzir=None):
    """Pedido em texto -> imagem (FLUX) -> modelo 3D com textura (TRELLIS.2)
    -> importado no Blender. `traduzir(prompt)` devolve texto do modelo de
    linguagem (opcional). Devolve (texto, deu_certo)."""
    import blender_recursos
    inicio = time.time()
    descricao = _limpar_pedido(pedido)
    prompt_en = ""
    for tentar in (blender_recursos.planejar_hf, traduzir):
        if not tentar:
            continue
        try:
            resp = tentar(PROMPT_INGLES % descricao) or ""
        except Exception:
            resp = ""
        resp = resp.strip().strip('"').splitlines()[0].strip() if resp.strip() else ""
        if 3 <= len(resp) <= 400 and re.search(r"[a-zA-Z]{3}", resp):
            prompt_en = resp
            break
    prompt_en = (prompt_en or descricao) + ESTILO_3D
    carimbo = time.strftime("%Y%m%d_%H%M%S")
    imagem, erro = gerar_conceito(prompt_en, PASTA_SAIDA / "gerados" / ("conceito_%s.png" % carimbo))
    if erro:
        return "Nao consegui o modelo detalhado: " + erro, False
    glb, erro = blender_recursos.gerar_malha(imagem)
    if erro:
        return "Nao consegui o modelo detalhado: " + erro, False
    nome = re.sub(r"[^\w]+", "_", _sem_acento(descricao)).strip("_")[:30] or "Modelo"
    texto = blender_recursos.blender_importar(str(glb), nome=nome.capitalize(), altura=1.0)
    if not texto.startswith("Importei"):
        return texto, False
    texto += _conferir_volume(nome.capitalize())
    return ("%s\nModelo DETALHADO criado por " + (blender_recursos.ULTIMO_MOTOR.get("nome") or "gerador 3D")
            + " em %.0fs.\n"
            "Desenho usado como base: %s\nArquivo 3D: %s\n"
            "Quer a versao de formas simples? Peca de novo com a palavra \"simples\"."
            % (texto, time.time() - inicio, imagem, glb)), True


def da_imagem(pedido=""):
    """Transforma a ultima imagem colada em projeto no Blender, de uma vez.
    Padrao: TRELLIS.2 (malha de verdade, com textura). Com a palavra
    "simples" (ou se o TRELLIS falhar), monta com formas basicas."""
    if not imagem_recente():
        return "Nao ha imagem recente. Cole a imagem (Ctrl+V) no Bigode e peca de novo."
    aviso = ""
    if not quer_simples(pedido):
        import blender_recursos
        texto = blender_recursos.blender_gerar_3d(str(ULTIMA_IMAGEM))
        if texto.startswith("Importei"):
            return texto
        aviso = "\n(O modelo fiel nao saiu: %s -- montei com formas simples.)" % texto[:300]
    b64 = base64.b64encode(ULTIMA_IMAGEM.read_bytes()).decode("ascii")
    r = referencia_da_imagem(b64, pedido)
    if not r.get("ok"):
        return "A visao nao respondeu: " + str(r.get("erro"))
    if not REFERENCIA.exists() or "Monte no blender a referencia" not in (r.get("texto") or ""):
        return (r.get("texto") or "A visao nao devolveu as pecas.") + aviso
    return blender_referencia() + aviso


PROMPT_TEXTO_PECAS = """Voce e um modelador 3D. Transforme o pedido em pecas simples para o Blender.
Responda SOMENTE com JSON, sem texto antes ou depois:
{"projeto": "nome curto", "pecas": [ ... ]}

Tipos de peca:
{"tipo":"cubo|esfera|cilindro|cone|rosca|plano","nome":"...","pos":[x,y,z],"escala":[x,y,z],"rot":[gx,gy,gz],"cor":"..."}
{"tipo":"membro","nome":"...","de":[x,y,z],"ate":[x,y,z],"raio":0.1,"cor":"..."}
{"tipo":"texto","nome":"...","texto":"...","pos":[x,y,z],"tamanho":0.2,"cor":"..."}

Regras: metros; Z para cima, chao z=0; frente olha para -Y (rosto e olhos com y negativo); X e a largura.
pos e o CENTRO. esfera [1,1,1] = 1 m de diametro; cubo [1,1,1] = 1 m; cilindro [1,1,1] = 1 m de diametro e 1 m de altura.
membro liga dois pontos (pernas, bracos, rabo, pes de mesa). Pecas devem se encostar, nada flutuando solto.
Cores: vermelho, azul, verde, amarelo, laranja, preto, branco, prata, roxo, rosa, marrom, cinza, bege, pele, dourado, ciano ou [r,g,b].
Entre 6 e 25 pecas.

Exemplo (gato sentado laranja):
{"projeto":"Gato","pecas":[
{"tipo":"esfera","nome":"corpo","pos":[0,0,0.35],"escala":[0.5,0.6,0.55],"cor":"laranja"},
{"tipo":"esfera","nome":"peito","pos":[0,-0.22,0.38],"escala":[0.3,0.2,0.35],"cor":"branco"},
{"tipo":"esfera","nome":"cabeca","pos":[0,-0.15,0.78],"escala":[0.4,0.36,0.34],"cor":"laranja"},
{"tipo":"cone","nome":"orelha_e","pos":[0.12,-0.12,0.98],"escala":[0.12,0.08,0.16],"cor":"laranja"},
{"tipo":"cone","nome":"orelha_d","pos":[-0.12,-0.12,0.98],"escala":[0.12,0.08,0.16],"cor":"laranja"},
{"tipo":"esfera","nome":"olho_e","pos":[0.08,-0.32,0.82],"escala":[0.07,0.03,0.08],"cor":"verde"},
{"tipo":"esfera","nome":"olho_d","pos":[-0.08,-0.32,0.82],"escala":[0.07,0.03,0.08],"cor":"verde"},
{"tipo":"esfera","nome":"focinho","pos":[0,-0.33,0.74],"escala":[0.12,0.06,0.07],"cor":"branco"},
{"tipo":"esfera","nome":"nariz","pos":[0,-0.36,0.76],"escala":[0.03,0.02,0.02],"cor":"rosa"},
{"tipo":"membro","nome":"pata_e","de":[0.1,-0.2,0.3],"ate":[0.1,-0.25,0.03],"raio":0.05,"cor":"branco"},
{"tipo":"membro","nome":"pata_d","de":[-0.1,-0.2,0.3],"ate":[-0.1,-0.25,0.03],"raio":0.05,"cor":"branco"},
{"tipo":"membro","nome":"rabo","de":[0,0.28,0.15],"ate":[0.25,0.35,0.55],"raio":0.04,"cor":"laranja"}]}

Pedido: %s"""


def montar_de_texto(resposta_modelo, pedido=""):
    """Recebe a resposta do modelo (JSON de pecas) e monta."""
    dados = extrair_json(resposta_modelo)
    if isinstance(dados, list):
        dados = {"pecas": dados}
    if not isinstance(dados, dict) or not dados.get("pecas"):
        return ("O modelo nao devolveu as pecas em JSON, entao nao montei nada. "
                "Tente descrever o objeto com mais detalhe."), False
    projeto = str(dados.get("projeto") or pedido[:30] or "Projeto Bigode")
    texto = blender_montar(pecas=dados["pecas"], projeto=projeto)
    return texto, texto.startswith("Projeto")


def blender_referencia(projeto="", **_):
    """Monta no Blender a ultima referencia lida de uma imagem."""
    if not REFERENCIA.exists():
        return ("Nao ha referencia de imagem guardada. Cole a imagem (Ctrl+V) no "
                "Bigode escrevendo junto o que fazer no Blender.")
    try:
        dados = json.loads(REFERENCIA.read_text(encoding="utf-8"))
    except ValueError:
        return "A referencia guardada esta corrompida. Cole a imagem de novo."
    return blender_montar(pecas=dados.get("pecas") or [],
                          projeto=projeto or dados.get("projeto") or "Referencia")


def blender_olhar(pergunta="", **_):
    """Tira um PNG da cena do Blender e pergunta ao olho o que ha nela."""
    PASTA_SAIDA.mkdir(exist_ok=True)
    destino = PASTA_SAIDA / "olhar_cena.png"
    salvo = blender_imagem(nome="olhar_cena", vista="tela")
    if not destino.exists() or not salvo.startswith("Imagem salva"):
        return "Nao consegui tirar a imagem da cena: " + salvo
    b64 = base64.b64encode(destino.read_bytes()).decode("ascii")
    r = olhar_imagem(b64, pergunta or (
        "Esta e uma cena 3D do Blender. Descreva em portugues os objetos, cores, "
        "posicoes relativas e o que parece faltar ou estar errado. Seja objetivo."))
    if not r.get("ok"):
        return "O olho do Bigode nao respondeu: " + str(r.get("erro"))
    return "O que vejo na cena do Blender:\n" + str(r.get("texto") or "")[:LIMITE_RESPOSTA]


# ==========================================================================
# ATALHO DIRETO (usado pelo cerebro.py, antes do modelo)          (28/09)
#
#   Teste real: "voce esta conectado com o blender?" -> o modelo local
#   abriu o Chrome, pesquisou "Venure Website" e nunca chamou uma
#   ferramenta do Blender. Mesma licao da pesquisa e do desenho diretos:
#   quando a frase ja diz a ferramenta, nao ha o que deliberar.
#
#   So dispara se a frase citar o Blender (ou 3D). Tudo que nao casar
#   aqui segue para o modelo normalmente.
# ==========================================================================

import re
import unicodedata


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower())
                   if unicodedata.category(c) != "Mn")


def _fala_de_blender(t):
    return "blender" in t or " 3d" in (" " + t)


def _texto_da_camisa(pergunta):
    """Pega o texto pedido para a camisa, mantendo maiusculas.
    Aceita: dominio (projetosoul.com.br), "entre aspas", ou
    'escrito X' / 'com o texto X' / 'conter X'."""
    p = pergunta or ""
    m = re.search(r"[\"'“”‘’]([^\"'“”‘’]{1,40})[\"'“”‘’]", p)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|br|io|ia)(?:\.br)?\b", p, re.I)
    if m:
        return m.group(0)
    m = re.search(r"(?:escrito|com o texto|com a frase|contendo|conter|contenha)\s+(.{1,40})$", p, re.I)
    if m:
        return m.group(1).strip(" .!?")
    return ""


PALAVRAS_MASCOTE = ("buda", "sentado", "meditando", "flutuando", "magro", "corpo", "camisa", "camiseta", "inteiro", "cartoon", "personagem",
                    "mascote", "bracos", "braco", "pernas", "rabo")


def pedido_direto(pergunta, contexto=()):
    """Devolve (acao, argumentos) quando a frase e inequivoca, senao None.
    acao: 'status', 'carrinho', 'objeto', 'mascote' ou 'imagem'.
    `contexto`: frases anteriores do Fred. Se ele ja estava falando do
    Blender, "crie agora o corpo no macaco" vale mesmo sem a palavra."""
    t = _sem_acento(pergunta)
    # palavra inteira: "conectado" contem "cone", "rosca" contem "rosa"
    palavras = set(re.findall(r"[a-z0-9]+", t))
    no_blender = _fala_de_blender(t) or any(
        _fala_de_blender(_sem_acento(c)) for c in (contexto or ()))

    # "outra variacao" / "refaz": repete a ultima geracao 3D com semente nova
    if re.search(r"outra (variac|versao|tentativa)|refa(z|ca|zer) (o modelo|o 3d|de novo)|gera de novo", t) \
            and (no_blender or "3d" in t or "modelo" in t) and ULTIMO_3D.exists():
        try:
            args = json.loads(ULTIMO_3D.read_text(encoding="utf-8"))
            args["variacao"] = True
            return "gerar_3d", args
        except Exception:
            pass

    extra = _pedido_recursos(pergunta, t, palavras, no_blender)
    if extra:
        return extra

    # Pedido vindo do painel Blender 3D: o modo ja vem escolhido.
    if no_blender and "(detalhado)" in (pergunta or "").lower():
        return "detalhado", {"pedido": pergunta.replace("(detalhado)", "").strip()[:400]}
    if no_blender and "(simples)" in (pergunta or "").lower():
        return "livre", {"pedido": pergunta.replace("(simples)", "com formas simples").strip()[:400]}

    # vem PRIMEIRO: a descricao da imagem pode citar macaco, carro etc.
    if no_blender and "referencia da imagem" in t:
        if quer_simples(t):
            return "referencia", {}
        return "da_imagem", {"pedido": "fiel"}

    # mascote: macaco de corpo inteiro / com camisa
    if no_blender and ("mascote" in palavras or (
            ("macaco" in palavras or "macacao" in palavras or "macao" in palavras)
            and any(w in palavras for w in PALAVRAS_MASCOTE))):
        cor = next((c for c in CORES if c in palavras), "")
        parado = any(w in t for w in ("parado", "sem animacao", "estatico"))
        meditando = any(w in t for w in ("sentad", "cruzad", "buda", "lotus", "medit",
                                          "flutu", "levit", "yoga", "zen"))
        texto = _texto_da_camisa(pergunta) or next(
            (x for x in (_texto_da_camisa(c) for c in reversed(list(contexto or ()))) if x), "")
        return "mascote", {"texto": texto, "cor": cor,
                           "animar": "nao" if parado else "sim",
                           "pose": "meditando" if meditando else "em_pe",
                           "magro": "sim" if ("magro" in t or "magrinho" in t) else "nao"}

    # "crie esse projeto no blender" depois de colar uma imagem: usa a
    # ULTIMA IMAGEM colada, em qualquer ordem que o Fred tenha feito.
    if _fala_de_blender(t) and any(w in t for w in (
            "imagem", "foto", "print", "o que estou vendo", "identico", "igual",
            "esse projeto", "essa figura", "desse", "dessa", "isso")):
        sem_bloco = re.sub(r"O que estou vendo.*?```.*?```", "", pergunta or "", flags=re.S).strip()
        return "da_imagem", {"pedido": sem_bloco[:200] or "reproduza o objeto da imagem"}

    if _fala_de_blender(t) and any(w in t for w in ("olhe", "olha", "olhar", "veja", "ve a cena",
                                                    "enxerg", "como esta a cena", "como ficou")):
        return "olhar", {"pergunta": pergunta}

    if not _fala_de_blender(t) and "carrinho" not in t:
        return None
    if "carrinho" in t or "hot wheels" in t or "hotwheels" in t or "miniatura" in t:
        if not _fala_de_blender(t) and not any(v in t for v in ("crie", "cria", "criar", "monte", "monta", "montar", "faca", "faz", "modele")):
            return None
        cor = next((c for c in CORES if c in palavras), "vermelho")
        return "carrinho", {"cor": cor}
    forma = next((FORMAS[p] for p in FORMAS
                  if p in palavras or p + "s" in palavras), None)
    if forma and _fala_de_blender(t):
        if any(p in t for p in ("pul", "quic")):
            anim = "pular"
        elif any(p in t for p in ("anim", "gir", "rod", "mexe", "movimento")):
            anim = "tudo" if ("pul" in t) else "girar"
        else:
            anim = "nenhuma"
        cor = next((c for c in CORES if c in palavras), "")
        return "objeto", {"forma": forma, "cor": cor, "animacao": anim}
    if "salv" in t and not any(p in t for p in ("png", "imagem", "foto", "print")):
        nome = re.search(r"(?:como|chamado|nome)\s+([\w-]+)", pergunta or "")
        return "salvar", {"nome": nome.group(1) if nome else ""}
    if any(p in t for p in ("png", "print", "foto da cena", "imagem da cena",
                            "salve a imagem", "salvar imagem", "exporte", "exportar imagem",
                            "render")):
        return "imagem", {}
    if any(p in t for p in ("conectad", "conexao", "acessar", "acessa", "consegue",
                            "esta aberto", "ta aberto", "funcionando", "ligado",
                            "cena", "o que tem", "quais objetos", "objetos")):
        return "status", {}
    # Pedido de CRIAR algo que nao tem ferramenta pronta: o cerebro pede
    # ao modelo SO a lista de pecas (sem ferramentas, sem laco) e monta.
    if _fala_de_blender(t) and any(v in palavras for v in VERBOS_CRIAR):
        if quer_simples(t):
            return "livre", {"pedido": pergunta.strip()[:400]}
        return "detalhado", {"pedido": pergunta.strip()[:400]}
    return None


RE_CAMINHO = r"[A-Za-z]:\\[^\n\"<>|]+?\.(?:%s)\b"


def _caminhos(texto, exts):
    return re.findall(RE_CAMINHO % "|".join(exts), texto or "", flags=re.I)


def _pedido_recursos(pergunta, t, palavras, no_blender):
    """Biblioteca, importar, referencias, textura, ficha JSON."""
    if not no_blender:
        return None
    # ficha tecnica em JSON colada na mensagem
    if '"pecas"' in (pergunta or "") or "'pecas'" in (pergunta or ""):
        return "ficha", {"texto": pergunta}
    if re.search(r"(instal\w*|baix\w*).{0,40}(gerador de human|mpfb|makehuman)", t):
        return "instalar_humano", {}
    # ficha JSON de PESSOA (avatar, rosto, cabelo...) -> MPFB
    if "{" in (pergunta or "") and extrair_json(pergunta) is not None:
        if re.search(r"gender|avatar|facial|face|jaw|nose|lip|skin|hair|demograph|ethnic|"
                     r"shape_keys|basemesh|sexo|rosto|cabelo|pele", t):
            return "humano", {"ficha": pergunta}
        return "livre", {"pedido": pergunta.strip()[:3000]}
    # ESCANEAMENTO (iPhone com LiDAR / RoomPlan / Polycam / Scaniverse)   (29/09)
    #   .usdz e .zip so chegam por aqui; glb/obj/ply viram escaneamento quando
    #   a frase fala em escanear -- ai o Bigode NAO estica e ainda mede.
    escaneados = _caminhos(pergunta, ["usdz", "usdc", "usda", "usd", "zip"])
    fala_de_scan = re.search(r"escane|scan|lidar|roomplan|polycam|scaniverse|comodo|ambiente|planta baixa", t)
    if escaneados or (fala_de_scan and _caminhos(pergunta, ["glb", "gltf", "obj", "fbx", "stl", "ply"])):
        alvo = (escaneados or _caminhos(pergunta, ["glb", "gltf", "obj", "fbx", "stl", "ply"]))[0]
        return "escaneamento", {"caminho": alvo}
    arquivos_3d = _caminhos(pergunta, ["glb", "gltf", "obj", "fbx", "stl", "ply", "svg"])
    if arquivos_3d:
        alt = re.search(r"(\d+(?:[.,]\d+)?)\s*(m|metro|metros|cm)\b", t)
        altura = 0
        if alt:
            altura = float(alt.group(1).replace(",", ".")) / (100 if alt.group(2) == "cm" else 1)
        return "importar", {"caminho": arquivos_3d[0], "altura": altura}
    imagens = _caminhos(pergunta, ["png", "jpg", "jpeg", "webp"])
    if imagens and any(w in t for w in ("frente", "lado", "topo", "ortograf")) and not (
            any(w in _sem_acento(t) for w in FIEL) or "modelo 3d" in t or "modelo" in t):
        refs = {}
        for chave in ("frente", "lado", "topo"):
            m = re.search(chave + r"\W{0,3}\s*(" + RE_CAMINHO % "png|jpg|jpeg|webp" + ")", pergunta, re.I)
            if m:
                refs[chave] = m.group(1)
        if not refs:
            refs = dict(zip(("frente", "lado", "topo"), imagens))
        alt = re.search(r"altura\s*(\d+(?:[.,]\d+)?)\s*(m|cm)?", t)
        if alt:
            refs["altura"] = float(alt.group(1).replace(",", ".")) / (100 if alt.group(2) == "cm" else 1)
        return "referencias", refs
    if imagens and (any(w in _sem_acento(t) for w in FIEL) or len(imagens) > 1) and not any(
            w in t for w in ("frente:", "lado:", "topo:", "rotulo", "textura", "estampa")):
        return "gerar_3d", {"caminho": imagens[0], "extras": imagens[1:4],
                            "qualidade": "maxima" if re.search(r"maxim|alta qualidade|melhor qualidade", t) else "normal"}
    if imagens and any(w in t for w in ("rotulo", "textura", "estampa", "adesivo", "aplique", "aplica")):
        alvo = re.search(r"\b(?:no|na|em)\s+(?:objeto\s+)?['\"]?([\w.]+)['\"]?\s*$", pergunta.strip(), re.I)
        nome_alvo = alvo.group(1) if alvo else ""
        if nome_alvo.lower() in ("objeto", "blender", "cena", "ela", "ele"):
            nome_alvo = ""
        return "textura", {"caminho": imagens[0], "objeto": nome_alvo}
    # biblioteca Poly Haven
    objeto_alvo = ""
    m_obj = re.search(r"\bno objeto\s+([\w.]+)", pergunta or "", re.I)
    if m_obj:
        objeto_alvo = m_obj.group(1)
    t = re.sub(r"\bno objeto\s+[\w.]+", " ", t)
    busca = re.sub(r"\bda biblioteca\b", " ", t)
    busca = re.sub(r"\b(no|na|de|um|uma|o|a|blender|coloque|coloca|poe|bota|use|usa|aplique|aplica|"
                   r"busque|busca|procure|traga|adicione|quero|me|da biblioteca|biblioteca|"
                   r"poly ?haven|modelo|pronto|real|hdri|ceu|luz|iluminacao|textura|material|cena|3d)\b",
                   " ", busca)
    busca = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", busca)).strip()
    if any(w in t for w in ("hdri", "ceu de", "ceu com", "iluminacao de", "luz de ambiente")):
        return "biblioteca", {"busca": busca or "studio", "tipo": "hdri"}
    if "textura de" in t or "material de" in t:
        return "biblioteca", {"busca": busca, "tipo": "textura", "objeto": objeto_alvo}
    if any(w in t for w in ("poly haven", "polyhaven", "biblioteca", "modelo pronto", "modelo real")):
        return "biblioteca", {"busca": busca, "tipo": "modelo"}
    return None


VERBOS_CRIAR = ("crie", "cria", "criar", "faca", "faz", "fazer", "monte", "monta", "montar",
                "modele", "modela", "modelar", "quero", "gere", "gera", "gerar", "construa",
                "construir", "desenhe", "coloque", "adicione", "bote")


def resposta_status():
    """Texto pronto para o Fred: esta conectado? o que tem na cena?"""
    if not no_ar():
        host, porta = _endereco()
        return "Nao estou conectado ao Blender agora.\n\n" + (_MSG_DESLIGADO % (host, porta))
    r = executar_codigo(_CODIGO_CENA, timeout=30)
    if r.get("status") != "ok":
        return "O Blender respondeu, mas deu erro ao ler a cena:\n" + _texto(r)
    d = r.get("result", {})
    linhas = ["Sim, estou conectado ao Blender (porta %d)." % _endereco()[1], "",
              "Arquivo: %s" % d.get("arquivo"),
              "Objetos na cena: %s" % d.get("total_objetos")]

    def andar(col, nivel=0):
        objs = col.get("objetos", [])
        if objs or nivel:
            nomes = ", ".join(o["nome"] for o in objs[:12])
            extra = " (+%d)" % (len(objs) - 12) if len(objs) > 12 else ""
            linhas.append("- %s: %s%s" % (col.get("nome"), nomes or "vazia", extra))
        for f in col.get("filhas", []):
            andar(f, nivel + 1)
    andar(d.get("colecoes", {}))
    linhas += ["", "Posso: ler a cena, montar o carrinho (ex.: \"crie um carrinho azul no blender\"), criar formas animadas (ex.: \"cria um macaco animado no blender\"), criar um mascote macaco de corpo inteiro com texto na camisa, "
               "salvar um PNG da camera, ou rodar codigo Python no Blender."]
    return "\n".join(linhas)


def executar_direto(acao, argumentos):
    """Roda o atalho. Devolve (texto, deu_certo)."""
    if acao == "status":
        texto = resposta_status()
        return texto, texto.startswith("Sim")
    if not no_ar():
        host, porta = _endereco()
        return _MSG_DESLIGADO % (host, porta), False
    if acao == "carrinho":
        texto = blender_carrinho(**argumentos)
        return texto, texto.startswith("Carrinho montado")
    if acao == "gerar_3d":
        try:
            ULTIMO_3D.write_text(json.dumps({k: v for k, v in argumentos.items() if k != "variacao"}),
                                 encoding="utf-8")
        except Exception:
            pass
    if acao == "escaneamento":
        import blender_recursos as r
        texto = r.blender_escaneamento(**argumentos)
        return texto, texto.startswith("Importei o escaneamento")
    if acao in ("biblioteca", "importar", "referencias", "textura", "gerar_3d"):
        import blender_recursos as r
        funcao = {"biblioteca": r.blender_biblioteca, "importar": r.blender_importar,
                  "referencias": r.blender_referencias, "textura": r.blender_textura,
                  "gerar_3d": r.blender_gerar_3d}[acao]
        texto = funcao(**argumentos)
        ok = texto.split(" ", 1)[0] in ("Importei", "Ceu/luz", "Textura", "Referencias")
        return texto, ok
    if acao in ("humano", "instalar_humano"):
        import blender_humano as hum
        texto = hum.blender_humano(**argumentos) if acao == "humano" else hum.instalar()
        return texto, texto.startswith(("Pessoa criada", "Pronto", "O gerador de humanos (MPFB) ja"))
    if acao == "ficha":
        return montar_de_texto(argumentos.get("texto", ""), "Ficha")
    if acao == "salvar":
        texto = blender_salvar(**argumentos)
        return texto, texto.startswith("Projeto salvo")
    if acao == "detalhado":
        return criar_detalhado(**argumentos)
    if acao == "da_imagem":
        texto = da_imagem(**argumentos)
        return texto, texto.startswith(("Projeto", "Importei"))
    if acao == "referencia":
        texto = blender_referencia(**argumentos)
        return texto, texto.startswith("Projeto")
    if acao == "olhar":
        texto = blender_olhar(**argumentos)
        return texto, texto.startswith("O que vejo")
    if acao == "mascote":
        texto = blender_mascote(**argumentos)
        return texto, texto.startswith("Mascote criado")
    if acao == "objeto":
        texto = blender_objeto(**argumentos)
        return texto, texto.startswith("Criei")
    if acao == "imagem":
        texto = blender_imagem(**argumentos)
        return texto, texto.startswith("Imagem salva")
    return "Acao desconhecida: %s" % acao, False


if __name__ == "__main__":
    # Teste rapido: python blender.py
    print("Blender no ar?", no_ar())
    if no_ar():
        print(blender_cena())
