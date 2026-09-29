#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""NAVEGADOR PROPRIO DO BIGODE (Playwright) -- sem depender da extensao
Venure · venure.com.br · 29/09/2026

POR QUE EXISTE
    A extensao do Chrome dormia (o Chrome suspende o service worker), nao
    entrava em paginas chrome:// e fazia a conversa esperar 90 s por nada.
    Aqui o proprio Bigode abre e comanda uma janela do Chrome (ou do Edge,
    que todo Windows tem) pelo Playwright -- a mesma tecnologia do
    "Playwright MCP" da Microsoft, so que embutida, sem Node e sem servidor
    a mais para ligar.

JANELA E PERFIL PROPRIOS
    Desde o Chrome 136 (2025) o Google nao deixa automacao entrar no perfil
    PADRAO do Chrome (seguranca contra roubo de cookies). Por isso a janela
    usa um perfil so do Bigode:  %LOCALAPPDATA%\bigode_3d\navegador_perfil
    Na primeira vez, faca login nos sites que quiser nessa janela: o login
    fica guardado para as proximas vezes.

AS MESMAS 9 ACOES DA EXTENSAO, COM A MESMA RESPOSTA
    ver, texto, ir, clicar, escrever, digitar, teclar, rolar, esperar.
    O texto devolvido tem o mesmo formato (PAGINA / ENDERECO / ELEMENTOS
    [n] ...), entao o cerebro.py e o prompt nao mudaram. Clicar e digitar
    agora usam mouse e teclado de verdade (o Playwright), o que funciona em
    sites que ignoravam o el.click() da extensao.

APROVACAO
    Clicar em comprar/enviar/pagar/apagar... e apertar Enter continuam
    pedindo "Aprovar / Negar" na propria pagina, igual a extensao.

INSTALACAO
    Automatica na primeira vez (~40 MB, pip --target em
    %LOCALAPPDATA%\bigode_3d\libs_navegador). Nao baixa navegador: usa o
    Chrome ou o Edge que ja estao no PC.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

PASTA = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".cache")) / "bigode_3d"
LIBS = PASTA / "libs_navegador"
PERFIL = PASTA / "navegador_perfil"
CANAIS = ("chrome", "msedge", None)       # None = Chromium do Playwright, se existir

_FILA = queue.Queue()
_TRAVA = threading.Lock()
_ESTADO = {"thread": None, "instalando": False, "canal": "", "erro": ""}

# ---------------------------------------------------------------- JS
_JS_MAPEAR = r"""
() => {
  const SELETOR = 'a[href],button,input,textarea,select,summary,' +
    '[role="button"],[role="link"],[role="tab"],[role="checkbox"],[role="menuitem"],' +
    '[contenteditable="true"],[onclick]';
  const visivel = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return false;
    const s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity < 0.1) return false;
    if (el.disabled) return false;
    return r.bottom > -400 && r.top < innerHeight + 800;
  };
  const rotulo = el => (el.getAttribute('aria-label') || el.placeholder || el.value ||
      el.innerText || el.title || el.alt || el.name || '').trim().replace(/\s+/g, ' ').slice(0, 70);
  const tipo = el => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'input') return (el.type || 'text');
    if (tag === 'a') return 'link';
    if (tag === 'textarea') return 'texto';
    if (tag === 'select') return 'lista';
    return tag;
  };
  document.querySelectorAll('[data-bigode-n]').forEach(e => e.removeAttribute('data-bigode-n'));
  const mapa = [...document.querySelectorAll(SELETOR)].filter(visivel).slice(0, 120);
  const itens = mapa.map((el, i) => {
    el.setAttribute('data-bigode-n', String(i));
    const extra = (el.value && el.tagName === 'INPUT') ? ' = "' + el.value.slice(0, 30) + '"' : '';
    return `[${i}] ${tipo(el)}: ${rotulo(el) || '(sem rótulo)'}${extra}`;
  });
  const texto = ((document.body && document.body.innerText) || '').replace(/\n{3,}/g, '\n\n').slice(0, 4000);
  return `PÁGINA: ${document.title}\nENDEREÇO: ${location.href}\n\n` +
         `ELEMENTOS (use o número para clicar ou escrever):\n${itens.join('\n')}\n\n` +
         `TEXTO VISÍVEL:\n${texto}`;
}
"""

_JS_ROTULO = r"""
el => (el.getAttribute('aria-label') || el.placeholder || el.value ||
       el.innerText || el.title || el.alt || el.name || '').trim().replace(/\s+/g, ' ').slice(0, 70)
"""

_JS_APROVAR = r"""
([acao, alvo, LIMITE]) => new Promise(resolve => {
  document.querySelector('[data-bigode-hitl]')?.remove();
  const fundo = document.createElement('div');
  fundo.dataset.bigodeHitl = '1';
  fundo.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:rgba(4,8,13,.72);display:grid;place-items:center;padding:20px;font:14px -apple-system,Segoe UI,sans-serif;color:#ECEFF4';
  const card = document.createElement('div');
  card.style.cssText = 'width:min(420px,100%);background:#11141B;border:1px solid #4A3D1A;border-radius:14px;padding:20px;box-shadow:0 18px 60px rgba(0,0,0,.5)';
  const titulo = document.createElement('div');
  titulo.textContent = 'Aprovação necessária';
  titulo.style.cssText = 'font-weight:700;font-size:16px;margin-bottom:9px;color:#FBBF24';
  const detalhe = document.createElement('div');
  detalhe.textContent = 'O Bigode quer ' + acao + ' em “' + (alvo || 'elemento da página') + '”.';
  detalhe.style.cssText = 'line-height:1.6;color:#A3ACBB;margin-bottom:16px';
  const linha = document.createElement('div');
  linha.style.cssText = 'display:flex;gap:9px;justify-content:flex-end';
  const negar = document.createElement('button');
  negar.textContent = 'Negar';
  negar.style.cssText = 'padding:9px 16px;border-radius:9px;border:1px solid #2A313E;background:none;color:#A3ACBB;cursor:pointer';
  const aprovar = document.createElement('button');
  aprovar.textContent = 'Aprovar';
  aprovar.style.cssText = 'padding:9px 16px;border-radius:9px;border:0;background:#34D399;color:#052A1E;font-weight:700;cursor:pointer';
  const fim = ok => { fundo.remove(); resolve(ok); };
  negar.onclick = () => fim(false);
  aprovar.onclick = () => fim(true);
  setTimeout(() => fim(false), LIMITE);
  linha.append(negar, aprovar); card.append(titulo, detalhe, linha); fundo.append(card);
  document.documentElement.append(fundo);
  aprovar.focus();
})
"""

CRITICOS = ("comprar", "finalizar", "enviar", "salvar", "excluir", "apagar", "assinar",
            "pagar", "publicar", "confirmar", "submit")
TECLAS = {"enter": "Enter", "tab": "Tab", "escape": "Escape", "esc": "Escape",
          "arrowdown": "ArrowDown", "arrowup": "ArrowUp", "arrowleft": "ArrowLeft",
          "arrowright": "ArrowRight", "backspace": "Backspace", "space": " ",
          "pagedown": "PageDown", "pageup": "PageUp", "home": "Home", "end": "End"}


# ---------------------------------------------------------------- instalacao
def instalado():
    return (LIBS / "playwright").exists()


def instalar():
    """pip --target: nao mexe no Python do Bigode nem nas outras pastas."""
    LIBS.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                        "--disable-pip-version-check", "--upgrade", "--target", str(LIBS),
                        "playwright"],
                       capture_output=True, text=True, timeout=900,
                       creationflags=0x08000000 if sys.platform == "win32" else 0)
    if r.returncode != 0 or not instalado():
        raise RuntimeError("Nao consegui instalar o Playwright: " + (r.stderr or r.stdout)[-300:])


# ---------------------------------------------------------------- trabalhador
def _abrir(pw):
    """Abre a janela com perfil proprio. Tenta Chrome, depois Edge."""
    erros = []
    for canal in CANAIS:
        pasta = PERFIL / (canal or "chromium")
        pasta.mkdir(parents=True, exist_ok=True)
        try:
            ctx = pw.chromium.launch_persistent_context(
                str(pasta), channel=canal, headless=os.environ.get("BIGODE_NAV_OCULTO") == "1",
                no_viewport=True, args=["--start-maximized"])
            _ESTADO["canal"] = canal or "chromium"
            return ctx
        except Exception as e:
            erros.append("%s: %s" % (canal or "chromium", str(e).splitlines()[0][:120]))
    raise RuntimeError("Nao achei Chrome nem Edge para abrir. " + " | ".join(erros))


def _pagina(ctx):
    vivas = [p for p in ctx.pages if not p.is_closed()]
    return vivas[-1] if vivas else ctx.new_page()


def _rotulo(loc):
    try:
        return loc.evaluate(_JS_ROTULO)
    except Exception:
        return ""


def _aprovado(page, acao, alvo):
    try:
        limite = int(float(os.environ.get("BIGODE_NAV_APROVACAO_S") or 120) * 1000)
        return bool(page.evaluate(_JS_APROVAR, [acao, alvo, limite]))
    except Exception:
        return False


def _elemento(page, numero):
    try:
        n = int(str(numero).strip().strip("[]"))
    except ValueError:
        raise RuntimeError("Numero invalido: %r. Use o numero da lista do navegador_ver." % numero)
    loc = page.locator('[data-bigode-n="%d"]' % n)
    if loc.count() == 0:
        raise RuntimeError("Não existe elemento [%d]. Chame navegador_ver de novo." % n)
    return n, loc.first


def _depois(page):
    try:
        page.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass


def _executar(page, acao, a):
    if acao == "ver":
        return page.evaluate(_JS_MAPEAR)

    if acao == "texto":
        corpo = page.evaluate("() => (document.body && document.body.innerText) || ''")
        return "PÁGINA: %s\nENDEREÇO: %s\n\n%s" % (page.title(), page.url, corpo[:12000])

    if acao == "ir":
        url = str(a.get("url") or "").strip().strip('"')
        if not url:
            return "Faltou o endereço."
        if "://" not in url and not url.startswith(("about:", "chrome:")):
            url = "https://" + url
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        return "Abri %s\n\n%s" % (page.url, page.evaluate(_JS_MAPEAR))

    if acao == "clicar":
        n, loc = _elemento(page, a.get("numero"))
        alvo = _rotulo(loc)
        if any(t in alvo.lower() for t in CRITICOS) and not _aprovado(page, "clicar", alvo):
            return "Ação negada pelo usuário."
        loc.scroll_into_view_if_needed(timeout=5000)
        loc.click(timeout=10000)
        _depois(page)
        return "Cliquei em [%d] %s.\nAgora estou em: %s" % (n, alvo, page.url)

    if acao == "escrever":
        n, loc = _elemento(page, a.get("numero"))
        texto = str(a.get("texto") or "")
        loc.scroll_into_view_if_needed(timeout=5000)
        try:
            loc.fill(texto, timeout=10000)
        except Exception:
            loc.click(timeout=10000)
            page.keyboard.type(texto, delay=15)
        return 'Escrevi "%s" no campo [%d] %s.' % (texto, n, _rotulo(loc))

    if acao == "digitar":
        texto = str(a.get("texto") or "")
        page.keyboard.type(texto, delay=15)
        return 'Digitei "%s" onde o cursor estava.' % texto[:200]

    if acao == "teclar":
        bruto = str(a.get("tecla") or "Enter").strip()
        tecla = TECLAS.get(bruto.lower().replace(" ", ""), bruto)
        if tecla == "Enter" and not _aprovado(page, "apertar Enter", "página " + page.title()[:40]):
            return "Ação negada pelo usuário."
        page.keyboard.press(tecla)
        _depois(page)
        return "Apertei %s. Estou em: %s" % (tecla, page.url)

    if acao == "rolar":
        d = str(a.get("direcao") or "baixo").lower()
        js = ("scrollTo({top:0})" if "topo" in d else
              "scrollTo({top:document.body.scrollHeight})" if "fim" in d else
              "scrollBy({top:-innerHeight*0.85})" if "cima" in d else
              "scrollBy({top:innerHeight*0.85})")
        page.evaluate("() => " + js)
        page.wait_for_timeout(500)
        return "Rolei a página. Chame navegador_ver para enxergar o que apareceu."

    if acao == "esperar":
        try:
            s = min(float(a.get("segundos") or 2), 20)
        except ValueError:
            s = 2
        page.wait_for_timeout(int(s * 1000))
        return "Esperei %gs. Estou em: %s" % (s, page.url)

    return "Ação desconhecida: %s" % acao


def _trabalhador():
    """Uma thread so fala com o Playwright (a API sincrona exige isso)."""
    pw = ctx = None
    while True:
        acao, args, resposta = _FILA.get()
        try:
            if pw is None:
                if not instalado():
                    _ESTADO["instalando"] = True
                    try:
                        instalar()
                    finally:
                        _ESTADO["instalando"] = False
                if str(LIBS) not in sys.path:
                    sys.path.insert(0, str(LIBS))
                from playwright.sync_api import sync_playwright
                pw = sync_playwright().start()
            if acao == "_fechar":
                if ctx is not None:
                    ctx.close()
                ctx = None
                resposta.put("fechado")
                continue
            for tentativa in (1, 2):
                try:
                    if ctx is None:
                        ctx = _abrir(pw)
                    page = _pagina(ctx)
                    resposta.put(_executar(page, acao, args or {}))
                    break
                except Exception as e:
                    # janela fechada pelo usuario: abre de novo uma vez
                    fechou = "closed" in str(e).lower() or "has been closed" in str(e).lower()
                    if tentativa == 1 and fechou:
                        ctx = None
                        continue
                    raise
            _ESTADO["erro"] = ""
        except Exception as e:
            _ESTADO["erro"] = str(e)[:300]
            resposta.put("Não consegui: %s" % str(e).splitlines()[0][:300])


def pedir(acao, args=None, espera=90):
    """Executa uma acao e devolve o texto (mesmo formato da extensao)."""
    with _TRAVA:
        t = _ESTADO["thread"]
        if t is None or not t.is_alive():
            t = threading.Thread(target=_trabalhador, daemon=True, name="navegador-bigode")
            t.start()
            _ESTADO["thread"] = t
    resposta = queue.Queue()
    _FILA.put((str(acao).replace("navegador_", ""), args or {}, resposta))
    limite = espera + (900 if not instalado() else 0)
    try:
        return resposta.get(timeout=limite)
    except queue.Empty:
        return ("O navegador do Bigode nao respondeu em %ds. Se houver um aviso de "
                "Aprovar/Negar na janela, responda a ele." % limite)


def fechar():
    return pedir("_fechar", {}, espera=20)


def estado():
    return {"instalado": instalado(), "instalando": _ESTADO["instalando"],
            "canal": _ESTADO["canal"], "erro": _ESTADO["erro"], "perfil": str(PERFIL)}


if __name__ == "__main__":
    # Teste rapido:  python navegador_bigode.py https://example.com
    alvo = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    print(pedir("ir", {"url": alvo}, espera=120))
    print(json.dumps(estado(), ensure_ascii=False))
    fechar()
