"""APONTAR O BIGODE DAQUI PARA O MOTOR DO COLAB

Rode NO SEU WINDOWS, na pasta do Bigode:

    python usar_motor_do_colab.py

Ele pede a receita que a celula 8-B do Colab imprimiu, confere se o motor
responde de verdade, e so entao grava no config.json.

POR QUE CONFERIR ANTES DE GRAVAR
    Se gravar um endereco errado, o Bigode sobe, parece bem, e so falha na
    hora da primeira pergunta -- com uma mensagem que fala de rede e nao diz
    que o culpado foi um "v" trocado no endereco. Testar leva dois segundos
    e transforma um misterio em uma frase.

PARA VOLTAR AO MOTOR DAQUI

    python usar_motor_do_colab.py --local

Venure - venure.com.br
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).resolve().parent / "config.json"
LOCAL = "http://localhost:8082/v1/chat/completions"


def ler_config():
    if not CONFIG.is_file():
        raise SystemExit(
            "Nao achei o config.json em %s.\n"
            "Rode este script de dentro da pasta do Bigode." % CONFIG.parent)
    return json.loads(CONFIG.read_text(encoding="utf-8-sig"))


def gravar_config(cfg):
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                      encoding="utf-8")


def testar(url, chave):
    """Uma pergunta minima. Se voltar resposta, o caminho inteiro funciona."""
    corpo = json.dumps({
        "messages": [{"role": "user", "content": "oi"}],
        "max_tokens": 1,
        "stream": False,
    }).encode("utf-8")
    pedido = urllib.request.Request(url, data=corpo,
                                    headers={"Content-Type": "application/json"})
    if chave:
        pedido.add_header("Authorization", "Bearer " + chave)
    try:
        with urllib.request.urlopen(pedido, timeout=90) as r:
            r.read()
        return True, ""
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, ("o motor respondeu %d: a chave nao confere. "
                           "Cole a receita inteira, sem cortar." % e.code)
        return False, "o motor respondeu %d." % e.code
    except urllib.error.URLError as e:
        return False, ("nao cheguei no endereco (%s). O Colab ainda esta "
                       "ligado? O link muda a cada sessao." % e.reason)
    except Exception as e:
        return False, str(e)


def main():
    cfg = ler_config()

    if "--local" in sys.argv:
        cfg["llm_url"] = LOCAL
        cfg["llm_chave"] = ""
        gravar_config(cfg)
        print("\n  Pronto. O Bigode volta a usar o motor desta maquina.")
        print("  Endereco: %s\n" % LOCAL)
        return

    print()
    print("=" * 68)
    print("  USAR A PLACA DO COLAB")
    print("=" * 68)
    print()
    print("  Cole aqui a receita que a celula 8-B imprimiu e de Enter.")
    print("  Ela comeca com {\"llm_url\": ...")
    print()
    bruto = input("  > ").strip()

    try:
        receita = json.loads(bruto)
        url = str(receita["llm_url"]).strip()
        chave = str(receita.get("llm_chave", "")).strip()
    except Exception:
        # Aceitar so o link tambem: e o erro mais provavel de quem esta com
        # pressa, e nao custa nada atender.
        if bruto.startswith("http"):
            url = bruto.rstrip("/")
            if not url.endswith("/v1/chat/completions"):
                url += "/v1/chat/completions"
            chave = input("  Chave: ").strip()
        else:
            raise SystemExit(
                "\n  Nao entendi. Cole a linha inteira que o Colab imprimiu,"
                "\n  das chaves { ate as chaves }.\n")

    print()
    print("  Testando (a primeira pergunta pode levar um minuto)...")
    ok, porque = testar(url, chave)

    if not ok:
        print()
        print("  NAO GRAVEI NADA -- %s" % porque)
        print()
        print("  O config.json continua como estava.")
        print("=" * 68)
        print()
        return

    cfg["llm_url"] = url
    cfg["llm_chave"] = chave
    gravar_config(cfg)

    print()
    print("  FUNCIONOU. Gravado no config.json.")
    print()
    print("    motor ... %s" % url)
    print("    chave ... %s..." % chave[:8])
    print()
    print("  Abra o Bigode de sempre. Ele pensa com a placa do Colab e")
    print("  continua mexendo nos arquivos desta maquina.")
    print()
    print("  Quando o Colab desligar, rode:")
    print("    python usar_motor_do_colab.py --local")
    print("=" * 68)
    print()


if __name__ == "__main__":
    main()
