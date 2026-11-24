#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Venure.com.br - Tecnologia
"""Soul: pesquisa educacional, rascunhos WordPress e kit social.

A biblioteca não publica artigos. A publicação é uma operação separada, com
confirmação explícita no método publicar_rascunho(). Credenciais ficam fora do
repositório, em arquivo de usuário com permissões restritas, ou no ambiente.
A pesquisa não fabrica fontes: PubMed é consultado pela API pública; URLs
ANVISA/SciELO/DOI são fornecidas e verificadas pelo usuário.
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import json
import os
import re
import secrets
import ssl
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

BASE = Path(__file__).resolve().parent
USER_HOME = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_CONFIG_HOME") or Path.home())
CONFIG_PATH = Path(os.environ.get("SOUL_CONNECTIONS_PATH") or
                   os.environ.get("SOUL_WP_CONFIG") or
                   (USER_HOME / "Bigode" / "conexoes.json"))
LEGACY_CONFIG_PATH = USER_HOME / "Bigode" / "soul_wordpress.json"
DEFAULT_OUTPUT = BASE / "memoria" / "soul"
HTTP_TIMEOUT = 20
MAX_ABSTRACT = 5000

_LOCK = threading.RLock()
_JOBS: dict[str, dict[str, Any]] = {}


def _safe_site(value: str) -> str:
    p = urllib.parse.urlsplit(str(value or "").strip())
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("O WordPress deve usar uma URL HTTPS válida, sem usuário/senha embutidos.")
    host = p.hostname.lower()
    if not (host == "projetosoul.com.br" or host.endswith(".projetosoul.com.br")):
        raise ValueError("Por segurança, a conexão desta tela aceita apenas projetosoul.com.br.")
    path = p.path.rstrip("/")
    return urllib.parse.urlunsplit(("https", p.netloc, path, "", ""))


def _ler_config() -> dict[str, Any]:
    try:
        whole = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(whole, dict):
            whole = {}
    except (OSError, ValueError, TypeError):
        whole = {}
    d = whole.get("soul_wordpress") if isinstance(whole.get("soul_wordpress"), dict) else {}
    if not d:
        try:
            legacy = json.loads(LEGACY_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(legacy, dict):
                d = legacy
        except (OSError, ValueError, TypeError):
            pass
    # Variáveis de ambiente prevalecem; nenhum endpoint recebe a senha.
    d["url"] = os.environ.get("SOUL_WP_URL", d.get("url", ""))
    d["usuario"] = os.environ.get("SOUL_WP_USER", d.get("usuario", ""))
    d["application_password"] = os.environ.get(
        "SOUL_WP_APP_PASSWORD", d.get("app_password", d.get("application_password", "")))
    d["pasta_saida"] = os.environ.get("SOUL_OUTPUT_DIR", d.get("pasta_saida", str(DEFAULT_OUTPUT)))
    d["categorias"] = d.get("categorias") if isinstance(d.get("categorias"), list) else []
    return d


def _resumo_config(d: dict[str, Any] | None = None) -> dict[str, Any]:
    d = d or _ler_config()
    return {"ok": True, "configurado": bool(d.get("url") and d.get("usuario") and d.get("application_password")),
            "url": d.get("url", ""), "usuario": d.get("usuario", ""),
            "senha_guardada": bool(d.get("application_password")),
            "pasta_saida": d.get("pasta_saida", str(DEFAULT_OUTPUT)),
            "segredo_exibido": False}


def estado() -> dict[str, Any]:
    return _resumo_config()


def salvar_config(dados: dict[str, Any]) -> dict[str, Any]:
    """Guardar credenciais de aplicação num arquivo local (não no config.json)."""
    dados = dados if isinstance(dados, dict) else {}
    anterior = _ler_config()
    url = str(dados.get("url", anterior.get("url", ""))).strip()
    usuario = str(dados.get("usuario", anterior.get("usuario", ""))).strip()
    senha = str(dados.get("app_password", dados.get("application_password", "")))
    if senha == "(guardado)" or not senha:
        senha = str(anterior.get("application_password", ""))
    pasta = str(dados.get("pasta_saida", anterior.get("pasta_saida", str(DEFAULT_OUTPUT)))).strip()
    if url:
        url = _safe_site(url)
    if len(usuario) > 200 or len(senha) > 500:
        raise ValueError("Usuário ou senha de aplicação acima do limite permitido.")
    if pasta:
        pasta = str(Path(pasta).expanduser().resolve())
    categorias = dados.get("categorias", anterior.get("categorias", []))
    try:
        categorias = sorted({int(x) for x in categorias if int(x) > 0})[:50]
    except (TypeError, ValueError):
        raise ValueError("Seleção de categorias WordPress inválida.") from None
    novo = {"url": url, "usuario": usuario, "app_password": senha,
            "pasta_saida": pasta or str(DEFAULT_OUTPUT), "categorias": categorias,
            "ativo": bool(dados.get("ativo", anterior.get("ativo", True)))}
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    try:
        whole = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(whole, dict): whole = {}
    except (OSError, ValueError, TypeError):
        whole = {}
    whole["soul_wordpress"] = novo
    tmp.write_text(json.dumps(whole, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(CONFIG_PATH)
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass
    return _resumo_config({**novo, "application_password": senha})


def _auth_headers(cfg: dict[str, Any]) -> dict[str, str]:
    import base64
    raw = (str(cfg.get("usuario") or "") + ":" +
           str(cfg.get("application_password") or "").replace(" ", "")).encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii"),
            "User-Agent": "BigodeIA-Soul/1.0", "Accept": "application/json"}


def _wp_request(method: str, endpoint: str, payload: dict[str, Any] | None = None,
                *, cfg: dict[str, Any] | None = None, raw: bytes | None = None,
                content_type: str = "application/json", extra_headers: dict[str, str] | None = None,
                timeout: int = HTTP_TIMEOUT) -> Any:
    cfg = cfg or _ler_config()
    if not (cfg.get("url") and cfg.get("usuario") and cfg.get("application_password")):
        raise RuntimeError("WordPress não configurado. Informe URL, usuário e Application Password.")
    base = _safe_site(cfg["url"]).rstrip("/") + "/wp-json/wp/v2"
    if not endpoint.startswith("/") or ".." in endpoint:
        raise ValueError("Rota WordPress inválida.")
    body = raw if raw is not None else (
        json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None)
    headers = _auth_headers(cfg)
    headers["Content-Type"] = content_type
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(base + endpoint, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            data = r.read(8_000_000)
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        # Nunca ecoar resposta que possa conter dados confidenciais; limite e higienize.
        detail = re.sub(r"[\r\n\t]+", " ", exc.read(1000).decode("utf-8", "replace"))
        raise RuntimeError("WordPress recusou a requisição (HTTP %s): %s" % (exc.code, detail[:250])) from None
    if "json" in ctype.lower() or (data[:1] in (b"{", b"[")):
        try:
            return json.loads(data.decode("utf-8", "replace"))
        except ValueError:
            pass
    return data


def testar_conexao() -> dict[str, Any]:
    cfg = _ler_config()
    if not (cfg.get("url") and cfg.get("usuario") and cfg.get("application_password")):
        return {"ok": False, "configurado": False, "mensagem": "Informe as credenciais para testar."}
    try:
        user = _wp_request("GET", "/users/me?context=edit", cfg=cfg)
        if not isinstance(user, dict) or not user.get("id"):
            return {"ok": False, "configurado": True, "mensagem": "A API respondeu, mas não confirmou a conta autenticada."}
        categories = _wp_request("GET", "/categories?context=edit&per_page=100&hide_empty=false", cfg=cfg)
        if not isinstance(categories, list): categories = []
        return {"ok": True, "configurado": True, "usuario": user.get("name", ""),
                "id": int(user["id"]),
                "categorias_selecionadas": [int(x) for x in (cfg.get("categorias") or []) if str(x).isdigit()],
                "categorias": [{"id": int(c.get("id") or 0), "nome": str((c.get("name") or "")[:120])}
                               for c in categories if c.get("id")],
                "mensagem": "WordPress autenticado; categorias carregadas; publicação não foi realizada."}
    except Exception as exc:
        return {"ok": False, "configurado": True, "mensagem": str(exc)[:300]}


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts: list[str] = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style", "noscript", "svg"):
            self.hidden += 1
        if not self.hidden and tag.lower() in ("p", "div", "li", "br", "h1", "h2", "h3"):
            self.parts.append(" ")
    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style", "noscript", "svg") and self.hidden:
            self.hidden -= 1
        if not self.hidden and tag.lower() in ("p", "div", "li", "br", "h1", "h2", "h3"):
            self.parts.append(" ")
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _html_text(value: str, limit: int = 12000) -> str:
    parser = _TextOnly(); parser.feed(value or "")
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    return text[:limit]


def _http_json(url: str, timeout: int = HTTP_TIMEOUT,
               allowed_roots: list[str] | None = None) -> Any:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Fonte externa deve usar HTTPS e não pode incluir credenciais.")
    roots = [str(x).lower().lstrip(".") for x in (allowed_roots or [parsed.hostname])]
    class _ScopedRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            target = urllib.parse.urlsplit(newurl)
            host = (target.hostname or "").lower()
            if target.scheme != "https" or not any(host == r or host.endswith("." + r) for r in roots):
                raise ValueError("Redirecionamento bloqueado para domínio fora da lista permitida.")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    req = urllib.request.Request(url, headers={"User-Agent": "BigodeIA-Soul/1.0 (educational research)",
                                               "Accept": "application/json,text/html;q=0.8"})
    opener = urllib.request.build_opener(_ScopedRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(req, timeout=timeout) as r:
        return r.read(2_000_000), r.headers.get("Content-Type", "")


def _anvisa_host(url: str) -> bool:
    p = urllib.parse.urlsplit(url)
    host = (p.hostname or "").lower()
    return p.scheme == "https" and host in ("gov.br", "www.gov.br") and "/anvisa/" in p.path.lower()


def buscar_pubmed(consulta: str, limite: int = 12) -> list[dict[str, Any]]:
    consulta = str(consulta or "").strip()
    if not consulta:
        raise ValueError("Informe o tema de pesquisa.")
    limite = max(1, min(20, int(limite)))
    term = urllib.parse.quote(consulta + " AND (" + str(_dt.date.today().year - 12) + ":3000[dp])")
    url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json"
           "&sort=date&retmax=%d&term=%s" % (limite, term))
    raw, _ = _http_json(url, allowed_roots=["ncbi.nlm.nih.gov"])
    ids = (json.loads(raw.decode("utf-8", "replace")).get("esearchresult") or {}).get("idlist", [])
    if not ids:
        return []
    fetch = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id=" +
             ",".join(urllib.parse.quote(str(x), safe="") for x in ids))
    xml, _ = _http_json(fetch, allowed_roots=["ncbi.nlm.nih.gov"])
    # Parse XML with stdlib; no external entities are resolved by ElementTree.
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    out = []
    for node in root.findall(".//PubmedArticle"):
        pmid = (node.findtext(".//PMID") or "").strip()
        title = " ".join("".join(node.find(".//ArticleTitle").itertext()).split()) if node.find(".//ArticleTitle") is not None else ""
        abstract = " ".join(" ".join("".join(a.itertext()).split())
                            for a in node.findall(".//Abstract/AbstractText"))
        year = (node.findtext(".//PubDate/Year") or "")
        if not year:
            year = (node.findtext(".//PubDate/MedlineDate") or "")[:4]
        journal = (node.findtext(".//Journal/Title") or "")
        if pmid and title:
            out.append({"fonte": "PubMed", "pmid": pmid, "titulo": title[:600],
                        "ano": year[:4], "periodico": journal[:250],
                        "resumo": abstract[:MAX_ABSTRACT],
                        "url": "https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid})
    return out


def buscar_fontes_manuais(urls: list[str]) -> list[dict[str, Any]]:
    fontes = []
    for raw_url in (urls or [])[:15]:
        url = str(raw_url or "").strip()
        if not url:
            continue
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        p = urllib.parse.urlsplit(url)
        if not p.hostname or p.username or p.password:
            continue
        host = p.hostname.lower()

        # Caso 1: DOI
        if host in ("doi.org", "dx.doi.org"):
            try:
                doi = urllib.parse.unquote(p.path.lstrip("/"))
                crossref = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
                raw, ctype = _http_json(crossref, allowed_roots=["crossref.org"])
                msg = json.loads(raw.decode("utf-8", "replace")).get("message") or {}
                title = " ".join(msg.get("title") or [])[:600]
                summary = _html_text(msg.get("abstract") or "", MAX_ABSTRACT)
                year = str((msg.get("published-print") or msg.get("published-online") or {}).get("date-parts", [[""]])[0][0])
                fontes.append({
                    "fonte": "SciELO/DOI",
                    "titulo": title or url,
                    "ano": year or str(_dt.datetime.now().year),
                    "resumo": summary or ("Publicação científica indexada sob DOI " + doi),
                    "url": "https://doi.org/" + urllib.parse.quote(doi, safe="/"),
                    "pmid": ""
                })
            except Exception:
                pass
            continue

        # Caso 2: URL direta do PubMed
        if "pubmed.ncbi.nlm.nih.gov" in host:
            m_pmid = re.search(r"/(\d{5,9})", p.path)
            if m_pmid:
                try:
                    f_pmid = buscar_pubmed(m_pmid.group(1), 1)
                    if f_pmid:
                        fontes.extend(f_pmid)
                        continue
                except Exception:
                    pass

        # Caso 3: Qualquer link de artigo da web (Notícias, Revistas, ANVISA, SciELO, Portais)
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
            )
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                raw_bytes = resp.read(2_000_000)
                raw_text = raw_bytes.decode("utf-8", "replace")

            m_tit = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw_text)
            title = _html.unescape(re.sub(r"<[^>]+>", " ", m_tit.group(1))).strip()[:600] if m_tit else ""

            m_desc = re.search(r'(?i)description[^">]*content="([^"]+)"', raw_text)
            desc = _html.unescape(m_desc.group(1)).strip() if m_desc else ""

            texto_limpo = _html_text(raw_text, 15000)
            resumo = desc if desc and len(desc) >= 80 else texto_limpo[:MAX_ABSTRACT]

            if not title:
                title = "Artigo em " + host.replace("www.", "")
            if not resumo:
                resumo = "Conteúdo consultado a partir de " + url

            nome_fonte = "ANVISA" if _anvisa_host(url) else ("SciELO" if "scielo" in host else host.replace("www.", ""))
            fontes.append({
                "fonte": nome_fonte,
                "titulo": title,
                "ano": str(_dt.datetime.now().year),
                "resumo": resumo[:MAX_ABSTRACT],
                "url": url,
                "pmid": ""
            })
        except Exception:
            pass
    return fontes


def buscar_openalex(consulta: str, limite: int = 8) -> list[dict[str, Any]]:
    """Busca na OpenAlex. Cobre o que o PubMed não cobre.

    POR QUE ESTE COLETOR EXISTE                              (04/10/2026)
        O PubMed indexa literatura biomédica. Agronomia, história, ciência
        social e direito simplesmente não estão lá -- buscar "história da
        cannabis no Brasil" no PubMed devolve farmacologia, e o artigo sai
        com fontes que não falam do assunto. A OpenAlex é multidisciplinar,
        pública e sem autenticação obrigatória.

    O ABSTRACT VEM DE CABEÇA PARA BAIXO
        A OpenAlex não guarda o resumo como texto. Guarda
        `abstract_inverted_index`: um dicionário palavra -> lista de
        posições. Reconstruir é ordenar por posição. Se eu simplesmente
        juntasse as chaves, sairia uma salada de palavras com cara de
        resumo -- pior que resumo vazio, porque passaria no teste de
        "tem resumo?" do coletar_fontes e iria para o prompt do modelo.
    """
    consulta = str(consulta or "").strip()
    if not consulta:
        return []
    limite = max(1, min(int(limite or 8), 25))
    # O mailto é pedido pela OpenAlex para uso educado da API pública; sem
    # ele a chamada cai na fila lenta. Não é credencial e não é segredo.
    url = ("https://api.openalex.org/works?search=%s&per_page=%d"
           "&mailto=contato@venure.com.br"
           % (urllib.parse.quote(consulta), limite))
    req = urllib.request.Request(url, headers={
        "User-Agent": "BigodeIA-Soul/1.0 (educational research)",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        dados = json.loads(r.read().decode("utf-8", "replace"))

    saida: list[dict[str, Any]] = []
    for w in (dados.get("results") or []):
        if not isinstance(w, dict):
            continue

        # Reconstrução do abstract a partir do índice invertido.
        resumo = ""
        idx = w.get("abstract_inverted_index")
        if isinstance(idx, dict):
            posicoes: list[tuple[int, str]] = []
            for palavra, onde in idx.items():
                if isinstance(onde, list):
                    for pos in onde:
                        if isinstance(pos, int):
                            posicoes.append((pos, str(palavra)))
            if posicoes:
                posicoes.sort(key=lambda x: x[0])
                resumo = " ".join(p for _, p in posicoes)

        titulo = str(w.get("title") or w.get("display_name") or "").strip()
        if not titulo:
            continue

        # Resumo curto não serve para fundamentar artigo. Melhor descartar
        # a fonte do que mandar ao modelo uma linha solta que ele vai
        # "completar" por conta própria.
        if len(resumo) < 120:
            continue

        doi = str(w.get("doi") or "").strip()
        alvo = doi or str((w.get("ids") or {}).get("openalex") or "")
        if not alvo.startswith("http"):
            continue

        loc = w.get("primary_location") or {}
        fonte_pub = (loc.get("source") or {}) if isinstance(loc, dict) else {}
        periodico = str(fonte_pub.get("display_name") or "").strip()

        saida.append({
            "fonte": "OpenAlex",
            "titulo": titulo[:300],
            "ano": str(w.get("publication_year") or "s.d."),
            "periodico": periodico[:160],
            "pmid": "",
            "url": alvo,
            "resumo": resumo[:MAX_ABSTRACT],
        })
    return saida


# ── BASE JURÍDICA E REGULATÓRIA ──────────────────────────────── (04/10/2026)
#
#   Direito não tem API de busca confiável e aberta como o PubMed. Então
#   estes diplomas entram de uma lista fechada, escrita à mão e conferida.
#
#   O QUE EU NÃO ESCREVI AQUI, E POR QUE
#       A diretriz pedia "precedentes do STJ (6ª e 5ª Turmas)". Pesquisei
#       antes de escrever e descobri que o caso principal -- 6ª Turma,
#       julgado em 14/06/2022, relator Min. Rogerio Schietti Cruz -- corre
#       EM SEGREDO DE JUSTIÇA. Não existe número público de processo.
#
#       Se eu tivesse escrito um número de Habeas Corpus de cabeça, ele
#       seria falso E impossível de conferir. Jurisprudência inventada num
#       artigo público sobre auto-cultivo não é deslize de formatação: é a
#       pessoa confiando numa garantia que não existe.
#
#       Então cito o que é verificável: o Informativo de Jurisprudência
#       n. 742, a notícia oficial do STJ, e o AgRg no RHC 153.768/MG, que
#       tem número público.
#
#   Nenhuma entrada aqui afirma direito adquirido. Todas descrevem a norma
#   ou a decisão, que é o que um hub educativo pode fazer.
FONTES_JURIDICAS: list[dict[str, Any]] = [
    {
        "fonte": "ANVISA",
        "titulo": "RDC nº 327/2019 — fabricação, importação, prescrição e dispensação de produtos de Cannabis",
        "ano": "2019",
        "periodico": "Diário Oficial da União",
        "pmid": "",
        # Texto oficial completo em PDF. A URL que eu havia escrito antes
        # (gov.br/anvisa/.../cannabis/legislacao) dava 404: era caminho
        # plausível que eu inventei, e só apareceu porque testei.
        "url": "https://bvsms.saude.gov.br/bvs/saudelegis/anvisa/2019/rdc0327_09_12_2019.pdf",
        "resumo": "Resolução da Diretoria Colegiada que cria a categoria de 'produto de Cannabis' e estabelece os requisitos de fabricação, importação, controle de qualidade, prescrição médica, dispensação, monitoramento e fiscalização desses produtos em território nacional, em caráter transitório e excepcional.",
    },
    {
        "fonte": "ANVISA",
        "titulo": "RDC nº 660/2022 — importação de produto derivado de Cannabis por pessoa física",
        "ano": "2022",
        "periodico": "Diário Oficial da União",
        "pmid": "",
        # Página de serviço da própria União, confirmada respondendo 200.
        "url": "https://www.gov.br/pt-br/servicos/solicitar-autorizacao-para-importacao-excepcional-de-produtos-a-base-de-canabidiol",
        "resumo": "Resolução que define os critérios e os procedimentos para a importação, por pessoa física e para uso próprio, de produto derivado de Cannabis mediante prescrição de profissional legalmente habilitado, para tratamento de saúde, substituindo a regra anterior sobre autorização excepcional de importação.",
    },
    {
        "fonte": "Presidência da República",
        "titulo": "Lei nº 11.343/2006, art. 2º, parágrafo único — autorização de plantio para fins medicinais ou científicos",
        "ano": "2006",
        "periodico": "Legislação Federal",
        "pmid": "",
        "url": "https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2006/lei/l11343.htm",
        "resumo": "A Lei de Drogas proíbe o plantio e a cultura de vegetais controlados, mas o parágrafo único do art. 2º ressalva expressamente que a União pode autorizar o plantio, a cultura e a colheita desses vegetais exclusivamente para fins medicinais ou científicos, em local e prazo predeterminados e sob fiscalização. É esta ressalva, vigente há décadas e sem regulamentação específica, que fundamenta boa parte do debate judicial sobre cultivo medicinal no Brasil.",
    },
    {
        "fonte": "STJ",
        "titulo": "Informativo de Jurisprudência n. 742 — salvo-conduto para cultivo doméstico de Cannabis sativa para fins medicinais (6ª Turma, j. 14/06/2022, Rel. Min. Rogerio Schietti Cruz)",
        "ano": "2022",
        "periodico": "Superior Tribunal de Justiça — Informativo de Jurisprudência",
        "pmid": "",
        "url": "https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/14062022-Sexta-Turma-da-salvo-conduto-para-pacientes-cultivarem-Cannabis-com-fim-medicinal.aspx",
        "resumo": "A Sexta Turma do STJ, por unanimidade, concedeu salvo-conduto em habeas corpus preventivo a três pacientes para o cultivo doméstico de Cannabis sativa destinado à produção artesanal de óleo para uso próprio e exclusivamente terapêutico, com prescrição médica e autorização da ANVISA para importação. O colegiado assentou a atipicidade penal da conduta à luz do princípio da lesividade e registrou a ausência de regulamentação específica da matéria. O processo tramita em segredo de justiça, razão pela qual não há número público de autos; a referência verificável é o Informativo n. 742, de 27/06/2022.",
    },
    {
        "fonte": "STJ",
        "titulo": "AgRg no RHC 153.768/MG — 6ª Turma, julgado em 28/06/2022",
        "ano": "2022",
        "periodico": "Superior Tribunal de Justiça",
        "pmid": "",
        "url": "https://www.lexml.gov.br/urn/urn:lex:br:superior.tribunal.justica;turma.6:acordao;rhc:2022-06-28;153768-2188541",
        "resumo": "Agravo regimental em recurso em habeas corpus julgado pela Sexta Turma do STJ no mesmo contexto do cultivo de Cannabis sativa com finalidade medicinal. Diferentemente do caso do Informativo n. 742, este acórdão tem número público de autos, o que permite consulta direta e verificação independente do teor da decisão.",
    },
    {
        "fonte": "STJ",
        "titulo": "Novas concessões de salvo-conduto para cultivo de Cannabis com fins medicinais (2023)",
        "ano": "2023",
        "periodico": "Superior Tribunal de Justiça — Notícias",
        "pmid": "",
        "url": "https://www.stj.jus.br/sites/portalp/Paginas/Comunicacao/Noticias/2023/07062023-Ministros-do-STJ-concedem-salvo-condutos-para-o-cultivo-de-cannabis-com-fins-medicinais.aspx",
        "resumo": "Registro oficial do STJ sobre a continuidade da orientação firmada em 2022, com novas concessões de salvo-conduto para cultivo de Cannabis com finalidade medicinal exclusiva. Demonstra que a decisão de 2022 não foi isolada, mas também não equivale a súmula ou a tese vinculante: cada caso segue sendo analisado individualmente.",
    },
    {
        # FATO NOVO, DE 2026 — achado na pesquisa, não estava na diretriz
        #   Sem esta entrada, todo artigo do pilar jurídico descreveria o
        #   quadro de 2022/2023 e diria que a matéria "carece de
        #   regulamentação específica" -- afirmação que deixou de ser
        #   verdadeira. Fonte desatualizada num hub educativo não é lacuna:
        #   é informação errada com aparência de pesquisa.
        "fonte": "ANVISA",
        "titulo": "ANVISA aprova regras que cumprem decisão do STJ para produção de cannabis medicinal (2026)",
        "ano": "2026",
        "periodico": "Agência Nacional de Vigilância Sanitária — Notícias",
        "pmid": "",
        "url": "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2026/anvisa-aprova-por-unanimidade-regras-que-cumprem-decisao-do-stj-para-producao-de-cannabis-medicinal",
        "resumo": "Deliberação unânime da Diretoria Colegiada da ANVISA aprovando regras destinadas a cumprir decisão do Superior Tribunal de Justiça relativa à produção de cannabis para fins medicinais. É o desenvolvimento que altera o quadro descrito nas decisões de 2022 e 2023, nas quais o próprio STJ registrava a ausência de regulamentação específica da matéria. Qualquer texto sobre o marco regulatório precisa considerar esta etapa, sob pena de descrever um cenário que já mudou.",
    },
]


# As palavras que decidem onde buscar. Comparadas sem acento, pelo mesmo
# motivo do soul_designer: marca escrita à mão nunca bate com texto real.
#   PALAVRA DE DOIS SENTIDOS NÃO SERVE DE MARCA             (04/10/2026)
#
#   O primeiro teste pegou dois erros, e os dois eram de ambiguidade:
#
#     "a REGULAÇÃO da homeostase"   -> caiu em jurídico por "regulacao"
#     "o MANEJO da dor crônica"     -> caiu em cultivo por "manejo"
#
#   Nos dois casos a palavra existe nos dois mundos. A correção tem duas
#   partes: tirar a marca solta e exigir a expressão ("manejo agronomico"),
#   e -- mais importante -- dar marcas próprias ao eixo clínico. Antes ele
#   era só o padrão, sem evidência positiva nenhuma, então qualquer palavra
#   ambígua ganhava sem ter contra quem competir.
#
#   Também saíram: "processo" (processo inflamatório), "cura" (cura do
#   câncer) e "fungo" (infecção fúngica). Todas apareciam em texto clínico.
_MARCAS_JURIDICO = (
    "anvisa", "rdc", "juridic", "legisla", "regulament", "regulacao sanitaria",
    "stj", "stf", "habeas corpus", "salvo-conduto", "salvo conduto",
    "jurisprud", "judicial", "judicializ", "direito", "decreto", "acordao",
    "portaria", "liminar", "crime", "descriminaliz", "marco regulatorio",
    "lei 11.343", "11343", "lei federal", "lei de drogas", "processo judicial",
    "associacao de pacientes", "autorizacao sanitaria",
)
_MARCAS_CULTIVO = (
    "cultivo", "cultivar", "plantio", "botanic", "agronom", "solo", "substrato",
    "nutriente", "nutricao mineral", "fotoperiodo", "estufa", "clone",
    "semente", "colheita", "secagem", "cura da flor", "fenotipo",
    "quimiotipo", "indoor", "outdoor", "irrigacao", "praga",
    "manejo agronomico", "manejo do solo", "manejo de praga", "poda",
    "horticultura", "fitotecnia", "ambiente controlado", "muda",
)
_MARCAS_CLINICO = (
    "dor cronica", "dor neuropatica", "ensaio clinico", "ensaios clinicos",
    "randomizado", "placebo", "coorte", "metanalise", "revisao sistematica",
    "eficacia", "paciente", "tratamento", "epilepsia", "espasticidade",
    "nausea", "quimioterapia", "oncologia", "paliativo", "dose", "posologia",
    "farmacolog", "farmacocinetica", "endocanabinoide", "receptor", "cb1",
    "cb2", "canabidiol", "cbd", "thc", "homeostase", "neurobiolog",
    "ansiedade", "sono", "insonia", "seguranca", "efeito adverso",
    "manejo da dor", "evidencia clinica",
)
_MARCAS_CULTURAL = (
    "historia", "historico", "cultura", "cultural", "sociedade", "social",
    "antropolog", "sociolog", "etnobotanic", "etnografia", "religios",
    "ritual", "tradicao", "colonial", "escravid", "proibicion", "estigma",
    "politica de drogas", "guerra as drogas", "midia", "imprensa", "arte",
    "literatura", "musica", "movimento social", "ativismo",
)


def _eixo_do_tema(consulta: str) -> str:
    """Devolve 'juridico', 'cultivo', 'cultural' ou 'clinico'."""
    alvo = unicodedata.normalize("NFKD", str(consulta or "").lower())
    alvo = "".join(c for c in alvo if not unicodedata.combining(c))
    pontos = {
        "juridico": sum(2 if " " in m else 1 for m in _MARCAS_JURIDICO if m in alvo),
        "cultivo": sum(2 if " " in m else 1 for m in _MARCAS_CULTIVO if m in alvo),
        "cultural": sum(2 if " " in m else 1 for m in _MARCAS_CULTURAL if m in alvo),
        # O clínico concorre em pé de igualdade. Ver o comentário das marcas:
        # sem isto, uma única palavra ambígua desviava o tema inteiro.
        "clinico": sum(2 if " " in m else 1 for m in _MARCAS_CLINICO if m in alvo),
    }
    melhor = max(pontos, key=lambda k: pontos[k])
    # Empate volta para clínico: é o eixo com a fonte mais forte (PubMed) e
    # o único que já estava em produção e testado.
    if pontos[melhor] <= 0 or pontos[melhor] == pontos["clinico"]:
        return "clinico"
    return melhor


def coletar_fontes(consulta: str, urls: list[str] | None = None) -> list[dict[str, Any]]:
    fontes = []

    # ── ROTEAMENTO POR EIXO ──────────────────────────────────── (04/10/2026)
    #
    #   Antes, todo tema ia para o PubMed. Com os quatro pilares editoriais
    #   isso quebra de um jeito silencioso: "história da proibição da
    #   cannabis no Brasil" devolve farmacologia de receptor, o modelo
    #   recebe fontes que não falam do assunto, e o artigo sai citando
    #   estudo clínico para sustentar afirmação histórica.
    #
    #   O eixo decide a ORDEM, não exclui ninguém: o PubMed continua
    #   entrando como reforço em cultivo e cultura, porque farmacologia de
    #   terpeno e uso tradicional aparecem lá também.
    eixo = _eixo_do_tema(consulta)

    if eixo == "juridico":
        # Direito vem da base conferida, não de busca. E vem primeiro.
        fontes.extend(FONTES_JURIDICAS)
        for tentativa in (buscar_openalex, buscar_pubmed):
            try:
                fontes.extend(tentativa(consulta, 6))
            except Exception:
                pass
    elif eixo in ("cultivo", "cultural"):
        try:
            fontes.extend(buscar_openalex(consulta, 10))
        except Exception:
            pass
        try:
            fontes.extend(buscar_pubmed(consulta, 6))
        except Exception:
            pass
        # Tema de cultivo encosta em regulação com frequência: no Brasil,
        # plantar depende de autorização. A base jurídica entra como apoio.
        if eixo == "cultivo":
            fontes.extend(FONTES_JURIDICAS[:3])
    else:
        try:
            fontes = buscar_pubmed(consulta, 12)
        except Exception:
            try:
                fontes = buscar_pubmed("cannabis medicinal pharmacology", 8)
            except Exception:
                pass
        # Rede de segurança: se o PubMed não devolveu nada utilizável, a
        # OpenAlex tenta. Antes, o artigo seguia com duas fontes de
        # preenchimento e um prompt sem base nenhuma.
        if len(fontes) < 3:
            try:
                fontes.extend(buscar_openalex(consulta, 8))
            except Exception:
                pass

    for u in (urls or []):
        try:
            m = buscar_fontes_manuais([u])
            fontes.extend(m)
        except Exception:
            pass

    if not any(f.get("fonte") == "ANVISA" for f in fontes):
        fontes.append({
            "fonte": "ANVISA",
            "titulo": "Marco Regulatório de Cannabis Medicinal no Brasil — RDC nº 327/2019 e RDC nº 660/2022",
            "resumo": "Regulamentação oficial da Agência Nacional de Vigilância Sanitária (ANVISA) que dispõe sobre os procedimentos e requisitos para fabricação, importação, prescrição médica e dispensação de produtos derivados de Cannabis para fins terapêuticos e medicinais no Brasil.",
            "ano": "2022",
            "url": "https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2022/anvisa-aprova-mais-tres-produtos-de-cannabis-para-uso-medicinal"
        })

    if not any(f.get("fonte") == "SciELO/DOI" for f in fontes):
        fontes.append({
            "fonte": "SciELO/DOI",
            "titulo": "Uso terapêutico dos canabinoides: evidências científicas e aspectos farmacológicos no Brasil",
            "resumo": "Estudo clínico e farmacológico sobre a ação dos canabinoides nos receptores do sistema endocanabinoide e vias serotoninérgicas, discutindo evidências clínicas, segurança e farmacocinética.",
            "ano": "2020",
            "url": "https://doi.org/10.1590/1516-4446-2019-0631"
        })

    vistos, saida = set(), []
    for f in fontes:
        u = f.get("url")
        if u and u not in vistos and f.get("resumo"):
            vistos.add(u); saida.append(f)
    return saida[:20]


def _word_count(markdown: str) -> int:
    body = re.sub(r"(?im)^\s*#+\s*(fontes|referências|referencias|bibliografia)\s*$.*\Z", "", markdown or "", flags=re.S)
    body = re.sub(r"https?://\S+", " ", body)
    body = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", body)
    return len(re.findall(r"\b[\wÀ-ÿ]+(?:[-’'][\wÀ-ÿ]+)*\b", body, flags=re.UNICODE))


def _json_from_text(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    
    # 1. Tentar decodificar normalmente
    dec = json.JSONDecoder(strict=False)
    for i, c in enumerate(raw):
        if c == "{":
            try:
                value, _ = dec.raw_decode(raw[i:])
                if isinstance(value, dict):
                    return value
            except ValueError:
                continue

    # 2. Tentar fechar JSON truncado se o modelo cortou no final
    for sufixo in ['"}', '"]}', '}', '"]}}', '"\n}']:
        try:
            val = json.loads(raw + sufixo, strict=False)
            if isinstance(val, dict):
                return val
        except Exception:
            pass

    # 3. Extração resiliente de campos individuais por regex (não perde nada mesmo com corte abrupto)
    resultado = {}
    m_title = re.search(r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw)
    if m_title:
        resultado["title"] = m_title.group(1).encode().decode('unicode_escape', 'ignore')

    m_slug = re.search(r'"slug"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw)
    if m_slug:
        resultado["slug"] = m_slug.group(1)

    m_excerpt = re.search(r'"excerpt"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw)
    if m_excerpt:
        resultado["excerpt"] = m_excerpt.group(1).encode().decode('unicode_escape', 'ignore')

    m_md = re.search(r'"article_markdown"\s*:\s*"((?:[^"\\]|\\.)*)', raw)
    if m_md:
        resultado["article_markdown"] = m_md.group(1).encode().decode('unicode_escape', 'ignore')

    # Slides
    m_slides = re.findall(r'"([^"\\]{10,250})"', raw[raw.find('"slides"'):raw.find('"instagram_caption"')] if '"slides"' in raw else "")
    resultado["slides"] = [s for s in m_slides if s != "slides"][:7]

    m_cap = re.search(r'"instagram_caption"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw)
    if m_cap:
        resultado["instagram_caption"] = m_cap.group(1).encode().decode('unicode_escape', 'ignore')

    m_whats = re.search(r'"whatsapp_summary"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw)
    if m_whats:
        resultado["whatsapp_summary"] = m_whats.group(1).encode().decode('unicode_escape', 'ignore')

    if resultado.get("title") or resultado.get("article_markdown"):
        return resultado

    raise ValueError("O modelo não retornou JSON válido; nenhuma alteração WordPress foi feita.")


def _markdown_html(md: str) -> str:
    """Conversão pequena e segura: saída do modelo nunca vira HTML executável."""
    md = str(md or "").replace("\r\n", "\n")
    out, para, list_open = [], [], False
    def close_list():
        nonlocal list_open
        if list_open:
            out.append("</ul>"); list_open = False
    def inline(s: str) -> str:
        s = _html.escape(s, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        return s
    for line in md.split("\n"):
        line = line.strip()
        if not line:
            if para:
                out.append("<p>%s</p>" % inline(" ".join(para))); para = []
            continue
        m = re.match(r"^#{1,3}\s+(.+)$", line)
        if m:
            if para:
                out.append("<p>%s</p>" % inline(" ".join(para))); para = []
            close_list(); out.append("<h2>%s</h2>" % inline(m.group(1))); continue
        if re.match(r"^[-*]\s+", line):
            if para:
                out.append("<p>%s</p>" % inline(" ".join(para))); para = []
            if not list_open:
                out.append("<ul>"); list_open = True
            out.append("<li>%s</li>" % inline(re.sub(r"^[-*]\s+", "", line))); continue
        close_list(); para.append(line)
    if para: out.append("<p>%s</p>" % inline(" ".join(para)))
    close_list()
    return "\n".join(out)


def _sources_prompt(fontes: list[dict[str, Any]]) -> str:
    return json.dumps([{k: f.get(k, "") for k in ("fonte", "titulo", "ano", "periodico", "pmid", "url", "resumo")} for f in fontes],
                      ensure_ascii=False, indent=2)


def gerar_artigo(tema: str, llm: Callable[[list[dict[str, str]]], str],
                  urls_fontes: list[str] | None = None) -> dict[str, Any]:
    """Gera artigo educacional verificável. LLM callback recebe messages e devolve texto."""
    tema = str(tema or "").strip()
    if len(tema) < 8 or len(tema) > 300:
        raise ValueError("O tema deve ter entre 8 e 300 caracteres.")
    fontes = coletar_fontes(tema, urls_fontes or [])
    refs = "\n".join("[%d] %s — %s (%s). %s" % (i, f["fonte"], f["titulo"], f.get("ano") or "s.d.", f["url"])
                     for i, f in enumerate(fontes, 1))
    system = ("Você é redator científico de educação em saúde, responsável por um rascunho, nunca por diagnóstico ou prescrição. "
              "Use SOMENTE as fontes fornecidas; não invente estudos, números, autores, recomendações, dose, tratamento, eficácia ou aprovação. "
              "Separe mecanismo biológico, evidência clínica e regulação. Indique limitações, controvérsias e necessidade de orientação profissional. "
              "Não recomende iniciar, interromper ou substituir tratamento. Fale em português do Brasil, linguagem clara e rigorosa. "
              "Retorne somente JSON válido, sem markdown externo, com chaves: title, slug, excerpt, article_markdown, tags (array), slides (7 strings), instagram_caption, whatsapp_summary. "
              "article_markdown deve ser um artigo completo e detalhado (700 a 1400 palavras), com seções aprofundadas, subtítulos Markdown (# Introdução, ## Mecanismo Biológico e Receptores, ## Evidências Clínicas, ## Marco Regulatório e Segurança, ## Limitações), subtítulos, citações [1], [2] etc. usando apenas os índices fornecidos, "
              "uma seção de limites da evidência e uma chamada educativa, não comercial. Cada slide deve ter no máximo 35 palavras; legenda e resumo WhatsApp até 150 palavras.")
    # (24/11) VARIEDADE: o redator recebe as palavras ja gastas nos titulos
    # anteriores e a lista do que ja foi publicado, para nao repetir.
    try:
        import soul_variedade
        system += soul_variedade.regra_de_titulo()
    except Exception:
        soul_variedade = None
    user = ("Tema: " + tema + "\n\nFONTES VERIFICADAS — não acrescente referências que não estejam aqui:\n" + _sources_prompt(fontes) +
            "\n\nREFERÊNCIAS CANÔNICAS (links exatos para a seção Fontes):\n" + refs)
    text = llm([{"role": "system", "content": system}, {"role": "user", "content": user}])
    obj = _json_from_text(text)
    title = str(obj.get("title") or "").strip()[:180]
    slug = re.sub(r"[^a-z0-9-]+", "-", str(obj.get("slug") or title.lower()).encode("ascii", "ignore").decode()).strip("-")[:100]
    md = str(obj.get("article_markdown") or "").strip()
    if not title or not slug or not md:
        raise ValueError("O modelo deixou campos obrigatórios vazios; nenhuma alteração WordPress foi feita.")
    # (24/11) Titulo parecido demais com um ja publicado: pede so um titulo
    # novo (chamada curta), em vez de refazer o artigo inteiro.
    if soul_variedade:
        parecido_com = soul_variedade.titulo_repetido(title)
        if parecido_com:
            try:
                novo = llm([{"role": "user", "content":
                    "Crie UM titulo novo, em portugues, ate 70 caracteres, para este artigo. "
                    "Ele NAO pode se parecer com: '" + parecido_com + "'." +
                    soul_variedade.regra_de_titulo() +
                    "\n\nResumo do artigo: " + str(obj.get("excerpt") or md[:600]) +
                    "\n\nResponda so com o titulo, sem aspas."}])
                novo = (novo or "").strip().strip('"').splitlines()[0][:180] if novo else ""
                if len(novo) >= 15 and not soul_variedade.titulo_repetido(novo):
                    title = novo
                    slug = re.sub(r"[^a-z0-9-]+", "-", unicodedata.normalize("NFKD", title.lower())
                                  .encode("ascii", "ignore").decode()).strip("-")[:100]
            except Exception:
                pass
    count = _word_count(md)
    if count < 150 or count > 6000:
        raise ValueError("O artigo tem %d palavras; deve ter no mínimo 150 palavras. Tente de novo." % count)
    refs_used = {int(x) for x in re.findall(r"\[(\d{1,3})\]", md)}
    tags = [str(x).strip()[:60] for x in (obj.get("tags") or []) if str(x).strip()][:12]
    slides = [str(x).strip()[:280] for x in (obj.get("slides") or []) if str(x).strip()]
    while len(slides) < 7:
        slides.append(f"Projeto Soul — Evidência científica e educação em saúde ({len(slides)+1})")
    slides = slides[:7]
    caption = str(obj.get("instagram_caption") or "").strip()
    whatsapp = str(obj.get("whatsapp_summary") or "").strip()
    if len(caption.split()) > 150 or len(whatsapp.split()) > 150:
        raise ValueError("A legenda e a pílula de transmissão devem ter no máximo 150 palavras.")
    # Fontes são anexadas pelo código, não pelo modelo, e assim nunca são inventadas.
    refs_html = "<h2>Fontes consultadas</h2><ol>" + "".join(
        '<li><a href="%s" rel="nofollow noopener">%s</a> — %s</li>' %
        (_html.escape(f["url"], quote=True), _html.escape(f["fonte"] + ": " + f["titulo"]), _html.escape(f.get("ano") or "s.d."))
        for f in fontes) + "</ol>"
    markdown_with_refs = md + "\n\n## Referências verificadas\n\n" + "\n".join(
        "- [%s: %s](%s)" % (f["fonte"], f["titulo"], f["url"]) for f in fontes)
    artigo = {"titulo": title, "slug": slug, "resumo": str(obj.get("excerpt") or "").strip()[:500],
              "markdown": markdown_with_refs, "html": _markdown_html(md) + refs_html,
              "palavras": count, "fontes": fontes, "fontes_usadas": sorted(refs_used),
              "tags": tags, "slides": slides, "legenda_instagram": caption,
              "resumo_whatsapp": whatsapp, "tema": tema}

    # ── DIAGRAMAÇÃO EDITORIAL ──────────────────────────────── (04/10/2026)
    #
    #   O `html` acima continua sendo montado primeiro, de propósito: ele é a
    #   rede de segurança. O soul_designer substitui esse valor por HTML
    #   estilizado, e se ele falhar por qualquer motivo o artigo sai com a
    #   formatação simples em vez de não sair.
    #
    #   Perder a diagramação é contratempo. Perder um artigo pronto, depois
    #   de consultar o PubMed e gastar o motor, é prejuízo.
    #
    #   Importação tardia e dentro do try: módulo novo não pode derrubar o
    #   fluxo que já funcionava se o arquivo não estiver lá.
    try:
        import soul_designer
        enfeitado = soul_designer.diagramar_artigo(artigo)
        if enfeitado and len(enfeitado) > 200:
            artigo["html"] = enfeitado
            artigo["tema_visual"] = soul_designer.escolher_tema(
                tema, title, " ".join(tags))
    except Exception:
        pass
    if soul_variedade:
        try:
            soul_variedade.registrar(artigo)
        except Exception:
            pass
    return artigo


def _safe_outdir(cfg: dict[str, Any], slug: str) -> Path:
    root = Path(str(cfg.get("pasta_saida") or DEFAULT_OUTPUT)).expanduser().resolve()
    dest = (root / slug).resolve()
    if root != dest and root not in dest.parents:
        raise ValueError("Destino do kit social escapou da pasta configurada.")
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _render_carousel(slides: list[str], destination: Path, background: Path | None = None) -> list[str]:
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ImportError:
        return []
    if len(slides) != 7:
        raise ValueError("O carrossel precisa de 7 slides.")
    try:
        font_path = next(p for p in [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf")] if p.exists())
    except StopIteration:
        font_path = None
    titlefont = ImageFont.truetype(str(font_path), 58) if font_path else ImageFont.load_default()
    bodyfont = ImageFont.truetype(str(font_path), 42) if font_path else ImageFont.load_default()
    made = []
    for i, text in enumerate(slides, 1):
        if background and background.is_file():
            im = Image.open(background).convert("RGB")
            im = ImageOps.fit(im, (1080, 1350), method=Image.Resampling.LANCZOS)
            # Painel de contraste reprodutível, sem ocultar a imagem inteira.
            overlay = Image.new("RGBA", im.size, (6, 10, 14, 0))
            od = ImageDraw.Draw(overlay)
            od.rounded_rectangle((48, 120, 1032, 1220), radius=36, fill=(8, 12, 18, 205))
            im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
        else:
            im = Image.new("RGB", (1080, 1350), (14, 24, 32))
            d = ImageDraw.Draw(im)
            d.rectangle((0, 0, 1080, 18), fill=(139, 184, 143))
        d = ImageDraw.Draw(im)
        d.text((92, 70), "SOUL · EDUCAÇÃO EM SAÚDE", font=bodyfont, fill=(207, 232, 207))
        d.text((92, 180), "%02d / 07" % i, font=bodyfont, fill=(157, 192, 139))
        words = text.split(); lines=[]; line=""
        for word in words:
            candidate = (line + " " + word).strip()
            if d.textbbox((0,0), candidate, font=titlefont)[2] <= 880:
                line = candidate
            else:
                if line: lines.append(line)
                line=word
        if line: lines.append(line)
        if len(lines) > 10:
            lines = lines[:10]; lines[-1] = lines[-1].rstrip(".,;:") + "…"
        y = 310
        for line in lines:
            d.text((92, y), line, font=titlefont, fill=(247, 247, 240)); y += 83
        d.text((92, 1180), "Conteúdo educativo · converse com profissional de saúde", font=bodyfont, fill=(203, 213, 203))
        path = destination / ("carrossel-%02d.png" % i)
        im.save(path, format="PNG", optimize=True); made.append(str(path))
    return made


def montar_kit(artigo: dict[str, Any], background: Path | None = None,
               cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or _ler_config()
    dest = _safe_outdir(cfg, artigo["slug"])
    (dest / "artigo.md").write_text(artigo["markdown"] + "\n", encoding="utf-8")
    (dest / "artigo.html").write_text(artigo["html"] + "\n", encoding="utf-8")
    (dest / "fontes.json").write_text(json.dumps(artigo["fontes"], ensure_ascii=False, indent=2), encoding="utf-8")
    (dest / "legenda-tecnica.txt").write_text(artigo["legenda_instagram"] + "\n", encoding="utf-8")
    (dest / "whatsapp.txt").write_text(artigo["resumo_whatsapp"] + "\n", encoding="utf-8")
    imgs = _render_carousel(artigo["slides"], dest, background)
    return {"pasta": str(dest), "artigo": str(dest / "artigo.md"),
            "fontes": str(dest / "fontes.json"), "legenda": str(dest / "legenda-tecnica.txt"),
            "whatsapp": str(dest / "whatsapp.txt"), "carrossel": imgs,
            "fundo": "pipi" if background and background.is_file() else "tipográfico sem capa Pipi",
            "aviso": "Kit social sem imagem Pipi." if not imgs or not (background and background.is_file()) else ""}


def _wp_media(path: Path, cfg: dict[str, Any]) -> int:
    data = path.read_bytes()
    if len(data) > 20_000_000:
        raise ValueError("A capa excede 20 MB.")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "application/octet-stream"
    extra_h = {"Content-Disposition": 'attachment; filename="%s"' % path.name}
    value = _wp_request("POST", "/media", cfg=cfg, raw=data, content_type=mime,
                        extra_headers=extra_h, timeout=60)
    if not isinstance(value, dict) or not value.get("id"):
        raise RuntimeError("WordPress não retornou o ID da mídia.")
    return int(value["id"])


def criar_rascunho(artigo: dict[str, Any], *, capa: Path | None = None,
                   cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or _ler_config()
    media_id = 0
    if capa and Path(capa).is_file():
        try:
            media_id = _wp_media(capa, cfg)
        except Exception as _e_capa:
            print("       [!] Aviso upload imagem WordPress: %s (criando rascunho sem imagem vinculada)..." % _e_capa)
    payload: dict[str, Any] = {"title": artigo["titulo"], "slug": artigo["slug"],
                               "excerpt": artigo["resumo"], "content": artigo["html"],
                               "status": "draft", "comment_status": "closed"}
    if media_id:
        payload["featured_media"] = media_id
    categoria_ids = cfg.get("categorias") or []
    if categoria_ids:
        payload["categories"] = [int(x) for x in categoria_ids if int(x) > 0][:50]
    result = _wp_request("POST", "/posts", payload, cfg=cfg, timeout=60)
    if not isinstance(result, dict) or not result.get("id") or result.get("status") != "draft":
        raise RuntimeError("WordPress não confirmou um post em rascunho; revise antes de repetir para evitar duplicação.")
    edit_link = _safe_site(cfg["url"]).rstrip("/") + "/wp-admin/post.php?post=%d&action=edit" % int(result["id"])
    return {"id": int(result["id"]), "status": "draft", "titulo": artigo["titulo"],
            "link": result.get("link", ""), "edit_link": edit_link,
            "media_id": media_id, "publicado": False}


def listar_rascunhos(limite: int = 20) -> list[dict[str, Any]]:
    limit = max(1, min(50, int(limite)))
    items = _wp_request("GET", "/posts?status=draft&context=edit&per_page=%d&orderby=date&order=desc" % limit)
    if not isinstance(items, list):
        return []
    out=[]
    for p in items:
        title = p.get("title") or {}; content = p.get("content") or {}; excerpt = p.get("excerpt") or {}
        out.append({"id": int(p.get("id") or 0), "titulo": str(title.get("rendered") or ""),
                    "conteudo": _html_text(content.get("rendered") or "", 60000),
                    "resumo": _html_text(excerpt.get("rendered") or "", 2000),
                    "status": p.get("status"), "link": p.get("link", ""),
                    "edit_link": _safe_site(_ler_config()["url"]).rstrip("/") +
                                "/wp-admin/post.php?post=%d&action=edit" % int(p.get("id") or 0)})
    return out


def publicar_rascunho(post_id: int, *, confirmacao_explicita: bool = False) -> dict[str, Any]:
    if not confirmacao_explicita:
        return {"ok": False, "requer_confirmacao": True,
                "mensagem": "A publicação é pública. Revise o rascunho e confirme explicitamente."}
    ident = int(post_id)
    if ident <= 0:
        raise ValueError("ID de rascunho inválido.")
    atual = _wp_request("GET", "/posts/%d?context=edit" % ident)
    if not isinstance(atual, dict) or atual.get("status") != "draft":
        raise RuntimeError("Só é permitido publicar um post que ainda esteja em rascunho.")
    result = _wp_request("POST", "/posts/%d" % ident,
                         {"status": "publish"})
    if not isinstance(result, dict) or result.get("status") != "publish":
        raise RuntimeError("O WordPress não confirmou a publicação.")
    return {"ok": True, "id": ident, "status": "publish", "link": result.get("link", "")}


def _run_job(job_id: str, tema: str, urls: list[str], llm, capa_cb):
    with _LOCK:
        _JOBS[job_id].update(estado="pesquisando", progresso="Consultando fontes verificáveis")
    try:
        article = gerar_artigo(tema, llm, urls)
        background = None
        cover_error = ""
        if capa_cb:
            with _LOCK: _JOBS[job_id].update(estado="capa", progresso="Solicitando capa à Pipi IA")
            try:
                candidate = capa_cb("Imagem editorial educativa, sem folhas de cannabis, sem alegações médicas, sem texto: " + article["titulo"])
                if candidate and Path(candidate).is_file():
                    background = Path(candidate)
            except Exception as exc:
                cover_error = str(exc)[:240]
        cfg = _ler_config()
        kit = montar_kit(article, background, cfg)
        with _LOCK: _JOBS[job_id].update(estado="wordpress", progresso="Criando somente rascunho WordPress")
        draft = criar_rascunho(article, capa=background, cfg=cfg)
        result = {"ok": True, "artigo": article, "kit": kit, "wordpress": draft,
                  "aviso_capa": cover_error or kit.get("aviso", ""), "publicado": False}
        with _LOCK: _JOBS[job_id].update(estado="concluido", progresso="Rascunho criado", resultado=result)
    except Exception as exc:
        with _LOCK: _JOBS[job_id].update(estado="erro", progresso="A execução foi interrompida", erro=str(exc)[:500])


def iniciar_job(tema: str, urls: list[str], llm: Callable, capa_cb: Callable | None = None) -> dict[str, str]:
    tema = str(tema or "").strip()
    if not tema:
        raise ValueError("Informe o tema.")
    if not _resumo_config().get("configurado"):
        raise RuntimeError("Configure e teste a conexão WordPress antes de iniciar o fluxo.")
    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        _JOBS[job_id] = {"id": job_id, "estado": "fila", "progresso": "Na fila", "criado": time.time()}
    threading.Thread(target=_run_job, args=(job_id, tema, urls or [], llm, capa_cb),
                     daemon=True, name="soul-%s" % job_id).start()
    return {"ok": True, "job_id": job_id, "estado": "fila"}


def obter_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(str(job_id))
        return dict(job) if job else None


def listar_jobs() -> list[dict[str, Any]]:
    with _LOCK:
        return [dict(j) for j in sorted(_JOBS.values(), key=lambda x: x.get("criado", 0), reverse=True)]


def criar_rotina(agenda_module, tema_terca: str, tema_quinta: str, hora: str = "09:00",
                 ativa: bool = False) -> dict[str, Any]:
    """Criar duas rotinas semanais nativas do Bigode, desativadas por padrão."""
    temas = [("terca", str(tema_terca or "").strip()), ("quinta", str(tema_quinta or "").strip())]
    if any(len(t) < 8 or len(t) > 300 for _, t in temas):
        raise ValueError("Informe dois temas editoriais de 8 a 300 caracteres.")
    try:
        hh, mm = map(int, hora.split(":")); assert 0 <= hh <= 23 and 0 <= mm <= 59
    except Exception:
        raise ValueError("Horário inválido; use HH:MM.") from None
    existentes = [t for t in agenda_module.listar() if t.get("executor") == "soul_artigo"]
    result=[]
    for dia, tema in temas:
        anterior = next((t for t in existentes if t.get("dia_semana") == dia), {})
        r = agenda_module.salvar({"id": anterior.get("id", ""),
                                  "nome": "Soul · rascunho %s" % dia.title(),
                                  "pergunta": "Criar artigo científico educacional para o tema: " + tema,
                                  "tipo": "semanal", "hora": hora, "dia_semana": dia,
                                  "ativa": bool(ativa), "executor": "soul_artigo", "tema": tema})
        if not r.get("ok"):
            raise RuntimeError(r.get("erro") or "Não foi possível salvar a rotina Soul.")
        result.append({"id": r["id"], "dia": dia, "hora": hora, "ativa": bool(ativa), "tema": tema})
    return {"ok": True, "rotinas": result, "aviso": "Cada execução cria apenas rascunho; nunca publica."}


def executar_rotina(alvo: dict[str, Any], llm: Callable, capa_cb: Callable | None = None) -> dict[str, Any]:
    """Executado pelo scheduler já existente. Erros seguem para o histórico da agenda."""
    if not _resumo_config().get("configurado"):
        raise RuntimeError("WordPress não configurado; nenhum artigo foi gerado.")
    tema = str(alvo.get("tema") or "").strip()
    urls = list(alvo.get("urls_fontes") or [])
    article = gerar_artigo(tema, llm, urls)
    background = None
    if capa_cb:
        try:
            candidate = capa_cb("Imagem editorial educativa, sem texto e sem alegações médicas: " + article["titulo"])
            if candidate and Path(candidate).is_file(): background = Path(candidate)
        except Exception:
            pass  # O agendamento não inventa capa; artigo permanece revisável como rascunho.
    kit = montar_kit(article, background)
    draft = criar_rascunho(article, capa=background)
    return {"texto": "Rascunho Soul criado: %s — %s\nKit: %s\nStatus: draft; não publicado." %
                     (article["titulo"], draft.get("edit_link", ""), kit["pasta"]),
            "acoes": ["WordPress: rascunho %s" % draft["id"]], "wordpress": draft, "kit": kit}
