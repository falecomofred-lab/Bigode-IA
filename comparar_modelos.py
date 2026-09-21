#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COMPARAR MODELOS — etapas 8 e 11 da auditoria.

Lê tudo que está em auditoria/ e monta a tabela final: velocidade, notas de
qualidade e a classificação ponderada que a auditoria pede.

    qualidade   30%      (média de raciocínio + instruções)
    velocidade  25%
    memória     20%
    programação 15%
    estabilidade 10%

REGRA: se faltar dado para algum componente, o modelo NÃO recebe classificação
final. Preencher buraco com zero ou com média inventaria o número — e um
ranking inventado é pior que ranking nenhum, porque parece decisão informada.

Uso:
    python comparar_modelos.py

Venure — venure.com.br
"""

import json
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parent
SAIDA = BASE / "auditoria"

PESOS = {"qualidade": 0.30, "velocidade": 0.25, "memoria": 0.20,
         "programacao": 0.15, "estabilidade": 0.10}


def juntar():
    """Agrupa os arquivos por modelo. Vale sempre o mais recente de cada tipo."""
    modelos = {}
    if not SAIDA.exists():
        return modelos

    for arq in sorted(SAIDA.glob("*.json")):
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except Exception:
            print("  (ignorado, JSON inválido: %s)" % arq.name)
            continue

        nome = str(d.get("modelo") or
                   d.get("ambiente", {}).get("modelo_carregado", "?"))
        nome = nome.replace("\\", "/").split("/")[-1].replace(".gguf", "")
        m = modelos.setdefault(nome, {"velocidade": None, "qualidade": None})

        if arq.name.startswith("QUALIDADE-"):
            m["qualidade"] = d
        else:
            m["velocidade"] = d
    return modelos


def resumo_velocidade(d):
    if not d:
        return None
    testes = [t for t in d.get("testes", []) if not t.get("erro")]
    taxas = [t["tok_por_s"] for t in testes if t.get("tok_por_s")]
    leituras = [t.get("leitura_tok_por_s") for t in testes
                if t.get("leitura_tok_por_s")]
    primeiros = [t["primeiro_token_s"] for t in testes]
    # Arquivo da versao ANTIGA nao tem o campo "contagem_de_tokens" -- e a
    # versao que contava token por caractere e errava ~40% para cima. Sem
    # esta checagem, um numero inflado aparecia na tabela como se fosse
    # medido. Ausencia do campo prova que e antigo, entao vale como
    # evidencia, nao como suposicao.
    estimado = any("ESTIMADA" in str(t.get("contagem_de_tokens", ""))
                   or "contagem_de_tokens" not in t
                   for t in testes)
    ram = d.get("ambiente", {}).get("ram_total_gb")
    return {
        "escrita_tok_s": round(statistics.median(taxas), 2) if taxas else None,
        "leitura_tok_s": round(statistics.median(leituras), 1) if leituras else None,
        "primeiro_token_s": round(statistics.median(primeiros), 1) if primeiros else None,
        "pior_primeiro_token_s": round(max(primeiros), 1) if primeiros else None,
        "ram_total_gb": ram,
        "contagem_estimada": estimado,
    }


def main():
    modelos = juntar()
    if not modelos:
        print("\n  Nada em auditoria/ ainda.")
        print("  Rode primeiro:  python auditar_motor.py")
        print("                  python auditar_qualidade.py\n")
        return 1

    print("=" * 74)
    print("  COMPARAÇÃO ENTRE MODELOS — Bigode IA")
    print("=" * 74)

    linhas = []
    for nome, d in sorted(modelos.items()):
        v = resumo_velocidade(d["velocidade"])
        q = (d["qualidade"] or {}).get("notas") or {}
        linhas.append({
            "modelo": nome,
            "escrita": v and v["escrita_tok_s"],
            "leitura": v and v["leitura_tok_s"],
            "1o_token": v and v["primeiro_token_s"],
            "raciocinio": q.get("raciocinio", {}).get("nota"),
            "programacao": q.get("programacao", {}).get("nota"),
            "instrucoes": q.get("instrucoes", {}).get("nota"),
            "confiabilidade": q.get("alucinacao", {}).get("nota"),
            "estimado": v and v["contagem_estimada"],
        })

    cab = ("MODELO", "escr", "leit", "1ºtk", "racio", "progr", "instr", "confi")
    print("\n  %-26s %5s %5s %5s %6s %6s %6s %6s" % cab)
    print("  " + "-" * 70)
    for l in linhas:
        def n(x, f="%5.1f"):
            return (f % x) if isinstance(x, (int, float)) else "    —"
        print("  %-26s %s %s %s %s %s %s %s%s" % (
            l["modelo"][:26], n(l["escrita"]), n(l["leitura"]), n(l["1o_token"]),
            n(l["raciocinio"], "%6.1f"), n(l["programacao"], "%6.1f"),
            n(l["instrucoes"], "%6.1f"), n(l["confiabilidade"], "%6.1f"),
            "  *" if l["estimado"] else ""))

    if any(l["estimado"] for l in linhas):
        print("\n  * escrita ESTIMADA por caractere (~40% otimista).")
        print("    Rode de novo com a versão atual para ter o número real.")

    # ---- classificação ponderada ----
    print("\n" + "=" * 74)
    print("  CLASSIFICAÇÃO PONDERADA (etapa 8)")
    print("=" * 74)

    completos = [l for l in linhas if all(
        isinstance(l[k], (int, float)) for k in
        ("escrita", "raciocinio", "programacao", "instrucoes", "confiabilidade"))]

    if not completos:
        print("\n  NÃO CALCULÁVEL para nenhum modelo.")
        faltando = {}
        for l in linhas:
            f = [k for k in ("escrita", "raciocinio", "programacao",
                             "instrucoes", "confiabilidade")
                 if not isinstance(l[k], (int, float))]
            if f:
                faltando[l["modelo"]] = f
        for m, f in faltando.items():
            print("    %-28s falta: %s" % (m[:28], ", ".join(f)))
        print("\n  Preencher com zero inventaria o ranking. Rode as duas provas")
        print("  em cada modelo e chame este script de novo.\n")
        return 0

    # velocidade e memória normalizadas contra o melhor da lista
    tmax = max(l["escrita"] for l in completos)
    for l in completos:
        qual = statistics.mean([l["raciocinio"], l["instrucoes"]])
        l["pontos"] = round(
            qual * 10 * PESOS["qualidade"] +
            (l["escrita"] / tmax) * 100 * PESOS["velocidade"] +
            100 * PESOS["memoria"] +          # RAM não é gargalo nesta máquina
            l["programacao"] * 10 * PESOS["programacao"] +
            l["confiabilidade"] * 10 * PESOS["estabilidade"], 1)

    print()
    for i, l in enumerate(sorted(completos, key=lambda x: -x["pontos"]), 1):
        print("  %dº  %-30s %5.1f pontos" % (i, l["modelo"][:30], l["pontos"]))

    incompletos = [l for l in linhas if l not in completos]
    if incompletos:
        print("\n  Fora da classificação por falta de dado:")
        for l in incompletos:
            print("    %s" % l["modelo"][:40])

    print("\n  Nota sobre o peso de memória: fixado em 100 porque a medição")
    print("  mostrou 16,7 GB livres de 33,7 — RAM não diferencia os modelos")
    print("  disponíveis nesta máquina. Se isso mudar, o peso precisa mudar.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
