# -*- coding: utf-8 -*-
"""
VARIEDADE E MARCA DO PROJETO SOUL                       (24/11/2026)
Venure · venure.com.br

O PROBLEMA QUE ISTO RESOLVE
    A tela tinha 8 temas fixos, escritos à mão em dois lugares (HTML e
    Python). Resultado medido em memoria/soul: de 9 artigos, 3 eram sobre
    sono e 2 sobre proibicionismo, e os títulos repetiam as mesmas
    palavras ("canabinoides", "sono", "evidências").

O QUE ESTE MÓDULO FAZ
    1. historico()        lê tudo o que já foi produzido (pastas em
                          memoria/soul + _historico.json).
    2. sugestoes()        devolve temas NOVOS: de um banco de 30 temas em
                          6 pilares, ou pedindo à IA, sempre descartando o
                          que se parece com algo já publicado.
    3. regra_de_titulo()  instrução para o redator não repetir as palavras
                          mais usadas nos títulos anteriores.
    4. titulo_repetido()  confere o título que saiu.
    5. prompt_capa()      monta um prompt de imagem preciso, com a
                          identidade visual do Soul e espaço para a marca.
    6. carimbar_marca()   escreve a marca PROJETO SOUL na capa com código
                          (modelo de imagem não escreve texto direito).
                          Se existir web/img/soul-logo.png, usa a logo real.
"""
from __future__ import annotations

import datetime
import json
import random
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
PASTA_SOUL = BASE / "memoria" / "soul"
HISTORICO = PASTA_SOUL / "_historico.json"
LOGO = BASE / "web" / "img" / "soul-logo.png"

# Identidade visual do site projetosoul.com.br (paleta escura + verde).
COR_FUNDO = (8, 8, 8)          # #080808
COR_VERDE = (61, 186, 111)     # #3DBA6F

PARECIDO_DEMAIS = 0.34         # fração de palavras-chave em comum

PALAVRAS_VAZIAS = set("""
a o os as um uma uns umas de do da dos das em no na nos nas por pelo pela
para com sem sobre entre e ou que como se ao aos à às seu sua seus suas
mais menos muito ja já nao não ser sao são é foi pode podem o-que qual
quais quando onde porque também tambem the of and in on for to
""".split())

# Palavras do nicho que aparecem em quase todo título: não contam como
# "repetição" sozinhas, senão nenhum título passaria.
PALAVRAS_DO_NICHO = {"cannabis", "cannabi", "canabis", "canabi", "medicinal", "soul", "projeto"}

# Banco de temas: 6 pilares x 5 temas, cada um com uma cena de capa.
BANCO = [
    # Medicina & Farmacologia
    ("Medicina & Farmacologia", "CBD e epilepsias refratárias: o que os ensaios com Dravet e Lennox-Gastaut mostraram",
     "neurologist reviewing an EEG brainwave printout on a clean desk, soft clinical light"),
    ("Medicina & Farmacologia", "Interações medicamentosas do canabidiol: enzimas do fígado e cuidados com outros remédios",
     "pharmacist hands arranging labeled pill organizers beside an amber dropper bottle"),
    ("Medicina & Farmacologia", "THC e náusea da quimioterapia: história de uso clínico e limites da evidência",
     "calm oncology day-room with an empty infusion chair and warm window light"),
    ("Medicina & Farmacologia", "Dor neuropática e canabinoides: onde a evidência é forte e onde ainda é fraca",
     "anatomical illustration of peripheral nerves glowing softly on dark background"),
    ("Medicina & Farmacologia", "Efeito comitiva: terpenos e canabinoides juntos, mito ou mecanismo",
     "glass laboratory vials with amber essential oils catching side light"),
    # Saúde mental & Comportamento
    ("Saúde Mental", "Ansiedade e canabidiol: o que os estudos com falar em público revelaram",
     "empty auditorium stage with a single microphone under a soft spotlight"),
    ("Saúde Mental", "Cannabis e adolescência: riscos para o cérebro em desenvolvimento",
     "abstract neural network of a developing brain, delicate glowing connections"),
    ("Saúde Mental", "Transtorno do espectro autista e CBD: expectativas das famílias e dados disponíveis",
     "parent and child hands building colorful wooden blocks on a table, gentle daylight"),
    ("Saúde Mental", "Dependência de cannabis: sinais, frequência e caminhos de tratamento",
     "quiet support group circle of empty chairs in a sunlit room"),
    ("Saúde Mental", "Estresse pós-traumático e sistema endocanabinoide: a memória do medo",
     "silhouette of a person by a rain-streaked window, calm muted tones"),
    # Cultivo & Botânica
    ("Cultivo & Botânica", "Genética e quimiotipos: por que duas plantas parecidas têm perfis químicos diferentes",
     "macro of plant DNA sample tubes in a rack with green-lit laboratory background"),
    ("Cultivo & Botânica", "Pragas e manejo integrado no cultivo medicinal sem agrotóxicos",
     "macro of a ladybug on a healthy green leaf, shallow depth of field"),
    ("Cultivo & Botânica", "Secagem e cura: como o pós-colheita muda canabinoides e terpenos",
     "wooden drying racks in a dim, clean curing room with a hygrometer"),
    ("Cultivo & Botânica", "Extração de óleo: solventes, temperatura e controle de qualidade",
     "stainless steel rotary evaporator in a modern extraction lab"),
    ("Cultivo & Botânica", "Cânhamo industrial: fibras, alimentos e construção civil",
     "stacked hempcrete blocks and natural fiber rope on a construction site table"),
    # História & Sociedade
    ("História & Sociedade", "Associações de pacientes no Brasil: como famílias abriram caminho para o acesso",
     "community meeting room with handwritten posters and folding chairs, warm light"),
    ("História & Sociedade", "Cannabis na medicina do século XIX: tinturas, farmácias e o esquecimento",
     "antique apothecary shelf with old glass tincture bottles and handwritten labels"),
    ("História & Sociedade", "Estigma e acesso: quem consegue tratamento com cannabis no Brasil hoje",
     "long hospital corridor with a single person waiting, documentary photography"),
    ("História & Sociedade", "Uruguai, Canadá e Alemanha: três modelos de regulação comparados",
     "three vintage passports on a map table with soft overhead light"),
    ("História & Sociedade", "Cannabis e povos tradicionais: usos documentados e cuidado com mitos",
     "ethnobotanical field notebook with pressed plants and pencil sketches"),
    # Direito & Regulação
    ("Direito & Regulação", "Importação de produto de cannabis por pessoa física: passo a passo da RDC 660",
     "customs desk with an unbranded parcel, stamped documents and reading glasses"),
    ("Direito & Regulação", "Farmácia magistral e cannabis: o que pode e o que não pode",
     "compounding pharmacy bench with precision scale and glass beakers"),
    ("Direito & Regulação", "Plano de saúde e SUS: decisões judiciais sobre custeio de canabidiol",
     "courthouse steps at dawn with long soft shadows"),
    ("Direito & Regulação", "Rotulagem e concentração: como ler o laudo de um produto de cannabis",
     "close-up of a laboratory certificate of analysis under a magnifier"),
    ("Direito & Regulação", "Dirigir após uso medicinal: o que a lei e a ciência dizem",
     "car dashboard at night with blurred city lights, calm and serious mood"),
    # Prática clínica & Paciente
    ("Prática Clínica", "Como é uma primeira consulta para tratamento com cannabis",
     "doctor and patient seated across a desk in a bright consulting room, faces not visible"),
    ("Prática Clínica", "Idosos e canabinoides: quedas, sonolência e ajuste cuidadoso",
     "elderly hands holding a cup of tea near a sunny window"),
    ("Prática Clínica", "Fibromialgia: relatos de pacientes e o que os estudos conseguem medir",
     "person stretching gently on a yoga mat in soft morning light"),
    ("Prática Clínica", "Efeitos adversos mais comuns e quando procurar o médico",
     "clipboard checklist and stethoscope on a clean white surface"),
    ("Prática Clínica", "Cuidados paliativos e cannabis: qualidade de vida no fim da vida",
     "hand holding another hand on a hospital blanket, warm compassionate light"),
]

CENA_POR_PILAR = {
    "Medicina & Farmacologia": "scientific 3D molecular visualization, clinical precision",
    "Saúde Mental": "calm human-centered editorial photography, quiet emotional tone",
    "Cultivo & Botânica": "agronomic research photography, botanical detail",
    "História & Sociedade": "documentary archival photography, human stories",
    "Direito & Regulação": "institutional editorial still life, serious and restrained",
    "Prática Clínica": "warm clinical editorial photography, patient dignity",
}


# --------------------------------------------------------------------- texto
def _normal(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def palavras(texto: str) -> set[str]:
    """Palavras-chave de um título/tema (sem acento, sem palavra vazia)."""
    ws = re.findall(r"[a-z0-9]{3,}", _normal(texto))
    return {w.rstrip("s") for w in ws if w not in PALAVRAS_VAZIAS}


def parecido(a: str, b: str) -> float:
    pa, pb = palavras(a) - PALAVRAS_DO_NICHO, palavras(b) - PALAVRAS_DO_NICHO
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / min(len(pa), len(pb))


# ----------------------------------------------------------------- histórico
def historico() -> list[dict]:
    """Tudo o que já foi produzido: título, tema e data."""
    itens: list[dict] = []
    try:
        itens = json.loads(HISTORICO.read_text(encoding="utf-8"))
    except Exception:
        itens = []
    vistos = {i.get("slug") for i in itens}
    if PASTA_SOUL.is_dir():
        for pasta in PASTA_SOUL.iterdir():
            if not pasta.is_dir() or pasta.name in vistos:
                continue
            # O nome da pasta e o slug do titulo ("canabinoides-e-sono").
            # (O artigo.md comeca em "# Introducao", nao no titulo.)
            titulo = pasta.name.replace("-", " ")
            itens.append({"slug": pasta.name, "titulo": titulo, "tema": "",
                          "data": datetime.datetime.fromtimestamp(
                              pasta.stat().st_mtime).strftime("%Y-%m-%d")})
    return itens


def registrar(artigo: dict) -> None:
    """Guarda o artigo gerado para os próximos não repetirem."""
    try:
        itens = json.loads(HISTORICO.read_text(encoding="utf-8"))
    except Exception:
        itens = []
    itens.append({"slug": artigo.get("slug", ""), "titulo": artigo.get("titulo", ""),
                  "tema": artigo.get("tema", ""),
                  "data": datetime.date.today().isoformat()})
    PASTA_SOUL.mkdir(parents=True, exist_ok=True)
    HISTORICO.write_text(json.dumps(itens[-300:], ensure_ascii=False, indent=1),
                         encoding="utf-8")


def _ja_feito(texto: str, hist: list[dict]) -> bool:
    return any(parecido(texto, h.get("titulo", "")) >= PARECIDO_DEMAIS
               or parecido(texto, h.get("tema", "")) >= PARECIDO_DEMAIS
               for h in hist)


# ----------------------------------------------------------------- sugestões
def _do_banco(n: int, hist: list[dict]) -> list[dict]:
    livres = [b for b in BANCO if not _ja_feito(b[1], hist)]
    random.shuffle(livres)
    # um tema por pilar primeiro, para variar de verdade
    escolhidos, pilares = [], set()
    for b in livres:
        if b[0] not in pilares:
            escolhidos.append(b); pilares.add(b[0])
    for b in livres:
        if len(escolhidos) >= n:
            break
        if b not in escolhidos:
            escolhidos.append(b)
    return [{"pilar": p, "tema": t, "prompt_capa": prompt_capa(t, p, c)}
            for p, t, c in escolhidos[:n]]


def _da_ia(n: int, hist: list[dict], llm) -> list[dict]:
    usados = "\n".join("- " + (h.get("titulo") or h.get("tema")) for h in hist[-40:])
    pilares = ", ".join(CENA_POR_PILAR)
    pedido = (
        "Você é editor do Projeto Soul, hub de educação sobre cannabis medicinal no Brasil. "
        "Proponha %d temas de artigo NOVOS, um de cada pilar quando possível (%s). "
        "Regras: cada tema com até 110 caracteres, específico (um público, uma pergunta, um dado), "
        "sem repetir palavras-chave entre si nem com a lista de já publicados; "
        "nada de promessa de cura ou recomendação de dose.\n\n"
        "JÁ PUBLICADOS (não repita assunto nem palavras principais):\n%s\n\n"
        "Responda SOMENTE JSON: [{\"pilar\": \"...\", \"tema\": \"...\", "
        "\"cena\": \"descrição em inglês de uma cena fotográfica para a capa, sem texto\"}]"
        % (n + 3, pilares, usados or "- (nenhum)"))
    bruto = llm([{"role": "user", "content": pedido}])
    m = re.search(r"\[.*\]", bruto or "", re.S)
    lista = json.loads(m.group(0)) if m else []
    saida: list[dict] = []
    for item in lista:
        tema = str(item.get("tema") or "").strip()
        pilar = str(item.get("pilar") or "Projeto Soul").strip()
        if len(tema) < 15 or _ja_feito(tema, hist):
            continue
        if any(parecido(tema, s["tema"]) >= PARECIDO_DEMAIS for s in saida):
            continue
        saida.append({"pilar": pilar, "tema": tema[:200],
                      "prompt_capa": prompt_capa(tema, pilar, str(item.get("cena") or ""))})
        if len(saida) >= n:
            break
    return saida


def sugestoes(usar_ia: bool = False, llm=None, n: int = 6) -> dict:
    hist = historico()
    lista: list[dict] = []
    origem = "banco"
    if usar_ia and llm:
        try:
            lista = _da_ia(n, hist, llm)
            origem = "ia"
        except Exception:
            lista = []
    if len(lista) < n:
        extra = [x for x in _do_banco(n, hist)
                 if not any(parecido(x["tema"], y["tema"]) >= PARECIDO_DEMAIS for y in lista)]
        lista += extra[: n - len(lista)]
    return {"ok": True, "origem": origem, "temas": lista,
            "ja_publicados": len(hist)}


# -------------------------------------------------------------------- título
def palavras_gastas(limite: int = 12) -> list[str]:
    """As palavras que mais se repetem nos títulos anteriores."""
    cont: dict[str, int] = {}
    for h in historico():
        for w in palavras(h.get("titulo", "")) - PALAVRAS_DO_NICHO:
            cont[w] = cont.get(w, 0) + 1
    return [w for w, c in sorted(cont.items(), key=lambda x: -x[1]) if c >= 2][:limite]


def regra_de_titulo() -> str:
    gastas = palavras_gastas()
    anteriores = [h.get("titulo", "") for h in historico()][-15:]
    return (
        " REGRAS DO TÍTULO (title): até 70 caracteres; específico e concreto; "
        "proibido começar com 'O papel', 'Descubra', 'Tudo sobre', 'Guia completo'; "
        "proibido ponto de exclamação e promessa de cura. "
        + ("Evite estas palavras, já gastas em títulos anteriores: %s. " % ", ".join(gastas)
           if gastas else "")
        + ("Não se pareça com estes títulos já publicados: %s." % " | ".join(anteriores)
           if anteriores else ""))


def titulo_repetido(titulo: str) -> str:
    """Devolve o título anterior parecido demais, ou '' se estiver ok."""
    for h in historico():
        if parecido(titulo, h.get("titulo", "")) >= 0.5:
            return h.get("titulo", "")
    return ""


# --------------------------------------------------------------------- capa
def prompt_capa(tema: str, pilar: str = "", cena: str = "") -> str:
    """Prompt de capa preciso, com a identidade visual do Projeto Soul."""
    estilo = CENA_POR_PILAR.get(pilar, "editorial science photography")
    cena = cena.strip() or ("a single clear subject that represents: " + tema)
    return (
        "Editorial cover image for Projeto Soul, a Brazilian medical cannabis education hub. "
        "Subject: %s. Style: %s. "
        "Visual identity: deep near-black background (#080808), one restrained accent of vivid "
        "leaf green (#3DBA6F), soft directional light, high contrast, premium health magazine. "
        "Composition: subject on the right two-thirds, calm empty dark area in the lower-left "
        "corner (reserved for the logo). Landscape 16:9, photorealistic, sharp focus. "
        "No text, no letters, no numbers, no logos, no watermark, no cannabis leaf icon, "
        "no smoking, no pills spilling, no medical claims." % (cena, estilo))


def prompt_de_qualquer(prompt: str) -> str:
    """Prompts antigos (só o título) ganham a identidade visual também."""
    if "Projeto Soul" in (prompt or ""):
        return prompt
    texto = re.sub(r"^(Imagem editorial educativa[^:]*:|Sophisticated[^:]*for:)\s*",
                   "", prompt or "", flags=re.I).strip()
    return prompt_capa(texto or "medical cannabis education")


def carimbar_marca(caminho: str) -> str:
    """Escreve a marca do Projeto Soul no canto inferior esquerdo da capa.
    Devolve o caminho da imagem nova (o original fica intacto)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return caminho
    try:
        orig = Path(caminho)
        im = Image.open(orig).convert("RGBA")
        w, h = im.size
        # sombra suave no canto, sumindo para cima e para a direita
        from PIL import ImageChops
        alto, largo = int(h * 0.30), int(w * 0.55)
        vert = Image.linear_gradient("L").resize((largo, alto))          # 0 em cima, 255 embaixo
        horiz = Image.linear_gradient("L").rotate(-90, expand=True).resize((largo, alto))  # 255 esq, 0 dir
        mascara = ImageChops.multiply(vert, horiz).point(lambda v: int(v * 0.8))
        escuro = Image.new("RGBA", (largo, alto), COR_FUNDO + (255,))
        escuro.putalpha(mascara)
        im.alpha_composite(escuro, (0, h - alto))
        d = ImageDraw.Draw(im)
        m = int(h * 0.05)
        if LOGO.is_file():
            logo = Image.open(LOGO).convert("RGBA")
            lh = int(h * 0.09)
            logo = logo.resize((int(logo.width * lh / logo.height), lh))
            im.alpha_composite(logo, (m, h - m - lh))
        else:
            fontes = [Path("C:/Windows/Fonts/arialbd.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf"),
                      Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
            fp = next((p for p in fontes if p.exists()), None)
            tam = max(18, int(h * 0.045))
            f1 = ImageFont.truetype(str(fp), tam) if fp else ImageFont.load_default()
            f2 = ImageFont.truetype(str(fp), int(tam * 0.5)) if fp else ImageFont.load_default()
            y = h - m - int(tam * 1.7)
            r = int(tam * 0.28)
            d.ellipse((m, y + tam // 2 - r, m + 2 * r, y + tam // 2 + r), fill=COR_VERDE + (255,))
            d.text((m + 3 * r, y), "PROJETO SOUL", font=f1, fill=(248, 250, 252, 255))
            d.text((m + 3 * r, y + int(tam * 1.15)), "projetosoul.com.br", font=f2,
                   fill=COR_VERDE + (255,))
        novo = orig.with_name(orig.stem + "_soul.png")
        im.convert("RGB").save(novo, "PNG", optimize=True)
        return str(novo)
    except Exception:
        return caminho
