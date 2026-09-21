"""FAZER OS ICONES OFICIAIS DO BIGODE E DA PIPI
Venure · venure.com.br · 17/09/2026

Roda uma vez, na pasta do Cerebro:

    python fazer_icones.py

Ele compoe a foto de cada gato sobre o fundo da marca e grava todos os
tamanhos que o Chrome, o Windows e o iPhone pedem, nas duas pastas.

    Bigode  ->  foto do Bigode  sobre VERDE  (#9DC08B)
    Pipi    ->  foto da Pipi    sobre ROSA CLARO (#F3CCD8)

POR QUE UM SCRIPT, E NAO CODIGO DENTRO DO SERVIDOR
    Compor imagem exige Pillow. O servidor da Pipi tem UMA dependencia --
    o `modal` -- e nao vale somar outra para um icone que muda uma vez por
    ano. Aqui o Pillow e usado na hora de FAZER o arquivo; depois o
    servidor so entrega o .png pronto.

    E o servidor ja prefere arquivo a desenho: o `icone()` procura
    web/img/icone-NNN.png antes de cair no desenho de reserva. Entao rodar
    isto uma vez substitui o desenho para sempre.

O QUE ESTAVA ERRADO ANTES                                   (17/09)
    . A Pipi nao tinha arquivo de icone nenhum, e o manifest.json vinha com
      "icons": [] -- vazio. O Chrome nunca ofereceu "Instalar app", e o que
      aparecia era o desenho de reserva: um V da Venure.
    . O Bigode TINHA a foto do gato, mas com fundo branco/transparente. Num
      tema escuro o recorte come a silhueta; num tema claro o gato branco
      desaparece no fundo branco. Fundo de marca resolve os dois.

PRECISA DE
    python -m pip install pillow
"""

from pathlib import Path
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("Falta o Pillow. Rode:  python -m pip install pillow")

AQUI = Path(__file__).resolve().parent

# Os tamanhos, e quem pede cada um:
#   16, 32, 48   aba do navegador e atalho do Windows
#   128          loja de extensoes do Chrome
#   180          tela de inicio do iPhone (apple-touch-icon)
#   192, 512     obrigatorios para o Chrome oferecer "Instalar app"
TAMANHOS = (16, 32, 48, 64, 128, 180, 192, 512)

PROJETOS = [
    {
        "nome": "Bigode IA",
        "pasta": AQUI / "web" / "img",
        # O primeiro que existir ganha. bigode.png e o recorte; o .jpg tem
        # fundo e serviria pior.
        "fontes": ["bigode-fonte.png", "bigode.png", "bigode.jpg"],
        # O verde da marca do Bigode, o mesmo --ac do index.html.
        "fundo": (157, 192, 139),
    },
    {
        "nome": "Pipi IA",
        "pasta": AQUI.parent / "Pipi IA" / "web" / "img",
        "fontes": ["pipi_gata_transparente.png", "pipi_gata.jpeg"],
        # Rosa claro: o rosa queimado (#E0849B) clareado, para a gata
        # cinza-prata aparecer por cima sem competir.
        "fundo": (243, 204, 216),
    },
]


def achar_fonte(pasta, nomes):
    for n in nomes:
        p = pasta / n
        if p.is_file():
            return p
    return None


def recortar_no_bicho(img):
    """Tira a margem transparente em volta do gato.

    A foto da Pipi tem 2096x2157 com muito vazio em volta. Sem este
    recorte, no icone de 16 px sobra um pontinho de gato no meio de um
    quadrado rosa -- e a 16 px voce tem que reconhecer QUAL das duas
    ferramentas e, sem ler nada.
    """
    if img.mode != "RGBA":
        return img
    caixa = img.getchannel("A").getbbox()
    return img.crop(caixa) if caixa else img


def quadrado(img, folga=0.08):
    """Poe a imagem num quadrado, centralizada, com uma folga em volta.

    A folga existe por causa do icone "maskable" do Android: ele recorta um
    circulo do centro. Sem folga, a orelha do gato sai cortada.
    """
    lado = int(max(img.size) * (1 + folga * 2))
    tela = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    tela.paste(img, ((lado - img.width) // 2, (lado - img.height) // 2), img
               if img.mode == "RGBA" else None)
    return tela


def cantos(img, raio_rel=0.22):
    """Arredonda os cantos, como o icone de aplicativo de hoje espera."""
    lado = img.width
    mascara = Image.new("L", (lado, lado), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        (0, 0, lado - 1, lado - 1), radius=int(lado * raio_rel), fill=255)
    saida = img.copy()
    saida.putalpha(mascara)
    return saida


def montar(fonte, cor_fundo, lado):
    bicho = Image.open(fonte)
    bicho = bicho.convert("RGBA")
    bicho = recortar_no_bicho(bicho)
    bicho = quadrado(bicho)

    # Redimensiona ANTES de compor, e com LANCZOS: reduzir depois de colar
    # mistura a borda do gato com o fundo e suja a silhueta.
    bicho = bicho.resize((lado, lado), Image.LANCZOS)

    fundo = Image.new("RGBA", (lado, lado), cor_fundo + (255,))
    fundo.alpha_composite(bicho)

    # Canto arredondado so a partir de 48: em 16 e 32 o arredondamento come
    # pixel demais e o icone fica lavado.
    return cantos(fundo) if lado >= 48 else fundo


def main():
    print()
    print("=" * 66)
    print("  ICONES OFICIAIS DA VENURE")
    print("=" * 66)

    for proj in PROJETOS:
        pasta = proj["pasta"]
        print()
        print("  %s" % proj["nome"])
        print("  " + "-" * 62)

        if not pasta.is_dir():
            print("  pasta nao encontrada: %s" % pasta)
            continue

        fonte = achar_fonte(pasta, proj["fontes"])
        if not fonte:
            print("  nao achei a foto. Procurei por: %s"
                  % ", ".join(proj["fontes"]))
            continue
        print("  foto  : %s" % fonte.name)
        print("  fundo : rgb%s" % (proj["fundo"],))

        feitos = []
        for lado in TAMANHOS:
            img = montar(fonte, proj["fundo"], lado)
            for prefixo in ("icone", "favicon"):
                destino = pasta / ("%s-%d.png" % (prefixo, lado))
                img.save(destino, "PNG", optimize=True)
            feitos.append(lado)

        # O .ico com varios tamanhos dentro: e o que o Windows usa no
        # atalho e o que o Chrome pede sozinho em /favicon.ico, sem olhar
        # o <head> da pagina.
        base = montar(fonte, proj["fundo"], 256)
        base.save(pasta / "favicon.ico", "ICO",
                  sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)])

        print("  gravei: icone-* e favicon-* em %s" % ", ".join(
            str(x) for x in feitos))
        print("          favicon.ico com 6 tamanhos dentro")

    print()
    print("=" * 66)
    print("  Pronto. Agora:")
    print("    1. feche e abra o Bigode e a Pipi")
    print("    2. na aba, Ctrl+F5  (o Chrome guarda icone com afinco)")
    print("    3. se ainda vier o antigo, abra em aba anonima para conferir")
    print("=" * 66)
    print()


if __name__ == "__main__":
    main()
