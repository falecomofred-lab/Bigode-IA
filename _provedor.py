"""Diz em que provedor o Bigode esta configurado. Usado pelo BIGODE.bat.
Venure · venure.com.br · 17/09/2026

Imprime uma palavra e nada mais:

    local          o motor roda nesta maquina (o .bat precisa subir o llamafile)
    huggingface    o modelo roda longe; nao ha motor local para subir
    modal          idem

E devolve codigo de saida:

    0    provedor REMOTO e pronto para usar
    1    local, ou remoto mal configurado (o .bat avisa e segue)

POR QUE ISTO E UM ARQUIVO, E NAO UMA LINHA NO .BAT        (17/09)
    Estava inline, dentro de um `for /f`:

        for /f "delims=" %%R in ('""%PY%" -c "import json,...read_text(...)"') do ...

    E quebrou na cara do Fred:

        /'config.json').read_text(encoding foi inesperado neste momento.

    O `cmd` interpreta os parenteses do codigo Python como parenteses DELE.
    Dentro de `for /f` nao ha escape que resolva isso de forma legivel --
    da para fazer com ^^ e aspas triplas, mas ninguem consegue ler nem
    consertar depois.

    Python em arquivo, .bat chamando o arquivo. Uma linha de cada lado.
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

# A PASTA DESTE ARQUIVO PRECISA ENTRAR NO CAMINHO, NA MAO      (17/09)
#
#   O BIGODE.bat pode escolher o Python EMBARCADO do pendrive. Aquele
#   vem com um python312._pth, que substitui o caminho de busca de
#   modulos por uma lista fixa -- e a pasta do script nao entra nela.
#
#   Resultado: `import modal_cliente` falhava, o except devolvia 1, e o
#   .bat concluia "o provedor esta escolhido, mas falta a credencial" --
#   com a credencial no lugar certo, gravada e funcionando.
#
#   E o mesmo tropeco que derrubou a Pipi com
#   "ModuleNotFoundError: No module named 'huggingface_cliente'".
#   A licao: script que pode ser chamado por Python embarcado declara o
#   proprio caminho, em vez de confiar em quem o chamou.
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def main():
    try:
        dados = json.loads(
            (BASE / "config.json").read_text(encoding="utf-8-sig") or "{}")
    except Exception:
        print("local")
        return 1

    provedor = str(dados.get("modelo_provedor") or "local").strip().lower()
    if provedor not in ("huggingface", "modal"):
        print("local")
        return 1

    print(provedor)

    # Remoto mas sem credencial nao e remoto: o .bat precisa saber a
    # diferenca para avisar em vez de abrir uma tela que nao responde.
    try:
        if provedor == "huggingface":
            import huggingface_cliente
            return 0 if huggingface_cliente.configurado() else 1
        import modal_cliente
        return 0 if modal_cliente.configurado(dados) else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
