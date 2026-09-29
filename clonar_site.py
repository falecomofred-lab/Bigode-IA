"""
CLONAR SITE -- o Bigode transforma um PRINT ou um LINK em HTML + style.css.

Dois caminhos:

  PRINT (imagem)
    1. Guarda o print e separa as cores de verdade dos pixels (sem chute).
    2. A visao do Bigode (modal_olho) descreve a tela de cima para baixo:
       textos, blocos, botoes, campos. Print comprido e fatiado, para as
       letras pequenas continuarem legiveis.
    3. Um modelo de codigo escreve o HTML e o CSS seguindo as regras do Fred
       (semantico, mobile first, sem framework, dizer o que ficou incerto).
       Ordem: Qwen2.5-Coder-32B no Hugging Face -> o proprio motor do Bigode.

  LINK (endereco)
    Baixa o HTML e as folhas de estilo do site, junta tudo num style.css,
    tira os scripts e deixa os links apontando para o site original.
    Sites montados por JavaScript (React etc.) chegam quase vazios: o
    Bigode avisa e sugere mandar um print.

Tudo vai para  <pasta_projetos>\\Clones\\<nome>\\
    index.html, style.css, LEIA-ME.txt (o que ficou incerto), print.png
    versoes\\  (a versao anterior, a cada ajuste)

Uso responsavel: clone sites seus, de clientes que autorizaram, ou para
estudar layout. Nao publique copia de marca/site de terceiros.
"""

import base64
import io
import json
import re
import shutil
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

JOBS = {}
_TRAVA = threading.Lock()


# ==========================================================================
# BASICO
# ==========================================================================

def _config():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def pasta_clones():
    raiz = str(_config().get("pasta_projetos") or "").strip()
    p = Path(raiz) / "Clones" if raiz else BASE / "clones"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        p = BASE / "clones"
        p.mkdir(parents=True, exist_ok=True)
    return p


def nome_seguro(nome):
    nome = re.sub(r"[^\w\- ]", "", str(nome or ""), flags=re.U).strip().replace(" ", "-")
    return (nome or "clone-" + time.strftime("%Y%m%d-%H%M%S"))[:60]


def _pasta_do(nome):
    return pasta_clones() / nome_seguro(nome)


def arquivo(nome, arq):
    """Caminho seguro de um arquivo de um clone (para a tela mostrar)."""
    pasta = _pasta_do(nome).resolve()
    alvo = (pasta / str(arq or "index.html")).resolve()
    if pasta not in alvo.parents or not alvo.is_file():
        return None
    return alvo


def listar():
    itens = []
    for p in sorted(pasta_clones().glob("*/index.html"),
                    key=lambda x: x.stat().st_mtime, reverse=True)[:40]:
        itens.append({"nome": p.parent.name,
                      "quando": time.strftime("%d/%m %H:%M", time.localtime(p.stat().st_mtime)),
                      "pasta": str(p.parent),
                      "tem_print": (p.parent / "print.png").exists()})
    return itens


def _job(etapa="", **extra):
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "estado": "rodando", "etapa": etapa, "etapas": [],
                 "erro": "", "nome": "", "incertezas": [], "motor": "",
                 "aviso": "", "inicio": time.time(), **extra}
    return jid


def _passo(jid, texto):
    j = JOBS.get(jid)
    if j is not None:
        j["etapa"] = texto
        j["etapas"].append(texto)


def status(jid):
    j = JOBS.get(jid)
    if not j:
        return {"ok": False, "erro": "Pedido nao encontrado (o Bigode foi reiniciado?)."}
    return {"ok": True, **j, "segundos": round(time.time() - j["inicio"])}


# ==========================================================================
# MODELOS
# ==========================================================================

def _token_hf():
    return str((_config().get("huggingface") or {}).get("token") or "").strip()


def chat_hf(prompt, max_tokens=7000, modelo=""):
    """Modelo de codigo grande no Hugging Face (router OpenAI). None se falhar."""
    token = _token_hf()
    if not token:
        return None
    modelo = modelo or (_config().get("huggingface") or {}).get("texto_modelo") \
        or "Qwen/Qwen2.5-Coder-32B-Instruct"
    corpo = {"model": modelo, "messages": [{"role": "user", "content": prompt}],
             "max_tokens": max_tokens, "temperature": 0.2}
    try:
        req = urllib.request.Request(
            "https://router.huggingface.co/v1/chat/completions",
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=300) as r:
            dados = json.loads(r.read().decode("utf-8"))
        return dados["choices"][0]["message"]["content"]
    except Exception:
        return None


# Modelos que VEEM o print e escrevem o codigo direto (Hugging Face).
# Testados em 28/09 com o mesmo print: o Qwen3-VL-235B foi de longe o mais fiel.
MODELOS_VISAO = ["Qwen/Qwen3-VL-235B-A22B-Instruct", "google/gemma-3-27b-it"]


def chat_hf_visao(prompt, imagem_png, modelo, max_tokens=8000):
    """Modelo com visao no Hugging Face: ve a imagem e responde. None se falhar."""
    token = _token_hf()
    if not token:
        return None
    b64 = base64.b64encode(imagem_png).decode("ascii")
    corpo = {"model": modelo, "max_tokens": max_tokens, "temperature": 0.2,
             "messages": [{"role": "user", "content": [
                 {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}},
                 {"type": "text", "text": prompt}]}]}
    try:
        req = urllib.request.Request(
            "https://router.huggingface.co/v1/chat/completions",
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=400) as r:
            dados = json.loads(r.read().decode("utf-8"))
        return dados["choices"][0]["message"]["content"]
    except Exception:
        return None


def _png(img, largura_max=1600):
    im = img.copy()
    if im.width > largura_max:
        im = im.resize((largura_max, int(im.height * largura_max / im.width)))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _escrever_codigo(prompt, reserva=None):
    """Tenta os modelos em ordem. Devolve (texto, motor)."""
    texto = chat_hf(prompt)
    if texto and "<" in texto:
        return texto, "Qwen2.5-Coder-32B (Hugging Face)"
    if reserva:
        try:
            texto = reserva(prompt)
            if texto and "<" in texto:
                return texto, "motor do Bigode"
        except Exception:
            pass
    return None, ""


# ==========================================================================
# PRINT -> DESCRICAO
# ==========================================================================

def _abrir_imagem(imagem_b64):
    from PIL import Image
    b64 = (imagem_b64 or "").strip()
    if b64.startswith("data:"):
        b64 = b64.partition(",")[2]
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")


def paleta(img, n=8):
    """Cores reais do print, da mais usada para a menos usada."""
    from PIL import Image
    peq = img.copy()
    peq.thumbnail((300, 300))
    q = peq.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: n * 3]
    contagem = sorted(q.getcolors() or [], reverse=True)
    total = sum(c for c, _ in contagem) or 1
    saida = []
    for qtd, idx in contagem:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        saida.append({"hex": "#%02x%02x%02x" % (r, g, b), "uso": round(100.0 * qtd / total)})
    return saida


def faixas(img):
    """Mede as FAIXAS horizontais do print (cabecalho, hero, rodape...) direto
    nos pixels: onde comeca e termina cada uma, a cor de fundo e a cor de
    destaque (texto/botao). Modelo de visao erra posicao e cor; pixel nao."""
    peq = img.copy()
    k = 400.0 / peq.width
    peq = peq.resize((400, max(1, int(peq.height * k))))
    w, h = peq.size
    px = peq.load()

    def fundo_da_linha(y):
        cont = {}
        for x in range(0, w, 4):
            r, g, b = px[x, y]
            chave = (r // 12, g // 12, b // 12)
            cont[chave] = cont.get(chave, 0) + 1
        chave, n = max(cont.items(), key=lambda kv: kv[1])
        return chave, n / (w / 4.0)

    linhas = [fundo_da_linha(y) for y in range(h)]
    grupos, ini = [], 0
    for y in range(1, h + 1):
        if y == h or linhas[y][0] != linhas[ini][0]:
            if y - ini >= max(6, h * 0.02) or not grupos:
                grupos.append([ini, y, linhas[ini][0]])
            else:
                grupos[-1][1] = y                    # faixa fina gruda na anterior
            ini = y
    # junta vizinhas com o mesmo fundo
    unidas = []
    for g in grupos:
        if unidas and unidas[-1][2] == g[2]:
            unidas[-1][1] = g[1]
        else:
            unidas.append(g)
    saida = []
    for y0, y1, chave in unidas[:12]:
        caixa = peq.crop((0, y0, w, y1))
        cores = caixa.quantize(colors=4).convert("RGB").getcolors(4 * 400 * 400) or []
        cores = sorted(cores, reverse=True)
        exatas = caixa.getcolors(caixa.width * caixa.height) or []
        fundo = "#%02x%02x%02x" % max(exatas)[1] if exatas else \
            "#%02x%02x%02x" % tuple(min(255, c * 12 + 6) for c in chave)
        outras = ["#%02x%02x%02x" % c for _, c in cores[1:3]]
        blocos = _blocos_na_faixa(caixa, max(exatas)[1] if exatas else None, k)
        saida.append({"de_px": int(y0 / k), "ate_px": int(y1 / k), "fundo": fundo,
                      "outras_cores": outras, "blocos": blocos})
    return saida


def _blocos_na_faixa(caixa, fundo, k):
    """Onde ha conteudo na horizontal: [(x0, x1, cor_mais_comum)] em px do print."""
    if fundo is None:
        return []
    w, h = caixa.size
    px = caixa.load()
    ocupado = []
    for x in range(w):
        dif = 0
        for y in range(0, h, 2):
            r, g, b = px[x, y]
            if abs(r - fundo[0]) + abs(g - fundo[1]) + abs(b - fundo[2]) > 40:
                dif += 1
        ocupado.append(dif > max(1, h // 2 * 0.04))
    blocos, ini = [], None
    for x in range(w + 1):
        cheio = x < w and ocupado[x]
        if cheio and ini is None:
            ini = x
        elif not cheio and ini is not None:
            # buracos pequenos (espaco entre palavras) nao separam blocos
            if x < w and any(ocupado[x:x + max(3, w // 60)]):
                continue
            if x - ini >= 3:
                parte = caixa.crop((ini, 0, x, h))
                cores = parte.getcolors(parte.width * parte.height) or []
                cor = "#%02x%02x%02x" % max(cores)[1] if cores else ""
                blocos.append([int(ini / k), int(x / k), cor])
            ini = None
    return blocos[:6]


def _fatias(img):
    """Print comprido vira partes de ~1,3x a largura (letras legiveis)."""
    w, h = img.size
    alt = int(w * 1.3)
    if h <= alt * 1.25:
        return [img]
    partes, y = [], 0
    while y < h and len(partes) < 5:
        partes.append(img.crop((0, y, w, min(h, y + alt))))
        y += alt - 40                       # pequena sobra para nao cortar textos
    return partes


PROMPT_VISAO = """Voce e um desenvolvedor front-end olhando o print de uma pagina (parte %d de %d).
Descreva a tela DE CIMA PARA BAIXO, para outra pessoa recriar em HTML e CSS sem ver a imagem.
Para cada bloco diga:
- tipo (cabecalho, menu, destaque/hero, cards, lista, formulario, rodape...)
- POSICAO: o que fica a ESQUERDA, no CENTRO e a DIREITA; quantas colunas; alinhamento do texto
- cor de fundo do bloco e cor dos textos (ex.: fundo verde-escuro, texto branco)
- TODOS os textos visiveis, exatamente como aparecem, entre aspas
- botoes e campos (placeholder, rotulo), icones, imagens (o que mostram)
- cores de fundo e de texto, tamanho relativo e peso da fonte, cantos arredondados, sombras
Se nao der para ler um texto ou ter certeza de algo, escreva [INCERTO: motivo].
Escreva em portugues, em linhas curtas. Nao escreva codigo."""


def descrever_print(img, jid=None):
    import blender
    partes = _fatias(img)
    textos = []
    for i, parte in enumerate(partes, 1):
        if jid:
            _passo(jid, "Lendo o print (parte %d de %d)" % (i, len(partes)))
        buf = io.BytesIO()
        parte.save(buf, "PNG")
        r = blender.olhar_imagem(base64.b64encode(buf.getvalue()).decode("ascii"),
                                 PROMPT_VISAO % (i, len(partes)), limite=1600, timeout=300)
        if not r.get("ok"):
            raise RuntimeError("A visao do Bigode nao respondeu: %s" % (r.get("erro") or "sem detalhe"))
        textos.append("### Parte %d de %d (de cima para baixo)\n%s" % (i, len(partes), (r.get("texto") or "").strip()))
    return "\n\n".join(textos)


# ==========================================================================
# DESCRICAO -> CODIGO
# ==========================================================================

REGRAS = """Regras:
- HTML completo e semantico (header, nav, main, section, footer...), lang="pt-BR", com <meta name="viewport">.
- CSS em arquivo separado: o HTML usa <link rel="stylesheet" href="style.css">. Nada de <style> nem style="" no HTML.
- NAO use frameworks (Bootstrap, Tailwind). CSS puro, com variaveis (:root) para as cores.
- Mobile first: estilos base para celular; @media (min-width: 768px) e (min-width: 1100px) para telas maiores.
- Reproduza cores, espacamentos, tipografia e layout o mais fiel possivel. Use as cores medidas abaixo.
- Formularios, botoes e campos com as tags certas (form, label, input, button, select, textarea), sem funcionalidade.
- Imagens: use <img> com src de placeholder (https://placehold.co/LARGURAxALTURA) e alt descrevendo a imagem original.
- Fontes: use pilhas seguras (system-ui, Arial, Georgia...). Se a fonte original for incerta, diga.
- NAO invente: onde a descricao tiver [INCERTO], mantenha o texto aproximado e liste em INCERTEZAS.

Responda EXATAMENTE neste formato, sem mais nada:
```html
(index.html completo)
```
```css
(style.css completo)
```
INCERTEZAS:
- (um item por linha; escreva "- nenhuma" se nao houver)"""


def prompt_codigo(descricao, cores, largura, altura, detalhes="", bandas=None):
    lista = ", ".join("%s (%d%%)" % (c["hex"], c["uso"]) for c in cores)
    txt_bandas = ""
    if bandas:
        txt_bandas = ("FAIXAS MEDIDAS NOS PIXELS, de cima para baixo (use estas alturas e fundos; "
                      "elas valem mais que a descricao):\n" + "\n".join(
                          "- faixa %d: de %dpx a %dpx (altura %dpx), fundo %s, outras cores %s; "
                          "areas com texto/elementos na horizontal (so para saber colunas e alinhamento): %s"
                          % (i + 1, b["de_px"], b["ate_px"], b["ate_px"] - b["de_px"], b["fundo"],
                             ", ".join(b["outras_cores"]) or "-",
                             "; ".join("x %d-%dpx" % tuple(bl[:2])
                                       for bl in b.get("blocos") or []) or "-")
                          for i, b in enumerate(bandas)) + "\n")
    return ("Voce vai atuar como um conversor de imagem para codigo. Recrie a pagina descrita abaixo.\n\n"
            "Tamanho do print: %dx%d px (tela de computador; faca a versao de celular empilhando os blocos).\n"
            "Cores MEDIDAS nos pixels (da mais usada para a menos usada): %s\n%s"
            "%s\n\nDESCRICAO DA TELA (feita por um modelo de visao; textos confiaveis, "
            "posicoes e cores aproximadas):\n%s\n\n%s"
            % (largura, altura, lista, txt_bandas,
               ("Observacoes do Fred: " + detalhes) if detalhes else "",
               descricao, REGRAS))


def separar_codigo(texto):
    """Tira html, css e incertezas da resposta do modelo."""
    t = texto or ""
    html = css = ""
    for lang, corpo in re.findall(r"```(\w*)\s*\n(.*?)```", t, flags=re.S):
        lang = lang.lower()
        if lang in ("html", "htm") and not html:
            html = corpo.strip()
        elif lang == "css" and not css:
            css = corpo.strip()
        elif not lang and not html and "<html" in corpo.lower():
            html = corpo.strip()
    if not html:
        m = re.search(r"(<!doctype html.*?</html>)", t, flags=re.S | re.I)
        html = m.group(1) if m else ""
    # CSS que o modelo deixou dentro do HTML vai para o style.css
    blocos = re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.S | re.I)
    if blocos:
        css = (css + "\n\n" + "\n\n".join(b.strip() for b in blocos)).strip()
        html = re.sub(r"\s*<style[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    if html and "style.css" not in html:
        if re.search(r"</head>", html, flags=re.I):
            html = re.sub(r"</head>", '  <link rel="stylesheet" href="style.css">\n</head>',
                          html, count=1, flags=re.I)
        else:
            html = '<link rel="stylesheet" href="style.css">\n' + html
    incertezas = []
    m = re.search(r"INCERTEZAS\s*:?(.*)$", t, flags=re.S | re.I)
    if m:
        for linha in m.group(1).splitlines():
            linha = linha.strip().lstrip("-*• ").strip()
            if linha and "```" not in linha and linha.lower() not in ("nenhuma", "nenhum"):
                incertezas.append(linha[:300])
    return html, css, incertezas[:30]


def _salvar(nome, html, css, notas, img=None):
    pasta = _pasta_do(nome)
    pasta.mkdir(parents=True, exist_ok=True)
    if (pasta / "index.html").exists():
        v = pasta / "versoes" / time.strftime("%Y%m%d-%H%M%S")
        v.mkdir(parents=True, exist_ok=True)
        for a in ("index.html", "style.css", "LEIA-ME.txt"):
            if (pasta / a).exists():
                shutil.copy2(pasta / a, v / a)
    (pasta / "index.html").write_text(html, encoding="utf-8")
    (pasta / "style.css").write_text(css or "/* sem CSS */\n", encoding="utf-8")
    (pasta / "LEIA-ME.txt").write_text(notas, encoding="utf-8")
    if img is not None:
        img.save(pasta / "print.png")
    return pasta


def _notas(origem, motor, incertezas, extra=""):
    linhas = ["CLONE GERADO PELO BIGODE IA", "Quando: " + time.strftime("%d/%m/%Y %H:%M"),
              "Origem: " + origem, "Modelo que escreveu o codigo: " + (motor or "-"), ""]
    if extra:
        linhas += [extra, ""]
    linhas.append("PONTOS INCERTOS (confira na imagem original):")
    linhas += ["- " + i for i in incertezas] or ["- nenhum informado"]
    linhas += ["", "Uso responsavel: publique so sites seus ou de clientes que autorizaram."]
    return "\n".join(linhas)


# ==========================================================================
# TRABALHOS (rodam em segundo plano; a tela consulta o andamento)
# ==========================================================================

def clonar_print(imagem_b64, nome="", detalhes="", reserva=None):
    jid = _job("Recebendo o print")
    JOBS[jid]["nome"] = nome_seguro(nome)
    threading.Thread(target=_rodar_print, args=(jid, imagem_b64, detalhes, reserva),
                     daemon=True).start()
    return {"ok": True, "id": jid, "nome": JOBS[jid]["nome"]}


def _rodar_print(jid, imagem_b64, detalhes, reserva):
    j = JOBS[jid]
    try:
        img = _abrir_imagem(imagem_b64)
        if img.width > 1600:
            img = img.resize((1600, int(img.height * 1600 / img.width)))
        _passo(jid, "Medindo as cores do print")
        cores = paleta(img)
        try:
            bandas = faixas(img)
        except Exception:
            bandas = []
        html = css = motor = descricao = ""
        incertezas = []
        tentativas = []
        # CAMINHO 1: um modelo que VE o print escreve o codigo direto
        png = _png(img)
        for modelo in MODELOS_VISAO:
            _passo(jid, "Olhando o print e escrevendo o codigo (%s, ~1 min)" % modelo.split("/")[-1])
            texto = chat_hf_visao(prompt_codigo(
                "(a imagem anexada E a tela; use-a como fonte principal)",
                cores, img.width, img.height, detalhes, bandas), png, modelo)
            if texto:
                html, css, incertezas = separar_codigo(texto)
                if "<body" in html.lower():
                    motor = modelo.split("/")[-1] + " (Hugging Face, vendo o print)"
                    break
            tentativas.append(modelo.split("/")[-1])
            html = ""
        # CAMINHO 2 (reserva): a visao do Bigode descreve, um modelo de codigo escreve
        if not html:
            _passo(jid, "Plano B: a visao do Bigode vai descrever a tela")
            descricao = descrever_print(img, jid)
            _passo(jid, "Escrevendo o HTML e o CSS (1 a 4 min)")
            texto, motor = _escrever_codigo(
                prompt_codigo(descricao, cores, img.width, img.height, detalhes, bandas), reserva)
            if not texto:
                raise RuntimeError("Nenhum modelo respondeu (%s, Hugging Face e motor do Bigode). "
                                   "Pode ser o credito gratis do Hugging Face do mes." % ", ".join(tentativas))
            html, css, incertezas = separar_codigo(texto)
            if "<body" not in html.lower():
                raise RuntimeError("O modelo nao devolveu um HTML completo. Tente de novo.")
        _passo(jid, "Salvando os arquivos")
        pasta = _salvar(j["nome"], html, css,
                        _notas("print enviado na tela", motor, incertezas,
                               "Cores medidas: " + ", ".join(c["hex"] for c in cores)), img)
        if descricao:
            (pasta / "descricao_da_tela.txt").write_text(descricao, encoding="utf-8")
        j.update(estado="pronto", motor=motor, incertezas=incertezas, pasta=str(pasta),
                 cores=[c["hex"] for c in cores])
        _passo(jid, "Pronto")
    except Exception as erro:
        j.update(estado="erro", erro=str(erro)[:400])


def clonar_link(url, nome="", reserva=None):
    url = (url or "").strip()
    if url and not re.match(r"https?://", url, flags=re.I):
        url = "https://" + url
    jid = _job("Abrindo o site")
    JOBS[jid]["nome"] = nome_seguro(nome or urllib.parse.urlparse(url).netloc.replace("www.", "").replace(".", "-"))
    threading.Thread(target=_rodar_link, args=(jid, url), daemon=True).start()
    return {"ok": True, "id": jid, "nome": JOBS[jid]["nome"]}


def _baixar_texto(url, limite=3_000_000):
    import gzip
    import zlib
    req = urllib.request.Request(url, headers={
        "User-Agent": AGENTE, "Accept-Language": "pt-BR,pt;q=0.9",
        "Accept-Encoding": "gzip, deflate", "Accept": "text/html,text/css,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        dados = r.read(limite)
        final = r.geturl()
        tipo = r.headers.get_content_charset() or "utf-8"
        codif = (r.headers.get("Content-Encoding") or "").lower()
    if "gzip" in codif or dados[:2] == b"\x1f\x8b":
        dados = gzip.decompress(dados)
    elif "deflate" in codif:
        try:
            dados = zlib.decompress(dados)
        except zlib.error:
            dados = zlib.decompress(dados, -zlib.MAX_WBITS)
    elif "br" in codif:
        raise RuntimeError("o site mandou a pagina num formato compactado (brotli) que o Bigode "
                           "nao abre. Use a opcao 'Um print'.")
    return dados.decode(tipo, "replace"), final


def _absoluto(base, alvo):
    alvo = (alvo or "").strip()
    if not alvo or alvo.startswith(("data:", "#", "mailto:", "tel:", "javascript:")):
        return alvo
    return urllib.parse.urljoin(base, alvo)


def _css_absoluto(css, base):
    return re.sub(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)",
                  lambda m: "url(%s%s%s)" % (m.group(1), _absoluto(base, m.group(2)), m.group(1)),
                  css)


def _rodar_link(jid, url):
    j = JOBS[jid]
    try:
        if not re.match(r"https?://[\w.-]+", url or ""):
            raise RuntimeError("Endereco invalido. Exemplo: https://www.exemplo.com.br")
        _passo(jid, "Baixando a pagina")
        html, final = _baixar_texto(url)
        _passo(jid, "Juntando as folhas de estilo")
        partes_css = []
        for tag in re.findall(r"<link\b[^>]*>", html, flags=re.I):
            if not re.search(r"rel\s*=\s*['\"]?[^'\">]*stylesheet", tag, flags=re.I):
                continue
            m = re.search(r"href\s*=\s*['\"]([^'\"]+)['\"]", tag, flags=re.I)
            if not m:
                continue
            endereco = _absoluto(final, m.group(1).replace("&amp;", "&"))
            try:
                css, final_css = _baixar_texto(endereco, 2_000_000)
                partes_css.append("/* ===== %s ===== */\n%s" % (endereco, _css_absoluto(css, final_css)))
            except Exception as e:
                partes_css.append("/* nao consegui baixar %s (%s) */" % (endereco, e))
        for bloco in re.findall(r"<style[^>]*>(.*?)</style>", html, flags=re.S | re.I):
            partes_css.append("/* ===== estilo de dentro da pagina ===== */\n" + _css_absoluto(bloco, final))
        _passo(jid, "Limpando o HTML")
        limpo = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
        limpo = re.sub(r"<noscript\b.*?</noscript>", "", limpo, flags=re.S | re.I)
        limpo = re.sub(r"<style\b.*?</style>", "", limpo, flags=re.S | re.I)
        limpo = re.sub(r"<link\b[^>]*stylesheet[^>]*>", "", limpo, flags=re.I)
        limpo = re.sub(r"\s(on\w+)\s*=\s*(['\"]).*?\2", "", limpo, flags=re.S | re.I)
        limpo = re.sub(r"(\s(?:src|href|poster)\s*=\s*)(['\"])(.*?)\2",
                       lambda m: m.group(1) + m.group(2) + _absoluto(final, m.group(3)) + m.group(2),
                       limpo, flags=re.I)
        limpo = re.sub(r"(\ssrcset\s*=\s*)(['\"])(.*?)\2",
                       lambda m: m.group(1) + m.group(2) + ", ".join(
                           " ".join([_absoluto(final, p.strip().split(" ")[0])] + p.strip().split(" ")[1:])
                           for p in m.group(3).split(",") if p.strip()) + m.group(2),
                       limpo, flags=re.I)
        if re.search(r"</head>", limpo, flags=re.I):
            limpo = re.sub(r"</head>", '  <link rel="stylesheet" href="style.css">\n</head>',
                           limpo, count=1, flags=re.I)
        else:
            limpo = '<link rel="stylesheet" href="style.css">\n' + limpo
        texto_visivel = re.sub(r"<[^>]+>", " ", re.sub(r"<head\b.*?</head>", "", limpo, flags=re.S | re.I))
        texto_visivel = re.sub(r"\s+", " ", texto_visivel).strip()
        aviso = ""
        if len(texto_visivel) < 250:
            aviso = ("A pagina chegou com pouquissimo texto. Se o site e montado por JavaScript "
                     "(comum em sites modernos), a copia fica vazia: tire um print da pagina e use "
                     "a opcao 'Um print'.")
        incertezas = ["Imagens e fontes continuam vindo do site original (precisam de internet)."]
        if aviso:
            incertezas.insert(0, aviso)
        _passo(jid, "Salvando os arquivos")
        pasta = _salvar(j["nome"], limpo, "\n\n".join(partes_css),
                        _notas(final, "copia direta (sem IA)", incertezas))
        j.update(estado="pronto", motor="copia direta do site (sem IA)", incertezas=incertezas,
                 pasta=str(pasta), aviso=aviso)
        _passo(jid, "Pronto")
    except Exception as erro:
        j.update(estado="erro", erro=str(erro)[:400])


PROMPT_AJUSTE = """Voce e um desenvolvedor front-end. Aplique o PEDIDO no codigo abaixo e devolva os DOIS arquivos
completos, mantendo tudo o que nao foi pedido para mudar. Mesmas regras: sem frameworks, mobile first,
CSS so no style.css.

PEDIDO DO FRED: %s

index.html atual:
```html
%s
```
style.css atual:
```css
%s
```

Responda EXATAMENTE neste formato:
```html
(index.html completo)
```
```css
(style.css completo)
```
INCERTEZAS:
- (um item por linha; "- nenhuma" se nao houver)"""


def ajustar(nome, pedido, reserva=None):
    jid = _job("Lendo o clone atual")
    JOBS[jid]["nome"] = nome_seguro(nome)
    threading.Thread(target=_rodar_ajuste, args=(jid, pedido, reserva), daemon=True).start()
    return {"ok": True, "id": jid, "nome": JOBS[jid]["nome"]}


def _rodar_ajuste(jid, pedido, reserva):
    j = JOBS[jid]
    try:
        pasta = _pasta_do(j["nome"])
        html = (pasta / "index.html").read_text(encoding="utf-8")
        css = (pasta / "style.css").read_text(encoding="utf-8") if (pasta / "style.css").exists() else ""
        if len(html) + len(css) > 60000:
            raise RuntimeError("Este clone e grande demais para ajustar com IA (mais de 60 mil letras). "
                               "Ajuste direto nos arquivos ou clone a partir de um print.")
        _passo(jid, "Aplicando o ajuste (1 a 4 min)")
        texto = motor = None
        if (pasta / "print.png").exists():
            png = (pasta / "print.png").read_bytes()
            for modelo in MODELOS_VISAO:
                texto = chat_hf_visao("A imagem anexada e o print ORIGINAL da tela.\n\n" +
                                      PROMPT_AJUSTE % (pedido, html, css), png, modelo)
                if texto and "<body" in texto.lower():
                    motor = modelo.split("/")[-1] + " (Hugging Face, vendo o print)"
                    break
                texto = None
        if not texto:
            texto, motor = _escrever_codigo(PROMPT_AJUSTE % (pedido, html, css), reserva)
        if not texto:
            raise RuntimeError("Nenhum modelo de codigo respondeu.")
        novo_html, novo_css, incertezas = separar_codigo(texto)
        if "<body" not in novo_html.lower():
            raise RuntimeError("O modelo nao devolveu um HTML completo. Tente de novo.")
        _passo(jid, "Salvando (a versao anterior fica em 'versoes')")
        _salvar(j["nome"], novo_html, novo_css or css,
                _notas("ajuste: " + pedido[:200], motor, incertezas))
        j.update(estado="pronto", motor=motor, incertezas=incertezas, pasta=str(pasta))
        _passo(jid, "Pronto")
    except Exception as erro:
        j.update(estado="erro", erro=str(erro)[:400])
