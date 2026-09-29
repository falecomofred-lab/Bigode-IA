"""Confere se e seguro colocar o Bigode na internet.        (29/09/2026)

Chamado pelo LINK_FIXO.bat antes de ligar o Tailscale Funnel.
Codigo de saida: 0 = pode ligar; 1 = nao pode (o motivo sai na tela).

Nao mostra nem grava nenhuma chave do config.json.

Venure - venure.com.br
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

import autenticacao  # noqa: E402


def main():
    try:
        cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8-sig") or "{}")
    except Exception:
        cfg = {}

    problemas = []
    if not cfg.get("exigir_login", True):
        problemas.append('config.json tem "exigir_login": false -- qualquer pessoa '
                         'com o link entraria sem senha.')
    if not autenticacao.existe_alguem():
        problemas.append("Ainda nao existe conta no Bigode. Abra http://127.0.0.1:7000 "
                         "neste PC e crie a sua ANTES (a primeira conta e a do dono).")
    if cfg.get("cadastro_aberto"):
        problemas.append('config.json tem "cadastro_aberto": true -- quem achar o link '
                         'poderia criar conta. Troque para false.')

    if problemas:
        print()
        for p in problemas:
            print("  [PAREI] " + p)
        return 1
    print("  [ok] Login obrigatorio, conta do dono criada, cadastro fechado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
