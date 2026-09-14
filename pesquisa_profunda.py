"""Pesquisa aprofundada nativa do Bigode IA.

O módulo pesquisa em várias consultas, abre fontes encontradas e pede ao modelo
ativo uma síntese com citações. Não depende do Manus nem de uma chave externa.
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

_JOBS = {}
_LOCK = threading.Lock()
_URL = re.compile(r"https?://[^\s<>()\]\[\"']+")


def _novo(consulta):
    jid = uuid.uuid4().hex[:16]
    with _LOCK:
        _JOBS[jid] = {"ok": True, "job_id": jid, "estado": "fila",
                      "consulta": consulta, "fontes": [], "texto": "",
                      "erro": "", "criado_em": time.time()}
    return jid


def obter(job_id):
    with _LOCK:
        return dict(_JOBS.get(job_id) or {})


def _atualizar(job_id, **mudancas):
    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id].update(mudancas)


def _consultas(consulta):
    q = consulta.strip()
    return [q, f"{q} fontes oficiais dados recentes", f"{q} análise comparação riscos limitações"]


def _urls(texto):
    saida = []
    for url in _URL.findall(texto or ""):
        url = url.rstrip(".,;:)")
        if "duckduckgo.com" in url or "mojeek.com" in url:
            continue
        if url not in saida:
            saida.append(url)
    return saida


def iniciar(consulta, buscar, ler, sintetizar):
    consulta = str(consulta or "").strip()
    if not consulta:
        raise ValueError("Informe o tema que deseja pesquisar.")
    jid = _novo(consulta)
    threading.Thread(target=_rodar, args=(jid, consulta, buscar, ler, sintetizar), daemon=True).start()
    return obter(jid)


def _rodar(jid, consulta, buscar, ler, sintetizar):
    try:
        _atualizar(jid, estado="pesquisando")
        resultados = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            tarefas = {pool.submit(buscar, q): q for q in _consultas(consulta)}
            for futuro in as_completed(tarefas):
                q = tarefas[futuro]
                try:
                    resultados.append((q, str(futuro.result())))
                except Exception as erro:
                    resultados.append((q, "Falha na busca: %s" % erro))
        urls = []
        for _, resultado in resultados:
            for url in _urls(resultado):
                if url not in urls:
                    urls.append(url)
        urls = urls[:8]
        _atualizar(jid, estado="lendo", fontes=urls)
        leituras = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            tarefas = {pool.submit(ler, url): url for url in urls}
            for futuro in as_completed(tarefas):
                url = tarefas[futuro]
                try:
                    leituras[url] = str(futuro.result())
                except Exception as erro:
                    leituras[url] = "Falha ao ler fonte: %s" % erro
        pacote = []
        for q, resultado in resultados:
            pacote.append("BUSCA COMPLEMENTAR: %s\n%s" % (q, resultado))
        for i, url in enumerate(urls, 1):
            pacote.append("FONTE [%d] %s\n%s" % (i, url, leituras.get(url, "")))
        _atualizar(jid, estado="sintetizando")
        prompt = (
            "Você é o pesquisador do Bigode IA. Responda em português brasileiro. "
            "Use somente as evidências abaixo; não invente fatos. Faça uma síntese "
            "clara e didática, destaque convergências e divergências, informe "
            "limitações e termine com Referências numeradas no formato [1], [2]. "
            "Quando uma afirmação não estiver confirmada, diga explicitamente.\n\n"
            "TEMA:\n%s\n\nEVIDÊNCIAS:\n%s" % (consulta, "\n\n".join(pacote)[:50000])
        )
        texto = sintetizar(prompt)
        _atualizar(jid, estado="concluido", texto=str(texto), fontes=urls,
                   finalizado_em=time.time())
    except Exception as erro:
        _atualizar(jid, estado="erro", erro=str(erro))


__all__ = ["iniciar", "obter"]
