"""INSTALAR O MOTOR E A MEMORIA SEMANTICA   -   celula 4

Duas instalacoes, com pesos bem diferentes.

O MOTOR (llama-cpp-python)
    E o que faz o Bigode pensar. Sem ele, nada funciona -- por isso a falha
    aqui INTERROMPE.

    Vem compilado com CUDA, num pacote pronto. A alternativa era compilar na
    hora: dez minutos, e em 09/09 a sessao do Colab morreu no meio da
    compilacao, duas vezes. Pacote pronto e a escolha certa.

A MEMORIA SEMANTICA (ChromaDB)
    Procura pelo SENTIDO do que voce pediu, nao pela palavra exata:
    "como faco a cobranca automatica" acha o trecho certo mesmo que o codigo
    diga "billing recorrente".

    Nao e essencial -- sem ela o Bigode continua lendo arquivo e buscando
    por palavra. Por isso a falha aqui AVISA E SEGUE.

NADA DE SAIDA ENGOLIDA
    Uma versao anterior descartava a saída do pip sem registrar o erro. Quando
    falhava, ninguem ficava sabendo, e o erro so aparecia tres celulas
    adiante como "o motor nao subiu". Falha silenciosa e o defeito mais
    caro deste projeto.

Venure - venure.com.br
"""

import subprocess


def _rodar(cmd):
    """Roda e MOSTRA o que aconteceu."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode != 0:
        print("  FALHOU:", cmd)
        print("  " + (r.stdout + r.stderr)[-1200:].replace("\n", "\n  "))
    return r.returncode == 0


print()
print("=" * 66)
print("  INSTALANDO")
print("=" * 66)

# ---- 1. o motor -----------------------------------------------------------
#
# QUAL PACOTE INSTALAR DEPENDE DE TER PLACA   (10/09)
#
#     O pacote com CUDA nao roda sem CUDA. Se voce instalar o cu124 numa
#     maquina sem GPU, ele ENTRA -- o pip diz "sucesso" -- e depois quebra
#     no import com:
#
#         libcudart.so.12: cannot open shared object file
#
#     Era o que acontecia toda vez que a cota de GPU do Colab acabava: a
#     celula dizia que tinha instalado, e o motor nunca subia.
#
#     Existe um pacote de CPU, no mesmo indice. Ele e MUITO mais lento --
#     2 nucleos do Colab contra os 2560 da T4 -- mas funciona. Entre um
#     Bigode devagar e nenhum Bigode, devagar ganha.
def _tem_placa():
    try:
        subprocess.check_output(["nvidia-smi"], stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


TEM_PLACA = _tem_placa()
IDX = "--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/"

if TEM_PLACA:
    print("\n  1/2  Motor com suporte a GPU...")
    ok = _rodar("pip install -q llama-cpp-python[server] " + IDX + "cu124")
    if not ok:
        print("       tentando a versao anterior do CUDA...")
        ok = _rodar("pip install -q llama-cpp-python[server] " + IDX + "cu121")
else:
    print("\n  1/2  SEM PLACA -- instalando o motor de CPU.")
    print("       Vai funcionar, mas devagar: conte com 2 a 5 palavras por")
    print("       segundo, contra ~90 na T4. Para conversa curta serve;")
    print("       para ler projeto inteiro, nao.")
    ok = _rodar("pip install -q llama-cpp-python[server] " + IDX + "cpu")
    if not ok:
        # Sem wheel pronto para esta versao do Python, o pip compila do
        # zero -- dez minutos, e a sessao do Colab pode morrer no meio.
        # Avisar antes e melhor do que deixar voce olhando a tela parada.
        print("       Sem pacote pronto. Vou compilar -- isso leva ~10 min.")
        ok = _rodar("pip install -q llama-cpp-python[server]")

if ok:
    # Instalar nao e o mesmo que funcionar. Conferimos de verdade.
    try:
        import importlib
        importlib.import_module("llama_cpp")
        print("       motor pronto (%s)." % ("GPU" if TEM_PLACA else "CPU"))
    except Exception as erro:
        print("       instalou mas NAO CARREGA: %s" % erro)
        if "libcudart" in str(erro):
            print("       Pacote de GPU numa maquina sem GPU. Rode a celula 2")
            print("       para confirmar, e rode esta de novo.")
        ok = False

if not ok:
    print()
    print("=" * 66)
    print("  SEM MOTOR O BIGODE NAO PENSA. O erro esta acima.")
    print("=" * 66)
    raise SystemExit("Motor nao instalado.")

# ---- 2. a memoria semantica ----------------------------------------------
print("\n  2/2  Memoria semantica (ChromaDB)...")
if _rodar("pip install -q chromadb"):
    try:
        import chromadb
        print("       ChromaDB pronto (versao %s)."
              % getattr(chromadb, "__version__", "?"))
    except Exception as erro:
        print("       instalou mas nao carrega: %s" % erro)
else:
    print("       nao instalou. O Bigode funciona sem -- so perde a busca")
    print("       por sentido. O erro esta acima.")

print()
print("=" * 66)
print("  PRONTO PARA LIGAR O MOTOR.")
print("=" * 66)
print()
