# -*- coding: utf-8 -*-
"""
TESTES REAIS DO BIGODE — rode ANTES e DEPOIS de qualquer mudança no código.
Venure · venure.com.br · 24/11/2026

Duplo clique em TESTAR_BIGODE.bat (com o Bigode aberto).

Manda as perguntas de perguntas.json para o Bigode, como um usuário faria,
e confere: respondeu? em quanto tempo? usou a ferramenta certa? entrou em
laço? O resultado vai para testes_reais/relatorio_AAAA-MM-DD_HHMM.md.

Só para rodar um teste:   python rodar_testes.py 2
"""
import datetime
import json
import sys
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BASE = AQUI.parent
MEDICOES = BASE / "memoria" / "medicoes.jsonl"
URL = "http://127.0.0.1:7000/api/chat"


def ultima_medicao():
    try:
        linhas = MEDICOES.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
        return json.loads(linhas[-1]) if linhas else {}
    except Exception:
        return {}


def perguntar(teste):
    msgs = []
    for h in teste.get("historico", []):
        msgs += [{"role": "user", "content": h}, {"role": "assistant", "content": "ok"}]
    msgs.append({"role": "user", "content": teste["pergunta"]})
    corpo = json.dumps({"mensagens": msgs, "modo": teste.get("modo", "auto")}).encode("utf-8")
    pedido = urllib.request.Request(URL, data=corpo, headers={"Content-Type": "application/json"})
    texto, erro, inicio = "", "", time.time()
    with urllib.request.urlopen(pedido, timeout=int(teste.get("max_s", 300)) + 120) as r:
        for linha in r:
            linha = linha.decode("utf-8", "replace").strip()
            if not linha.startswith("data:"):
                continue
            try:
                ev = json.loads(linha[5:])
            except Exception:
                continue
            if ev.get("tipo") == "texto":
                texto += ev.get("texto", "")
            elif ev.get("tipo") == "descartar":
                texto = ""
            elif ev.get("tipo") == "erro":
                erro = ev.get("texto", "")
            elif ev.get("tipo") == "fim":
                break
    return texto, erro, time.time() - inicio


def main():
    testes = json.loads((AQUI / "perguntas.json").read_text(encoding="utf-8"))
    if len(sys.argv) > 1:
        ids = {int(x) for x in sys.argv[1:] if x.isdigit()}
        testes = [t for t in testes if t["id"] in ids]
    linhas, passou = [], 0
    for t in testes:
        print("Teste %d (%s): %s" % (t["id"], t["modo"], t["pergunta"][:60]), flush=True)
        antes = ultima_medicao().get("quando")
        try:
            texto, erro, gasto = perguntar(t)
        except Exception as e:
            texto, erro, gasto = "", "sem resposta: %s" % e, 0
        med = ultima_medicao()
        if med.get("quando") == antes:
            med = {}
        usadas = med.get("ferramentas_usadas", [])
        problemas = []
        if erro:
            problemas.append("erro: " + erro[:120])
        if not texto.strip() and not erro:
            problemas.append("resposta vazia")
        if gasto > t.get("max_s", 300):
            problemas.append("lento (%.0fs > %ds)" % (gasto, t["max_s"]))
        if "max_passos" in t and med.get("passos", 0) > t["max_passos"]:
            problemas.append("%d passos (máx %d)" % (med.get("passos", 0), t["max_passos"]))
        if t.get("ferramenta") and t["ferramenta"] not in usadas:
            problemas.append("não usou %s" % t["ferramenta"])
        for proibido in t.get("sem_texto", []):
            if proibido.lower() in texto.lower():
                problemas.append("apareceu '%s'" % proibido)
        ok = not problemas
        passou += ok
        print("   %s  %.0fs  %s" % ("OK " if ok else "FALHOU", gasto, "; ".join(problemas)), flush=True)
        linhas.append("| %d | %s | %s | %.0f s | %s | %s | %s |" % (
            t["id"], t["modo"], t["pergunta"][:50].replace("|", "/"), gasto,
            med.get("tokens_entrada", "?"), ", ".join(usadas) or "—",
            "OK" if ok else "FALHOU: " + "; ".join(problemas)))
    agora = datetime.datetime.now()
    rel = AQUI / ("relatorio_%s.md" % agora.strftime("%Y-%m-%d_%H%M"))
    rel.write_text(
        "# Testes reais do Bigode — %s\n\n**%d de %d passaram.**\n\n"
        "| # | Modo | Pergunta | Tempo | Tokens lidos | Ferramentas | Resultado |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n%s\n"
        % (agora.strftime("%d/%m/%Y %H:%M"), passou, len(testes), "\n".join(linhas)),
        encoding="utf-8")
    print("\n%d de %d passaram. Relatório: %s" % (passou, len(testes), rel))
    return 0 if passou == len(testes) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        if "--sem-pausa" not in sys.argv:
            input("\nAperte Enter para fechar...")
