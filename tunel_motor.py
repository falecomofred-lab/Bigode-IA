"""MODO HIBRIDO: A PLACA AQUI, OS SEUS ARQUIVOS AI   -   celula 8-B

Publica o MOTOR (porta 8082) em vez do Bigode (7000).

O PROBLEMA QUE ISTO RESOLVE
    O Bigode rodando no Colab e rapido e nao alcanca nada seu. Ele enxerga
    o Google Drive montado e mais nada -- o C:\\ do Fred fica do outro lado
    da internet. "Edite meu arquivo" vira "que arquivo?".

    O Bigode rodando no Windows alcanca tudo e pensa devagar: sem placa,
    duas a cinco palavras por segundo.

    Nenhum dos dois e o que ele pediu. O hibrido e:

        cerebro no Windows  ->  alcanca C:\\, G:\\, o Chrome, tudo
        motor no Colab      ->  a placa faz a conta pesada

    O que viaja pelo tunel e so texto: a pergunta vai, a resposta volta. Os
    arquivos nunca saem da maquina do Fred -- quem os le e o cerebro, que
    esta la.

ELE NAO BRIGA MAIS COM A CELULA 8   (13/09)
    Eu tinha escrito aqui que "tunel gratuito do Cloudflare so aceita um por
    processo". Nao e verdade, e o erro custou caro: da para rodar varios
    cloudflared ao mesmo tempo, cada um com seu endereco. Quem derrubava os
    outros era o nosso proprio `pkill -f cloudflared`.

    Agora o tuneis.py mata so o tunel da porta 8082. A celula 8 (Bigode) e a
    8-C (desenhista) podem estar de pe junto com esta.

A CHAVE NAO E DETALHE
    Este endereco e publico. Sem chave, quem topasse com ele usaria a placa
    e a cota do Fred. O ligar_motor.py sobe o motor com `--api_key` e grava
    a chave em /content/motor.chave; ela sai impressa aqui embaixo.

Venure - venure.com.br
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

for _onde in ("/content/bigode",
              "/content/drive/MyDrive/projetos/Cerebro"):
    if _onde not in sys.path:
        sys.path.insert(0, _onde)

import tuneis                                            # noqa: E402

PORTA = 8082

print()
print("=" * 70)
print("  MODO HIBRIDO  --  a placa aqui, os seus arquivos ai")
print("=" * 70)

# ---- a chave ---------------------------------------------------------------
CHAVE = ""
_arq = Path("/content/motor.chave")
if _arq.is_file():
    CHAVE = _arq.read_text().strip()
if not CHAVE:
    CHAVE = str(globals().get("CHAVE_MOTOR") or "").strip()

if not CHAVE:
    raise SystemExit(
        "\n  Nao achei a chave do motor em /content/motor.chave.\n"
        "  Rode a celula 6 (ligar o motor) e volte aqui.\n")


# ---- o motor esta de pe? ---------------------------------------------------
def _motor_no_ar():
    pedido = urllib.request.Request("http://127.0.0.1:%d/v1/models" % PORTA)
    pedido.add_header("Authorization", "Bearer " + CHAVE)
    try:
        urllib.request.urlopen(pedido, timeout=5)
        return True
    except urllib.error.HTTPError as e:
        # 401 aqui quer dizer "estou de pe, mas essa chave nao serve" -- que
        # e uma falha diferente de "nao ha ninguem na porta". Vale separar.
        print("\n  O motor respondeu %d: a chave gravada nao confere." % e.code)
        print("  Rode a celula 6 de novo para gerar uma chave nova.")
        return False
    except Exception:
        return False


if not _motor_no_ar():
    print()
    print("  O motor nao esta respondendo na porta %d." % PORTA)
    print("  Um tunel agora criaria um link que devolve erro.")
    print()
    print("  Rode a celula 6 (ligar o motor) e volte aqui.")
    print("=" * 70)
    raise SystemExit("Motor fora do ar.")

print()
LINK = tuneis.abrir(PORTA, "o motor")

print()
print("=" * 70)

if not LINK:
    print("  SEM LINK. O motivo esta acima.")
    print("=" * 70)
    raise SystemExit("Tunel nao abriu.")

URL_MOTOR = LINK + "/v1/chat/completions"

# Uma linha so, para colar. Escrever dois valores na mao em dois campos e
# onde a pessoa erra -- troca a ordem, perde um caractere da chave, e o erro
# que aparece la na frente e "o motor nao respondeu".
RECEITA = json.dumps({"llm_url": URL_MOTOR, "llm_chave": CHAVE})

print()
print("  MOTOR PUBLICADO:")
print()
print("      " + URL_MOTOR)
print()
print("  " + "-" * 66)
print("  AGORA, NO SEU WINDOWS:")
print()
print("    1. Abra o Prompt de Comando na pasta do Bigode")
print("    2. Rode:      python usar_motor_do_colab.py")
print("    3. Cole isto quando ele pedir:")
print()
print("       " + RECEITA)
print()
print("    4. Abra o Bigode de sempre. Ele vai pensar com a placa daqui")
print("       e mexer nos arquivos dai.")
print("  " + "-" * 66)
print()
_outras = [p for p in tuneis.de_pe() if p != PORTA]
if _outras:
    print("  Tambem publicados agora: %s"
          % ", ".join(str(p) for p in _outras))
    print()
print("  Este endereco e PUBLICO e muda a cada sessao. A chave e o que")
print("  impede um estranho de gastar a sua placa. Nao publique a receita.")
print()
print("  Mexa na aba de vez em quando: 90 min parado e o Colab desliga.")
print("=" * 70)
print()
