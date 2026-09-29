#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BLENDER HUMANO - pessoa realista a partir de uma ficha JSON         (28/09)

Usa o MPFB 2 (MakeHuman para Blender, gratuito, GPL) e o pacote
makehuman_system_assets (CC0): corpo e rosto parametricos, pele por idade
e etnia, olhos, sobrancelhas, cabelo e roupa.

    instalar()          baixa e instala o MPFB e o pacote de assets (1 vez)
    blender_humano(f)   ficha JSON -> pessoa no Blender

A ficha pode vir em qualquer formato razoavel: o mapeador procura por
palavras nas chaves (gender, age, african, jaw, nose, lip, cheek, hair...)
e converte valores de 0 a 1, onde 0.5 e neutro.

Venure - venure.com.br
"""

import json
import re
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
# Fora do Google Drive de proposito: sao ~310 MB que o Drive tentaria subir.
import tempfile
INSTALADORES = Path(tempfile.gettempdir()) / "bigode_blender_instaladores"

URL_LISTA_EXTENSOES = "https://extensions.blender.org/api/v1/extensions/"
URLS_ASSETS = (
    "https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip",
    "https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip",
)
AGENTE = "BigodeIA/1.0 (venure.com.br)"


def _b():
    import blender
    return blender


def _baixar(url, destino, timeout=600):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temp = destino.with_suffix(destino.suffix + ".parcial")
    # curl (vem no Windows 10+) e muito mais rapido e aguenta 267 MB sem
    # travar; o urllib fica de reserva.
    import shutil, subprocess
    curl = shutil.which("curl")
    if curl:
        r = subprocess.run([curl, "-L", "-s", "-f", "--max-time", str(timeout), "-A", AGENTE,
                            "-o", str(temp), url], capture_output=True)
        if r.returncode == 0 and temp.exists() and temp.stat().st_size > 0:
            temp.replace(destino)
            return destino
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(temp, "wb") as f:
        while True:
            bloco = r.read(1 << 20)
            if not bloco:
                break
            f.write(bloco)
    temp.replace(destino)
    return destino


_IMPORTAR_MPFB = r'''
import importlib, sys
def _mpfb(pacote, nome):
    for m in list(sys.modules):
        if m.endswith(pacote):
            return getattr(importlib.import_module(m), nome)
    raise ImportError("MPFB nao carregado")
'''


def estado():
    """{'mpfb': bool, 'assets': bool}"""
    b = _b()
    r = b.executar_codigo(_IMPORTAR_MPFB + r'''
try:
    AssetService = _mpfb("mpfb.services.assetservice", "AssetService")
    result = {"mpfb": True, "assets": bool(AssetService.system_assets_pack_is_installed())}
except Exception as e:
    result = {"mpfb": False, "assets": False, "erro": str(e)}
''', timeout=60)
    return r.get("result") or {"mpfb": False, "assets": False}


def instalar(**_):
    """Instala o MPFB (45 MB) e o pacote de assets CC0 (267 MB)."""
    b = _b()
    passos = []
    st = estado()
    if not st.get("mpfb"):
        lista = json.loads(urllib.request.urlopen(urllib.request.Request(
            URL_LISTA_EXTENSOES, headers={"User-Agent": AGENTE}), timeout=60).read().decode("utf-8"))
        item = next((e for e in lista.get("data", []) if e.get("id") == "mpfb"), None)
        if not item:
            return "Nao achei o MPFB em extensions.blender.org."
        zip_mpfb = _baixar(item["archive_url"], INSTALADORES / ("mpfb-%s.zip" % item["version"]))
        r = b.executar_codigo(
            "import bpy\n"
            "bpy.ops.extensions.package_install_files(filepath=%r, repo='user_default', "
            "enable_on_install=True)\nresult={'ok': True}" % str(zip_mpfb), timeout=300)
        if r.get("status") != "ok":
            return "Falhou ao instalar o MPFB no Blender:\n" + b._texto(r)
        passos.append("MPFB %s instalado" % item["version"])
        st = estado()
        if not st.get("mpfb"):
            return ("O MPFB foi instalado, mas ainda nao carregou. Feche e abra o Blender "
                    "e peca de novo: 'instale o gerador de humanos no blender'.")
    if not st.get("assets"):
        zip_assets = INSTALADORES / "makehuman_system_assets_cc0.zip"
        if not zip_assets.exists():
            erro = None
            for url in URLS_ASSETS:
                try:
                    _baixar(url, zip_assets, timeout=1800)
                    erro = None
                    break
                except Exception as e:
                    erro = e
            if erro:
                return "Nao consegui baixar os assets do MakeHuman: %s" % erro
        r = b.executar_codigo(_IMPORTAR_MPFB + r'''
import zipfile
LocationService = _mpfb("mpfb.services.locationservice", "LocationService")
AssetService = _mpfb("mpfb.services.assetservice", "AssetService")
destino = LocationService.get_user_data()
with zipfile.ZipFile(%r) as z:
    z.extractall(destino)
AssetService.update_all_asset_lists()
try:
    AssetService.rescan_pack_metadata()
except Exception:
    pass
result = {"ok": True, "destino": destino}
''' % str(zip_assets), timeout=600)
        if r.get("status") != "ok":
            return "Falhou ao instalar os assets:\n" + b._texto(r)
        passos.append("assets do MakeHuman (CC0) instalados")
    if not passos:
        return "O gerador de humanos (MPFB) ja estava instalado e pronto."
    return "Pronto: " + "; ".join(passos) + "."


# ==========================================================================
# FICHA -> PARAMETROS
# ==========================================================================

def _achatar(d, prefixo=""):
    saida = {}
    if isinstance(d, dict):
        for k, v in d.items():
            saida.update(_achatar(v, (prefixo + "." if prefixo else "") + str(k).lower()))
    elif isinstance(d, list):
        saida[prefixo] = " ".join(str(x) for x in d).lower()
    else:
        saida[prefixo] = d if isinstance(d, (int, float)) and not isinstance(d, bool) else str(d).lower()
    return saida


def _alvo(nome, v, pares):
    """0.5 = neutro. >0.5 usa -incr, <0.5 usa -decr, peso ate 1."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return
    if v > 1.0:            # alguem mandou em escala 0-100
        v = v / 100.0
    peso = round(abs(v - 0.5) * 2, 3)
    if peso < 0.04:
        return
    lado = pares[0] if v > 0.5 else pares[1]
    for n in (nome if isinstance(nome, (list, tuple)) else [nome]):
        yield n.replace("{}", lado), peso


# (palavras que TODAS precisam estar na chave, alvo(s), (sufixo_mais, sufixo_menos))
REGRAS = [
    (("jaw", "width"), "chin/chin-width-{}.target.gz", ("incr", "decr")),
    (("jaw", "defin"), "chin/chin-bones-{}.target.gz", ("incr", "decr")),
    (("chin", "prom"), "chin/chin-prominent-{}.target.gz", ("incr", "decr")),
    (("chin", "height"), "chin/chin-height-{}.target.gz", ("incr", "decr")),
    (("cheek",), ["cheek/l-cheek-bones-{}.target.gz", "cheek/r-cheek-bones-{}.target.gz"], ("incr", "decr")),
    (("nostril",), "nose/nose-nostrils-width-{}.target.gz", ("incr", "decr")),
    (("nose", "depth"), "nose/nose-scale-depth-{}.target.gz", ("incr", "decr")),
    (("nose", "bridge"), "nose/nose-width1-{}.target.gz", ("incr", "decr")),
    (("nose", "width"), "nose/nose-scale-horiz-{}.target.gz", ("incr", "decr")),
    (("lip", "upper"), "mouth/mouth-upperlip-volume-{}.target.gz", ("incr", "decr")),
    (("lip", "lower"), "mouth/mouth-lowerlip-volume-{}.target.gz", ("incr", "decr")),
    (("eye", "droop"), ["eyes/l-eye-corner1-{}.target.gz", "eyes/r-eye-corner1-{}.target.gz"], ("down", "up")),
    (("eye", "depth"), ["eyes/l-eye-push1-{}.target.gz", "eyes/r-eye-push1-{}.target.gz"], ("in", "out")),
    (("head", "width"), "head/head-scale-horiz-{}.target.gz", ("incr", "decr")),
]


def _idade_macro(anos):
    """MakeHuman: 0 = 1 ano, 0.1875 = 11, 0.5 = 25, 1.0 = 90."""
    anos = max(1.0, min(90.0, float(anos)))
    if anos <= 11:
        return round((anos - 1) / 10 * 0.1875, 3)
    if anos <= 25:
        return round(0.1875 + (anos - 11) / 14 * 0.3125, 3)
    return round(0.5 + (anos - 25) / 65 * 0.5, 3)


CABELOS = [("dread", "afro01"), ("afro", "afro01"), ("braid", "braid01"), ("trança", "braid01"),
           ("ponytail", "ponytail01"), ("bob", "bob01"), ("long", "long01"), ("longo", "long01"),
           ("short", "short02"), ("curto", "short02"), ("bald", ""), ("careca", "")]
OLHOS = ["brownlight", "brown", "bluegreen", "deepblue", "lightblue", "blue", "green", "grey", "ice"]


def ficha_para_parametros(ficha):
    plano = _achatar(ficha)
    texto = " ".join("%s=%s" % (k, v) for k, v in plano.items())
    macro, alvos, notas = {}, [], []

    # sexo
    if re.search(r"\b(female|feminino|mulher|woman)\b", texto):
        macro["gender"] = 0.0
    elif re.search(r"\b(male|masculino|homem|man)\b", texto):
        macro["gender"] = 1.0
    # idade
    anos = next((v for k, v in plano.items() if "age" in k.split(".")[-1] or "idade" in k), None)
    if isinstance(anos, (int, float)) and anos > 1.5:
        macro["age"] = _idade_macro(anos)
    # etnia (MakeHuman: african / asian / caucasian)
    for chave in ("african", "asian", "caucasian"):
        if chave in texto:
            macro.update({"african": 0.0, "asian": 0.0, "caucasian": 0.0})
            macro[chave] = 1.0
            break
    # corpo
    for k, v in plano.items():
        if isinstance(v, (int, float)):
            ult = k.split(".")[-1]
            if ult in ("muscle", "musculo"):
                macro["muscle"] = max(0.0, min(1.0, float(v)))
            elif ult in ("weight", "peso"):
                macro["weight"] = max(0.0, min(1.0, float(v)))

    # rosto: regras por palavra na chave
    for k, v in plano.items():
        if not isinstance(v, (int, float)):
            continue
        for palavras, alvo, pares in REGRAS:
            if all(p in k for p in palavras):
                alvos.extend(_alvo(alvo, v, pares))
                break
    # formato do rosto e expressao por texto
    formato = " ".join(str(v) for k, v in plano.items() if "face_shape" in k or "formato" in k)
    for palavra, alvo in (("oval", "head/head-oval.target.gz"), ("square", "head/head-square.target.gz"),
                          ("round", "head/head-round.target.gz"), ("strong_jaw", "head/head-square.target.gz")):
        if palavra in formato:
            alvos.append((alvo, 0.5))
    if "upturned" in texto or "smile" in texto or "sorriso" in texto:
        alvos.append(("mouth/mouth-angles-up.target.gz", 0.4))

    # pele por idade / etnia / sexo (pacote CC0 tem young/middleage/old)
    idade = anos if isinstance(anos, (int, float)) else 30
    faixa = "young" if idade < 35 else ("middleage" if idade < 60 else "old")
    etnia = next((e for e in ("african", "asian", "caucasian") if macro.get(e) == 1.0), "caucasian")
    sexo = "female" if macro.get("gender") == 0.0 else "male"
    pele = "%s_%s_%s" % (faixa, etnia, sexo)

    # cabelo, olhos, sobrancelha, roupa
    cabelo = "short02"
    ref_cabelo = " ".join(str(v) for k, v in plano.items() if "hair" in k and "facial" not in k)
    for chave, nome in CABELOS:
        if chave in ref_cabelo:
            cabelo = nome
            break
    if "dread" in ref_cabelo:
        notas.append("dreadlocks nao existem no pacote gratuito: usei afro01, o mais proximo")
    olho = "brown"
    ref_olho = " ".join(str(v) for k, v in plano.items() if "eye" in k and "color" in k).replace("_", " ")
    for chave, nome in (("light brown", "brownlight"), ("brown", "brown"), ("castanh", "brown"),
                        ("blue green", "bluegreen"), ("light blue", "lightblue"), ("deep blue", "deepblue"),
                        ("blue", "blue"), ("azul", "blue"), ("green", "green"), ("verde", "green"),
                        ("grey", "grey"), ("gray", "grey"), ("cinza", "grey")):
        if chave in ref_olho:
            olho = nome
            break
    if any("facial_hair" in k or "beard" in k for k in plano):
        notas.append("barba nao existe no pacote gratuito do MakeHuman: ficou sem barba")
    roupa = ""
    if re.search(r"shirt|camisa|clothing|wardrobe|roupa", texto):
        roupa = "female_casualsuit01" if sexo == "female" else "male_casualsuit01"
    if re.search(r"hex|albedo|melanin|wrinkle|pores|salt", texto):
        notas.append("cor exata de pele, rugas finas e cabelo grisalho dependem de textura; "
                     "usei a pele pronta mais proxima (%s)" % pele)
    busto = "bust" in texto or "busto" in texto
    # o mesmo alvo duas vezes (ficha + ajuste) somaria: vale o ultimo
    unicos = {}
    for rel, peso in alvos:
        base = re.sub(r"-(incr|decr|up|down|in|out)\.target\.gz$", "", rel)
        unicos[base] = (rel, peso)
    alvos = list(unicos.values())
    return {"macro": macro, "alvos": alvos, "pele": pele, "cabelo": cabelo, "olho": olho,
            "roupa": roupa, "busto": busto, "notas": notas}


_CODIGO_HUMANO = _IMPORTAR_MPFB + r'''
import bpy, os
from mathutils import Vector
P = %r
HumanService = _mpfb("mpfb.services.humanservice", "HumanService")
TargetService = _mpfb("mpfb.services.targetservice", "TargetService")
LocationService = _mpfb("mpfb.services.locationservice", "LocationService")
AssetService = _mpfb("mpfb.services.assetservice", "AssetService")
HOP = _mpfb("mpfb.entities.objectproperties", "HumanObjectProperties")

# uma pessoa por vez: a ficha nova substitui a anterior
velha = bpy.data.collections.get("Humano")
if velha:
    for o in list(velha.objects): bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(velha)
antes = set(bpy.data.objects)
h = HumanService.create_human()
for chave, valor in P["macro"].items():
    HOP.set_value(chave, valor, entity_reference=h)
TargetService.reapply_macro_details(h)

raiz = LocationService.get_mpfb_data("targets")
aplicados, faltou = 0, []
for rel, peso in P["alvos"]:
    caminho = os.path.join(raiz, *rel.split("/"))
    if os.path.exists(caminho):
        TargetService.load_target(h, caminho, weight=peso)
        aplicados += 1
    else:
        faltou.append(rel)

pele = AssetService.find_asset_absolute_path(P["pele"] + ".mhmat", asset_subdir="skins")
if pele:
    HumanService.set_character_skin(pele, h, skin_type="MAKESKIN")
itens = [("eyes", "low-poly.mhclo", "Eyes"), ("eyebrows", "eyebrow001.mhclo", "Eyebrows"),
         ("eyelashes", "eyelashes01.mhclo", "Eyelashes"), ("teeth", "teeth_base.mhclo", "Teeth"),
         ("tongue", "tongue01.mhclo", "Tongue")]
if P["cabelo"]:
    itens.append(("hair", P["cabelo"] + ".mhclo", "Hair"))
itens[0] = ("eyes", "low-poly.mhclo", "Eyes")
if P["roupa"]:
    itens.append(("clothes", P["roupa"] + ".mhclo", "Clothes"))
colocados = []
for pasta, arq, tipo in itens:
    c = AssetService.find_asset_absolute_path(arq, asset_subdir=pasta)
    if c:
        try:
            HumanService.add_mhclo_asset(c, h, asset_type=tipo)
            colocados.append(tipo)
        except Exception as e:
            faltou.append("%%s: %%s" %% (arq, e))
    else:
        faltou.append(arq)

# ao lado do que ja existe, em colecao propria
novos = [o for o in bpy.data.objects if o not in antes]
COL = bpy.data.collections.new("Humano")
bpy.context.scene.collection.children.link(COL)
for o in novos:
    for c in list(o.users_collection): c.objects.unlink(o)
    COL.objects.link(o)
xs = [(o.matrix_world @ Vector(c)).x for o in bpy.context.scene.objects
      if o.type in ('MESH', 'CURVE', 'FONT') and o.name not in COL.objects and o.name != "Chao"
      for c in o.bound_box]
if xs:
    h.location.x = max(xs) + 1.5

# enquadra (no busto, so a parte de cima)
bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
h.select_set(True); bpy.context.view_layer.objects.active = h
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for s in area.spaces:
            if s.type == 'VIEW_3D':
                s.shading.type = 'MATERIAL'; s.region_3d.view_perspective = 'PERSP'
        reg = next((r for r in area.regions if r.type == 'WINDOW'), None)
        if reg:
            with bpy.context.temp_override(area=area, region=reg):
                bpy.ops.view3d.view_selected()
            import math
            from mathutils import Euler
            for s in area.spaces:
                if s.type == 'VIEW_3D':      # de frente, levemente de lado
                    s.region_3d.view_rotation = Euler((math.radians(85), 0, math.radians(15))).to_quaternion()
            with bpy.context.temp_override(area=area, region=reg):
                bpy.ops.view3d.view_selected()
            if P["busto"]:
                for s in area.spaces:
                    if s.type == 'VIEW_3D':
                        pts = [h.matrix_world @ Vector(c) for c in h.bound_box]
                        topo = max(p.z for p in pts)
                        s.region_3d.view_location = Vector((h.location.x, h.location.y, topo - 0.25))
                        s.region_3d.view_distance = 1.2
result = {"humano": h.name, "alvos": aplicados, "itens": colocados, "faltou": faltou[:8],
          "pele": bool(pele)}
'''


def blender_humano(ficha="", **_):
    """Cria uma pessoa realista (MPFB) a partir de uma ficha JSON."""
    b = _b()
    if isinstance(ficha, str):
        dados = b.extrair_json(ficha)
        if dados is None:
            return "Nao achei um JSON valido na ficha."
    else:
        dados = ficha
    # Ficha nova sem sexo/idade/etnia = AJUSTE da pessoa anterior: funde
    # com a ultima ficha em vez de criar alguem do zero.      (28/09)
    guardada = BASE / "producao_blender" / "ultimo_humano.json"
    texto_novo = json.dumps(dados).lower()
    if guardada.exists() and not re.search(r"\b(gender|sexo|age|apparent_age|idade|african|asian|caucasian|ethnicity\w*|demographics)\b", texto_novo):
        try:
            anterior = json.loads(guardada.read_text(encoding="utf-8"))
            dados = {"anterior": anterior, "ajuste": dados}
        except ValueError:
            pass
    st = estado()
    if not st.get("mpfb") or not st.get("assets"):
        return ("O gerador de humanos (MPFB, gratuito) ainda nao esta instalado no Blender. "
                "Peca: 'instale o gerador de humanos no blender' (baixa ~310 MB uma vez so).")
    p = ficha_para_parametros(dados)
    try:
        guardada.parent.mkdir(parents=True, exist_ok=True)
        guardada.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    r = b.executar_codigo(_CODIGO_HUMANO % (p,), timeout=300)
    if r.get("status") != "ok":
        return b._texto(r)
    res = r.get("result", {})
    linhas = ["Pessoa criada no Blender com o MPFB (MakeHuman): %s ajustes de rosto aplicados, "
              "pele %s, itens: %s." % (res.get("alvos"), p["pele"], ", ".join(res.get("itens", [])) or "nenhum")]
    if p["macro"]:
        linhas.append("Corpo: " + ", ".join("%s=%s" % kv for kv in p["macro"].items()))
    for n in p["notas"]:
        linhas.append("Obs.: " + n)
    if res.get("faltou"):
        linhas.append("Nao encontrado: " + ", ".join(res["faltou"]))
    return "\n".join(linhas)
