"""MODELOS NO DISCO DO COMPUTADOR — Bigode IA

Copia as IAs do pendrive para o disco interno e avisa o Bigode onde elas
estao. Uma coisa so, sem voce editar arquivo nenhum.

    python usar_modelos_do_disco.py

POR QUE ISSO AJUDA

O pendrive e USB. Cada leitura do arquivo de 4 GB passa por um cabo lento.
O disco do computador e muitas vezes mais rapido, e o Bigode reconhece
sozinho a diferenca: modelo no C: ele le "sob demanda" (mais rapido de
ligar); modelo no pendrive ele carrega inteiro antes (evita o USB engasgar
no meio da conversa).

O QUE ELE NAO FAZ

Nao apaga nada do pendrive. Os arquivos ficam nos dois lugares -- se voce
levar o pendrive para outra maquina, continua funcionando la.

Nao promete milagre: se a maquina for lenta para este tamanho de modelo,
copiar para o disco ajuda a LIGAR mais rapido, nao a PENSAR mais rapido.
Quem responde isso e o medir_maquina.py.

Venure — venure.com.br · tecnologia propria
"""

import json
import shutil
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
DESTINO = Path(r"C:\Bigode-Modelos")

# Onde procurar. A raiz do pendrive e a pasta do Bigode sao os dois lugares
# que o proprio Bigode ja varre.
ONDE_PROCURAR = [BASE.anchor and Path(BASE.anchor), BASE, BASE / "modelos"]


def gb(caminho):
    return caminho.stat().st_size / 1e9


def copiar_com_barra(origem, destino):
    """shutil.copy sozinho fica mudo por minutos num arquivo de 4 GB, e a
    pessoa nao sabe se travou. Aqui a barra anda."""
    total = origem.stat().st_size
    feito = 0
    t0 = time.time()
    with origem.open("rb") as e, destino.open("wb") as s:
        while True:
            pedaco = e.read(4 * 1024 * 1024)
            if not pedaco:
                break
            s.write(pedaco)
            feito += len(pedaco)
            pct = feito * 100 // total
            barra = "#" * (pct // 4) + "." * (25 - pct // 4)
            sys.stdout.write("\r     [%s] %3d%%  %.1f/%.1f GB"
                             % (barra, pct, feito / 1e9, total / 1e9))
            sys.stdout.flush()
    sys.stdout.write("\r     [%s] 100%%  %.1f GB em %.0fs%s\n"
                     % ("#" * 25, total / 1e9, time.time() - t0, " " * 12))


def main():
    print()
    print("=" * 66)
    print("  LEVAR AS IAs PARA O DISCO DO COMPUTADOR")
    print("=" * 66)

    # ---------- achar ----------
    achados, vistos = [], set()
    for pasta in ONDE_PROCURAR:
        if not pasta or not pasta.exists():
            continue
        for arq in sorted(pasta.glob("*.gguf")):
            if arq.name.lower() in vistos:
                continue
            vistos.add(arq.name.lower())
            achados.append(arq)

    if not achados:
        print("\n  Nao achei arquivo .gguf nenhum.")
        print("  Rode de dentro da pasta do Bigode, no pendrive.\n")
        return 1

    print("\n  Achei:")
    for a in achados:
        print("    %-52s %.1f GB" % (a.name[:52], gb(a)))

    # ---------- espaco ----------
    precisa = sum(a.stat().st_size for a in achados)
    try:
        livre = shutil.disk_usage(DESTINO.anchor).free
    except Exception:
        livre = 0
    print("\n  Precisa de %.1f GB. Livre no %s: %.1f GB."
          % (precisa / 1e9, DESTINO.anchor, livre / 1e9))
    if livre and livre < precisa * 1.15:
        print("\n  Nao ha espaco com folga. Libere espaco e tente de novo.\n")
        return 1

    print("\n  Vou copiar para: %s" % DESTINO)
    print("  Nada e apagado do pendrive.")
    if input("\n  Pode copiar? (s/N) ").strip().lower() != "s":
        print("  Cancelado.\n")
        return 0

    # ---------- copiar ----------
    DESTINO.mkdir(parents=True, exist_ok=True)
    copiados = 0
    for a in achados:
        alvo = DESTINO / a.name
        if alvo.exists() and alvo.stat().st_size == a.stat().st_size:
            print("\n  %s  ja estava la, do mesmo tamanho." % a.name[:48])
            copiados += 1
            continue
        print("\n  %s" % a.name[:56])
        try:
            copiar_com_barra(a, alvo)
            if alvo.stat().st_size != a.stat().st_size:
                print("     A copia saiu incompleta. Apagando.")
                alvo.unlink()
                continue
            copiados += 1
        except Exception as e:
            print("\n     Falhou: %s" % e)
            if alvo.exists():
                try:
                    alvo.unlink()
                except Exception:
                    pass

    if not copiados:
        print("\n  Nada foi copiado.\n")
        return 1

    # ---------- avisar o Bigode ----------
    # Sem este passo o Bigode nao ve os arquivos novos: ele so varre a raiz
    # do pendrive e a propria pasta.
    cfg = BASE / "config.json"
    try:
        dados = json.loads(cfg.read_text(encoding="utf-8"))
        pastas = dados.get("pastas_modelos") or []
        if str(DESTINO) not in pastas:
            pastas.insert(0, str(DESTINO))       # primeiro: prefere o disco
            dados["pastas_modelos"] = pastas
            copia = cfg.with_name("config-antes.json")
            shutil.copy2(cfg, copia)
            cfg.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            print("\n  Avisei o Bigode. (copia do config em %s)" % copia.name)
        else:
            print("\n  O Bigode ja conhecia essa pasta.")
    except Exception as e:
        print("\n  Copiei os arquivos, mas nao consegui avisar o Bigode (%s)." % e)
        print("  Abra o config.json e acrescente, dentro das chaves:")
        print('      "pastas_modelos": ["%s"],' % str(DESTINO).replace("\\", "\\\\"))

    print()
    print("=" * 66)
    print("  PRONTO — %d arquivo(s) no disco" % copiados)
    print("=" * 66)
    print()
    print("  Agora:")
    print("   1. Feche a janela do MOTOR e a do BIGODE.")
    print("   2. Abra o Bigode de novo.")
    print("   3. Em Configuracoes, clique em LIGAR no modelo que quiser.")
    print()
    print("  Os modelos vao aparecer uma vez so na lista, mesmo estando nos")
    print("  dois lugares -- o Bigode prefere o do disco.")
    print()
    print("  Depois, meca:  python medir_maquina.py")
    print("  Se o tempo nao mudar, o gargalo nao era o pendrive.")
    print()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n\n  Cancelado.\n")
        raise SystemExit(130)
