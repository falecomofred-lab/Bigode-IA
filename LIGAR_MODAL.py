# -*- coding: utf-8 -*-
"""
LIGAR O MOTOR DA MODAL NO BIGODE — sem precisar lembrar de senha
Venure · venure.com.br · 24/11/2026

Rode uma vez (duplo clique em LIGAR_MODAL.bat). Ele:

  1. Acorda o app `bigode-motor` (Qwen 7B numa placa L4) na Modal.
  2. Procura a senha (token) que ja existe nos arquivos do projeto
     e testa cada uma conversando de verdade com o modelo.
  3. Se nenhuma servir, CRIA uma senha nova, grava na Modal
     (segredo `bigode-token`) e republica o motor.
  4. So grava no config.json o que respondeu de verdade.

Depois disso, o bigodeepipi.bat / BIGODE.bat ja abre usando a Modal e
acorda a placa sozinho na partida.

A senha NUNCA aparece na tela.

Para voltar ao motor do seu computador:
    python LIGAR_MODAL.py --desligar
"""
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"
PIPI_MODAL = BASE.parent / "Pipi IA" / "modal.json"

# Endereco do app bigode-motor (funcao `servidor`) no workspace falecomofred-lab.
# Padrao da Modal: https://<workspace>--<app>-<funcao>.modal.run
ENDERECO = os.environ.get(
    "BIGODE_MODAL_URL",
    "https://falecomofred-lab--bigode-motor-servidor.modal.run").rstrip("/")
CHAT = ENDERECO + "/v1/chat/completions"
SAUDE = ENDERECO + "/health"


def ler_json(caminho):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8-sig") or "{}")
    except Exception:
        return {}


def gravar_config(dados):
    CONFIG.write_text(json.dumps(dados, ensure_ascii=False, indent=2),
                      encoding="utf-8")


def http(url, corpo=None, token="", timeout=60):
    cab = {"Content-Type": "application/json"}
    if token:
        cab["Authorization"] = "Bearer " + token
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    pedido = urllib.request.Request(url, data=dados, headers=cab,
                                    method="POST" if dados else "GET")
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:300]
    except Exception as e:
        return 0, str(e)[:300]


def acordar(minutos=10):
    """Espera o /health responder 200. Container frio leva 30 s a alguns minutos."""
    print("  Acordando a placa na Modal (pode levar ate %d min)" % minutos, end="", flush=True)
    fim = time.time() + minutos * 60
    while time.time() < fim:
        cod, _ = http(SAUDE, timeout=120)
        if cod == 200:
            print(" pronta.")
            return True
        print(".", end="", flush=True)
        time.sleep(5)
    print(" nao respondeu.")
    return False


def testar(token):
    """True se o modelo respondeu texto com esta senha."""
    corpo = {"messages": [{"role": "user", "content": "Responda apenas: ok"}],
             "max_tokens": 8, "temperature": 0, "stream": False}
    for _ in range(3):
        cod, txt = http(CHAT, corpo, token=token, timeout=300)
        if cod == 200:
            try:
                msg = json.loads(txt)["choices"][0]["message"]
                return bool((msg.get("content") or "").strip() or msg.get("tool_calls"))
            except Exception:
                return False
        if cod in (401, 403):
            return False
        time.sleep(10)          # 503 = ainda carregando o modelo
    return False


def senhas_do_projeto():
    """Senhas ja guardadas no projeto (sem mostrar nenhuma)."""
    achadas = []
    cfg = ler_json(CONFIG)
    m = cfg.get("modal") or {}
    achadas.append(m.get("token"))
    for p in (m.get("perfis") or {}).values():
        achadas.append((p or {}).get("token"))
    achadas.append(os.environ.get("BIGODE_TOKEN"))
    achadas.append(os.environ.get("COMFY_TOKEN"))
    pipi = ler_json(PIPI_MODAL)
    achadas.append(pipi.get("token"))
    achadas.append((pipi.get("edicao_modal") or {}).get("token"))
    vistas, saida = set(), []
    for s in achadas:
        s = (s or "").strip()
        if s and s not in vistas:
            vistas.add(s)
            saida.append(s)
    return saida


def comando_modal():
    """Acha o programa `modal` (o mesmo que publicou os apps)."""
    candidatos = [[sys.executable, "-m", "modal"], ["py", "-m", "modal"],
                  ["python", "-m", "modal"]]
    if shutil.which("modal"):
        candidatos.insert(0, ["modal"])
    for c in candidatos:
        try:
            r = subprocess.run(c + ["--version"], capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                return c
        except Exception:
            continue
    return None


def criar_senha_nova():
    """Cria senha nova, grava no segredo bigode-token e republica o motor."""
    nova = secrets.token_urlsafe(32)
    modal = comando_modal()
    if modal:
        print("  Gravando a senha nova na Modal (segredo bigode-token)...")
        r = subprocess.run(modal + ["secret", "create", "bigode-token",
                                    "BIGODE_TOKEN=" + nova, "--force"],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            print("  [!] A Modal recusou: " + (r.stderr or r.stdout)[-300:].replace(nova, "***"))
            return None
        print("  Republicando o motor (1 a 5 min)...")
        amb = dict(os.environ, BIGODE_PERFIL="conversa", PYTHONIOENCODING="utf-8")
        r = subprocess.run(modal + ["deploy", "modal_motor.py"], cwd=str(BASE),
                           env=amb, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            print("  [!] O deploy falhou: " + (r.stderr or r.stdout)[-400:])
            return None
        return nova

    # Sem o programa modal neste computador: voce cola a senha no site.
    print()
    print("  O programa 'modal' nao esta instalado neste computador.")
    print("  Vou copiar uma senha nova para a sua area de transferencia")
    print("  e abrir a pagina de Segredos da Modal.")
    try:
        subprocess.run("clip", input=nova, text=True, shell=True, timeout=10)
    except Exception:
        print("  [!] Nao consegui copiar. Instale com:  py -m pip install modal")
        return None
    webbrowser.open("https://modal.com/secrets/falecomofred-lab/main")
    print()
    print("  No site: abra 'bigode-token' > Edit > no campo BIGODE_TOKEN")
    print("  apague o valor antigo e aperte Ctrl+V > Save.")
    print("  Depois, em Apps > bigode-motor, clique em 'Stop app' se ele")
    print("  estiver rodando (ele volta sozinho com a senha nova).")
    input("\n  Quando terminar, aperte Enter aqui... ")
    return nova


def salvar(token):
    cfg = ler_json(CONFIG)
    antigo = dict(cfg.get("modal") or {})
    perfis = dict(antigo.get("perfis") or {})
    perfis["conversa"] = {"url": CHAT, "health_url": SAUDE, "token": token}
    cfg["modal"] = {"ativo": True, "url": CHAT, "health_url": SAUDE,
                    "token": token, "perfil": "conversa", "perfis": perfis}
    cfg["modelo_provedor"] = "modal"
    gravar_config(cfg)


def desligar():
    cfg = ler_json(CONFIG)
    m = dict(cfg.get("modal") or {})
    m["ativo"] = False
    cfg["modal"] = m
    cfg["modelo_provedor"] = "local"
    gravar_config(cfg)
    print("\n  Pronto. O Bigode volta a usar o motor do seu computador.\n")


def main():
    if "--desligar" in sys.argv:
        return desligar()
    print()
    print("=" * 64)
    print("  LIGAR O MOTOR DA MODAL NO BIGODE")
    print("=" * 64)
    print("  Endereco: " + ENDERECO)
    print()
    if not acordar():
        print("\n  A Modal nao respondeu. Confira em modal.com > Apps se o")
        print("  'bigode-motor' esta Deployed. Nada foi alterado.\n")
        return 1

    for i, s in enumerate(senhas_do_projeto(), 1):
        print("  Testando a senha guardada n.%d..." % i, end=" ", flush=True)
        if testar(s):
            print("funcionou.")
            salvar(s)
            print("\n  PRONTO. O Bigode agora usa a Modal.")
            print("  Abra pelo bigodeepipi.bat normalmente.\n")
            return 0
        print("nao serve.")

    print("\n  Nenhuma senha guardada serviu. Vou criar uma nova.")
    nova = criar_senha_nova()
    if not nova:
        print("\n  Nada foi alterado no Bigode.\n")
        return 1
    acordar()
    if testar(nova):
        salvar(nova)
        print("\n  PRONTO. Senha nova criada e guardada. O Bigode agora usa a Modal.")
        print("  Abra pelo bigodeepipi.bat normalmente.\n")
        return 0
    print("\n  [!] O motor ainda recusa a senha nova. Espere 2 minutos e")
    print("      rode este arquivo de novo. Nada foi alterado no Bigode.\n")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        if os.name == "nt" and "--sem-pausa" not in sys.argv:
            input("  Aperte Enter para fechar...")
