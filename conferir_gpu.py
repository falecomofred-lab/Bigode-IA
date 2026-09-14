"""CONFERIR GPU - tem placa de video nesta sessao?

Celula 2 do Colab. Uma linha la, a logica aqui.

POR QUE VIROU ARQUIVO
    Era codigo dentro da celula. Duas razoes para tirar de la:

    1. O `raise SystemExit` estava DENTRO de um `except`. O Python encadeia
       as duas excecoes (FileNotFoundError -> SystemExit), e o formatador de
       traceback do IPython engasga nesse par: cospe 200 linhas de
       "Internal Python error in the inspect module" e enterra a unica linha
       que importava, que era "SEM GPU".

    2. Editar bloco indentado na celula do Colab e uma briga: o editor
       fecha aspas sozinho e soma a indentacao dele com a que voce digita.
       Num arquivo .py normal isso nao acontece, e o sincronizar-bigode.ps1
       espalha para as tres copias como qualquer outro arquivo.

O QUE ELE DEIXA PARA TRAS
    PLACA    o nome e a memoria, ou "" quando nao ha placa
    TEM_GPU  True/False, para quem quiser decidir sem repetir a checagem

Venure - venure.com.br
"""

import subprocess

PLACA = ""
try:
    PLACA = subprocess.check_output(
        ["nvidia-smi", "--query-gpu=name,memory.total",
         "--format=csv,noheader"], text=True).strip()
except Exception:
    # Engolido de proposito. Quem trata e o `if` la embaixo, FORA do
    # except -- e o que impede o encadeamento que gerava a parede de texto.
    PLACA = ""

TEM_GPU = bool(PLACA)

if TEM_GPU:
    print("GPU:", PLACA)
else:
    # NAO PARA MAIS AQUI   (10/09)
    #
    # Antes esta celula levantava SystemExit e a sessao acabava. Fazia
    # sentido enquanto o motor so existia em versao CUDA. Mas existe um
    # motor de CPU, e o resto do notebook aprendeu a usa-lo: a celula 4
    # instala o pacote certo e a 6 sobe com as camadas no processador.
    #
    # Entao a resposta honesta deixou de ser "pare" e passou a ser
    # "da para seguir, mas devagar, e so com as IAs leves".
    print()
    print("=" * 68)
    print("  SEM PLACA  --  DA PARA SEGUIR, MAS DEVAGAR")
    print("=" * 68)
    print()
    print("  Este Colab conectou sem GPU. Duas causas possiveis:")
    print()
    print("  1. O TIPO ESTA ERRADO")
    print("     Ambiente de execucao -> Alterar o tipo de ambiente")
    print("     -> GPU T4 -> Salvar")
    print()
    print("  2. A COTA GRATUITA DE GPU ACABOU        <-- o caso comum")
    print("     Ao tentar salvar, o Colab responde: 'Nao e possivel")
    print("     conectar ao back-end da GPU devido aos limites de uso'.")
    print("     Espere algumas horas, ou assine o Colab Pro.")
    print()
    print("  ------------------------------------------------------------")
    print("  SE QUISER SEGUIR ASSIM MESMO:")
    print()
    print("    Continue rodando as celulas. O motor sobe no PROCESSADOR --")
    print("    2 a 5 palavras por segundo, contra ~90 na T4.")
    print()
    print("    Escolha uma IA LEVE na celula 1:")
    print("      granite           4,2 GB   o mais rapido que voce tem")
    print("      qwen-coder-leve   3,8 GB   codigo, comprimido mais forte")
    print()
    print("    O que NAO vai funcionar sem placa:")
    print("      - criar imagens (o ComfyUI precisa de GPU)")
    print("      - as IAs de 10 GB para cima")
    print("      - ler projeto inteiro: a leitura do prompt fica lenta")
    print("  ------------------------------------------------------------")
    print()
    print("  Conversa curta e leitura de um arquivo funcionam bem.")
    print("=" * 68)
    print()
