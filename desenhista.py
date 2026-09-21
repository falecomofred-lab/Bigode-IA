"""DESENHISTA - instala e liga o ComfyUI no Colab

Roda uma vez por sessao. Depois disso o Bigode desenha sozinho, pela
ferramenta `gerar_imagem`.

Como usar (celula do Colab):

    exec(open('/content/drive/MyDrive/projetos/Cerebro/desenhista.py').read())

O QUE ELE BAIXA, E DE ONDE
    Tudo do HuggingFace, direto para o disco do Colab -- nao para o Drive.

    Parece errado (baixar 10 GB toda sessao?), mas foi medido: a rede do
    Colab puxa do HuggingFace a ~100 MB/s, entao os 10 GB levam ~2 minutos.
    Guardar no Drive custaria o mesmo tempo de UPLOAD uma vez, mais uma
    leitura lenta pelo Drive montado toda sessao. O caminho curto e este.

        flux1-schnell-Q4_K_S.gguf        ~6,8 GB   o desenhista
        t5-v1_1-xxl-encoder-Q3_K_L.gguf  ~2,5 GB   le a frase inteira
        clip_l.safetensors               ~250 MB   le palavra por palavra
        ae.safetensors                   ~335 MB   transforma em pixel

POR QUE --lowvram
    A T4 tem 15 GB e o motor de TEXTO ja mora nela. Com `--lowvram` o
    ComfyUI carrega um pedaco por vez -- primeiro o leitor de texto, depois
    o desenhista -- em vez de tudo junto. O pico cai de ~10 GB para ~7,5 GB,
    e ai cabe ao lado do granite.

    Com o deepseek carregado (12,5 GB) nao cabe de jeito nenhum. A propria
    ferramenta avisa isso antes de tentar.

Venure - venure.com.br
"""

import os
import subprocess
import time
import urllib.request
from pathlib import Path

RAIZ = Path("/content/ComfyUI")
PORTA = 8188


def _rodar(cmd, onde=None):
    """Roda e MOSTRA se deu errado. Falha silenciosa e o defeito mais caro
    deste projeto -- ja custou meia hora procurando bug que nao existia."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       cwd=str(onde) if onde else None)
    if r.returncode != 0:
        print("   FALHOU:", cmd)
        print("   " + (r.stdout + r.stderr)[-700:].replace("\n", "\n   "))
    return r.returncode == 0


def _baixar(url, destino, rotulo, espelhos=()):
    """Baixa e, quando falha, DIZ POR QUE.

    A FALHA CALADA QUE CUSTOU UMA SESSAO                       (13/09)

        Isto usava `wget -q`, que engole a saida inteira. Quando o
        ae.safetensors nao veio, a tela mostrou:

            tradutor de pixel (VAE)  baixando... FALHOU

        e mais nada. "FALHOU" nao e diagnostico: 401 (repositorio
        fechado), 404 (mudou de lugar) e disco cheio pedem tres acoes
        completamente diferentes, e a mensagem nao separava nenhuma.

        Agora vai com `curl`, que devolve o codigo HTTP, e a mensagem
        diz o que fazer para cada caso.

    ESPELHOS
        Alguns repositorios da HuggingFace passam a exigir aceite de
        licenca de um dia para o outro. Quando isso acontece, o arquivo
        continua existindo em copias publicas. A lista `espelhos` e
        tentada em ordem antes de desistir.
    """
    destino = Path(destino)
    if destino.is_file() and destino.stat().st_size > 1_000_000:
        print("   %-22s ja esta aqui" % rotulo)
        return True
    destino.parent.mkdir(parents=True, exist_ok=True)

    # O token so entra se voce tiver posto um. Repositorio fechado sem
    # token e justamente o caso que queremos diagnosticar.
    token = os.environ.get("HF_TOKEN", "").strip()
    cabecalho = ('-H "Authorization: Bearer %s" ' % token) if token else ""

    for tentativa, endereco in enumerate([url] + list(espelhos)):
        if tentativa:
            print("   %-22s tentando espelho %d..."
                  % ("", tentativa), end="", flush=True)
        else:
            print("   %-22s baixando..." % rotulo, end="", flush=True)
        t0 = time.time()

        # -L segue redirecionamento, -f devolve erro em vez de gravar a
        # pagina de erro como se fosse o arquivo, -w imprime o codigo.
        r = subprocess.run(
            'curl -sL -f %s-w "%%{http_code}" -o "%s" "%s"'
            % (cabecalho, destino, endereco),
            shell=True, capture_output=True, text=True)
        codigo = (r.stdout or "").strip()[-3:]

        if destino.is_file() and destino.stat().st_size > 1_000_000:
            print(" %.1f GB em %.0fs" % (destino.stat().st_size / 1e9,
                                         time.time() - t0))
            return True

        print(" FALHOU (HTTP %s)" % (codigo or "?"))
        if codigo in ("401", "403"):
            print("      Este repositorio pede aceite de licenca.")
            print("      Abra o endereco abaixo no navegador, aceite, e")
            print("      depois rode nesta mesma sessao:")
            print("        import os; os.environ['HF_TOKEN'] = 'hf_...'")
            print("      %s" % endereco.split("/resolve/")[0])
        elif codigo == "404":
            print("      O arquivo mudou de lugar neste repositorio.")

        # Arquivo pela metade atrapalha a proxima tentativa: o teste la
        # em cima veria um .safetensors truncado e o daria por bom.
        try:
            if destino.is_file():
                destino.unlink()
        except Exception:
            pass

    return False


def esta_no_ar():
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/system_stats" % PORTA,
                               timeout=3)
        return True
    except Exception:
        return False


print()
print("=" * 66)
print("  LIGANDO O DESENHISTA")
print("=" * 66)

if esta_no_ar():
    print("\n  Ja esta no ar na porta %d. Nada a fazer." % PORTA)
else:
    # ---- 1. o ComfyUI ----------------------------------------------------
    if not RAIZ.is_dir():
        print("\n  1/4  Trazendo o ComfyUI...")
        _rodar("git clone --depth 1 "
               "https://github.com/comfyanonymous/ComfyUI %s" % RAIZ)
        _rodar("pip install -q -r requirements.txt", RAIZ)
    else:
        print("\n  1/4  ComfyUI ja esta aqui.")

    # ---- 2. a extensao que le GGUF ---------------------------------------
    #
    # O ComfyUI puro nao abre GGUF. Sem esta extensao os arquivos do city96
    # sao so bytes que ele nao reconhece.
    nos = RAIZ / "custom_nodes" / "ComfyUI-GGUF"
    if not nos.is_dir():
        print("  2/4  Trazendo o leitor de GGUF...")
        _rodar("git clone --depth 1 https://github.com/city96/ComfyUI-GGUF %s"
               % nos)
        _rodar("pip install -q -r requirements.txt", nos)
    else:
        print("  2/4  Leitor de GGUF ja esta aqui.")

    # ---- 3. os modelos ---------------------------------------------------
    print("  3/4  Modelos:")
    HF = "https://huggingface.co"
    tudo_certo = all([
        _baixar(HF + "/city96/FLUX.1-schnell-gguf/resolve/main/"
                     "flux1-schnell-Q4_K_S.gguf",
                RAIZ / "models/unet/flux1-schnell-Q4_K_S.gguf",
                "desenhista (FLUX)"),
        _baixar(HF + "/city96/t5-v1_1-xxl-encoder-gguf/resolve/main/"
                     "t5-v1_1-xxl-encoder-Q3_K_L.gguf",
                RAIZ / "models/clip/t5-v1_1-xxl-encoder-Q3_K_L.gguf",
                "leitor de frase (T5)"),
        _baixar(HF + "/comfyanonymous/flux_text_encoders/resolve/main/"
                     "clip_l.safetensors",
                RAIZ / "models/clip/clip_l.safetensors",
                "leitor de palavra"),
        # O VAE e o que falhou em 13/09. O repositorio oficial da
        # black-forest-labs passou a pedir aceite de licenca; o
        # Comfy-Org publica o MESMO arquivo aberto, e e o espelho que a
        # propria comunidade do ComfyUI usa.
        _baixar(HF + "/black-forest-labs/FLUX.1-schnell/resolve/main/"
                     "ae.safetensors",
                RAIZ / "models/vae/ae.safetensors",
                "tradutor de pixel (VAE)",
                espelhos=[
                    HF + "/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/"
                         "main/split_files/vae/ae.safetensors",
                    HF + "/StableDiffusionVN/Flux/resolve/main/Vae/"
                         "ae.safetensors",
                ]),
    ])

    if not tudo_certo:
        print("\n  [PARE] Faltou arquivo. O erro esta acima.")
    else:
        # ---- 4. ligar ----------------------------------------------------
        print("  4/4  Subindo na porta %d" % PORTA, end="")
        log = open("/content/desenhista.log", "w")
        proc_desenhista = subprocess.Popen(
            ["python3", "main.py",
             "--listen", "127.0.0.1", "--port", str(PORTA),
             "--lowvram",            # um pedaco por vez; ver o cabecalho
             "--disable-auto-launch",
             "--dont-print-server"],
            cwd=str(RAIZ), stdout=log, stderr=subprocess.STDOUT)

        for i in range(90):
            time.sleep(2)
            if esta_no_ar():
                print("\n\n  No ar em %ds." % (i * 2))
                break
            print(".", end="")
        else:
            print("\n\n  Nao subiu. O que ele disse:")
            print(open("/content/desenhista.log").read()[-2000:])

if esta_no_ar():
    # Quanto sobra na placa AGORA -- e a conta que decide se vai funcionar.
    try:
        livre = float(subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free",
             "--format=csv,noheader,nounits"],
            text=True).strip().splitlines()[0]) / 1024.0
    except Exception:
        livre = 0.0

    print()
    print("=" * 66)
    print("  O BIGODE JA PODE DESENHAR")
    print()
    print("  Peca na tela dele, em portugues mesmo:")
    print('    "crie uma imagem de um cafe ao amanhecer, luz quente,')
    print('     vista de cima, formato story"')
    print()
    print("  Formatos: quadrado, retrato, paisagem, story, capa")
    print("  Saida:    Criativos/, dentro da sua pasta de projetos")
    print("  Licenca:  Apache 2.0 - uso comercial liberado, sem marca d'agua")
    if livre:
        print()
        print("  Memoria livre na placa: %.1f GB" % livre)
        if livre < 7.5:
            print("  ATENCAO: o desenho precisa de ~7,5 GB. Troque a IA de")
            print("  texto para o granite (celula 9, NOVA = \"granite\").")
    print("=" * 66)
    print()
