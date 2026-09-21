"""TUNEIS - publicar uma porta do Colab, sem derrubar as outras

O DEFEITO QUE ISTO CONSERTA   (13/09)
    Cada script de tunel comecava com `pkill -f cloudflared`, que mata
    TODOS os tuneis da maquina -- nao so o seu. Como tres coisas diferentes
    querem ser publicadas ao mesmo tempo:

        7000  o Bigode inteiro          tunel.py
        8082  o motor, no modo hibrido  tunel_motor.py
        8188  o ComfyUI, para a Pipi    tunel_desenhista.py

    ligar um derrubava o outro, e o link antigo continuava na mao do Fred
    parecendo valido -- ate ele abrir e receber erro.

    E o pior: eu mesmo escrevi no cabecalho do tunel_motor.py que "tunel
    gratuito do Cloudflare so aceita um por processo". Nao e verdade. Da
    para rodar varios cloudflared ao mesmo tempo, cada um com seu endereco.
    Quem impedia era o nosso proprio pkill.

    Aqui o pkill casa com a PORTA. Cada tunel so mata o seu antecessor.

COMO USAR

    import tuneis
    url = tuneis.abrir(8082, "o motor")

Venure - venure.com.br
"""

import re
import subprocess
import time
from pathlib import Path

CLOUDFLARED = Path("/content/cloudflared")
ENDERECO = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

# Guardado por porta para o chamador poder encerrar depois, e para o processo
# nao ser recolhido pelo Python enquanto ainda esta servindo.
PROCESSOS = {}


def _log(porta):
    return Path("/content/tunel-%d.log" % porta)


def preparar():
    """Baixa o cloudflared uma vez por sessao."""
    if CLOUDFLARED.is_file():
        return True
    print("  Baixando o cloudflared...")
    subprocess.run(
        'wget -q -O %s https://github.com/cloudflare/cloudflared/releases/'
        'latest/download/cloudflared-linux-amd64 && chmod +x %s'
        % (CLOUDFLARED, CLOUDFLARED), shell=True)
    return CLOUDFLARED.is_file()


def derrubar(porta):
    """Mata SO o tunel desta porta.

    O padrao casa com a linha de comando do processo, que contem
    `--url http://127.0.0.1:8082`. Um tunel de outra porta nao casa, e por
    isso sobrevive -- que e o ponto deste arquivo inteiro.
    """
    subprocess.run(
        ['pkill', '-f', 'cloudflared.*127\\.0\\.0\\.1:%d' % porta],
        capture_output=True)
    PROCESSOS.pop(porta, None)
    time.sleep(1)


def abrir(porta, rotulo="", espera_seg=80):
    """Publica a porta e devolve o endereco. Devolve "" se nao conseguir.

    O log e recriado do zero a cada chamada. Sem isso, um tunel novo lia o
    endereco do tunel ANTIGO que ainda estava escrito no arquivo -- e o Fred
    recebia um link morto que parecia recem-nascido.
    """
    if not preparar():
        print("  Nao consegui baixar o cloudflared.")
        return ""

    derrubar(porta)

    arq = _log(porta)
    arq.write_text("")                       # zera antes de ler

    PROCESSOS[porta] = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--url", "http://127.0.0.1:%d" % porta,
         "--no-autoupdate"],
        stdout=open(arq, "w"), stderr=subprocess.STDOUT)

    print("  Abrindo o tunel%s" % (" de " + rotulo if rotulo else ""), end="")
    for _ in range(max(1, espera_seg // 2)):
        time.sleep(2)
        try:
            achado = ENDERECO.search(arq.read_text())
            if achado:
                print(" pronto.")
                return achado.group(0)
        except Exception:
            pass
        print(".", end="")

    print(" nao abriu.")
    try:
        print(arq.read_text()[-1200:])
    except Exception:
        pass
    return ""


def de_pe():
    """Quais portas estao publicadas agora, na visao do sistema."""
    try:
        saida = subprocess.check_output(
            ["pgrep", "-af", "cloudflared"], text=True)
    except Exception:
        return []
    portas = []
    for linha in saida.splitlines():
        achado = re.search(r"127\.0\.0\.1:(\d+)", linha)
        if achado:
            portas.append(int(achado.group(1)))
    return sorted(set(portas))
