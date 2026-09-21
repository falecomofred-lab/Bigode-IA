# -*- coding: utf-8 -*-
"""Memória semântica local do Bigode IA usando ChromaDB persistente."""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Iterable


BASE = Path(__file__).resolve().parent
COLECOES_PADRAO = ("codigo", "seguros", "cannabis")


def carregar_config() -> dict:
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def caminho_chroma() -> Path:
    bruto = str(carregar_config().get("chroma_path", "./chroma_db"))
    caminho = Path(bruto)
    return caminho if caminho.is_absolute() else BASE / caminho


# ══════════════════════════════════════════════════════════════════════
# UM CLIENTE SO, VIVO, PARA O PROCESSO INTEIRO            (20/09/2026)
# ══════════════════════════════════════════════════════════════════════
#
#   Esta funcao criava um `PersistentClient` NOVO a cada chamada -- e toda
#   pergunta do Fred passa por aqui. Parecia inofensivo: o ChromaDB guarda
#   o "System" em cache pela configuracao, entao o segundo cliente
#   reaproveita o primeiro em vez de abrir outro banco.
#
#   O problema esta no que o proprio ChromaDB faz ao parar um System
#   (chromadb/api/rust.py, linha 131):
#
#       def stop(self) -> None:
#           del self.bindings
#
#   Ele APAGA o atributo. Depois disso, qualquer uso do mesmo objeto da:
#
#       AttributeError: 'RustBindingsAPI' object has no attribute 'bindings'
#       ValueError: Could not connect to tenant default_tenant
#
#   Que e exatamente o erro que apareceu no erros.log em 13/09, sumiu,
#   voltou ontem na indexacao, e me fez errar o diagnostico DUAS vezes no
#   mesmo dia: primeiro disse "instalacao quebrada" (nao estava -- o .pyd
#   nativo esta no lugar e o import funciona), depois disse "esta tudo bem"
#   (tambem nao -- so funcionava ate o primeiro stop).
#
#   Intermitencia e o que faz um defeito parecer coisa de outro mundo. A
#   causa aqui e banal: objeto usado depois de morto.
#
#   O conserto e guardar UM cliente e devolver sempre o mesmo. Se ele tiver
#   sido parado por qualquer motivo, o proprio `_vivo` percebe e constroi
#   outro -- em vez de estourar na cara de quem perguntou.
_CLIENTE = {"obj": None}
_TRAVA_CLIENTE = threading.Lock()


def _vivo(cliente):
    """O cliente ainda responde, ou foi parado por baixo?"""
    if cliente is None:
        return False
    try:
        cliente.heartbeat()
        return True
    except Exception:
        return False


def _cliente():
    try:
        import chromadb
    except ImportError as erro:
        raise RuntimeError(
            "ChromaDB não está instalado. Execute: pip install chromadb"
        ) from erro

    with _TRAVA_CLIENTE:
        if _vivo(_CLIENTE["obj"]):
            return _CLIENTE["obj"]
        caminho_chroma().mkdir(parents=True, exist_ok=True)
        # `reset` antes de recriar: sem isto o ChromaDB devolve o MESMO
        # System morto que acabamos de descartar, e o conserto nao
        # conserta nada.
        try:
            from chromadb.api.shared_system_client import SharedSystemClient
            SharedSystemClient.clear_system_cache()
        except Exception:
            pass
        _CLIENTE["obj"] = chromadb.PersistentClient(path=str(caminho_chroma()))
        return _CLIENTE["obj"]


# AVISAR UMA VEZ, NAO A CADA MENSAGEM                          (17/09)
#
#   O erro do ChromaDB e o MESMO em toda pergunta, e a pilha dele tem 40
#   linhas. Gravado a cada mensagem, ele enche o erros.log e esconde as
#   falhas de verdade -- que e o unico motivo de aquele arquivo existir.
#
#   Entao: a primeira vez vai inteira para o log, e a partir dai so conta.
_QUEBRADO = {"avisado": False, "vezes": 0, "motivo": ""}


def _avisar_quebrado(erro):
    _QUEBRADO["vezes"] += 1
    _QUEBRADO["motivo"] = str(erro)[:300]
    if _QUEBRADO["avisado"]:
        return
    _QUEBRADO["avisado"] = True
    texto = str(erro)
    dica = ""
    if "tenant" in texto or "bindings" in texto:
        # A causa conhecida: a camada Python do chromadb e as bindings em
        # Rust em versoes que nao combinam. Reinstalar as duas resolve.
        dica = ("  A instalacao do chromadb esta incompleta (a camada Python "
                "e as bindings em Rust nao combinam). No Python do Bigode: "
                "pip install --force-reinstall chromadb  --  ou desligue a "
                "memoria semantica com \"injetar_chroma\": false no "
                "config.json.")
    try:
        registro = BASE / "memoria" / "erros.log"
        registro.parent.mkdir(parents=True, exist_ok=True)
        import datetime
        with open(registro, "a", encoding="utf-8") as arq:
            arq.write("\n" + "=" * 70 + "\n")
            arq.write("%s  memoria semantica desligada nesta sessao\n"
                      % datetime.datetime.now().isoformat(timespec="seconds"))
            arq.write("  O Bigode segue respondendo SEM ela.\n")
            arq.write("  Motivo: %s\n" % texto[:500])
            if dica:
                arq.write(dica + "\n")
    except Exception:
        pass        # log nunca pode derrubar o atendimento


def situacao() -> dict:
    """Para a tela dizer que a memoria semantica caiu, em vez de ficar muda."""
    return {
        "quebrada": _QUEBRADO["avisado"],
        "vezes": _QUEBRADO["vezes"],
        "motivo": _QUEBRADO["motivo"],
    }


def dominios_configurados() -> dict[str, dict]:
    cfg = carregar_config()
    dominios = cfg.get("dominios") or {}
    if not isinstance(dominios, dict):
        dominios = {}
    if not dominios:
        dominios = {nome: {"nome": nome.title(), "pastas": [], "palavras": [], "ativo": True}
                    for nome in COLECOES_PADRAO}
    saida: dict[str, dict] = {}
    for nome, item in dominios.items():
        if not isinstance(item, dict):
            continue
        chave = _normalizar_nome(nome)
        if not chave:
            continue
        caminhos = item.get("pastas") or item.get("caminhos") or []
        if isinstance(caminhos, str):
            caminhos = [caminhos]
        saida[chave] = {
            "nome": str(item.get("nome") or nome).strip()[:80],
            "pastas": [str(p).strip() for p in caminhos if str(p).strip()],
            "palavras": [str(p).lower() for p in (item.get("palavras") or [])],
            "ativo": bool(item.get("ativo", True)),
        }
    return saida


def _normalizar_nome(nome: str) -> str:
    """"Código" vira "codigo", e não "c_digo".                  (20/09)

    A versao anterior trocava qualquer caractere fora de [a-z0-9_] por
    underline. Em portugues isso destroi a palavra: "Código" virava
    "c_digo", "Serviços" virava "servi_os".

    O estrago foi real. O Fred tinha um dominio "codigo" indexado; ao
    salvar de novo pela tela, o nome normalizado mudou para "c_digo" e o
    ChromaDB criou uma COLECAO NOVA. Ficaram as duas:

        codigo  ->     0 blocos   (a velha, orfa)
        c_digo  -> 1.164 blocos   (a nova)

    Duas colecoes para o mesmo assunto, e o roteador podendo cair na
    vazia. Acento nao pode mudar a identidade de nada.

    `unicodedata.normalize("NFD", ...)` separa a letra do acento; o filtro
    seguinte joga o acento fora e mantem a letra. Cedilha entra junto: "ç"
    vira "c".
    """
    import unicodedata
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", str(nome))
        if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9_]+", "_", sem_acento.lower()).strip("_")[:63]


def colecoes_ativas() -> list[str]:
    return [nome for nome, item in dominios_configurados().items() if item.get("ativo", True)]


def _arquivos_indexaveis(pastas: Iterable[str]):
    """Encontra documentos e código relevantes, excluindo credenciais."""
    ignorar = {".git", ".venv", "venv", "node_modules", "__pycache__", "chroma_db"}
    extensoes = {".md", ".txt", ".py", ".js", ".jsx", ".ts", ".tsx", ".html",
                 ".css", ".scss", ".json", ".yaml", ".yml", ".sql", ".toml"}
    nomes_protegidos = {"config.json", "conexoes.json", "usuarios.json"}
    vistos: set[str] = set()
    for bruto in pastas:
        raiz = Path(bruto).expanduser()
        if not raiz.exists() or not raiz.is_dir():
            continue
        for arquivo in raiz.rglob("*"):
            if (not arquivo.is_file() or arquivo.suffix.lower() not in extensoes
                    or arquivo.name.lower() in nomes_protegidos
                    or arquivo.name.lower().startswith(".env")):
                continue
            if any(parte in ignorar for parte in arquivo.parts):
                continue
            chave = str(arquivo.resolve())
            if chave in vistos or not arquivo.is_file():
                continue
            vistos.add(chave)
            yield arquivo


def _blocos(conteudo: str, tamanho: int = 1800, sobreposicao: int = 250):
    texto = conteudo.strip()
    if not texto:
        return
    inicio = 0
    while inicio < len(texto):
        fim = min(len(texto), inicio + tamanho)
        bloco = texto[inicio:fim].strip()
        if bloco:
            yield bloco
        if fim >= len(texto):
            break
        inicio = max(inicio + 1, fim - sobreposicao)


def _colecao(cliente, nome: str):
    return cliente.get_or_create_collection(
        name=_normalizar_nome(nome),
        metadata={"hnsw:space": "cosine"},
    )


def indexar_dominios() -> dict:
    # Sem o ChromaDB instalado isto lancava a excecao para cima, o servidor
    # devolvia erro 500 e a tela nao dizia nada -- o botao simplesmente nao
    # fazia nada. Devolver a explicacao e melhor que derrubar a chamada.
    try:
        cliente = _cliente()
    except RuntimeError as erro:
        return {"ok": False, "erro": str(erro), "colecoes": {}, "erros": [str(erro)]}
    dominios = dominios_configurados()
    resumo = {"colecoes": {}, "erros": []}
    for nome, item in dominios.items():
        if not item.get("ativo", True):
            continue
        colecao = _colecao(cliente, nome)
        arquivos = list(_arquivos_indexaveis(item.get("pastas", [])))
        ids: list[str] = []
        docs: list[str] = []
        metadados: list[dict] = []
        for arquivo in arquivos:
            try:
                conteudo = arquivo.read_text(encoding="utf-8", errors="ignore")
            except OSError as erro:
                resumo["erros"].append(f"{arquivo}: {erro}")
                continue
            try:
                colecao.delete(where={"caminho": str(arquivo.resolve())})
            except Exception:
                pass
            for numero, bloco in enumerate(_blocos(conteudo)):
                ids.append(_id_bloco(arquivo, numero))
                docs.append(bloco)
                metadados.append({
                    "caminho": str(arquivo.resolve()),
                    "titulo": arquivo.stem,
                    "dominio": nome,
                    "bloco": numero,
                })
        if ids:
            for inicio in range(0, len(ids), 64):
                colecao.add(
                    ids=ids[inicio:inicio + 64],
                    documents=docs[inicio:inicio + 64],
                    metadatas=metadados[inicio:inicio + 64],
                )
        resumo["colecoes"][nome] = {
            "pastas": item.get("pastas", []),
            "arquivos": len(arquivos),
            "blocos": len(ids),
            "total": colecao.count(),
        }
    return resumo


def _id_bloco(arquivo: Path, numero: int) -> str:
    import hashlib
    return hashlib.sha1(f"{arquivo.resolve()}::{numero}".encode("utf-8")).hexdigest()


def buscar_no_chroma(consulta: str, colecao: str = "", limite: int = 5) -> str:
    consulta = str(consulta or "").strip()
    if not consulta:
        return "Informe uma consulta para buscar no ChromaDB."
    try:
        cliente = _cliente()
    except RuntimeError as erro:
        return str(erro)
    nomes = [colecao] if colecao and colecao != "todas" else colecoes_ativas()
    resultados = []
    for nome in nomes:
        try:
            col = _colecao(cliente, nome)
            if col.count() == 0:
                continue
            dados = col.query(
                query_texts=[consulta],
                n_results=min(max(int(limite), 1), 10),
                include=["documents", "metadatas", "distances"],
            )
            docs = (dados.get("documents") or [[]])[0]
            metas = (dados.get("metadatas") or [[]])[0]
            distancias = (dados.get("distances") or [[]])[0]
            for doc, meta, distancia in zip(docs, metas, distancias):
                resultados.append((float(distancia or 0), nome, doc, meta or {}))
        except Exception as erro:
            return f"Falha ao consultar a coleção {nome}: {erro}"
    if not resultados:
        return "Nenhum trecho relevante encontrado no ChromaDB."
    resultados.sort(key=lambda item: item[0])
    saida = []
    for distancia, nome, doc, meta in resultados[:max(int(limite), 1)]:
        saida.append(
            f"--- [{nome}] {meta.get('titulo', 'sem título')} | distância {distancia:.4f} ---\n"
            f"{meta.get('caminho', '')}\n{doc}"
        )
    return "\n\n".join(saida)


def contexto_relevante(consulta: str, colecao: str = "", limite: int = 3):
    # MEMORIA SEMANTICA NAO PODE DERRUBAR A CONVERSA           (17/09)
    #
    #   Aqui so se pegava RuntimeError. Mas o chromadb quebrado levanta
    #   ValueError:
    #
    #       AttributeError: 'RustBindingsAPI' object has no attribute 'bindings'
    #       ValueError: Could not connect to tenant default_tenant.
    #
    #   Esse ValueError passava reto: subia por montar_system, _chat_interno
    #   e do_POST, e MATAVA o pedido. A conexao HTTP caia no meio, e a tela
    #   mostrava "O motor derrubou a conexao".
    #
    #   O motor estava intacto. O log do dia 13 registra isso tres vezes,
    #   inclusive um "falha atendendo ('127.0.0.1', 49526)" -- que e o
    #   servidor morrendo no meio da resposta, nao o motor.
    #
    #   Culpar a peca errada e o pior efeito de um erro mal capturado: o
    #   Fred passou a trocar de modelo e esperar carregamento por causa de
    #   uma biblioteca de busca instalada pela metade.
    #
    #   Esta memoria e um ACRESCIMO. Se ela falha, o Bigode responde sem
    #   ela -- que e exatamente o que ele fazia antes de ela existir.
    try:
        cliente = _cliente()
    except Exception as erro:
        _avisar_quebrado(erro)
        return "", []
    nomes = [colecao] if colecao and colecao != "todas" else colecoes_ativas()
    fontes = []
    blocos = []
    falhas = []
    for nome in nomes:
        try:
            col = _colecao(cliente, nome)
            if col.count() == 0:
                continue
            dados = col.query(
                query_texts=[consulta],
                n_results=min(max(int(limite), 1), 10),
                include=["documents", "metadatas", "distances"],
            )
            docs = (dados.get("documents") or [[]])[0]
            metas = (dados.get("metadatas") or [[]])[0]
            distancias = (dados.get("distances") or [[]])[0]
            for doc, meta, distancia in zip(docs, metas, distancias):
                if float(distancia or 1) > 0.65:
                    continue
                meta = meta or {}
                caminho = str(meta.get("caminho", ""))
                fontes.append(caminho or f"{nome}:{meta.get('titulo', '')}")
                blocos.append(
                    f"[{nome} | {meta.get('titulo', '')} | distância {float(distancia or 0):.4f}]\n{doc}"
                )
        except Exception as erro:
            falhas.append(f"{nome}: {erro}")
    if not blocos and falhas:
        # ISTO IA PARA DENTRO DO PROMPT DO MODELO               (17/09)
        #
        #   O texto abaixo era devolvido como CONTEXTO -- ou seja, o erro da
        #   biblioteca de busca virava parte das instrucoes do sistema, e o
        #   modelo gastava janela lendo "Could not connect to tenant
        #   default_tenant" antes de ler a pergunta do Fred.
        #
        #   Falha de infraestrutura pertence ao log, nao ao prompt. O
        #   modelo nao tem o que fazer com ela.
        _avisar_quebrado(RuntimeError("; ".join(falhas[:2])))
        return "", []
    return "\n\n---\n\n".join(blocos[:limite]), fontes[:limite]


def salvar_dominios(dominios: dict) -> dict:
    cfg = carregar_config()
    atuais = dominios_configurados()
    novos = {}
    for nome, item in (dominios or {}).items():
        chave = _normalizar_nome(nome)
        if not chave or not isinstance(item, dict):
            continue
        caminhos = item.get("pastas") or []
        if isinstance(caminhos, str):
            caminhos = [caminhos]
        novos[chave] = {
            "nome": str(item.get("nome") or nome).strip()[:80],
            "pastas": [str(p).strip() for p in caminhos if str(p).strip()],
            "palavras": [str(p).strip().lower() for p in item.get("palavras", []) if str(p).strip()],
            "ativo": bool(item.get("ativo", True)),
        }
    if not novos:
        novos = atuais
    cfg["dominios"] = novos
    (BASE / "config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return novos


def status() -> dict:
    """Retorna estado resumido sem falhar quando o ChromaDB ainda não existe."""
    resultado = {
        "ativo": False,
        "caminho": str(caminho_chroma()),
        "colecoes": {},
        "erro": "",
    }
    try:
        cliente = _cliente()
        for nome in colecoes_ativas():
            resultado["colecoes"][nome] = _colecao(cliente, nome).count()
        resultado["ativo"] = True
    except Exception as erro:
        resultado["erro"] = str(erro)
    return resultado
