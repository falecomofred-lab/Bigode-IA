"""ADAPTAR O BIGODE PARA LINUX   -   celula 5

Reescreve o config.json da copia do Colab. O codigo fica intacto: o que
muda e so a configuracao.

POR QUE PRECISA
    O config.json que veio do Drive e o do Windows. Ele aponta o motor para
    D:\\, os projetos para G:\\ e a memoria para um caminho que nao existe
    aqui. Subir o Bigode sem reaplicar isso da um programa que procura um
    motor inexistente -- e a mensagem que aparece na tela nao diz nada
    disso.

POR QUE E UM ARQUIVO SO, USADO EM DOIS LUGARES
    Esta mesma adaptacao precisa acontecer em tres momentos: na celula 5, ao
    ligar o Bigode (celula 7) e ao atualizar o codigo (celula 11). Ter o
    mesmo trecho copiado em tres lugares e como se cria diferenca entre
    eles -- alguem conserta um e esquece os outros.

    Aqui e um arquivo. Os outros dois chamam este.

Venure - venure.com.br
"""

import json
from pathlib import Path

CASA = Path("/content/bigode")
RAIZ_DRIVE = Path("/content/drive/MyDrive")
CATALOGO_PY = RAIZ_DRIVE / "projetos/Cerebro/catalogo_ia.py"

if not (CASA / "config.json").is_file():
    raise SystemExit(
        "Nao ha config.json em %s. Rode a celula 3 (trazer o Bigode)." % CASA)

# Em vez de estourar NameError quando as celulas de cima nao rodaram.
if any(n not in globals() for n in ("JANELA", "PASTA_GGUF")):
    if CATALOGO_PY.is_file():
        if "IA" not in globals():
            IA = "granite"
        exec(CATALOGO_PY.read_text(encoding="utf-8"), globals())
    else:
        JANELA = 8192
        PASTA_GGUF = ("/content/drive/Othercomputers/"
                      "USB e dispositivos externos/Pen IA")

_cfg_arq = CASA / "config.json"
_cfg = json.loads(_cfg_arq.read_text(encoding="utf-8-sig"))

_cfg["llm_url"] = "http://127.0.0.1:8082/v1/chat/completions"
_cfg["porta"] = 7000
_cfg["contexto"] = JANELA                                     # noqa: F821
_cfg["acesso_rede"] = True
_cfg["pastas_modelos"] = ["/content/modelos", PASTA_GGUF]     # noqa: F821
_cfg["pastas_liberadas"] = ["/content/drive/MyDrive", "/content/trabalho"]

# O diario e a memoria semantica moram no DRIVE, e nao na maquina do Colab:
# assim sobrevivem a desconexao, e a proxima sessao sabe onde pararam.
_cfg["pasta_historico"] = "/content/drive/MyDrive/projetos/Cerebro/Historico"
_cfg["chroma_path"] = "/content/drive/MyDrive/projetos/Cerebro/chroma_db"

# As colecoes semanticas apontam para G:\ no Windows. Sem traduzir, a
# indexacao nao acha pasta nenhuma e o Chroma fica vazio sem dizer por que.
for _dom in (_cfg.get("dominios") or {}).values():
    _dom["pastas"] = [str(p).replace("\\", "/")
                      .replace("G:/Meu Drive", "/content/drive/MyDrive")
                      .replace("G:/My Drive", "/content/drive/MyDrive")
                      for p in (_dom.get("pastas") or [])]

_cfg_arq.write_text(json.dumps(_cfg, ensure_ascii=False, indent=2),
                    encoding="utf-8")

# TERMINAL desligado: maquina emprestada com endereco publico. Rodar comando
#   arbitrario ali e risco sem contrapartida.
# NAVEGADOR ligado: a extensao vive no SEU Chrome e age no SEU navegador --
#   quem esta na nuvem e so o cerebro.
_cx_arq = CASA / "conexoes.json"
if _cx_arq.exists():
    _cx = json.loads(_cx_arq.read_text(encoding="utf-8"))
    if "terminal" in _cx:
        _cx["terminal"]["ativa"] = False
    if "navegador" in _cx:
        _cx["navegador"]["ativa"] = True
    _cx_arq.write_text(json.dumps(_cx, ensure_ascii=False, indent=2),
                       encoding="utf-8")

Path("/content/trabalho").mkdir(exist_ok=True)

# Silencioso quando chamado de dentro de outro arquivo: quem liga o Bigode
# ja tem a sua propria conversa com voce, e duas nao ajudam.
if not globals().get("_ADAPTAR_CALADO"):
    print()
    print("=" * 66)
    print("  ADAPTADO PARA LINUX")
    print("=" * 66)
    print("  janela ..... %d" % JANELA)                       # noqa: F821
    print("  IAs em ..... %s" % PASTA_GGUF)                   # noqa: F821
    print("  pastas ..... %s" % _cfg["pastas_liberadas"])
    print("  diario ..... %s" % _cfg["pasta_historico"])
    print("  terminal ... desligado (maquina emprestada)")
    print("  navegador .. ligado (cole o link nas Opcoes da extensao)")
    print("=" * 66)
    print()
