"""O SEU LINK   -   celula 8

Publica o BIGODE (porta 7000) e imprime o endereco.

O QUE MUDOU   (13/09)
    Antes este arquivo matava todos os cloudflared antes de abrir o seu.
    Isso derrubava o tunel do motor (8082) e o do desenhista (8188) sem
    avisar -- e o link antigo continuava na mao do Fred parecendo valido.
    Agora quem cuida disso e o tuneis.py, que mata so o tunel da porta
    7000. Os outros continuam de pe.

O QUE ELE JA FAZIA
    Conferir a porta 7000 ANTES de abrir o tunel. Sem isso nascia um link
    bonito que devolvia 502, e voce so descobria depois de abrir.

O ENDERECO E PUBLICO
    Enquanto o Colab estiver ligado, quem tiver o link chega na sua tela de
    login. A senha continua protegendo, mas o endereco nao e segredo.

E ELE MUDA A CADA SESSAO
    Tunel gratuito nao tem nome fixo. Toda vez que esta celula roda, nasce
    um endereco novo -- e por isso a extensao do Chrome precisa ser
    atualizada junto.

Venure - venure.com.br
"""

import sys
import urllib.request

# O `exec` da celula roda com o cwd em /content, onde nao ha tuneis.py.
for _onde in ("/content/bigode",
              "/content/drive/MyDrive/projetos/Cerebro"):
    if _onde not in sys.path:
        sys.path.insert(0, _onde)

import tuneis                                            # noqa: E402

PORTA = 7000


def _bigode_no_ar():
    try:
        urllib.request.urlopen(
            "http://127.0.0.1:%d/api/login/estado" % PORTA, timeout=3)
        return True
    except Exception:
        return False


print()
print("=" * 66)
print("  O SEU LINK")
print("=" * 66)

# ---- o Bigode esta de pe? -------------------------------------------------
if not _bigode_no_ar():
    print()
    print("  O Bigode nao esta respondendo na porta %d." % PORTA)
    print("  Um tunel agora criaria um link que devolve erro.")
    print()
    print("  Rode a celula 7 (ligar o Bigode) e volte aqui.")
    print("=" * 66)
    raise SystemExit("Bigode fora do ar.")

print()
LINK = tuneis.abrir(PORTA, "o Bigode")

print()
print("=" * 66)
if LINK:
    print()
    print("  SEU BIGODE ESTA AQUI:")
    print()
    print("      " + LINK)
    print()
    print("  Abra em qualquer aparelho. E-mail e senha de sempre.")
    print()
    print("  PARA A EXTENSAO DO CHROME FALAR COM ESTA SESSAO:")
    print("    chrome://extensions -> Bigode -> Detalhes -> Opcoes")
    print("    cole o link no campo da nuvem e clique em Salvar e testar.")
    print()
    print("  Este endereco e PUBLICO enquanto o Colab estiver ligado.")
    print("  Ele muda a cada sessao. Nao compartilhe.")
    print()
    _outras = [p for p in tuneis.de_pe() if p != PORTA]
    if _outras:
        print("  Tambem publicados agora: %s"
              % ", ".join(str(p) for p in _outras))
        print()
    print("  Mexa na aba de vez em quando: 90 min parado e o Colab desliga.")
else:
    print("  SEM LINK. O motivo esta acima.")
print("=" * 66)
print()
