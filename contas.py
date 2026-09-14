"""CONTAS — Bigode IA

Ver, promover e apagar contas de acesso ao Bigode.

O que existe na tela do Bigode nao cobre isto: a funcao `remover` do
autenticacao.py se recusa a apagar o DONO -- de proposito, para ninguem
ficar trancado do lado de fora. Para trocar de dono e preciso promover a
outra conta primeiro. E o que este script faz, na ordem certa.

    python contas.py                              so mostra
    python contas.py --dono voce@exemplo.com      passa a ser o dono
    python contas.py --apagar outra@exemplo.com   apaga a conta

O arquivo e salvo com copia de seguranca antes de qualquer mudanca.
Nenhuma senha e lida, mostrada ou alterada aqui.

FECHE O BIGODE ANTES. Com ele aberto, a proxima gravacao do servidor pode
desfazer o que voce mudou.

Venure — venure.com.br · tecnologia propria
"""

import argparse
import datetime
import json
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARQ = BASE / "usuarios.json"


def ler():
    if not ARQ.is_file():
        raise SystemExit("\n  Não achei %s\n" % ARQ)
    d = json.loads(ARQ.read_text(encoding="utf-8"))
    if not isinstance(d, dict) or "usuarios" not in d:
        raise SystemExit("\n  %s não tem o formato esperado.\n" % ARQ.name)
    return d


def gravar(d):
    """Copia primeiro, grava depois. Se o disco falhar no meio, a copia
    continua inteira -- e sem ela ninguem entra mais no Bigode."""
    carimbo = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    copia = ARQ.with_name("usuarios-antes-%s.json" % carimbo)
    shutil.copy2(ARQ, copia)
    ARQ.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  Cópia de segurança: %s" % copia.name)


def mostrar(d):
    print("\n  CONTAS DESTE BIGODE")
    print("  " + "-" * 62)
    for u in d["usuarios"]:
        print("    %-34s %-14s %s%s" % (
            u.get("email", "?"), u.get("nome", ""),
            "DONO  " if u.get("dono") else "      ",
            "· entra pelo %s" % u["provedor"].title()
            if u.get("provedor") not in ("local", None) else ""))
    print()


def achar(d, email):
    email = (email or "").strip().lower()
    for u in d["usuarios"]:
        if (u.get("email") or "").lower() == email:
            return u
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dono", default="", help="e-mail que passa a ser o dono")
    ap.add_argument("--apagar", default="", help="e-mail da conta a apagar")
    ap.add_argument("--sim", action="store_true", help="não perguntar antes")
    args = ap.parse_args()

    d = ler()
    mostrar(d)

    if not args.dono and not args.apagar:
        print("  Para trocar o dono:  python contas.py --dono seu@email.com")
        print("  Para apagar:         python contas.py --apagar outro@email.com\n")
        return 0

    mudou = False

    # ---------------- promover ----------------
    if args.dono:
        u = achar(d, args.dono)
        if not u:
            raise SystemExit("\n  Não existe conta com esse e-mail.\n")
        if u.get("dono"):
            print("  %s já é o dono." % u["email"])
        else:
            for outro in d["usuarios"]:
                outro["dono"] = False
            u["dono"] = True
            mudou = True
            print("  %s passa a ser o DONO." % u["email"])

    # ---------------- apagar ----------------
    if args.apagar:
        u = achar(d, args.apagar)
        if not u:
            raise SystemExit("\n  Não existe conta com esse e-mail.\n")
        if len(d["usuarios"]) <= 1:
            raise SystemExit("\n  É a única conta. Apagar tranca você do lado "
                             "de fora do Bigode.\n")
        if u.get("dono"):
            raise SystemExit(
                "\n  Essa é a conta de DONO. Promova a outra primeiro:\n"
                "    python contas.py --dono OUTRO@EMAIL\n"
                "  Depois volte e apague esta.\n")
        if not args.sim:
            print("\n  Vou apagar %s (%s)." % (u["email"], u.get("nome", "")))
            print("  As conversas e os projetos NÃO são apagados — só o acesso.")
            if input("  Confirma? (s/N) ").strip().lower() != "s":
                print("  Cancelado.\n")
                return 0
        d["usuarios"] = [x for x in d["usuarios"]
                         if (x.get("email") or "").lower()
                         != u["email"].lower()]
        mudou = True
        print("  Apagada: %s" % u["email"])

    if not mudou:
        print("\n  Nada mudou.\n")
        return 0

    if not any(x.get("dono") for x in d["usuarios"]):
        raise SystemExit("\n  Isso deixaria o Bigode sem dono. Cancelado, "
                         "nada foi gravado.\n")

    gravar(d)
    d = ler()
    mostrar(d)
    print("  Pronto. Abra o Bigode e entre com a conta que sobrou.\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n\n  Cancelado. Nada foi alterado.\n")
        raise SystemExit(130)
