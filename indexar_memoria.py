#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REINDEXAR A MEMÓRIA — pelo terminal, vendo o que acontece
Venure · venure.com.br · 20/09/2026

    python indexar_memoria.py

O botão da tela faz a mesma coisa. Este arquivo existe porque indexar com a
placa pode levar minutos e falhar no meio, e a tela devolve só um resumo no
fim -- quando já é tarde para entender o que aconteceu.

Aqui você vê o motor escolhido ANTES de começar, e o erro completo se vier.
"""

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))       # o Python embutido nao poe o proprio dir


def achar_python_do_bigode():
    """O Python portátil do projeto — o único que tem o ChromaDB.

    O `python` do PATH é o do Windows, e nele o chromadb não está
    instalado: rodar por ele dá "ChromaDB não está instalado", que parece
    um problema de instalação e é só o interpretador errado. Já custou uma
    rodada inteira.
    """
    candidatos = [
        Path(r"G:\Outros computadores\USB e dispositivos externos"
             r"\Pen IA\Cerebro\python\python.exe"),
        BASE / "python" / "python.exe",
        BASE.parent / "Pen IA" / "Cerebro" / "python" / "python.exe",
    ]
    for c in candidatos:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def main():
    try:
        import chromadb  # noqa: F401
    except ImportError:
        print()
        print("  [x] Este Python não tem o ChromaDB.")
        print("      Você rodou com: %s" % sys.executable)
        certo = achar_python_do_bigode()
        if certo:
            print()
            print("      O Bigode usa o Python portátil do projeto. Rode assim:")
            print()
            print('      & "%s" indexar_memoria.py' % certo)
        else:
            print()
            print("      Não achei o Python portátil do projeto. Ou instale aqui:")
            print("      python -m pip install chromadb")
        print()
        return 1

    import chroma_memoria as cm

    motor = cm._motor_da_memoria()

    print()
    print("  INDEXAR A MEMÓRIA DO BIGODE")
    print("  " + "-" * 62)
    print("  motor: %s" % ("PLACA (bge-m3, na Modal)" if motor == "placa"
                           else "local (o modelo que vem no ChromaDB)"))

    if motor == "placa":
        print()
        print("  As coleções nascem com sufixo `__placa`, ao lado das antigas.")
        print("  Nada é apagado: desligar a placa devolve a memória de antes.")
    else:
        try:
            import placa_memoria
            motivo = placa_memoria.ultimo_erro() or \
                placa_memoria.situacao().get("ultimo_erro") or ""
        except Exception as erro:
            motivo = str(erro)[:200]
        if motivo:
            print("  (a placa não entrou: %s)" % motivo)
            print("  Se era para ela entrar, rode `python usar_modal_memoria.py`.")

    dominios = cm.dominios_configurados()
    if not dominios:
        print("\n  [x] Nenhum domínio configurado.")
        print("      Configurações > Domínios de memória, na tela do Bigode.")
        return 1

    print()
    for nome, item in dominios.items():
        pastas = item.get("pastas") or []
        print("  %-14s %s" % (nome, ", ".join(pastas) or "(sem pasta!)"))

    print("\n  Indexando… (com a placa, o primeiro lote acorda a máquina)")
    resumo = cm.indexar_dominios()

    print()
    for nome, dados in (resumo.get("colecoes") or {}).items():
        print("  [ok] %-14s %d arquivos, %d blocos novos, %d no total"
              % (nome, dados.get("arquivos", 0), dados.get("blocos", 0),
                 dados.get("total", 0)))

    erros = resumo.get("erros") or []
    if erros:
        print()
        for e in erros[:10]:
            print("  [!]  %s" % e)
        if len(erros) > 10:
            print("  [!]  … e mais %d" % (len(erros) - 10))

    if resumo.get("ok") is False:
        print("\n  PAROU NO MEIO. Nada ficou pela metade dentro do índice.")
        return 1

    print("\n  Pronto. Faça uma pergunta ao Bigode sobre um dos domínios.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
