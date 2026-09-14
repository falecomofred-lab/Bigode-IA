"""O DESENHISTA PARA A PIPI   -   celula 8-C

Publica o ComfyUI (porta 8188) para a Pipi IA, que roda no Windows do Fred.

POR QUE ISTO EXISTE
    A Pipi e o maestro de imagens: ela monta o workflow, escolhe o modelo e
    guarda o resultado. Quem desenha de verdade e o ComfyUI, que precisa de
    uma placa NVIDIA. A maquina do Fred nao tem CUDA disponivel, entao o
    ComfyUI local nunca sobe -- a porta 8188 la fica muda.

    A celula 10 (desenhista.py) ja levanta um ComfyUI aqui no Colab, com a
    T4 e com o FLUX ja baixado. Faltava so deixar a Pipi chegar nele.

        Pipi (Windows)  ->  tunel  ->  ComfyUI (Colab, T4)

    Assim ninguem instala CUDA em lugar nenhum e a Pipi passa a desenhar
    hoje. O caminho definitivo continua sendo o Modal, quando o endpoint de
    la deixar de ser um esqueleto -- mas validar primeiro aqui custa zero
    credito.

ATENCAO, E E SERIO
    O ComfyUI NAO TEM SENHA. Nenhuma. Enquanto este tunel estiver de pe,
    quem tiver o endereco manda desenhar na sua placa e ve as imagens que
    voce gerou. O endereco e sorteado e muda a cada sessao, mas isso e
    obscuridade, nao protecao.

    Nao publique, nao cole em grupo, e rode a celula 13 quando terminar.

Venure - venure.com.br
"""

import sys
import urllib.request

for _onde in ("/content/bigode",
              "/content/drive/MyDrive/projetos/Cerebro"):
    if _onde not in sys.path:
        sys.path.insert(0, _onde)

import tuneis                                            # noqa: E402

PORTA = 8188


def _comfy_no_ar():
    try:
        urllib.request.urlopen(
            "http://127.0.0.1:%d/system_stats" % PORTA, timeout=4)
        return True
    except Exception:
        return False


print()
print("=" * 70)
print("  O DESENHISTA PARA A PIPI")
print("=" * 70)

if not _comfy_no_ar():
    print()
    print("  O ComfyUI nao esta respondendo na porta %d." % PORTA)
    print()
    print("  Rode a celula 10 (ligar o desenhista) e volte aqui.")
    print("  Ela baixa o FLUX e sobe o ComfyUI -- leva alguns minutos na")
    print("  primeira vez da sessao.")
    print("=" * 70)
    raise SystemExit("ComfyUI fora do ar.")

print()
LINK = tuneis.abrir(PORTA, "o desenhista")

print()
print("=" * 70)

if not LINK:
    print("  SEM LINK. O motivo esta acima.")
    print("=" * 70)
    raise SystemExit("Tunel nao abriu.")

print()
print("  DESENHISTA PUBLICADO:")
print()
print("      " + LINK)
print()
print("  " + "-" * 66)
print("  AGORA, NO SEU WINDOWS:")
print()
print("    1. Abra o Prompt de Comando na pasta da Pipi IA")
print("    2. Rode:      python usar_desenhista_do_colab.py")
print("    3. Cole o endereco acima quando ele pedir")
print("    4. Inicie a Pipi com:   pipi.bat")
print()
print("    Ela vai usar a T4 daqui em vez de procurar o ComfyUI na sua")
print("    maquina.")
print("  " + "-" * 66)
print()
_outras = [p for p in tuneis.de_pe() if p != PORTA]
if _outras:
    print("  Tambem publicados agora: %s"
          % ", ".join(str(p) for p in _outras))
    print()
print("  O ComfyUI NAO TEM SENHA. Enquanto este link estiver de pe, quem")
print("  tiver o endereco desenha na sua placa. Nao compartilhe, e rode a")
print("  celula 13 ao terminar.")
print()
print("  Mexa na aba de vez em quando: 90 min parado e o Colab desliga.")
print("=" * 70)
print()
