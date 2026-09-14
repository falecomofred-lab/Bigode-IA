#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FERRAMENTAS - as maos do Bigode

Cada ferramenta e uma funcao simples que recebe argumentos e devolve texto.
Ferramentas marcadas com escrita=True exigem autorizacao do usuario antes de rodar.

Venure - venure.com.br
"""

import json
import os
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parent

# Tudo que uma ferramenta devolve entra no contexto e sera reprocessado a cada
# mensagem seguinte. Em CPU, 12.000 caracteres custavam ~4.400 tokens, o que
# sozinho gastava minutos por resposta. 3.500 e o equilibrio entre ver o
# suficiente do arquivo e manter a conversa rapida.
LIMITE_TEXTO = 3500


# ==========================================================================
# Configuracao / seguranca
# ==========================================================================

def _config():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _conexoes():
    try:
        return json.loads((BASE / "conexoes.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _pastas_liberadas():
    cfg = _config()
    lista = cfg.get("pastas_liberadas") or []
    saida = []
    for item in lista:
        try:
            texto = str(item)
            saida.append(Path(texto).resolve())
            if os.name != "nt":
                traduzido = re.sub(r"^[Gg]:[\\/](?:Meu Drive|My Drive)[\\/]",
                                   "/content/drive/MyDrive/", texto).replace("\\", "/")
                if traduzido != texto:
                    saida.append(Path(traduzido).resolve())
        except Exception:
            pass
    saida.append(BASE)
    return saida


def arrumar_caminho(caminho):
    """Conserta um caminho quase certo antes de julgar se e permitido.

    Conversa real de 24/08:

        Fred: "abra o Lucas Garage, dentro do drive, pasta projetos"
        Bigode: "a pasta D:\\G\\Meu Drive\\projetos\\lucas_garage esta fora
                 dos locais permitidos... mova o projeto"

    Repare no `D:\\G\\`. O modelo escreveu o caminho sem os dois-pontos do
    disco. `Path(...).resolve()` tratou como RELATIVO e grudou na pasta onde
    o Bigode roda. Virou um caminho que nunca existiu, foi barrado, e a
    mensagem mandou o Fred mover a pasta -- conselho errado, sobre um
    problema que nao era dele.

    Modelo pequeno erra caminho o tempo todo: esquece o dois-pontos, troca
    barra, usa o nome com espaco no lugar do nome da pasta. Barrar sem
    tentar consertar joga fora minutos de trabalho por causa de um caractere.

    Aqui tentamos, em ordem: o caminho como veio; a versao com o
    dois-pontos de volta; e o mesmo nome procurado dentro de cada pasta
    liberada. O primeiro que EXISTIR vence.
    """
    bruto = str(caminho or "").strip().strip('"').strip("'")
    if not bruto:
        return bruto

    candidatos = [bruto]

    # ═══ O MESMO PROJETO, DOIS ENDERECOS ═══════════════════════════════
    #
    # 09/09, no Colab. O Fred pediu para criar um jogo de damas e entrou
    # num laco de cinco mensagens:
    #
    #     Bigode: "a pasta G:\Meu Drive\projetos/jogo-damas esta fora das
    #              pastas liberadas"
    #     Fred:   "G:\Meu Drive\projetos\jogo-damas esse eh o correto,
    #              atencao!!!"
    #     Bigode: (a mesma recusa, de novo)
    #
    # Os dois estavam certos. No computador do Fred o Drive e `G:`. No
    # Colab, o mesmo Drive fica montado em /content/drive/MyDrive. As
    # skills, o jeito_de_trabalhar.md e a cabeca do Fred falam `G:` --
    # e do lado de la esse caminho simplesmente nao existe.
    #
    # Exigir que ele aprenda dois enderecos para a mesma pasta seria
    # transferir para o Fred um problema que e nosso. Traduzimos aqui.
    trocas = [
        (r"^[Gg]:[\\/](?:Meu Drive|My Drive)[\\/]", "/content/drive/MyDrive/"),
        (r"^[Gg]:[\\/]", "/content/drive/MyDrive/"),
        (r"^[Dd]:[\\/]Cerebro[\\/]", "/content/bigode/"),
        (r"^[Dd]:[\\/]", "/content/trabalho/"),
    ] if os.name != "nt" else [
        # O caminho contrario tambem acontece: o diario escrito no Colab
        # guarda caminhos /content/..., e o Fred le no Windows.
        (r"^/content/drive/MyDrive/", "G:\\Meu Drive\\"),
        (r"^/content/bigode/", "D:\\Cerebro\\"),
    ]
    for padrao, destino in trocas:
        if re.match(padrao, bruto):
            candidatos.append(re.sub(padrao, destino, bruto))
            # A tradução é a intenção explícita do usuário. Ela deve ser
            # preservada mesmo antes de a pasta final existir, pois é assim
            # que projetos novos são criados no Drive montado.
            if os.name != "nt":
                return candidatos[-1]
            break

    # "G\Meu Drive\..." ou "G/Meu Drive/..." -> "G:\Meu Drive\..."
    #
    # So no Windows. Em Linux (Colab) nao ha letra de unidade, e "/c/algo"
    # e um caminho legitimo -- transformar em "C:\algo" criaria um caminho
    # que nunca existe.
    if os.name == "nt":
        achado = re.match(r"^[\\/]?([A-Za-z])[\\/](.+)$", bruto)
        if achado and ":" not in bruto[:3]:
            candidatos.append("%s:\\%s" % (achado.group(1).upper(),
                                          achado.group(2)))

    # Nome solto, ou caminho relativo: procura dentro de cada pasta liberada.
    #
    # A separacao usa a barra do sistema. Antes era sempre "\", e em Linux
    # isso transformava "/content/drive/x" num NOME DE ARQUIVO com barras
    # invertidas dentro -- que nunca existe. Funcionava por acidente, porque
    # o laco abaixo desfazia a troca; agora e por desenho.
    cauda = bruto.replace("\\", "/").lstrip("/") if os.name != "nt" \
        else bruto.replace("/", "\\").lstrip("\\")
    for raiz in _pastas_liberadas():
        candidatos.append(str(raiz / cauda))
        # O modelo costuma repetir um pedaco que ja esta na raiz, tipo
        # "projetos/lucas_garage" quando a raiz JA e .../projetos. Tentamos
        # tirando um nivel de cada vez, do comeco.
        partes = [x for x in cauda.replace("\\", "/").split("/") if x]
        for corte in range(1, len(partes)):
            candidatos.append(str(raiz.joinpath(*partes[corte:])))

    for c in candidatos:
        try:
            if Path(c).exists():
                return c
        except Exception:
            continue

    # ═══ E QUANDO O ALVO AINDA NAO EXISTE? ══════════════════════════════
    #
    # Criar pasta, criar projeto, escrever arquivo novo: o caminho pedido
    # NAO existe ainda -- e nao pode existir, esse e o ponto.
    #
    # A busca acima, que exige `exists()`, devolvia o caminho cru nesses
    # casos. No Colab isso significava devolver "G:\Meu Drive\..." intacto,
    # que a cerca barrava. Foi o laco de 09/09: cinco mensagens tentando
    # criar `jogo-damas`, com o Fred repetindo o caminho certo e o Bigode
    # recusando o certo.
    #
    # Aqui a regra vira: basta a PASTA DE CIMA existir. Se o lugar onde vai
    # nascer e real e liberado, o caminho serve.
    for c in candidatos:
        try:
            pai = Path(c).parent
            if pai.exists() and pai.is_dir():
                return c
        except Exception:
            continue
    return bruto


def _permitido(caminho):
    try:
        alvo = Path(arrumar_caminho(caminho)).resolve()
    except Exception:
        return False
    for raiz in _pastas_liberadas():
        try:
            alvo.relative_to(raiz)
            return True
        except ValueError:
            continue
    return False


def _negado(caminho):
    """A recusa tem de dizer onde ELE PODE ir, nao mandar voce mudar de vida.

    A mensagem antiga sugeria "mova o projeto para uma pasta aceita". Isso e
    conselho errado: a pasta certa ja estava liberada; quem errou foi o
    caminho digitado.
    """
    libs = [str(r) for r in _pastas_liberadas()]
    return ("Nao encontrei '%s' e ele nao esta nas pastas liberadas.\n\n"
            "Voce PODE entrar em:\n%s\n\n"
            "Tente de novo com o caminho completo a partir de uma dessas, "
            "ou chame listar_pasta na pasta de cima para ver os nomes reais."
            % (caminho, "\n".join("  - " + l for l in libs) or "  (nenhuma)"))


def _sensivel(caminho):
    """Arquivos de credencial nunca entram no contexto do modelo."""
    nome = Path(caminho).name.lower()
    sufixos = (".env", ".pem", ".key", ".pfx", ".p12")
    return (nome in {"config.json", "conexoes.json", "usuarios.json"}
            or nome.startswith(".env") or nome.endswith(sufixos)
            or "secret" in nome or "token" in nome)


def _corta(texto, limite=LIMITE_TEXTO):
    texto = texto or ""
    if len(texto) <= limite:
        return texto
    return (texto[:limite] +
            "\n\n[... mostrei %d de %d caracteres. Se precisar do resto, "
            "peca de novo indicando a parte.]" % (limite, len(texto)))


IGNORAR = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
           "build", ".next", "vendor", ".cache", ".idea", ".vscode"}


# --------------------------------------------------------------------------
# "Nao encontrei" e a porta de entrada da invencionice: o modelo tenta um nome,
# leva um nao seco e preenche o vazio chutando. Entao um nome errado nunca volta
# vazio - volta com os vizinhos mais parecidos, e o modelo so precisa escolher.
# --------------------------------------------------------------------------

def _normalizar(nome):
    """Tira acento, separador e palavra-cola para comparar 'sabor e prosa v2'
    com 'sabor_prosa_emporio_v2'."""
    import unicodedata
    texto = unicodedata.normalize("NFKD", (nome or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    for sujeira in ("-", "_", ".", "/", "\\"):
        texto = texto.replace(sujeira, " ")
    cola = {"e", "de", "da", "do", "a", "o", "os", "as", "the", "and"}
    return [p for p in texto.split() if p and p not in cola]


def _semelhanca(alvo, candidato):
    """0 a 1. Combina palavras em comum com parecenca de escrita."""
    import difflib
    a, b = _normalizar(alvo), _normalizar(candidato)
    if not a or not b:
        return 0.0
    comuns = len(set(a) & set(b))
    por_palavra = comuns / len(set(a))
    por_letra = difflib.SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()
    return max(por_palavra, por_letra * 0.9)


def _parecidos(caminho, quantos=6, corte=0.34):
    """Vizinhos do caminho pedido, do mais parecido para o menos.

    Procura na pasta-mae e, se ela tambem nao existir, sobe ate achar uma que
    exista. Devolve lista de (nome, e_pasta, semelhanca)."""
    alvo = Path(caminho)
    nome = alvo.name
    mae = alvo.parent
    while str(mae) not in ("", ".") and not mae.exists() and mae != mae.parent:
        mae = mae.parent
    if not mae.exists() or not mae.is_dir():
        return []
    saida = []
    try:
        for item in mae.iterdir():
            if item.name in IGNORAR:
                continue
            nota = _semelhanca(nome, item.name)
            if nota >= corte:
                saida.append((str(item), item.is_dir(), nota))
    except Exception:
        return []
    saida.sort(key=lambda x: -x[2])
    return saida[:quantos]


def _dica_parecidos(caminho, verbo="encontrei"):
    """Mensagem pronta para devolver no lugar de um 'nao encontrado' seco."""
    achados = _parecidos(caminho)
    if not achados:
        return ("Nao %s '%s' e nao ha nada parecido na pasta acima. "
                "Use listar_pasta na pasta-mae para ver o que existe de verdade. "
                "NAO invente o conteudo e NAO crie nada sem perguntar ao Fred."
                % (verbo, caminho))
    linhas = ["Nao existe '%s'. Mas achei estes nomes parecidos:" % caminho, ""]
    for cam, e_pasta, nota in achados:
        linhas.append("%s %s   (%d%% parecido)"
                      % ("[pasta]" if e_pasta else "[arquivo]", cam, round(nota * 100)))
    linhas.append("")
    linhas.append("Escolha o mais provavel e chame a ferramenta de novo com o "
                  "caminho exato acima. Nao crie pasta nova: o que o Fred quer "
                  "quase sempre ja esta nessa lista.")
    return "\n".join(linhas)


# ==========================================================================
# Arquivos
# ==========================================================================

def listar_pasta(caminho="", **_):
    caminho = arrumar_caminho(caminho)
    if not _permitido(caminho):
        return _negado(caminho)
    pasta = Path(caminho)
    if not pasta.exists():
        return _dica_parecidos(caminho)
    if not pasta.is_dir():
        return "Nao e uma pasta: %s" % caminho

    pastas, arquivos = [], []
    try:
        for item in sorted(pasta.iterdir(), key=lambda x: x.name.lower()):
            if item.name in IGNORAR:
                continue
            if item.is_dir():
                pastas.append("[pasta] " + item.name)
            else:
                try:
                    kb = item.stat().st_size / 1024
                    arquivos.append("%s  (%.1f KB)" % (item.name, kb))
                except Exception:
                    arquivos.append(item.name)
    except PermissionError:
        return "Sem permissao para ler: %s" % caminho

    linhas = ["Conteudo de %s" % caminho, ""]
    linhas += pastas + arquivos
    linhas.append("")
    linhas.append("Total: %d pastas, %d arquivos" % (len(pastas), len(arquivos)))
    return _corta("\n".join(linhas))


def ler_arquivo(caminho="", **_):
    if _sensivel(caminho):
        return "NEGADO: arquivo de configuração ou credencial protegido."
    if not _permitido(caminho):
        return "NEGADO: '%s' esta fora das pastas liberadas." % caminho
    arquivo = Path(caminho)
    if not arquivo.exists():
        return _dica_parecidos(caminho)
    try:
        if arquivo.stat().st_size > 3_000_000:
            return "Arquivo grande demais (%.1f MB)." % (arquivo.stat().st_size / 1e6)
        return _corta(arquivo.read_text(encoding="utf-8", errors="ignore"))
    except Exception as erro:
        return "Erro ao ler: %s" % erro


def buscar(termo="", pasta="", **_):
    raiz = Path(pasta) if pasta else (_pastas_liberadas()[0] if _pastas_liberadas() else BASE)
    if pasta and not _permitido(raiz):
        return "NEGADO: a pasta solicitada esta fora das pastas liberadas."
    if not raiz.exists():
        return "Pasta nao encontrada: %s" % raiz

    achados, vistos = [], 0
    padrao = (termo or "").lower()
    for arquivo in raiz.rglob("*"):
        if vistos > 4000 or len(achados) >= 40:
            break
        if any(p in IGNORAR for p in arquivo.parts):
            continue
        if not arquivo.is_file():
            continue
        if _sensivel(arquivo) or arquivo.suffix.lower() in {".gguf", ".exe", ".zip", ".png", ".jpg",
                                      ".mp4", ".pdf", ".bin", ".dll"}:
            continue
        vistos += 1
        try:
            if arquivo.stat().st_size > 900_000:
                continue
            texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if padrao in arquivo.name.lower():
            achados.append("%s  [nome do arquivo]" % arquivo)
            continue
        for numero, linha in enumerate(texto.splitlines(), 1):
            if padrao in linha.lower():
                achados.append("%s:%d  %s" % (arquivo, numero, linha.strip()[:160]))
                break

    if not achados:
        return "Nada encontrado para '%s' em %s" % (termo, raiz)
    return _corta("Resultados para '%s':\n\n" % termo + "\n".join(achados))


def escrever_arquivo(caminho="", conteudo="", **_):
    if _sensivel(caminho):
        return "NEGADO: arquivo de configuração ou credencial protegido."
    if not _permitido(caminho):
        return "NEGADO: '%s' esta fora das pastas liberadas." % caminho
    arquivo = Path(caminho)
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        existia = arquivo.exists()
        arquivo.write_text(conteudo, encoding="utf-8")
        return "%s: %s (%d caracteres)" % (
            "Atualizado" if existia else "Criado", caminho, len(conteudo))
    except Exception as erro:
        return "Erro ao escrever: %s" % erro


BINARIOS = {".gguf", ".exe", ".zip", ".rar", ".png", ".jpg", ".jpeg", ".gif",
            ".webp", ".ico", ".svg", ".mp4", ".mp3", ".pdf", ".bin", ".dll",
            ".db", ".sqlite", ".sqlite3", ".woff", ".woff2", ".ttf", ".lock"}


def raio_x(caminho="", **_):
    """Inventario real de um projeto, feito em codigo e nao pelo modelo.

    Este e o antidoto contra auditoria inventada: o modelo nao precisa adivinhar
    quais arquivos existem, porque recebe a lista completa e verdadeira de uma
    vez, com tamanho e numero de linhas. Depois disso ele so pode ler o que
    esta na lista."""
    if not _permitido(caminho):
        return "NEGADO: '%s' esta fora das pastas liberadas." % caminho
    raiz = Path(caminho)
    if not raiz.exists():
        return _dica_parecidos(caminho)
    if not raiz.is_dir():
        return "Nao e uma pasta: %s" % caminho

    itens, pulados, total_linhas = [], 0, 0
    for arquivo in sorted(raiz.rglob("*"), key=lambda p: str(p).lower()):
        if any(p in IGNORAR for p in arquivo.parts) or not arquivo.is_file():
            continue
        rel = str(arquivo.relative_to(raiz)).replace("\\", "/")
        try:
            tam = arquivo.stat().st_size
        except Exception:
            continue
        if arquivo.suffix.lower() in BINARIOS:
            pulados += 1
            continue
        if tam > 400_000:
            itens.append((rel, tam, None))
            continue
        try:
            linhas = arquivo.read_text(encoding="utf-8", errors="ignore").count("\n") + 1
        except Exception:
            linhas = None
        if linhas:
            total_linhas += linhas
        itens.append((rel, tam, linhas))
        if len(itens) >= 300:
            break

    if not itens:
        return ("A pasta %s existe mas nao tem nenhum arquivo de texto/codigo "
                "(%d binarios ignorados). Diga isso ao Fred; nao invente "
                "conteudo." % (caminho, pulados))

    linhas_saida = ["RAIO-X DE %s" % caminho, "",
                    "%d arquivos de codigo/texto, %d linhas no total."
                    % (len(itens), total_linhas), ""]
    for rel, tam, ln in itens:
        linhas_saida.append("%-58s %6s  %s"
                            % (rel, "%.0fKB" % (tam / 1024),
                               ("%d linhas" % ln) if ln else "grande demais"))
    linhas_saida += ["",
                     "Esta lista e a verdade. Nenhum outro arquivo existe neste "
                     "projeto. Para auditar, chame ler_arquivo em cada um destes "
                     "caminhos (prefixados por %s) e comente SO o que voce leu. "
                     "Nunca cite arquivo que nao esteja nesta lista." % caminho]
    return _corta("\n".join(linhas_saida), 6000)


def criar_pasta(caminho="", confirmado=False, **_):
    if not _permitido(caminho):
        return "NEGADO: '%s' esta fora das pastas liberadas." % caminho
    if Path(caminho).exists():
        return "Ja existe: %s (nada a fazer)" % caminho

    # Criar pasta parecida com uma que ja existe e como o Bigode estraga o
    # Drive do Fred: nasce 'sabor_e_prosa_v2' ao lado de 'sabor_prosa_emporio_v2'
    # e ninguem mais sabe qual e a boa. So passa com confirmado=true.
    if not confirmado:
        vizinhos = [(c, n) for c, e_pasta, n in _parecidos(caminho, corte=0.5) if e_pasta]
        if vizinhos:
            linhas = ["NAO CRIEI. Ja existe pasta muito parecida com '%s':" % caminho, ""]
            linhas += ["%s   (%d%% parecido)" % (c, round(n * 100)) for c, n in vizinhos]
            linhas.append("")
            linhas.append("Quase sempre o Fred esta falando de uma dessas. Use a "
                          "existente. Se for mesmo um projeto novo, confirme com "
                          "ele e chame de novo com confirmado=true.")
            return "\n".join(linhas)
    try:
        Path(caminho).mkdir(parents=True, exist_ok=True)
        return "Pasta criada: %s" % caminho
    except Exception as erro:
        return "Erro: %s" % erro


def mover(origem="", destino="", **_):
    if _sensivel(origem) or _sensivel(destino):
        return "NEGADO: arquivo de configuração ou credencial protegido."
    if not (_permitido(origem) and _permitido(destino)):
        return "NEGADO: origem ou destino fora das pastas liberadas."
    try:
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(origem, destino)
        return "Movido: %s -> %s" % (origem, destino)
    except Exception as erro:
        return "Erro: %s" % erro


def apagar(caminho="", **_):
    if _sensivel(caminho):
        return "NEGADO: arquivo de configuração ou credencial protegido."
    if not _permitido(caminho):
        return "NEGADO: '%s' esta fora das pastas liberadas." % caminho
    alvo = Path(caminho)
    try:
        if alvo.is_dir():
            shutil.rmtree(alvo)
            return "Pasta apagada: %s" % caminho
        alvo.unlink()
        return "Arquivo apagado: %s" % caminho
    except Exception as erro:
        return "Erro: %s" % erro


def rodar_comando(comando="", pasta="", **_):
    if pasta and not _permitido(pasta):
        return "NEGADO: a pasta de trabalho esta fora das pastas liberadas."
    diretorio = pasta if pasta else str(BASE)
    try:
        resultado = subprocess.run(
            comando, shell=True, cwd=diretorio, capture_output=True,
            text=True, timeout=180, encoding="utf-8", errors="ignore",
        )
        saida = (resultado.stdout or "") + (resultado.stderr or "")
        return _corta("Codigo de saida: %d\n\n%s" % (resultado.returncode, saida.strip()), 6000)
    except subprocess.TimeoutExpired:
        return "Comando passou de 180 segundos e foi interrompido."
    except Exception as erro:
        return "Erro: %s" % erro


# ==========================================================================
# GitHub
# ==========================================================================

def _github(caminho_api, metodo="GET", corpo=None):
    conexoes = _conexoes()
    dados = conexoes.get("github", {})
    token = (dados.get("token") or "").strip()
    if not token:
        return None, "GitHub sem token. Configure em Conexoes."

    url = "https://api.github.com" + caminho_api
    cabecalhos = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Bigode-Venure",
        "Authorization": "Bearer " + token,
    }
    corpo_bytes = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    if corpo_bytes:
        cabecalhos["Content-Type"] = "application/json"

    pedido = urllib.request.Request(url, data=corpo_bytes, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            texto = resposta.read().decode("utf-8", "ignore")
            return (json.loads(texto) if texto.strip() else {}), None
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", "ignore")[:400]
        return None, "GitHub respondeu %s: %s" % (erro.code, detalhe)
    except Exception as erro:
        return None, "Falha no GitHub: %s" % erro


def github_repos(**_):
    dados, erro = _github("/user/repos?per_page=100&sort=updated")
    if erro:
        return erro
    linhas = ["Seus repositorios (%d):" % len(dados), ""]
    for repo in dados:
        linhas.append("- %s  [%s]  %s" % (
            repo.get("full_name"),
            "privado" if repo.get("private") else "publico",
            (repo.get("description") or "")[:80],
        ))
    return _corta("\n".join(linhas))


def github_ler(repo="", caminho="", **_):
    if not repo:
        return "Informe o repositorio no formato usuario/nome."
    dados, erro = _github("/repos/%s/contents/%s" % (repo, caminho))
    if erro:
        return erro
    if isinstance(dados, list):
        linhas = ["Conteudo de %s/%s:" % (repo, caminho), ""]
        for item in dados:
            linhas.append("%s %s" % ("[pasta]" if item["type"] == "dir" else "       ",
                                     item["name"]))
        return _corta("\n".join(linhas))
    import base64
    try:
        conteudo = base64.b64decode(dados.get("content", "")).decode("utf-8", "ignore")
        return _corta(conteudo)
    except Exception:
        return "Nao consegui decodificar esse arquivo (pode ser binario)."


def github_criar_repo(nome="", privado=True, descricao="", **_):
    corpo = {"name": nome, "private": bool(privado), "description": descricao,
             "auto_init": False}
    dados, erro = _github("/user/repos", "POST", corpo)
    if erro:
        return erro
    return "Repositorio criado: %s" % dados.get("html_url")


def github_commit(repo="", caminho="", conteudo="", mensagem="", **_):
    import base64
    if not mensagem:
        mensagem = "Atualiza %s via Bigode" % caminho

    sha = None
    atual, _erro = _github("/repos/%s/contents/%s" % (repo, caminho))
    if isinstance(atual, dict):
        sha = atual.get("sha")

    corpo = {
        "message": mensagem,
        "content": base64.b64encode(conteudo.encode("utf-8")).decode("ascii"),
    }
    if sha:
        corpo["sha"] = sha

    dados, erro = _github("/repos/%s/contents/%s" % (repo, caminho), "PUT", corpo)
    if erro:
        return erro
    return "Commit feito em %s/%s" % (repo, caminho)


def github_issue(repo="", titulo="", corpo="", **_):
    dados, erro = _github("/repos/%s/issues" % repo, "POST",
                          {"title": titulo, "body": corpo})
    if erro:
        return erro
    return "Issue criada: %s" % dados.get("html_url")


# ==========================================================================
# Web
# ==========================================================================

def _baixar(url, timeout=25, dados=None):
    """Busca uma pagina. Com `dados`, manda por POST.

    O User-Agent de navegador de verdade nao e disfarce: buscadores
    devolvem pagina diferente (ou nenhuma) para quem se identifica como
    robo, e a nossa e uma consulta feita por uma pessoa, uma de cada vez.
    """
    corpo = None
    cabecalhos = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }
    if dados is not None:
        corpo = urllib.parse.urlencode(dados).encode("utf-8")
        cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"

    pedido = urllib.request.Request(url, data=corpo, headers=cabecalhos)
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        bruto = resposta.read()
    return bruto.decode("utf-8", "ignore")


def _html_para_texto(html):
    html = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", html)
    texto = re.sub(r"<[^>]+>", " ", html)
    for de, para in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"),
                     ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")]:
        texto = texto.replace(de, para)
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n\s*\n\s*\n+", "\n\n", texto)
    return texto.strip()


def _limpar_link(link):
    """O DuckDuckGo embrulha o destino real dentro de uma URL de redirecionamento."""
    if "uddg=" in link:
        try:
            link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
        except Exception:
            pass
    if link.startswith("//"):
        link = "https:" + link
    return link


# Tres formas de ler a mesma pagina de resultados. Elas existem porque o
# DuckDuckGo muda o HTML de tempos em tempos, e quando muda, uma expressao
# sozinha para de achar QUALQUER COISA -- e o Bigode dizia "Sem resultados
# para 'cannabis no brasil'", que soa como "pesquisei e nao ha nada". Era
# falso: ele pesquisou e nao soube ler a resposta.
_PADROES_BUSCA = (
    # layout classico do /html/
    r'(?is)<a[^>]+class="result__a"[^>]+href="(.*?)".*?>(.*?)</a>.*?'
    r'class="result__snippet".*?>(.*?)</a>',
    # mesma coisa, mas com os atributos na ordem inversa
    r'(?is)<a[^>]+href="(.*?)"[^>]+class="result__a".*?>(.*?)</a>.*?'
    r'class="result__snippet".*?>(.*?)</a>',
    # layout do /lite/: tabela simples, sem classe no link
    r'(?is)<a[^>]+class="result-link"[^>]+href="(.*?)".*?>(.*?)</a>.*?'
    r'class="result-snippet".*?>(.*?)</td>',
)


def _wikipedia(consulta, quantos=4):
    """Fundo de poco da busca: a Wikipedia em portugues.

    ═══ POR QUE ISTO EXISTE ═══════════════════════════════════════════════

    09/09/2026. O Fred perguntou "quem foi Corisco no cangaco". O Bigode
    tinha acabado de afirmar, com toda a confianca, que Corisco era um
    canabinoide extraido da Corynanthe yohimbe -- invencao completa. A
    resposta certa dependia de uma busca, e a busca respondeu:

        "a pagina de resultados veio num formato que nao sei ler"

    O DuckDuckGo mudou o HTML de novo. Ja tinha mudado dias antes. Vai
    mudar outra vez.

    Raspar HTML de buscador e uma corrida que nunca se ganha: o formato e
    deles, muda quando eles querem, e nao ha aviso. A Wikipedia tem uma API
    publica, estavel ha anos, que devolve JSON -- e cobre exatamente o tipo
    de pergunta em que um modelo de 7B mais inventa: quem foi alguem, o que
    e alguma coisa, quando aconteceu.

    Nao substitui o buscador para noticia, preco ou site de empresa. Mas
    garante que "quem foi Corisco" nunca mais fique sem resposta.
    """
    api = ("https://pt.wikipedia.org/w/api.php?action=query&list=search"
           "&srsearch=%s&srlimit=%d&format=json&utf8=1"
           % (urllib.parse.quote(consulta), quantos))
    dados = json.loads(_baixar(api, timeout=20))
    achados = (dados.get("query") or {}).get("search") or []
    if not achados:
        return []

    itens = []
    for a in achados:
        titulo = a.get("title", "")
        # O `snippet` vem com <span> de destaque; vira texto limpo.
        trecho = _html_para_texto(a.get("snippet", "")).strip()
        endereco = ("https://pt.wikipedia.org/wiki/"
                    + urllib.parse.quote(titulo.replace(" ", "_")))
        itens.append((endereco, titulo, trecho))
    return itens


def web_buscar(consulta="", **_):
    consulta = (consulta or "").strip()
    if not consulta:
        return "Preciso saber o que pesquisar."

    # POST em vez de GET: o /html/ do DuckDuckGo passou a recusar consulta
    # na URL em 09/09. O formulario deles sempre foi POST -- estavamos
    # usando o atalho que agora fechou.
    tentativas = [
        ("https://html.duckduckgo.com/html/", {"q": consulta}),
        ("https://lite.duckduckgo.com/lite/", {"q": consulta}),
        ("https://www.mojeek.com/search?q=" + urllib.parse.quote(consulta), None),
    ]

    ultimo_erro = ""
    for base, corpo in tentativas:
        try:
            html = _baixar(base, dados=corpo)
        except Exception as erro:
            ultimo_erro = str(erro)
            continue

        itens = []
        for padrao in _PADROES_BUSCA:
            itens = re.findall(padrao, html)
            if itens:
                break

        if not itens:
            # Ultimo recurso: qualquer link externo com texto, na ordem em
            # que aparece. Perde o resumo, mas devolve fonte -- que e o que
            # o selo de evidencia precisa.
            crus = re.findall(r'(?is)<a[^>]+href="(https?://[^"]+|/l/\?[^"]+)"[^>]*>(.*?)</a>', html)
            vistos, itens = set(), []
            for link, titulo in crus:
                limpo = _limpar_link(link)
                texto = _html_para_texto(titulo).strip()
                if (not texto or len(texto) < 12 or "duckduckgo" in limpo
                        or limpo in vistos):
                    continue
                vistos.add(limpo)
                itens.append((link, titulo, ""))
                if len(itens) >= 8:
                    break

        if not itens:
            ultimo_erro = "a página de resultados veio num formato que não sei ler"
            continue

        linhas = ["Resultados para '%s':" % consulta, ""]
        for link, titulo, trecho in itens[:8]:
            linhas.append("- " + _html_para_texto(titulo))
            linhas.append("  " + _limpar_link(link))
            if trecho:
                linhas.append("  " + _html_para_texto(trecho)[:200])
            linhas.append("")
        return _corta("\n".join(linhas))

    # Nenhum buscador respondeu. Antes de desistir, a Wikipedia -- que tem
    # API de verdade e nao muda de formato a cada semana.
    try:
        itens = _wikipedia(consulta)
    except Exception as erro:
        itens = []
        ultimo_erro = "%s; e a Wikipedia tambem falhou (%s)" % (ultimo_erro, erro)

    if itens:
        linhas = ["Resultados para '%s' (Wikipedia em portugues):" % consulta,
                  ""]
        for link, titulo, trecho in itens:
            linhas.append("- " + titulo)
            linhas.append("  " + link)
            if trecho:
                linhas.append("  " + trecho[:250])
            linhas.append("")
        linhas.append("(Os buscadores nao responderam agora; isto veio da "
                      "Wikipedia. Para ir alem, peca para eu abrir um destes "
                      "enderecos com web_ler.)")
        return _corta("\n".join(linhas))

    # Nem a Wikipedia. Dizer o motivo, e nao "sem resultados": a diferenca
    # entre "nao existe" e "nao consegui" muda completamente o que o Fred faz.
    return ("Nao consegui pesquisar '%s' agora. Motivo: %s.\n"
            "Isto e uma falha da busca, NAO quer dizer que o assunto nao "
            "exista -- e NAO me autoriza a responder de memoria. Se voce "
            "tiver o endereco de um site, posso abrir com web_ler ou pelo "
            "navegador." % (consulta, ultimo_erro or "desconhecido"))


def web_ler(url="", **_):
    if not url.startswith("http"):
        url = "https://" + url
    try:
        return _corta("Conteudo de %s\n\n" % url + _html_para_texto(_baixar(url)), 10000)
    except Exception as erro:
        return "Nao consegui abrir %s: %s" % (url, erro)


# --------------------------------------------------------------------------
# calculo seguro: somente aritmetica, sem executar codigo arbitrario
# --------------------------------------------------------------------------
def calcular(expressao="", **_):
    import ast
    import operator as op
    permitidos = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
                  ast.Div: op.truediv, ast.Pow: op.pow, ast.Mod: op.mod,
                  ast.USub: op.neg, ast.UAdd: op.pos}
    texto = str(expressao or "").strip().replace(",", ".")
    if not texto:
        return "Preciso da expressão ou dos números para calcular."
    try:
        arvore = ast.parse(texto, mode="eval")
        def visitar(no):
            if isinstance(no, ast.Expression): return visitar(no.body)
            if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
                return no.value
            if isinstance(no, ast.BinOp) and type(no.op) in permitidos:
                a, b = visitar(no.left), visitar(no.right)
                if isinstance(no.op, ast.Pow) and abs(b) > 100: raise ValueError("expoente grande")
                return permitidos[type(no.op)](a, b)
            if isinstance(no, ast.UnaryOp) and type(no.op) in permitidos:
                return permitidos[type(no.op)](visitar(no.operand))
            raise ValueError("use apenas números e + - * / % ** ( )")
        resultado = visitar(arvore)
        return "Resultado: %s" % (int(resultado) if isinstance(resultado, float) and resultado.is_integer() else resultado)
    except ZeroDivisionError:
        return "Não é possível dividir por zero."
    except Exception as erro:
        return "Não consegui calcular: %s" % erro

# ==========================================================================
# Utilidades: data/hora, clima e dados publicos do Brasil
# Todas gratuitas e sem chave de acesso.
# ==========================================================================

def _json_api(url, timeout=15):
    pedido = urllib.request.Request(url, headers={
        "User-Agent": "Bigode-Venure/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return json.loads(resposta.read().decode("utf-8", "ignore"))


DIAS = ["segunda-feira", "terca-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sabado", "domingo"]
MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def agora(**_):
    """Data e hora reais. Modelo de linguagem nao sabe que dia e hoje."""
    from datetime import datetime
    a = datetime.now()
    return ("Agora: %s, %d de %s de %d, %02d:%02d\n"
            "Formato ISO: %s\n"
            "Semana do ano: %s | Dia do ano: %s"
            % (DIAS[a.weekday()], a.day, MESES[a.month - 1], a.year, a.hour, a.minute,
               a.isoformat(timespec="seconds"),
               a.strftime("%W"), a.strftime("%j")))


def clima(cidade="", **_):
    """Previsao do tempo pelo Open-Meteo (sem chave)."""
    if not cidade.strip():
        return "Informe a cidade."
    try:
        busca = _json_api("https://geocoding-api.open-meteo.com/v1/search?name="
                          + urllib.parse.quote(cidade) + "&count=1&language=pt")
        lugares = busca.get("results") or []
        if not lugares:
            return "Nao encontrei a cidade '%s'." % cidade
        p = lugares[0]
        dados = _json_api(
            "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
            "&current=temperature_2m,relative_humidity_2m,precipitation,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            "&timezone=America%%2FSao_Paulo&forecast_days=3"
            % (p["latitude"], p["longitude"]))
        atual = dados.get("current", {})
        dia = dados.get("daily", {})
        linhas = ["Tempo em %s (%s)" % (p.get("name"), p.get("admin1", "")), "",
                  "Agora: %s C, umidade %s%%, chuva %s mm"
                  % (atual.get("temperature_2m"), atual.get("relative_humidity_2m"),
                     atual.get("precipitation"))]
        for i, data in enumerate(dia.get("time", [])[:3]):
            linhas.append("%s: min %s C, max %s C, chance de chuva %s%%"
                          % (data, dia["temperature_2m_min"][i],
                             dia["temperature_2m_max"][i],
                             dia["precipitation_probability_max"][i]))
        return "\n".join(linhas)
    except Exception as erro:
        return "Nao consegui consultar o tempo: %s" % erro


def cep(cep="", **_):
    """Endereco completo a partir do CEP (ViaCEP)."""
    numero = re.sub(r"\D", "", cep or "")
    if len(numero) != 8:
        return "CEP invalido. Use 8 digitos."
    try:
        d = _json_api("https://viacep.com.br/ws/%s/json/" % numero)
        if d.get("erro"):
            return "CEP %s nao encontrado." % numero
        return ("CEP %s\nLogradouro: %s\nBairro: %s\nCidade: %s/%s\nIBGE: %s\nDDD: %s"
                % (d.get("cep"), d.get("logradouro"), d.get("bairro"),
                   d.get("localidade"), d.get("uf"), d.get("ibge"), d.get("ddd")))
    except Exception as erro:
        return "Falha ao consultar o CEP: %s" % erro


def cnpj(cnpj="", **_):
    """Dados cadastrais de uma empresa (BrasilAPI / Receita Federal)."""
    numero = re.sub(r"\D", "", cnpj or "")
    if len(numero) != 14:
        return "CNPJ invalido. Use 14 digitos."
    try:
        d = _json_api("https://brasilapi.com.br/api/cnpj/v1/%s" % numero)
        socios = d.get("qsa") or []
        linhas = [
            "CNPJ: %s" % d.get("cnpj"),
            "Razao social: %s" % d.get("razao_social"),
            "Nome fantasia: %s" % (d.get("nome_fantasia") or "-"),
            "Situacao: %s" % d.get("descricao_situacao_cadastral"),
            "Abertura: %s" % d.get("data_inicio_atividade"),
            "Atividade: %s" % d.get("cnae_fiscal_descricao"),
            "Endereco: %s, %s - %s, %s/%s - CEP %s"
            % (d.get("logradouro"), d.get("numero"), d.get("bairro"),
               d.get("municipio"), d.get("uf"), d.get("cep")),
            "Telefone: %s" % (d.get("ddd_telefone_1") or "-"),
            "Capital social: R$ %s" % d.get("capital_social"),
        ]
        if socios:
            linhas.append("Socios: " + ", ".join(
                s.get("nome_socio", "") for s in socios[:8]))
        return "\n".join(linhas)
    except urllib.error.HTTPError:
        return "CNPJ %s nao encontrado na Receita." % numero
    except Exception as erro:
        return "Falha ao consultar o CNPJ: %s" % erro


def feriados(ano="", **_):
    """Feriados nacionais do ano (BrasilAPI). Util para prazos de contrato."""
    from datetime import datetime
    alvo = re.sub(r"\D", "", str(ano or "")) or str(datetime.now().year)
    try:
        d = _json_api("https://brasilapi.com.br/api/feriados/v1/%s" % alvo)
        return ("Feriados nacionais de %s:\n" % alvo) + "\n".join(
            "%s - %s" % (f.get("date"), f.get("name")) for f in d)
    except Exception as erro:
        return "Falha ao consultar feriados: %s" % erro


def cotacao(moedas="USD-BRL", **_):
    """Cambio do dia (AwesomeAPI). Ex: USD-BRL, EUR-BRL."""
    par = (moedas or "USD-BRL").upper().strip()
    try:
        d = _json_api("https://economia.awesomeapi.com.br/json/last/" + par)
        linhas = []
        for chave, v in d.items():
            linhas.append("%s/%s: R$ %s (min %s, max %s, variacao %s%%) em %s"
                          % (v.get("code"), v.get("codein"), v.get("bid"),
                             v.get("low"), v.get("high"), v.get("pctChange"),
                             v.get("create_date")))
        return "\n".join(linhas) or "Par nao encontrado."
    except Exception as erro:
        return "Falha ao consultar cotacao: %s" % erro


# ==========================================================================
# Memoria
# ==========================================================================

def memoria(consulta="", **_):
    pasta = BASE / "memoria" / "projetos"
    if not pasta.exists():
        return "Memoria vazia. Rode ATUALIZAR_MEMORIA.bat."

    termos = {t for t in re.findall(r"[a-zA-Z0-9À-ÿ_\-]{3,}",
                                    (consulta or "").lower())}
    pontuados = []
    for arquivo in pasta.glob("*.md"):
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        minusculo = texto.lower()
        pontos = sum(1 for t in termos if t in minusculo)
        if t_in_nome := sum(4 for t in termos if t in arquivo.stem.lower()):
            pontos += t_in_nome
        if pontos:
            pontuados.append((pontos, arquivo, texto))

    if not pontuados:
        nomes = sorted(a.stem for a in pasta.glob("*.md"))
        return "Nada especifico encontrado. Projetos na memoria:\n\n" + "\n".join(
            "- " + n for n in nomes)

    pontuados.sort(key=lambda x: x[0], reverse=True)
    partes = [texto[:5000] for _p, _a, texto in pontuados[:2]]
    return _corta("\n\n---\n\n".join(partes))


# ==========================================================================
# Registro
# ==========================================================================

def ligada_navegador():
    """A conexao do Chrome esta ligada nas Conexoes? (usada pelo cerebro.py
    para decidir se le a pagina antes de falar com o modelo)."""
    item = _conexoes().get("navegador")
    if isinstance(item, dict):
        return bool(item.get("ativa", True))
    return True


def _no_navegador(**_):
    """Executada pela extensao do Chrome. O cerebro.py intercepta antes daqui."""
    return ("A extensao do Chrome nao esta conectada. Abra o painel do Bigode no "
            "navegador para eu poder agir nas paginas.")


def _desenhar(descricao="", formato="", nome="", modelo="", negativo="",
              passos=4, guidance=3.5, semente=0, pasta_saida="", **_):
    """Passa o pedido para o ComfyUI, que roda num processo separado.

    O `import` fica AQUI DENTRO, e nao no topo do arquivo, de proposito: o
    `imagens.py` e opcional. Quem roda o Bigode no pendrive nao tem ComfyUI
    nenhum, e um import no topo derrubaria o carregamento do ferramentas.py
    inteiro por causa de uma funcao que aquela maquina nunca vai usar.
    """
    try:
        import imagens
    except Exception as erro:
        return ("O modulo de desenho nao carregou (%s). Rode o "
                "sincronizar-bigode.ps1 e a celula 10 do Colab." % erro)
    return imagens.gerar_imagem(
        descricao=descricao, formato=formato, nome=nome, modelo=modelo,
        negativo=negativo, passos=passos, guidance=guidance, semente=semente,
        pasta_saida=pasta_saida)


def usar_habilidade(nome="", **_):
    """Carrega um manual especializado para o contexto atual."""
    import habilidades
    return habilidades.abrir((nome or "").strip())


def apresentar_plano(objetivo="", passos="", **_):
    """Tratada dentro do cerebro.py: para o fluxo e espera o Fred aprovar."""
    return "aguardando aprovacao"


def criar_projeto(nome="", descricao="", stack="", **_):
    """Cria a pasta do projeto novo dentro da area de projetos do Fred."""
    cfg = _config()
    raiz = Path(cfg.get("pasta_projetos") or (_pastas_liberadas()[0]))
    if not nome.strip():
        return "Informe o nome do projeto."

    limpo = re.sub(r'[<>:"/\\|?*]', "-", nome.strip())[:60]
    destino = raiz / limpo
    if not _permitido(destino):
        return "NEGADO: '%s' esta fora das pastas liberadas." % destino

    if destino.exists():
        return ("A pasta ja existe: %s\nConteudo atual:\n%s"
                % (destino, listar_pasta(caminho=str(destino))))
    try:
        destino.mkdir(parents=True)
        if descricao or stack:
            leiame = "# %s\n\n%s\n" % (limpo, descricao)
            if stack:
                leiame += "\n**Tecnologias:** %s\n" % stack
            (destino / "README.md").write_text(leiame, encoding="utf-8")
        return ("Projeto criado em: %s\nUse este caminho como base para todos os "
                "arquivos deste projeto." % destino)
    except Exception as erro:
        return "Erro ao criar: %s" % erro


# ===================== NOVA FERRAMENTA: VAULT =====================
def buscar_no_chroma(consulta: str, colecao: str = "", limite: int = 5) -> str:
    """Busca trechos semanticamente similares nas coleções ChromaDB."""
    import chroma_memoria
    return chroma_memoria.buscar_no_chroma(consulta, colecao, limite)


CATALOGO = {
    "usar_habilidade": {"fn": usar_habilidade, "escrita": False, "args": "nome",
                        "desc": "Carrega um manual especializado do Fred antes de executar."},
    "apresentar_plano": {"fn": apresentar_plano, "escrita": False,
                         "args": "objetivo, passos",
                         "desc": "OBRIGATORIO antes de alterar algo. Mostra o plano e espera aprovacao."},
    "criar_projeto":    {"fn": criar_projeto, "escrita": True,
                         "args": "nome, descricao, stack",
                         "desc": "Cria a pasta de um projeto novo e devolve o caminho base."},
    "buscar_no_chroma": {"fn": buscar_no_chroma, "escrita": False,
                         "args": "consulta, colecao, limite",
                         "desc": "Busca trechos semanticamente similares no ChromaDB por coleção."},

    # leitura - livres
    "listar_pasta":   {"fn": listar_pasta,   "escrita": False, "args": "caminho",
                       "desc": "Lista arquivos e pastas de um diretorio."},
    "ler_arquivo":    {"fn": ler_arquivo,    "escrita": False, "args": "caminho",
                       "desc": "Le o conteudo de um arquivo."},
    "buscar":         {"fn": buscar,         "escrita": False, "args": "termo, pasta",
                       "desc": "Procura um texto dentro dos arquivos de uma pasta."},
    "memoria":        {"fn": memoria,        "escrita": False, "args": "consulta",
                       "desc": "Consulta o que o Bigode sabe dos projetos do Fred."},
    "github_repos":   {"fn": github_repos,   "escrita": False, "args": "",
                       "desc": "Lista os repositorios do GitHub."},
    "github_ler":     {"fn": github_ler,     "escrita": False, "args": "repo, caminho",
                       "desc": "Le arquivo ou pasta de um repositorio."},
    "web_buscar":     {"fn": web_buscar,     "escrita": False, "args": "consulta",
                       "desc": "Pesquisa na internet."},
    "web_ler":        {"fn": web_ler,        "escrita": False, "args": "url",
                       "desc": "Abre uma pagina e devolve o texto."},

    # desenho - executado pelo ComfyUI, num processo separado
    #
    # `escrita: True` porque ela CRIA arquivo no disco do Fred. Toda
    # ferramenta que escreve passa pela autorizacao -- desenhar nao e
    # excecao, mesmo parecendo inofensivo.
    "gerar_imagem":   {"fn": _desenhar,       "escrita": True,
                       "args": "descricao, formato, nome",
                       "desc": "Cria uma imagem a partir de uma descricao e "
                               "salva em PNG de alta resolucao, sem marca "
                               "d'agua. Formatos: quadrado, retrato, "
                               "paisagem, story, capa. Descreva com "
                               "riqueza de detalhe - luz, angulo, estilo, "
                               "cores - que o resultado melhora muito."},

    # navegador - executadas pela extensao do Chrome
    "navegador_ver":      {"fn": _no_navegador, "escrita": False, "args": "",
                           "desc": "Le a pagina aberta no Chrome e lista os elementos "
                                   "clicaveis numerados. Use SEMPRE antes de clicar."},
    "navegador_ir":       {"fn": _no_navegador, "escrita": True, "args": "url",
                           "desc": "Abre um endereco na aba atual do Chrome."},
    "navegador_clicar":   {"fn": _no_navegador, "escrita": True, "args": "numero",
                           "desc": "Clica no elemento com aquele numero da lista."},
    "navegador_escrever": {"fn": _no_navegador, "escrita": True, "args": "numero, texto",
                           "desc": "Digita um texto no campo com aquele numero."},
    "navegador_teclar":   {"fn": _no_navegador, "escrita": True, "args": "tecla",
                           "desc": "Aperta uma tecla: Enter, Tab, Escape, ArrowDown."},
    "navegador_rolar":    {"fn": _no_navegador, "escrita": False, "args": "direcao",
                           "desc": "Rola a pagina: baixo, cima, topo ou fim."},
    "navegador_esperar":  {"fn": _no_navegador, "escrita": False, "args": "segundos",
                           "desc": "Espera a pagina carregar antes de continuar."},

    # utilidades - dados reais, gratuitas e sem chave
    "calcular":       {"fn": calcular,       "escrita": False, "args": "expressao",
                       "desc": "Calcula uma expressão aritmética com segurança."},
    "agora":          {"fn": agora,          "escrita": False, "args": "",
                       "desc": "Data e hora reais. Use antes de calcular prazo ou dizer que dia e hoje."},
    "clima":          {"fn": clima,          "escrita": False, "args": "cidade",
                       "desc": "Previsao do tempo de uma cidade."},
    "cep":            {"fn": cep,            "escrita": False, "args": "cep",
                       "desc": "Endereco completo a partir de um CEP."},
    "cnpj":           {"fn": cnpj,           "escrita": False, "args": "cnpj",
                       "desc": "Dados de empresa na Receita: razao social, situacao, endereco, socios."},
    "feriados":       {"fn": feriados,       "escrita": False, "args": "ano",
                       "desc": "Feriados nacionais do ano."},
    "cotacao":        {"fn": cotacao,        "escrita": False, "args": "moedas",
                       "desc": "Cotacao de moeda do dia. Ex: USD-BRL."},

    "raio_x":         {"fn": raio_x,         "escrita": False, "args": "caminho",
                       "desc": "Inventario completo e real de um projeto: todos os "
                               "arquivos com tamanho e numero de linhas. Use SEMPRE "
                               "antes de auditar, revisar ou analisar um projeto."},

    # escrita - exigem autorizacao
    "escrever_arquivo": {"fn": escrever_arquivo, "escrita": True, "args": "caminho, conteudo",
                         "desc": "Cria ou substitui um arquivo."},
    "criar_pasta":      {"fn": criar_pasta,      "escrita": True, "args": "caminho",
                         "desc": "Cria uma pasta."},
    "mover":            {"fn": mover,            "escrita": True, "args": "origem, destino",
                         "desc": "Move ou renomeia."},
    "apagar":           {"fn": apagar,           "escrita": True, "args": "caminho",
                         "desc": "Apaga arquivo ou pasta."},
    "rodar_comando":    {"fn": rodar_comando,    "escrita": True, "args": "comando, pasta",
                         "desc": "Executa um comando no terminal."},
    "github_criar_repo": {"fn": github_criar_repo, "escrita": True, "args": "nome, privado, descricao",
                          "desc": "Cria um repositorio novo."},
    "github_commit":     {"fn": github_commit,     "escrita": True, "args": "repo, caminho, conteudo, mensagem",
                          "desc": "Envia um arquivo para o repositorio."},
    "github_issue":      {"fn": github_issue,      "escrita": True, "args": "repo, titulo, corpo",
                          "desc": "Abre uma issue."},
}


PARAMETROS = {
    "usar_habilidade":   {"nome": "Identificador da habilidade, ex: contrato-locacao"},
    "apresentar_plano":  {"objetivo": "O que sera feito",
                          "passos": "Um passo por linha"},
    "criar_projeto":     {"nome": "Nome da pasta do projeto",
                          "descricao": "O que o projeto faz",
                          "stack": "Tecnologias, ex: Node + Express + SQLite"},
    "buscar_no_chroma":  {"consulta": "Pergunta ou palavras-chave para busca semântica",
                          "colecao": "Nome da coleção/domínio ou 'todas'",
                          "limite": "Quantidade máxima de trechos relevantes"},
    "listar_pasta":      {"caminho": "Caminho completo da pasta"},
    "ler_arquivo":       {"caminho": "Caminho completo do arquivo"},
    "buscar":            {"termo": "Texto a procurar", "pasta": "Pasta onde procurar"},
    "memoria":           {"consulta": "Nome do projeto ou assunto"},
    "github_repos":      {},
    "github_ler":        {"repo": "usuario/repositorio", "caminho": "Caminho no repositorio"},
    "web_buscar":        {"consulta": "O que pesquisar"},
    "web_ler":           {"url": "Endereco da pagina"},
    "gerar_imagem":      {"descricao": "O que desenhar, em detalhe: assunto, luz, angulo, estilo, cores",
                          "formato": "quadrado, retrato, paisagem, story ou capa",
                          "nome": "Nome do arquivo (opcional)",
                          "modelo": "Nome do GGUF de difusao (opcional)",
                          "negativo": "O que evitar (opcional)",
                          "passos": "1 a 20; FLUX schnell usa 4",
                          "guidance": "Orientacao; normalmente 3.5",
                          "semente": "Numero para repetir o resultado (opcional)",
                          "pasta_saida": "Pasta do projeto liberada (opcional)"},
    "navegador_ver":     {},
    "navegador_ir":      {"url": "Endereco completo"},
    "navegador_clicar":  {"numero": "Numero do elemento na lista"},
    "navegador_escrever": {"numero": "Numero do campo", "texto": "Texto a digitar"},
    "navegador_teclar":  {"tecla": "Enter, Tab, Escape, ArrowDown"},
    "navegador_rolar":   {"direcao": "baixo, cima, topo ou fim"},
    "navegador_esperar": {"segundos": "Quantos segundos esperar"},
    "calcular":          {"expressao": "Expressão aritmética, ex: (1200 * 0.15) + 80"},
    "agora":             {},
    "clima":             {"cidade": "Nome da cidade, ex: Belo Horizonte"},
    "cep":               {"cep": "CEP com 8 digitos"},
    "cnpj":              {"cnpj": "CNPJ com 14 digitos"},
    "feriados":          {"ano": "Ano com 4 digitos. Vazio = ano atual"},
    "cotacao":           {"moedas": "Par de moedas, ex: USD-BRL"},
    "escrever_arquivo":  {"caminho": "Caminho completo do arquivo",
                          "conteudo": "Conteudo do arquivo"},
    "raio_x":            {"caminho": "Caminho da pasta do projeto"},
    "criar_pasta":       {"caminho": "Caminho da nova pasta",
                          "confirmado": "true so depois do Fred confirmar que e "
                                        "projeto novo mesmo, quando ja existe "
                                        "pasta de nome parecido"},
    "mover":             {"origem": "Caminho atual", "destino": "Novo caminho"},
    "apagar":            {"caminho": "Caminho do arquivo ou pasta"},
    "rodar_comando":     {"comando": "Comando a executar", "pasta": "Pasta de trabalho"},
    "github_criar_repo": {"nome": "Nome do repositorio", "privado": "true ou false",
                          "descricao": "Descricao curta"},
    "github_commit":     {"repo": "usuario/repositorio", "caminho": "Caminho no repositorio",
                          "conteudo": "Conteudo do arquivo", "mensagem": "Mensagem do commit"},
    "github_issue":      {"repo": "usuario/repositorio", "titulo": "Titulo",
                          "corpo": "Descricao"},
}

OBRIGATORIOS = {
    "usar_habilidade": ["nome"],
    "apresentar_plano": ["objetivo", "passos"],
    "criar_projeto": ["nome"],
    "buscar_no_chroma": ["consulta"],
    "listar_pasta": ["caminho"], "ler_arquivo": ["caminho"], "buscar": ["termo"],
    "raio_x": ["caminho"],
    "memoria": ["consulta"], "github_ler": ["repo"], "web_buscar": ["consulta"],
    "gerar_imagem": ["descricao"],
    "navegador_ir": ["url"], "navegador_clicar": ["numero"],
    "navegador_escrever": ["numero", "texto"], "navegador_teclar": ["tecla"],
    "web_ler": ["url"], "clima": ["cidade"], "cep": ["cep"], "cnpj": ["cnpj"],
    "cotacao": ["moedas"], "escrever_arquivo": ["caminho", "conteudo"],
    "criar_pasta": ["caminho"], "mover": ["origem", "destino"], "apagar": ["caminho"],
    "rodar_comando": ["comando"], "github_criar_repo": ["nome"],
    "github_commit": ["repo", "caminho", "conteudo"], "github_issue": ["repo", "titulo"],
}


GRUPOS = {
    "github":     ("github_repos", "github_ler", "github_criar_repo",
                   "github_commit", "github_issue"),
    "navegador":  ("navegador_ver", "navegador_ir", "navegador_clicar",
                   "navegador_escrever", "navegador_teclar", "navegador_rolar",
                   "navegador_esperar"),
    "utilidades": ("calcular", "agora", "cep", "cnpj", "feriados", "cotacao"),
    "web":        ("web_buscar", "web_ler"),
    "terminal":   ("rodar_comando",),
    "desenho":    ("gerar_imagem",),
}

GATILHOS_GRUPO = {
    "github":     ("github", "repositorio", "repositório", "repo", "commit",
                   "issue", "pull request", "versionar", "publicar o codigo",
                   "publicar o código"),
    # "tela" e "aba" entraram em 24/08: o Fred perguntou "o que tem na minha
    # tela" e o grupo do navegador ficou de fora do catalogo, porque nenhuma
    # dessas palavras estava aqui. Ele nao usa a palavra "navegador" quando
    # esta olhando para uma pagina -- usa "tela".
    "navegador":  ("navegador", "chrome", "site", "página", "pagina", "url",
                   "http", "clicar", "clique", "login", "logar", "formulario",
                   "formulário", "preencher", "acessar o", "entrar no",
                   "pythonanywhere", "comprar", "cadastrar no",
                   "tela", "aba", "guia aberta", "estou vendo", "esta aberto",
                   "está aberto", "enxergar"),
    "utilidades": ("calcule", "calcular", "cálculo", "calculo", "quanto dá", "quanto da", "hoje", "data", "hora", "dia", "prazo", "vencimento",
                   "feriado", "cep", "cnpj", "empresa", "cotacao", "cotação",
                   "dolar", "dólar", "euro", "clima", "tempo", "previsao",
                   "previsão", "temperatura"),
    "web":        ("pesquis", "busca na", "buscar na", "internet", "google",
                   "noticia", "notícia", "documentacao", "documentação",
                   "site oficial"),
    "terminal":   ("comando", "terminal", "instalar", "npm", "pip", "executar o",
                   "rodar o", "build", "teste"),
    # Palavras de quem PEDE arte, nao de quem fala sobre arte. "imagem"
    # sozinho nao entra: "me mostre a imagem do arquivo" nao e pedido de
    # desenho. Por isso os gatilhos vem colados no verbo.
    "desenho":    ("desenhe", "desenha", "desenhar", "gere uma imagem",
                   "gerar imagem", "gera uma imagem", "crie uma imagem",
                   "criar imagem", "cria uma imagem", "faca uma imagem",
                   "faça uma imagem", "ilustra", "ilustre", "ilustracao",
                   "ilustração", "criativo", "criativos", "arte para",
                   "banner", "thumbnail", "capa para", "poster", "pôster",
                   "anuncio", "anúncio", "logo para", "wallpaper",
                   "papel de parede", "foto de", "renderiza", "mockup"),
}


def para_pergunta(texto, garantir=()):
    """Devolve so as ferramentas que fazem sentido para o pedido.

    Mandar as 32 ferramentas em toda mensagem custa ~3.500 tokens, que o modelo
    reprocessa toda vez. Filtrando, o custo cai para menos da metade e a resposta
    comeca muito mais rapido.
    """
    catalogo = ativas()
    baixo = (texto or "").lower()

    grupos_fora = set()
    for grupo, gatilhos in GATILHOS_GRUPO.items():
        if not any(g in baixo for g in gatilhos):
            grupos_fora.add(grupo)

    # Grupos que o cerebro.py sabe que vao ser precisos, mesmo sem gatilho na
    # frase. Caso real: "na barra de busca escreva cannabis" -- o Bigode ja
    # tinha lido a pagina e sabia que era acao de navegador, mas a frase nao
    # tem nenhuma palavra da lista de gatilhos. Sem isto o catalogo chegaria
    # SEM navegador_escrever, e ele nao teria como executar o que acabou de
    # ser mandado fazer.
    grupos_fora -= set(garantir or ())

    descartar = set()
    for grupo in grupos_fora:
        descartar.update(GRUPOS.get(grupo, ()))

    filtrado = {n: d for n, d in catalogo.items() if n not in descartar}
    return filtrado or catalogo


def esquema_openai(catalogo=None):
    """Formato padrao de function calling: bem mais confiavel que protocolo em texto,
    principalmente em modelos menores."""
    catalogo = catalogo or ativas()
    saida = []
    for nome, dados in catalogo.items():
        campos = PARAMETROS.get(nome, {})
        saida.append({
            "type": "function",
            "function": {
                "name": nome,
                "description": dados["desc"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        chave: {"type": "string", "description": texto}
                        for chave, texto in campos.items()
                    },
                    "required": OBRIGATORIOS.get(nome, []),
                },
            },
        })
    return saida


def ativas():
    """Devolve o catalogo filtrado pelas conexoes ligadas."""
    conexoes = _conexoes()

    def ligada(chave, padrao=True):
        item = conexoes.get(chave)
        if isinstance(item, dict):
            return bool(item.get("ativa", padrao))
        return padrao

    # A busca semântica só entra se a pasta persistente já tiver dados.
    # Não importamos ChromaDB aqui: em máquinas portáteis essa importação
    # pode levar dezenas de segundos ou travar por incompatibilidade NumPy.
    chroma_tem_conteudo = False
    try:
        import json as _json
        cfg = _json.loads((Path(__file__).resolve().parent / "config.json").read_text(encoding="utf-8-sig"))
        bruto = Path(str(cfg.get("chroma_path", "./chroma_db")))
        pasta = bruto if bruto.is_absolute() else Path(__file__).resolve().parent / bruto
        chroma_tem_conteudo = pasta.exists() and any(
            p.is_file() and p.stat().st_size > 0 for p in pasta.rglob("*")
        )
    except Exception:
        chroma_tem_conteudo = False

    saida = {}
    for nome, dados in CATALOGO.items():
        if nome == "buscar_no_chroma" and not chroma_tem_conteudo:
            continue
        if nome.startswith("github") and not ligada("github"):
            continue
        if nome.startswith("web_") and not ligada("web"):
            continue
        if nome in ("agora", "clima", "cep", "cnpj", "feriados", "cotacao") \
                and not ligada("utilidades"):
            continue
        if nome.startswith("navegador_") and not ligada("navegador", False):
            continue
        if nome in ("listar_pasta", "ler_arquivo", "buscar", "raio_x",
                    "escrever_arquivo", "criar_pasta", "mover",
                    "apagar") and not ligada("arquivos"):
            continue
        if nome == "rodar_comando" and not ligada("terminal", False):
            continue
        # Desenho: so entra no catalogo se o ComfyUI estiver de pe.
        #
        # Mesma logica do `buscar_no_chroma` acima. Oferecer uma ferramenta
        # que so pode responder "o desenhista nao esta ligado" gasta tokens
        # do prompt e ensina o modelo a tentar o que nao existe. No pendrive,
        # onde nao ha ComfyUI, ela simplesmente nao aparece.
        if nome == "gerar_imagem":
            if not ligada("desenho", True):
                continue
            try:
                import imagens
                if not imagens.no_ar():
                    continue
            except Exception:
                continue
        saida[nome] = dados
    return saida


def descrever(catalogo=None):
    """Texto que entra no system prompt ensinando o modelo a usar as ferramentas."""
    catalogo = catalogo or ativas()
    linhas = []
    for nome, dados in catalogo.items():
        marca = "  [pede autorizacao]" if dados["escrita"] else ""
        linhas.append("- %s(%s) - %s%s" % (nome, dados["args"], dados["desc"], marca))
    return "\n".join(linhas)


def executar(nome, argumentos):
    catalogo = ativas()
    if nome not in catalogo:
        return "Ferramenta '%s' nao existe ou esta desligada nas Conexoes." % nome
    try:
        return catalogo[nome]["fn"](**(argumentos or {}))
    except TypeError as erro:
        return "Argumentos invalidos para %s: %s" % (nome, erro)
    except Exception as erro:
        return "Erro em %s: %s" % (nome, erro)


def exige_autorizacao(nome):
    dados = ativas().get(nome)
    return bool(dados and dados["escrita"])
