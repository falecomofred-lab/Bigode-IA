#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BIGODE IA - plataforma de IA da Venure (venure.com.br)

Interface + identidade + memoria semantica + ferramentas sobre um modelo local (llamafile).
Usa a biblioteca padrao do Python e o ChromaDB para memoria vetorial local.

Uso:  python cerebro.py
"""

import datetime
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# garante que o Python portatil enxergue os modulos ao lado deste arquivo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Integrações opcionais: o Bigode local continua funcionando com Llama mesmo
# quando os módulos remotos ainda não foram sincronizados para a pasta Drive.
try:
    import modal_cliente
except ImportError:
    class _ModalAusente:
        @staticmethod
        def configurado(cfg): return False
    modal_cliente = _ModalAusente()
try:
    import huggingface_cliente
except ImportError:
    class _HuggingFaceAusente:
        @staticmethod
        def configurado(): return False
    huggingface_cliente = _HuggingFaceAusente()
try:
    import pesquisa_profunda
except ImportError:
    class _PesquisaAusente:
        @staticmethod
        def iniciar(*args, **kwargs):
            raise RuntimeError('Pesquisa Profunda indisponível: sincronize pesquisa_profunda.py.')
        @staticmethod
        def obter(*args, **kwargs): return None
    pesquisa_profunda = _PesquisaAusente()

import agenda
import armazenamento
import diario
import especialistas
import autenticacao
import chroma_memoria
import ferramentas
import habilidades
import roteador_semantico
import modelos
import voz
import runtime

BASE = Path(__file__).resolve().parent
MEMORIA = BASE / "memoria"
PROJETOS = MEMORIA / "projetos"

PENDENTES = {}
NAVEGADOR = {}          # acoes esperando a extensao do Chrome executar
EXTENSAO = {"vista": 0}  # ultima vez que a extensao deu sinal de vida
TRAVA = threading.Lock()

# Avisa a extensao, na hora, que chegou trabalho para ela.
#
# Sem isto a extensao so descobre no proximo fetch, e entre um fetch e outro
# o Chrome pode ter posto o service worker para dormir. Com isto, a chamada
# dela fica ABERTA esperando -- e um fetch aberto mantem o worker acordado.
# Dois problemas resolvidos pela mesma linha: a acao chega instantanea, e a
# extensao para de morrer de tedio.
CHEGOU = threading.Event()

# So um aquecimento por vez (ver aquecer()).
TRAVA_AQUECER = threading.Lock()


# ==========================================================================
# Configuracao
# ==========================================================================

def ler(caminho, padrao=""):
    try:
        return Path(caminho).read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return padrao


def config():
    dados = json.loads(ler(BASE / "config.json", "{}") or "{}")
    dados.setdefault("llm_url", "http://localhost:8082/v1/chat/completions")
    # Chave do motor. Vazia quando ele mora na mesma maquina -- ninguem de
    # fora alcanca 127.0.0.1. Preenchida no modo hibrido, em que o motor
    # fica no Colab atras de um endereco publico: la, sem chave, qualquer um
    # que descobrisse o link gastaria a placa e a cota do Fred.
    dados.setdefault("llm_chave", "")
    dados.setdefault("modelo_provedor", "local")
    # ENDERECO NAO E SEGREDO, MAS TAMBEM NAO E CODIGO      (14/09)
    #
    #     Aqui estava escrito o endereco real do endpoint da Modal, com o
    #     nome da workspace dentro. Nao e um token -- sozinho ele nao da
    #     acesso a nada. Mas num repositorio PUBLICO e um convite: um
    #     endereco ao vivo, identificado, que qualquer um pode martelar.
    #
    #     Endereco de instalacao pertence ao config.json, que o
    #     .gitignore barra. O codigo fica vazio e cada maquina preenche o
    #     seu -- que e como ja funciona o llm_url logo acima.
    dados.setdefault("modal", {
        "ativo": False,
        "url": "",
        "health_url": "",
        "token": "",
    })
    dados.setdefault("porta", 7000)
    # 0.3 deixa o texto travado e repetitivo em modelos pequenos.
    # 0.45 com penalidade de repeticao soa natural sem virar invencionice.
    dados.setdefault("temperatura", 0.45)
    dados.setdefault("max_tokens", 1000)
    dados.setdefault("max_passos", 8)
    dados.setdefault("memorias_por_pergunta", 3)
    dados.setdefault("nivel_autorizacao", "sempre")
    dados.setdefault("contexto", 8192)
    dados.setdefault("threads", 8)
    dados.setdefault("threads_leitura", None)   # None = todos os nucleos logicos
    dados.setdefault("usar_mmap", None)      # None = decide pelo tipo de disco
    dados.setdefault("injetar_memoria", False)
    dados.setdefault("injetar_chroma", True)
    dados.setdefault("chroma_path", "./chroma_db")
    dados.setdefault("dominios", {
        "codigo": {"nome": "Código", "pastas": ["G:\\Meu Drive\\projetos\\codigo"],
                   "palavras": ["python", "código", "api", "programação"], "ativo": True},
        "seguros": {"nome": "Seguros", "pastas": ["G:\\Meu Drive\\projetos\\seclar"],
                    "palavras": ["seguro", "susep", "apólice", "sinistro"], "ativo": True},
        "cannabis": {"nome": "Cannabis", "pastas": ["G:\\Meu Drive\\projetos\\soul"],
                     "palavras": ["cannabis", "anvisa", "plantio", "medicinal"], "ativo": True},
    })
    dados.setdefault("acesso_rede", True)      # permite abrir pelo celular na mesma wi-fi
    dados.setdefault("codigo_acesso", "")      # legado: substituido pelo login
    dados.setdefault("exigir_login", True)     # pede e-mail e senha para entrar
    dados.setdefault("login_social", {         # opcional: ver LEIAME para configurar
        "google": {"client_id": "", "client_secret": ""},
        "github": {"client_id": "", "client_secret": ""},
    })
    dados.setdefault("pastas_liberadas", ["G:\\Meu Drive\\projetos"])
    dados.setdefault("aguardar_modelo_seg", 900)

    # Chave de pareamento da extensao do Chrome.
    #
    # Por que nao usar o cookie de sessao: uma chamada da extensao
    # (chrome-extension://...) para localhost:7000 e cross-site, e o cookie
    # tem SameSite=Lax -- o Chrome simplesmente nao envia. Nao adianta fazer
    # login: o cookie nunca chega. Cabecalho nao obedece a SameSite, entao a
    # extensao se identifica por chave, como fazem o Claude e o Manus.
    if not dados.get("chave_extensao"):
        dados["chave_extensao"] = uuid.uuid4().hex
        try:
            (BASE / "config.json").write_text(
                json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    
    # o prompt do sistema + o esquema das ferramentas ja ocupam ~3800 tokens:
    # abaixo de 8192 nada cabe e o motor responde "exceeds context size"
    if int(dados.get("contexto", 0)) < 8192:
        dados["contexto"] = 8192

    # temperatura muito baixa e a causa mais comum de resposta repetitiva
    if float(dados.get("temperatura", 0)) < 0.35:
        dados["temperatura"] = 0.45

    # resposta gigante em CPU lenta vira espera de meia hora: limita
    teto = max(400, min(1200, int(dados["contexto"]) // 5))
    if int(dados.get("max_tokens", 0)) > teto:
        dados["max_tokens"] = teto
    return dados


def cabecalhos_llm(cfg=None):
    """Os cabecalhos de toda chamada ao motor.

    POR QUE ISSO EXISTE
        Ate agora o motor sempre morou em 127.0.0.1, onde ninguem de fora
        chega -- e por isso a chamada ia sem nenhuma identificacao.

        No modo hibrido isso deixa de valer. O cerebro roda no Windows do
        Fred, para alcancar os arquivos dele de verdade, e o motor fica no
        Colab, pela placa. Entre os dois ha um tunel com endereco PUBLICO.
        Sem chave, quem descobrisse o endereco usaria a placa e a cota do
        Fred a vontade.

        `llama_cpp.server --api_key X` responde 401 sem o Bearer certo. A
        chave e gerada por sessao no ligar_motor.py e viaja para ca dentro
        do config.json, escrita pelo usar_motor_do_colab.py.

        Quando `llm_chave` esta vazia -- o caso de quem roda tudo local --
        nada muda: o cabecalho sai igual ao de antes.
    """
    cfg = cfg if cfg is not None else config()
    cabecalhos = {"Content-Type": "application/json"}
    chave = (cfg.get("llm_chave") or "").strip()
    if chave:
        cabecalhos["Authorization"] = "Bearer " + chave
    return cabecalhos


def salvar_config(novo):
    """Grava, e se a janela mudou, RECARREGA O MOTOR sozinho.

    Este era o laco que mais custou tempo ao Fred: o arquivo dizia 12.288, o
    motor continuava com 8.192, e a tela respondia "o motor derrubou a
    conexao". Ele fechava, abria, fechava de novo -- e o desencontro voltava.
    A ferramenta pedia uma danca manual que ele nao tinha como adivinhar.

    A janela e lida UMA vez, quando o motor sobe. Mudar o numero no arquivo
    nao alcanca um motor que ja esta rodando. Entao quem muda o numero passa
    a ser responsavel por reiniciar quem depende dele.
    """
    atual = config()
    antes = int(atual.get("contexto", 0))
    atual.update(novo)
    (BASE / "config.json").write_text(
        json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")

    depois = int(atual.get("contexto", 0))
    if depois != antes and PROVEDOR.online():
        modelo = (PROVEDOR.atual() or {}).get("id", "")
        if modelo:
            print("   Janela mudou de %d para %d. Recarregando o motor..."
                  % (antes, depois))
            anotar_erro("janela %d -> %d: recarregando o motor sozinho"
                        % (antes, depois))
            threading.Thread(
                target=lambda: PROVEDOR.carregar(modelo), daemon=True).start()
    return atual


def config_publica():
    """Configuração necessária para a interface, sem segredos."""
    dados = dict(config())
    for chave in ("github_token", "codigo_acesso", "chave_extensao"):
        dados.pop(chave, None)
    if isinstance(dados.get("modal"), dict):
        dados["modal"] = {k: v for k, v in dados["modal"].items() if k != "token"}
    sociais = dados.get("login_social")
    if isinstance(sociais, dict):
        dados["login_social"] = {
            provedor: {"configurado": bool(item.get("client_id") and item.get("client_secret"))}
            for provedor, item in sociais.items() if isinstance(item, dict)
        }
    return dados


def conexoes():
    return json.loads(ler(BASE / "conexoes.json", "{}") or "{}")


def custo_conexoes():
    """Quantos tokens cada conexao acrescenta em TODA mensagem enviada."""
    try:
        catalogo = ferramentas.ativas()
        saida = {}
        for chave, nomes in ferramentas.GRUPOS.items():
            lista = [d for n, d in catalogo.items() if n in nomes]
            if lista:
                esquema = ferramentas.esquema_openai(
                    {n: d for n, d in catalogo.items() if n in nomes})
                saida[chave] = _tokens(json.dumps(esquema, ensure_ascii=False))
        # arquivos = tudo que sobra fora dos grupos nomeados
        agrupadas = {n for g in ferramentas.GRUPOS.values() for n in g}
        resto = {n: d for n, d in catalogo.items() if n not in agrupadas}
        if resto:
            saida["arquivos"] = _tokens(
                json.dumps(ferramentas.esquema_openai(resto), ensure_ascii=False))
        return saida
    except Exception:
        return {}


def conexoes_publicas():
    """Versao para o frontend: token nunca sai em texto puro."""
    custos = custo_conexoes()
    saida = {}
    for chave, item in conexoes().items():
        if not isinstance(item, dict):
            continue
        copia = {k: v for k, v in item.items() if k != "token"}
        copia["tem_token"] = bool((item.get("token") or "").strip())
        copia["custo"] = custos.get(chave, 0)
        saida[chave] = copia
    return saida


def salvar_conexoes(recebido):
    """Preserva tokens existentes quando o frontend manda campo vazio."""
    atual = conexoes()
    for chave, item in (recebido or {}).items():
        if not isinstance(item, dict):
            continue
        item.pop("tem_token", None)
        antigo = atual.get(chave, {})
        if not (item.get("token") or "").strip() and antigo.get("token"):
            item["token"] = antigo["token"]
        atual[chave] = item
    for chave in list(atual):
        if chave not in (recebido or {}):
            del atual[chave]
    (BASE / "conexoes.json").write_text(
        json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")


# ==========================================================================
# Prompt
# ==========================================================================

IGNORADAS = set("""
de da do das dos a o as os e ou que para por com sem no na nos nas um uma em
ao aos eu voce meu minha seu sua como qual quais quando onde porque isso isto
esse essa este esta ser estar tem ter faz fazer preciso quero pode posso mais
menos muito todo toda todos todas nao sim entao aqui sobre ate tambem ja bem
mesmo cada outro nosso the and for you with this that
""".split())


def chaves(texto):
    achadas = re.findall(r"[a-zA-Z0-9À-ÿ_\-]{3,}", (texto or "").lower())
    return {p for p in achadas if p not in IGNORADAS}


# Faixas Unicode de emoji e simbolos decorativos. Nao pega acento, cedilha
# nem simbolo tecnico (=, %, ->), so pictograma.
_SEM_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F000-\U0001F0FF"
    "\U00002600-\U000026FF\U0001F900-\U0001F9FF\U0000FE0F\U0000200D]+")


def limpar_resposta(texto):
    """Remove ruído conversacional sem alterar o conteúdo técnico.

    Modelos locais às vezes repetem despedidas, P.S. e convites genéricos.
    Esses trechos não ajudam o Frederico e podem crescer até ocupar a resposta.
    A limpeza é conservadora: só remove blocos conhecidos e linhas duplicadas.
    """
    if not texto:
        return ""
    linhas = str(texto).replace("\r\n", "\n").split("\n")
    saida, vistos = [], set()
    # Linhas de encerramento em serie. Medido em 26/08: numa unica resposta o
    # modelo escreveu "Resposta final", "Resposta final (simplificada)",
    # "Resposta final (conclusao)", "Nota de encerramento", "Fim da resposta",
    # "Atencao ao usuario" e "Dica rapida" -- cada uma repetindo a anterior.
    # Sao cabecalhos de ciclo: onde eles aparecem, a resposta ja acabou.
    ruido = (
        "estou pronto para ajudar", "sinta-se à vontade para dizer",
        "se precisar de mais ajuda", "se você tiver alguma outra pergunta",
        "se voce tiver alguma outra pergunta", "por favor forneça as palavras-chave",
        "por favor forneca as palavras-chave",
        "resposta final", "nota de encerramento", "fim da resposta",
        "finalização:", "finalizacao:", "atenção ao usuário", "atencao ao usuario",
        "espero que isso ajude", "estou à disposição", "estou a disposicao",
        "estou aqui para ajudar", "é só me chamar", "e so me chamar",
        "basta me dizer o que você precisa", "qualquer outro detalhe",
    )
    for linha in linhas:
        limpa = linha.strip()
        normalizada = re.sub(r"\s+", " ", limpa).lower()
        if not limpa:
            if saida and saida[-1] != "":
                saida.append("")
            continue
        if re.match(r"^p\.?s\.?\d*\b", normalizada) or re.match(r"^(nota|atenção|atencao)(?:\s+\d+)?\s*:", normalizada):
            continue
        if any(trecho in normalizada for trecho in ruido):
            continue

        # Emojis fora.
        #
        # O temperamento.md diz "sem emojis" desde sempre. Em 26/08 ele
        # respondeu com trinta e poucos: foguete, lupa, casinha, maleta,
        # carinha sorrindo. Instrucao nao segurou -- e a terceira vez nesta
        # base em que instrucao perde para habito treinado do modelo.
        #
        # Tirar no caminho de saida e definitivo e nao custa nada. O texto
        # continua igual; so os simbolos somem.
        limpa = _SEM_EMOJI.sub("", limpa).strip()
        if not limpa:
            continue
        linha = _SEM_EMOJI.sub("", linha)
        normalizada = re.sub(r"\s+", " ", limpa).lower()

        chave = normalizada
        if len(chave) > 30 and chave in vistos:
            continue
        if len(chave) > 30:
            vistos.add(chave)
        saida.append(linha.rstrip())
    while saida and not saida[-1].strip():
        saida.pop()
    return "\n".join(saida).strip()


def memoria_relevante(pergunta, limite=3):
    if not PROJETOS.exists():
        return "", []
    termos = chaves(pergunta)
    if not termos:
        return "", []
    pontuados = []
    for arquivo in PROJETOS.glob("*.md"):
        texto = ler(arquivo)
        if not texto:
            continue
        pontos = len(termos & chaves(texto[:6000]))
        for termo in termos:
            if termo in arquivo.stem.lower():
                pontos += 12
        if pontos:
            pontuados.append((pontos, arquivo, texto))
    pontuados.sort(key=lambda x: x[0], reverse=True)
    blocos = [t[:3000] for _p, _a, t in pontuados[:limite]]
    fontes = [a.stem for _p, a, _t in pontuados[:limite]]
    return "\n\n---\n\n".join(blocos), fontes


PROTOCOLO_TEXTO = """
# FERRAMENTAS

Voce pode agir no computador do Fred usando as ferramentas abaixo.

{lista}

## Como chamar

Quando precisar usar uma ferramenta, escreva uma frase curta dizendo o que vai
fazer e termine a mensagem EXATAMENTE com este bloco:

<ferramenta>
{{"nome": "listar_pasta", "args": {{"caminho": "G:\\\\Meu Drive\\\\projetos"}}}}
</ferramenta>

Regras:
- Uma ferramenta por vez. Pare de escrever depois do bloco.
- O resultado volta para voce na proxima mensagem. Ai continue o raciocinio.
- Caminhos do Windows usam barra dupla no JSON: "G:\\\\Meu Drive\\\\projetos".
- Nao invente resultado de ferramenta. Se precisa saber, chame a ferramenta.
"""

PROTOCOLO = """
# COMO VOCE TRABALHA

Voce EXECUTA, nao descreve. Use ferramentas quando elas forem necessárias para cumprir o pedido.

Conversa simples, saudação, explicação geral, brainstorming ou pedido de redação não exigem ferramenta por si só. Para fatos atuais, números, leis, arquivos, código, projetos, internet ou dados do computador, busque evidência antes de afirmar.

Citou pasta, projeto, arquivo, repositorio, auditoria, analise ou correcao?
Primeira acao = chamar ferramenta e ver o dado real. Sem excecao.
Nao sabe o caminho? Comece em listar_pasta("G:\\\\Meu Drive\\\\projetos") e desca.
Nunca descreva um arquivo sem ter lido.

Precisa saber a data, prazo ou vencimento? Chame agora() primeiro.

# ANTES DE ALTERAR

Ler: livre. Alterar (escrever, criar, mover, apagar, commitar, rodar comando):

1. Investigue: liste a pasta e leia os arquivos envolvidos.
2. Chame apresentar_plano com passos concretos, citando arquivos reais que leu.
   Ruim: "revisar o codigo". Bom: "corrigir a validacao em src/auth/login.js".
3. Pare e espere. Aprovado, execute tudo sem pedir de novo. Recusado, pergunte.

# NAVEGADOR

Com as ferramentas navegador_* voce controla o Chrome do Fred de verdade.
Regra unica e obrigatoria: chame navegador_ver ANTES de clicar ou escrever.
Ela devolve os elementos numerados; use esses numeros. Nunca chute numero.

Depois de clicar, apertar Enter ou navegar, a pagina muda: chame navegador_ver
outra vez antes da proxima acao.

Fluxo tipico:
navegador_ir(url) -> navegador_ver() -> navegador_escrever(3, "texto")
-> navegador_teclar("Enter") -> navegador_esperar(2) -> navegador_ver()

Nunca preencha dados de cartao, senha ou pagamento sem o Fred mandar
explicitamente naquela mensagem.

# CONSTRUIR PROJETO

Plano listando os arquivos -> criar_projeto(nome) -> escrever_arquivo um por um,
no caminho que criar_projeto devolveu. Falta so o nome? Sugira e siga.

Voce e desenvolvedor senior: codigo completo (nunca "// implementar aqui"),
src/ com rotas e config separadas, package.json ou requirements.txt,
.gitignore, .env.example, README. Chave sempre em variavel de ambiente.
Valide entrada e trate erro.
"""


TRACOS = {
    "objetivo": "Va direto ao ponto. Responda exatamente ao que foi perguntado.",
    "conciso": "Seja claro e proporcional: respostas simples podem ser curtas; tarefas complexas precisam de detalhes suficientes.",
    "sem_bajulacao": "Nunca elogie a pergunta nem o usuario. Nada de 'otima pergunta' "
                     "ou 'excelente ideia'. Comece pela resposta.",
    "sem_devaneio": "Nao especule nem encha linguica. Se nao souber, diga que nao sabe. "
                    "Nunca invente arquivo, funcao, numero, nome ou fato.",
    "cetico": "Questione premissas erradas e discorde quando for o caso. "
              "Concordar com tudo nao ajuda.",
    "tecnico": "Use termos tecnicos precisos. Nao simplifique demais.",
    "pratico": "Prefira exemplo concreto e codigo pronto a explicacao teorica.",
    "formal": "Tom profissional e sobrio, sem girias e sem emojis.",
}


def personalidade():
    dados = json.loads(ler(MEMORIA / "personalidade.json", "{}") or "{}")
    dados.setdefault("tracos", ["objetivo", "sem_bajulacao", "sem_devaneio"])
    dados.setdefault("instrucoes", "")
    return dados


def salvar_personalidade(dados):
    limpo = {
        "tracos": [t for t in (dados.get("tracos") or []) if t in TRACOS],
        "instrucoes": (dados.get("instrucoes") or "").strip(),
    }
    (MEMORIA / "personalidade.json").write_text(
        json.dumps(limpo, ensure_ascii=False, indent=2), encoding="utf-8")
    return limpo


def bloco_personalidade():
    dados = personalidade()
    linhas = []
    if dados["tracos"]:
        linhas.append("# COMO RESPONDER\n")
        linhas += ["- " + TRACOS[t] for t in dados["tracos"] if t in TRACOS]
    if dados["instrucoes"]:
        linhas.append("\n# INSTRUCOES DO FRED\n")
        linhas.append(dados["instrucoes"])
    return "\n".join(linhas)


PROTOCOLO_CURTO = """
# COMO VOCE TRABALHA

Voce EXECUTA, nao descreve. Ja tem acesso a tudo: nunca peca permissao nem
pergunte um caminho que voce mesmo pode descobrir com listar_pasta.

Falou de pasta, projeto, arquivo ou auditoria? Chame a ferramenta ANTES de
responder. Nunca fale de um arquivo sem ter lido.
Precisa de data ou prazo? Chame agora().

Antes de escrever, mover ou apagar qualquer coisa: chame apresentar_plano,
com os arquivos reais que voce leu, e espere o Fred aprovar.

# COMO VOCE FALA

Converse como uma pessoa, nao como manual. Seja breve quando o pedido for simples e desenvolva a resposta quando o pedido exigir explicacao, plano, código ou comparação. Não corte informações importantes apenas para ser curto. Sem repetir, sem reformular a mesma ideia, sem "como mencionei anteriormente".

Nao recite as regras acima nem descreva seu proprio funcionamento.
Terminou de responder? Pare. Nao ofereca resumo do que acabou de dizer.
"""


def prompt_pequeno():
    """Modelo pequeno se perde com muita instrucao: entrega melhor com pouco."""
    modelo = PROVEDOR.atual() or {}
    return float(modelo.get("gb", 99)) < 12


_MAPA = {"quando": 0, "texto": ""}


def mapa_dos_projetos():
    """A LISTA DOS SEUS PROJETOS, direto no prompt.

    Por que existe -- 23/08, conversa real:

        Voce: "no meu drive, pasta projetos, tem um projeto chamado
               Lucas Garage. Do que se trata?"
        Ele:  "a habilidade lucas_garage nao esta disponivel"

    Ele tratou o nome de uma PASTA como se fosse uma habilidade. Nao foi
    burrice: ele nao tinha como saber que "Lucas Garage" e um projeto. Nada
    no prompt dizia quais projetos existem, entao ele chutou entre as
    ferramentas que conhecia -- e chutou errado. Duzentos e trinta segundos
    para chegar em "nao encontrei".

    Com a lista na mao ele nao precisa adivinhar: le o nome, ve o caminho,
    e chama `listar_pasta` no lugar certo de primeira.

    Custa uns 40 tokens por projeto. E caro, e vale: e a diferenca entre
    achar de primeira e gastar quatro minutos procurando.

    Fica em cache por 5 minutos -- indexar leva tempo e a lista quase nunca
    muda no meio de uma conversa.
    """
    if time.time() - _MAPA["quando"] < 300:
        return _MAPA["texto"]

    linhas = []
    if PROJETOS.exists():
        for arq in sorted(PROJETOS.glob("*.md")):
            nome = caminho = ""
            try:
                for linha in arq.read_text(encoding="utf-8",
                                           errors="ignore").splitlines()[:6]:
                    if linha.startswith("# PROJETO: "):
                        nome = linha[11:].strip()
                    elif linha.startswith("- Caminho: "):
                        caminho = linha[11:].strip().strip("`")
                    if nome and caminho:
                        break
            except Exception:
                continue
            if nome and caminho:
                linhas.append("- **%s** -> `%s`" % (nome, caminho))

    # Teto: 30 projetos. Com 43 o texto passava de 1.700 tokens e, somado
    # ao resto, estourava a janela do modelo -- o motor derrubava a conexao.
    if len(linhas) > 30:
        sobrando = len(linhas) - 30
        linhas = linhas[:30]
        linhas.append("- (e mais %d; use `listar_pasta` na pasta de projetos)"
                      % sobrando)

    if linhas:
        _MAPA["texto"] = (
            "# OS PROJETOS DO FRED\n\n"
            "Estes existem de verdade, com o caminho exato. Pediram um pelo "
            "nome? Chame `listar_pasta` no caminho da lista. NUNCA trate nome "
            "de projeto como habilidade, e nunca diga que nao encontrou sem "
            "ter chamado `listar_pasta` no caminho certo.\n\n"
            + "\n".join(linhas))
    else:
        _MAPA["texto"] = ""
    _MAPA["quando"] = time.time()
    return _MAPA["texto"]


def montar_system(pergunta, colecao=""):
    cfg = config()
    roteamento = roteador_semantico.classificar_consulta(pergunta)
    colecao_alvo = colecao or roteamento.get("colecao", "todas")
    # temperamento.md vem logo depois da identidade: e a disciplina que vale
    # para qualquer modelo. Fica no comeco do prompt (parte estavel), entao o
    # cache do motor nao e invalidado por causa dele.
    partes = ["Responda SEMPRE em portugues do Brasil.",
              ler(MEMORIA / "identidade.md"),
              ler(MEMORIA / "temperamento.md"), bloco_personalidade(),
              ler(MEMORIA / "jeito_de_trabalhar.md")]

    catalogo = ferramentas.ativas()
    if catalogo:
        # Com function calling nativo o modelo ja recebe o catalogo pelo template;
        # repetir em texto so gastaria contexto.
        if not usar_nativas(cfg):
            partes.append(
                PROTOCOLO_TEXTO.format(lista=ferramentas.descrever(catalogo)).strip())
        partes.append((PROTOCOLO_CURTO if prompt_pequeno() else PROTOCOLO).strip())
        partes.append("# PASTAS LIBERADAS\n\n" + "\n".join(
            "- " + p for p in cfg.get("pastas_liberadas", [])))
        partes.append(habilidades.resumo_para_prompt(pergunta))
        # A lista de projetos entra junto com o resto do que e FIXO, para o
        # motor guardar tudo de uma vez e nao reler a cada conversa.
        partes.append(mapa_dos_projetos())

    # A memoria so entra no prompt se voce pedir. Mantendo o prompt do sistema
    # identico entre as mensagens, o cache do motor e reaproveitado e a resposta
    # comeca muito mais rapido. Sem isso, o Bigode busca pela ferramenta memoria().
    fontes = []
    if cfg.get("injetar_memoria"):
        contexto, fontes = memoria_relevante(
            pergunta, int(cfg.get("memorias_por_pergunta", 3)))
        if contexto:
            partes.append("# MEMORIA DOS PROJETOS\n\nUse como fato apenas o que "
                          "estiver abaixo.\n\n" + contexto)

    fontes_chroma = []
    if cfg.get("injetar_chroma", True):
        contexto_chroma, fontes_chroma = chroma_memoria.contexto_relevante(
            pergunta, colecao_alvo, int(cfg.get("memorias_por_pergunta", 3)))
        if contexto_chroma:
            partes.append(
                "# MEMORIA SEMANTICA DO CHROMADB\n\n"
                "Roteamento: coleção %s. Use como fato apenas os trechos abaixo; "
                "se não houver evidência suficiente, diga que não sabe.\n\n%s"
                % (colecao_alvo, contexto_chroma)
            )
            fontes.extend(fontes_chroma)

    # ═══ ONDE VOCES PARARAM ═══════════════════════════════════════════
    #
    # O que o Fred pediu em 09/09: "quero manter o Bigode como um consultor".
    # Consultor que esquece tudo entre uma reuniao e outra nao e consultor.
    #
    # Isto vem do diario em Markdown no Drive -- que sobrevive ao pendrive,
    # ao Colab e a troca de maquina. Custa uns 300 tokens e some primeiro se
    # a janela apertar.
    if cfg.get("lembrar_do_passado", True):
        try:
            retomada = diario.retomar(cfg)
            if retomada:
                partes.append(retomada)
        except Exception:
            pass          # memoria e conforto; nunca derruba a conversa

    # ═══ O SYSTEM TEM DE CABER ═══════════════════════════════════════
    #
    # Em 23/08 o motor comecou a derrubar a conexao em toda pergunta. A
    # causa: eu acrescentei a lista dos 43 projetos ao prompt e ninguem
    # conferia o tamanho. A conta da janela:
    #
    #   contexto ................... 8.192
    #   - reserva para a resposta ... 2.730
    #   - catalogo de ferramentas ... ~2.700  (34 ferramentas)
    #   - margem ...................... 250
    #   = sobra para o texto fixo ... ~2.500
    #
    # E o texto fixo tinha passado de 4.500. Nao havia como caber, e o
    # motor simplesmente cortava.
    #
    # Agora, se nao couber, os blocos OPCIONAIS saem, do menos essencial
    # para o mais: primeiro o mapa de projetos, depois os manuais, depois
    # a memoria semantica. Identidade e temperamento nunca saem -- sao o
    # que segura a invencao.
    # O teto real, nao um palpite em porcentagem: o que sobra da janela
    # depois de reservar a resposta, o catalogo de ferramentas e a margem.
    # Medido em 23/08: o catalogo das 34 ferramentas sozinho ocupa 3.835
    # tokens -- mais que todo o texto de instrucoes.
    limite = int(cfg.get("contexto", 8192))
    teto = (limite
            - min(int(cfg.get("max_tokens", 4096)), limite // 3)
            - _tokens_ferramentas(cfg, None)
            - 400)                      # margem + espaco para a sua pergunta
    teto = max(900, teto)
    # ONDE VOCES PARARAM entra na frente de MEMORIA SEMANTICA na fila de
    # corte: se o prompt apertar, e melhor perder o fio da conversa passada
    # do que perder as instrucoes de comportamento. Mas ele fica ANTES dos
    # projetos e das habilidades, porque continuidade vale mais que catalogo.
    opcionais = ["# OS PROJETOS DO FRED", "# MEMORIA SEMANTICA",
                 "# HABILIDADES DISPONIVEIS", "# MEMORIA DOS PROJETOS",
                 "# ONDE VOCES PARARAM", "# PASTAS LIBERADAS"]
    cortados = []
    for cabecalho in opcionais:
        texto = "\n\n".join(p.strip() for p in partes if p and p.strip())
        if _tokens(texto) <= teto:
            break
        antes = len(partes)
        partes = [p for p in partes
                  if not (p or "").strip().startswith(cabecalho)]
        if len(partes) < antes:
            cortados.append(cabecalho.replace("# ", ""))

    final = "\n\n".join(p.strip() for p in partes if p and p.strip())
    if cortados:
        anotar_erro("prompt grande demais para a janela de %d: tirei %s"
                    % (limite, ", ".join(cortados)))
    return final, fontes


# ==========================================================================
# Modelo
# ==========================================================================

# Quando este processo comecou. Serve para descobrir se o Bigode que esta no
# ar e mais VELHO que o cerebro.py do disco -- ou seja, se voce copiou codigo
# novo para o pendrive e esqueceu de reabrir. Ja aconteceu, e a pessoa fica
# medindo o efeito de uma correcao que nem esta rodando.
INICIADO_EM = time.time()

PROVEDOR = modelos.LocalModelProvider(config, salvar_config)


def modelo_online():
    return PROVEDOR.online()


def usar_nativas(cfg=None):
    """Decide sozinho como chamar ferramentas, conforme o modelo carregado.

    O Qwen tem secao de tools no template e aceita function calling oficial.
    O DeepSeek-Coder-V2 usa o formato antigo 'User:/Assistant:', sem tools:
    com ele, so o protocolo em texto funciona.
    """
    cfg = cfg or config()
    escolha = cfg.get("ferramentas_nativas", "auto")
    if isinstance(escolha, bool):
        return escolha
    modelo = PROVEDOR.atual() or {}
    return bool(modelo.get("ferramentas_nativas", True))


def extensao_ligada():
    """A extensao do Chrome esta viva?

    Aqui estava o defeito que fez o Bigode dizer "nao posso ver sua tela".

    O Chrome mata o service worker de uma extensao MV3 depois de ~30
    segundos parado. O nosso volta sozinho: ha um alarme de 30s que o
    religa, e ao acordar ele busca a fila e executa o que estiver la. Ou
    seja: extensao dormindo NAO e extensao desligada -- e extensao que vai
    responder daqui a pouco.

    Mas a regra antiga era "deu sinal nos ultimos 15 segundos". Com o
    alarme de 30s, essa janela passa MAIS DA METADE do tempo fechada. O
    Bigode entao desistia antes de tentar, devolvia "a extensao nao esta
    ativa", e o modelo traduzia isso para o Fred como "sou uma IA e nao
    vejo sua tela". Foi por isso que funcionou uma vez e falhou nas
    seguintes: dependia de o worker estar acordado naquele segundo.

    90 segundos cobrem com folga um ciclo inteiro do alarme.
    """
    return (time.time() - EXTENSAO["vista"]) < 90


def extensao_conhecida():
    """A extensao ja apareceu alguma vez desde que o Bigode abriu?

    Serve para decidir entre "esperar, que ela acorda" e "nem tentar".
    Nunca ter aparecido significa nao instalada, ou sem login nas Opcoes.
    """
    return EXTENSAO["vista"] > 0


def pedir_ao_navegador(nome, args, evento, espera=90):
    """Manda a acao para a extensao do Chrome e espera o resultado.

    O caminho da entrega mudou, e vale registrar por que. Antes, a acao ia
    para a TELA e a tela repassava para a extensao por postMessage. Isso so
    funcionava com o Bigode aberto DENTRO do painel lateral: numa aba
    normal, window.parent == window, e a resposta voltava na hora dizendo
    que a extensao nao estava aberta -- mesmo com ela instalada e rodando.
    Era o motivo de o navegador nunca funcionar.

    Agora a acao fica numa fila aqui no servidor e a extensao vem buscar
    sozinha. Nao importa mais onde a tela esta aberta -- nem se esta aberta.
    """
    pedido = uuid.uuid4().hex[:10]
    gatilho = threading.Event()
    with TRAVA:
        NAVEGADOR[pedido] = {
            "gatilho": gatilho, "resultado": None, "entregue": False,
            "acao": nome.replace("navegador_", ""), "args": args or {},
            "criado": time.time(),
        }
    CHEGOU.set()          # acorda a extensao na hora, sem esperar o proximo fetch

    # A tela continua recebendo o aviso: e o que faz aparecer "Navegando" na
    # narracao. Mas ela nao e mais o carteiro.
    evento({"tipo": "navegador", "id": pedido,
            "acao": nome.replace("navegador_", ""), "args": args or {}})

    # O aviso abaixo vai junto de toda falha do navegador.
    #
    # 24/08: o Fred pediu "o que tem na tela do meu navegador agora". O
    # Bigode CHAMOU navegador_ver -- a narracao mostrou "Olhando a pagina" --
    # a chamada falhou, e a resposta que ele deu foi:
    #
    #     "como uma inteligencia artificial sem acesso direto ao seu
    #      computador, nao posso ver a tela do seu navegador"
    #
    # Isso e falso e e o pior tipo de erro: manda o Fred procurar defeito
    # numa capacidade que existe. O modelo pegou a falha e a traduziu como
    # limitacao propria, porque e o que modelo de linguagem aprendeu a
    # dizer. A instrucao abaixo tira essa saida dele.
    NAO_NEGUE = ("\n\n[INSTRUCAO AO ASSISTENTE: isto e uma falha temporaria, "
                 "nao uma limitacao sua. Voce TEM acesso ao navegador do "
                 "Fred. Diga a ele exatamente o que falhou, no texto acima. "
                 "NUNCA responda que voce nao pode ver a tela dele ou que e "
                 "uma IA sem acesso ao computador.]")

    # So desiste se a extensao NUNCA apareceu. Se ela ja deu sinal alguma
    # vez, o pedido fica na fila e a gente espera: o Chrome pode ter posto o
    # service worker para dormir, e o alarme de 30s vai acorda-lo -- ao
    # acordar, a primeira coisa que ele faz e buscar esta fila.
    #
    # A regra antiga desistia na hora, e era o que produzia a resposta
    # errada. Esperar 90 segundos e melhor que mentir em 1 segundo.
    if not extensao_conhecida():
        with TRAVA:
            NAVEGADOR.pop(pedido, None)
        anotar_erro("navegador_%s: a extensao nunca deu sinal nesta sessao"
                    % nome.replace("navegador_", ""))
        return ("A extensao do Bigode nunca deu sinal desde que abri. "
                "Confira em chrome://extensions se ela esta instalada e "
                "ligada, e se voce entrou nas Opcoes dela com o mesmo "
                "e-mail desta tela." + NAO_NEGUE)

    if not gatilho.wait(espera):
        with TRAVA:
            NAVEGADOR.pop(pedido, None)
        anotar_erro("navegador_%s: sem resposta em %ds"
                    % (nome.replace("navegador_", ""), espera))
        return ("O navegador nao respondeu em %ds. Confira se ha uma aba "
                "aberta num site normal -- em paginas chrome:// a extensao "
                "nao consegue entrar." % espera + NAO_NEGUE)

    with TRAVA:
        return NAVEGADOR.pop(pedido, {}).get("resultado") or "(sem retorno)"


def _tokens(texto):
    """Estimativa conservadora. Codigo e JSON geram mais tokens por caractere
    que texto corrido, entao usamos 2,7 em vez de 4 para nao subestimar."""
    return int(len(texto or "") / 2.7) + 1


def _tokens_ferramentas(cfg, esquema=None):
    """O esquema das ferramentas viaja em toda requisicao e ocupa contexto."""
    if not usar_nativas(cfg):
        return 0
    try:
        lista = esquema if esquema is not None else ferramentas.esquema_openai()
        return _tokens(json.dumps(lista, ensure_ascii=False))
    except Exception:
        return 800


def caber_no_contexto(mensagens, cfg, esquema=None):
    """Descarta as mensagens mais antigas ate o pedido caber na janela do modelo.
    O prompt do sistema e a ultima pergunta nunca sao descartados."""
    limite = int(cfg.get("contexto", 4096))
    reserva = int(cfg.get("max_tokens", 4096))
    disponivel = (limite
                  - min(reserva, limite // 3)      # espaco para a resposta
                  - _tokens_ferramentas(cfg, esquema)
                  - 250)                           # margem de seguranca

    system = mensagens[0]
    corpo = mensagens[1:]
    if not corpo:
        return mensagens

    usado = _tokens(system["content"])
    mantidas, cortadas = [], 0

    # percorre de tras para frente: o mais recente e o mais importante
    for msg in reversed(corpo):
        custo = _tokens(msg.get("content", ""))
        if mantidas and usado + custo > disponivel:
            cortadas += 1
            continue
        usado += custo
        mantidas.append(msg)

    mantidas.reverse()

    # se ate a ultima mensagem sozinha estoura, corta o conteudo dela
    if len(mantidas) == 1 and usado > disponivel:
        limite_chars = max(400, disponivel * 3)
        mantidas[0] = dict(mantidas[0])
        mantidas[0]["content"] = ("[...trecho inicial removido por tamanho...]\n"
                                  + mantidas[0]["content"][-limite_chars:])

    # NUNCA alterar o texto do system: qualquer mudanca no inicio do prompt
    # invalida o cache do motor e obriga a reprocessar tudo (minutos perdidos).
    # O aviso de corte vai numa mensagem propria, no fim.
    if cortadas and mantidas:
        mantidas.insert(0, {"role": "user", "content":
                            "[Nota interna do sistema, nao comente nem cite: %d "
                            "mensagens antigas sairam por falta de espaco. Se "
                            "precisar de algo que estava nelas, releia o arquivo "
                            "com a ferramenta em vez de confiar na lembranca.]"
                            % cortadas})

    return [system] + mantidas


def _extrair_parcial(args_json, campo="conteudo"):
    """Le o valor de um campo enquanto o JSON ainda esta chegando pela metade.
    E o que permite mostrar o codigo aparecendo em tempo real."""
    marca = '"%s"' % campo
    pos = args_json.find(marca)
    if pos < 0:
        return None
    pos = args_json.find('"', pos + len(marca) + 1)
    if pos < 0:
        return None

    saida, i, n = [], pos + 1, len(args_json)
    escapes = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/"}
    while i < n:
        c = args_json[i]
        if c == "\\" and i + 1 < n:
            seguinte = args_json[i + 1]
            if seguinte == "u" and i + 5 < n:
                try:
                    saida.append(chr(int(args_json[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except Exception:
                    pass
            saida.append(escapes.get(seguinte, seguinte))
            i += 2
            continue
        if c == '"':
            break
        saida.append(c)
        i += 1
    return "".join(saida)


class Medidor:
    """Cronometro por etapa de um pedido, e o registro das evidencias.

    POR QUE ISTO EXISTE
        Antes so dava para saber que "demorou um minuto". Nao dava para saber
        se o minuto foi lendo o prompt, gerando texto, rodando ferramenta ou
        esperando voce clicar em autorizar. Sem essa separacao, trocar de
        modelo e palpite: pode-se dobrar a velocidade de geracao e o usuario
        nao sentir diferenca nenhuma, porque o tempo estava em outro lugar.

    A METRICA QUE IMPORTA
        Nao e tokens por segundo. E **tempo ate a tarefa correta**: do inicio
        do pedido ate uma resposta sustentada por evidencia. Um modelo tres
        vezes mais rapido que inventa e precisa de duas correcoes e mais lento
        na pratica.

    EVIDENCIA
        Guarda o que o agente realmente abriu, escreveu e executou. E isso que
        permite dizer, no fim, se a resposta se sustenta ou se ficou
        `nao_verificado`.
    """

    def __init__(self, pergunta="", modelo="", projeto=""):
        self.inicio = time.time()
        self.pergunta = (pergunta or "")[:300]
        self.modelo = modelo
        self.projeto = projeto

        self.prefill = 0.0          # motor lendo o prompt
        self.decode = 0.0           # motor escrevendo
        self.ferramentas = 0.0      # executando ferramenta
        self.autorizacao = 0.0      # esperando voce decidir

        self.chamadas_modelo = 0
        self.tokens_entrada = 0
        self.tokens_saida = 0
        self.pedacos = 0
        self.vezes_obrigado = 0     # quantas vezes precisou forcar ferramenta

        self.passos = 0
        self.ferramentas_usadas = []
        self.arquivos_lidos = []
        self.arquivos_escritos = []
        self.comandos = []
        self.fontes_web = []        # sites e buscas: a evidencia do mundo la fora
        self.erros = []

    # ---------------------------------------------------------- anotacoes
    def anotar_modelo(self, prefill, decode, pedacos, tokens_entrada,
                      tokens_saida, obrigou_ferramenta=False):
        self.chamadas_modelo += 1
        self.prefill += prefill
        self.decode += decode
        self.pedacos += pedacos
        self.tokens_entrada += tokens_entrada
        self.tokens_saida += tokens_saida
        if obrigou_ferramenta:
            self.vezes_obrigado += 1

    def anotar_ferramenta(self, nome, segundos, args=None):
        self.ferramentas += segundos
        self.ferramentas_usadas.append(nome)
        args = args or {}
        alvo = str(args.get("caminho") or args.get("nome") or "")
        if nome in ("ler_arquivo", "raio_x", "listar_pasta", "usar_habilidade",
                    "buscar"):
            if alvo:
                self.arquivos_lidos.append(alvo)
        elif nome in ("escrever_arquivo", "criar_projeto", "criar_pasta"):
            if alvo:
                self.arquivos_escritos.append(alvo)
        elif nome in ("terminal", "rodar_comando", "executar"):
            self.comandos.append(str(args.get("comando", ""))[:120])
        elif nome in ("web_buscar", "web_ler", "github_ler", "github_repos"):
            # Faltava contar isto. Uma resposta inteira baseada em pesquisa na
            # internet nao contava como verificada -- o selo so olhava arquivo
            # e comando. Para pergunta sobre o mundo, a fonte E a web.
            self.fontes_web.append(str(args.get("url") or args.get("consulta")
                                       or args.get("repo") or "")[:120])

    def anotar_autorizacao(self, segundos):
        self.autorizacao += segundos

    def anotar_erro(self, texto):
        self.erros.append(str(texto)[:200])

    # ---------------------------------------------------------- leitura
    @property
    def total(self):
        return time.time() - self.inicio

    @property
    def tem_evidencia(self):
        """Ele abriu ALGUMA coisa antes de responder?"""
        return bool(self.arquivos_lidos or self.arquivos_escritos
                    or self.comandos or self.fontes_web)

    @property
    def tem_fonte_externa(self):
        """Especificamente: consultou o mundo la fora?

        Separado de propria evidencia porque sao perguntas diferentes. Para
        "o que tem no meu projeto?", ler o arquivo basta. Para "quando a
        maconha foi proibida no Brasil?", ler arquivo nenhum resolve -- so
        vale fonte externa, e a memoria do modelo nao conta como fonte.
        """
        return bool(self.fontes_web)

    def tokens_por_segundo(self):
        return round(self.tokens_saida / self.decode, 1) if self.decode > 0.05 else 0.0

    def resumo(self, verificado=None):
        """O que vai para a tela e para o arquivo de medicoes."""
        total = self.total
        outros = max(total - self.prefill - self.decode
                     - self.ferramentas - self.autorizacao, 0)
        return {
            "modelo": self.modelo,
            "projeto": self.projeto,
            "pergunta": self.pergunta,
            "quando": datetime.datetime.now().isoformat(timespec="seconds"),

            "total_s": round(total, 1),
            "prefill_s": round(self.prefill, 1),
            "decode_s": round(self.decode, 1),
            "ferramentas_s": round(self.ferramentas, 1),
            "autorizacao_s": round(self.autorizacao, 1),
            "outros_s": round(outros, 1),

            "tokens_saida": self.tokens_saida,
            "tokens_entrada": self.tokens_entrada,
            "tok_por_s": self.tokens_por_segundo(),

            "chamadas_modelo": self.chamadas_modelo,
            "passos": self.passos,
            "vezes_obrigado": self.vezes_obrigado,
            "ferramentas_usadas": self.ferramentas_usadas,
            "arquivos_lidos": self.arquivos_lidos,
            "arquivos_escritos": self.arquivos_escritos,
            "comandos": self.comandos,
            "erros": self.erros,
            "tem_evidencia": self.tem_evidencia,
            "verificado": verificado,
        }

    def gravar(self, verificado=None):
        """Uma linha por pedido em memoria/medicoes.jsonl.

        Arquivo simples de proposito: da para abrir no bloco de notas, somar
        no Excel, e comparar dois modelos sem instalar nada.
        """
        try:
            destino = BASE / "memoria" / "medicoes.jsonl"
            destino.parent.mkdir(parents=True, exist_ok=True)
            with open(destino, "a", encoding="utf-8") as arq:
                arq.write(json.dumps(self.resumo(verificado),
                                     ensure_ascii=False) + "\n")
        except Exception:
            pass        # medir nunca pode derrubar o atendimento


class Cancelado(Exception):
    """O usuario apertou parar ou fechou a aba."""


def chamar_modelo(mensagens, ao_receber, com_ferramentas=True, ao_ferramenta=None,
                  esquema=None, obrigar_ferramenta=False, medidor=None):
    """Stream do modelo. Devolve (texto, chamada_de_ferramenta_ou_None).

    Usa function calling nativo quando disponivel: modelos menores seguem o
    padrao oficial muito melhor do que um protocolo inventado em texto.

    `medidor` recebe os tempos separados. Sem isso so da para saber que
    "demorou um minuto", sem saber ONDE. E a diferenca entre trocar de modelo
    por palpite e trocar sabendo o que se ganha.
    """
    cfg = config()
    if cfg.get("modelo_provedor") == "huggingface" and huggingface_cliente.configurado():
        inicio_hf = time.time()
        hf_cfg = cfg.get("huggingface") or {}
        texto_hf = huggingface_cliente.chat(
            mensagens, model=hf_cfg.get("texto_modelo"),
            temperature=cfg["temperatura"], max_tokens=cfg["max_tokens"],
            tools=(esquema if com_ferramentas else None))
        if texto_hf:
            ao_receber(texto_hf)
        if medidor is not None:
            medidor["inicio"] = inicio_hf
            medidor["primeiro_token"] = time.time()
            medidor["fim"] = time.time()
        return texto_hf, None
    if cfg.get("modelo_provedor") == "modal" and modal_cliente.configurado(cfg):
        inicio_modal = time.time()
        resposta_modal = modal_cliente.gerar(
            cfg, mensagens, temperatura=cfg["temperatura"],
            max_tokens=cfg["max_tokens"])
        texto_modal = resposta_modal["texto"]
        if texto_modal:
            ao_receber(texto_modal)
        if medidor is not None:
            medidor["inicio"] = inicio_modal
            medidor["primeiro_token"] = time.time()
            medidor["fim"] = time.time()
        # O endpoint Modal atual não implementa tool calling; manter a rota
        # local para ferramentas evita executar ações sem confirmação explícita.
        return texto_modal, None
    payload = {
        "messages": mensagens,
        "temperature": float(cfg["temperatura"]),
        "max_tokens": int(cfg["max_tokens"]),
        "stream": True,

        # GUARDAR O QUE JA FOI LIDO.
        #
        # As instrucoes fixas (identidade, temperamento, ferramentas) sao as
        # MESMAS em toda conversa: 2.533 tokens que nao mudam. Sem esta linha
        # o motor le tudo de novo a cada conversa nova.
        #
        # Medido em 19/08/2026 pelo medir_prompt.py --real:
        #     conversa nova ....... 94,0s ate a primeira letra
        #     segunda mensagem ..... 5,6s
        # Dezessete vezes. O texto so e reaproveitado dentro da mesma conversa.
        #
        # Com cache_prompt o motor guarda o pedaco inicial que se repete e
        # comeca a ler dali. Custa nada e nao mexe em uma virgula das
        # instrucoes -- o caminho oposto, cortar texto, economizaria menos e
        # levaria junto as regras que seguram a invencao.
        "cache_prompt": True,

        # Anti-repeticao com mao leve. Empilhar penalidade alta faz o modelo
        # fugir do vocabulario correto e cair em outro idioma ou em simbolo
        # solto. min_p corta a cauda improvavel sem distorcer o resto.
        "top_p": 0.9,
        "min_p": 0.05,
        "repeat_penalty": 1.06,
        "repeat_last_n": 128,
        "presence_penalty": 0.1,
        "frequency_penalty": 0.1,
    }
    if com_ferramentas and usar_nativas(cfg):
        lista = esquema if esquema is not None else ferramentas.esquema_openai()
        if lista:
            payload["tools"] = lista
            # Se o modelo suporta ferramentas nativas, permitimos auto ou required,
            # mas em obrigar_ferramenta ou na primeira rodada garantimos que ele escolha.
            payload["tool_choice"] = "required" if obrigar_ferramenta else "auto"
            if obrigar_ferramenta:
                payload["temperature"] = 0.2
    pedido = urllib.request.Request(
        cfg["llm_url"],
        data=json.dumps(payload).encode("utf-8"),
        headers=cabecalhos_llm(cfg),
    )
    completo = []
    chamadas = {}
    comeco = time.time()
    primeiro_token = None       # marca o fim da leitura do prompt
    pedacos_recebidos = 0
    with urllib.request.urlopen(pedido, timeout=1800) as resposta:
        for linha_bruta in resposta:
            linha = linha_bruta.decode("utf-8", "ignore").strip()
            if not linha.startswith("data:"):
                continue
            carga = linha[5:].strip()
            if carga == "[DONE]":
                break
            try:
                item = json.loads(carga)
                delta = item["choices"][0].get("delta", {})
            except Exception:
                continue

            # O primeiro pedaco que chega — texto OU chamada de ferramenta —
            # marca o momento em que o motor terminou de LER o prompt e comecou
            # a ESCREVER. Antes disso e prefill; depois, decode.
            if primeiro_token is None and (delta.get("content")
                                           or delta.get("tool_calls")):
                primeiro_token = time.time()

            pedaco = delta.get("content", "")
            if pedaco:
                pedacos_recebidos += 1
                completo.append(pedaco)
                ao_receber("".join(completo))

            # function calling nativo chega em pedacos e precisa ser remontado
            for tc in (delta.get("tool_calls") or []):
                indice = tc.get("index", 0)
                atual = chamadas.setdefault(indice, {"nome": "", "args": ""})
                funcao = tc.get("function") or {}
                if funcao.get("name"):
                    atual["nome"] = funcao["name"]
                if funcao.get("arguments"):
                    atual["args"] += funcao["arguments"]
                    if ao_ferramenta and atual["nome"]:
                        ao_ferramenta(atual["nome"], atual["args"])

    texto = "".join(completo)
    fim = time.time()
    PROVEDOR.registrar_velocidade(len(completo), fim - comeco)

    if medidor is not None:
        prefill = (primeiro_token - comeco) if primeiro_token else (fim - comeco)
        decode = (fim - primeiro_token) if primeiro_token else 0.0
        medidor.anotar_modelo(
            prefill=prefill,
            decode=decode,
            pedacos=pedacos_recebidos,
            tokens_entrada=_tokens(json.dumps(mensagens, ensure_ascii=False)),
            tokens_saida=_tokens(texto),
            obrigou_ferramenta=bool(obrigar_ferramenta),
        )

    chamada = None
    if chamadas:
        primeira = chamadas[sorted(chamadas)[0]]
        if primeira["nome"]:
            try:
                argumentos = json.loads(primeira["args"] or "{}")
            except Exception:
                argumentos = {}
            chamada = (primeira["nome"], argumentos)

    return texto, chamada


PADRAO_FERRAMENTA = re.compile(r"<ferramenta>\s*(\{.*?\})\s*</ferramenta>", re.S)
PADRAO_ALT = re.compile(r"```(?:json)?\s*(\{\s*\"nome\".*?\})\s*```", re.S)


# Formato <tool_call> — o padrao de fato de quem nao usa function calling
# nativo. Aparece em Qwen, Granite, Hermes e em quase todo servidor que nao
# implementa a chamada de ferramenta da OpenAI.
#
# 09/09: primeira vez rodando na nuvem, o Fred pediu informacao sobre
# cannabis e a tela mostrou isto, cru:
#
#     <tool_call>
#     {"name": "web_buscar", "arguments": "{\n \"consulta\": \"cannabis\"\n}"}
#     </tool_call>
#
# O modelo fez a coisa certa: pediu a ferramenta. Quem nao entendeu foi o
# Bigode -- ele so sabia ler `nome`/`args`, e ali vinha `name`/`arguments`.
# O motor da nuvem (llama-cpp-python) nao converte isso em chamada nativa
# como o llamafile do pendrive fazia.
#
# Ensinar o Bigode a ler os dois formatos e melhor que caçar configuracao de
# servidor: funciona em qualquer motor, hoje e no proximo que a gente usar.
PADRAO_TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)


def _objetos_json(texto):
    """Devolve cada objeto JSON completo encontrado no texto.

    Feito contando chaves em vez de regex. Uma expressao como `\\{.*?\\}`
    para no PRIMEIRO fecha-chaves -- e numa chamada de ferramenta o primeiro
    fecha-chaves e o dos argumentos, no meio do objeto:

        {"name": "web_buscar", "arguments": {"consulta": "cannabis"}}
                                                                  ^ aqui

    Ela devolveria JSON quebrado. Contar chaves acerta sempre, e ainda
    respeita chaves dentro de texto entre aspas.
    """
    dentro_de_aspas = escapado = False
    nivel = comeco = 0
    for i, c in enumerate(texto):
        if escapado:
            escapado = False
            continue
        if c == "\\":
            escapado = True
            continue
        if c == '"':
            dentro_de_aspas = not dentro_de_aspas
            continue
        if dentro_de_aspas:
            continue
        if c == "{":
            if nivel == 0:
                comeco = i
            nivel += 1
        elif c == "}":
            if nivel > 0:
                nivel -= 1
                if nivel == 0:
                    yield texto[comeco:i + 1]


def _normalizar_chamada(dados):
    """Aceita as duas grafias e devolve (nome, args) ou (None, None).

    `arguments` costuma vir como TEXTO contendo JSON, nao como objeto --
    e o caso do exemplo acima. Sem esse desembrulho, args viraria uma
    string e a ferramenta receberia lixo.
    """
    if not isinstance(dados, dict):
        return None, None
    nome = dados.get("nome") or dados.get("name")
    if not nome:
        return None, None
    args = (dados.get("args") if dados.get("args") is not None
            else dados.get("argumentos") if dados.get("argumentos") is not None
            else dados.get("arguments") if dados.get("arguments") is not None
            else dados.get("parameters"))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    return str(nome), (args if isinstance(args, dict) else {})


def extrair_chamada(texto):
    texto = texto or ""

    # 1) Os formatos com marcador em volta: <ferramenta>, ```json, <tool_call>
    for padrao in (PADRAO_FERRAMENTA, PADRAO_ALT, PADRAO_TOOL_CALL):
        for achado in padrao.finditer(texto):
            try:
                nome, args = _normalizar_chamada(json.loads(achado.group(1)))
                if nome:
                    return nome, args
            except Exception:
                continue

    # 2) JSON solto no meio da resposta, sem marcador nenhum. So vale a pena
    #    procurar se o texto ao menos MENCIONA um nome de chamada -- assim um
    #    JSON qualquer que o Fred tenha pedido para ele escrever nao vira
    #    ferramenta por engano.
    if '"name"' in texto or '"nome"' in texto:
        for bruto in _objetos_json(texto):
            try:
                nome, args = _normalizar_chamada(json.loads(bruto))
                if nome and nome in ferramentas.ativas():
                    return nome, args
            except Exception:
                continue
    return None, None


def resumir(nome, args):
    partes = []
    for chave, valor in (args or {}).items():
        texto = str(valor)
        if len(texto) > 90:
            texto = texto[:90] + "..."
        partes.append('%s="%s"' % (chave, texto))
    return "%s(%s)" % (nome, ", ".join(partes))


def _final(caminho):
    """Ultimo pedaco de um caminho, para caber na tela."""
    if not caminho:
        return ""
    limpo = str(caminho).replace("/", "\\").rstrip("\\")
    return limpo.split("\\")[-1] or limpo


def _lugar(caminho):
    """Caminho em linguagem de gente, para o Fred saber ONDE ele esta mexendo.

    'G:\\Meu Drive\\projetos\\carteira2026\\app.py'  ->  'Drive › projetos › carteira2026 › app.py'
    'D:\\Cerebro\\web\\index.html'                   ->  'Pendrive › Bigode › web › index.html'

    So mostrar o nome do arquivo esconde a informacao mais importante: em que
    projeto ele esta. Duas pastas diferentes tem README.md.
    """
    if not caminho:
        return ""
    limpo = str(caminho).replace("/", "\\").rstrip("\\")
    partes = [p for p in limpo.split("\\") if p]
    if not partes:
        return limpo

    # troca a letra da unidade por um nome que se entende
    apelidos = {"g:": "Drive", "d:": "Pendrive", "c:": "Computador"}
    if partes[0].lower() in apelidos:
        partes[0] = apelidos[partes[0].lower()]
    if len(partes) > 1 and partes[1].lower() in ("meu drive", "my drive"):
        partes.pop(1)

    # No Colab nao ha letra de unidade: o Drive fica montado em
    # /content/drive/MyDrive e o trabalho em /content. Sem isto, o caminho
    # aparecia como "content › drive › MyDrive › projetos › x" -- tres
    # niveis de encanamento antes da informacao que interessa.
    if partes[:3] == ["content", "drive", "MyDrive"]:
        partes = ["Drive"] + partes[3:]
    elif partes[:2] == ["content", "bigode"]:
        partes = ["Bigode"] + partes[2:]
    elif partes[:2] == ["content", "trabalho"]:
        partes = ["Trabalho"] + partes[2:]

    # caminho longo: mostra o comeco, corta o meio, mantem as duas ultimas
    if len(partes) > 4:
        partes = [partes[0], "…"] + partes[-2:]
    return " › ".join(partes)


def _dominio(url):
    from urllib.parse import urlparse
    try:
        alvo = url if str(url).startswith("http") else "https://" + str(url)
        return urlparse(alvo).netloc.replace("www.", "")
    except Exception:
        return str(url)[:40]


def narrar(nome, args, concluido=False):
    """Traduz a chamada tecnica para uma frase que qualquer um entende.

    A regra: escreva como voce contaria por telefone para alguem que nao ve a
    tela. Nao e "listar_pasta(G:/...)", e "estou na pasta projetos, vendo o
    que tem dentro". Enquanto acontece vai no gerundio; quando termina vira
    passado, para a lista de passos ler como um relato do que foi feito.
    """
    a = args or {}
    caminho = _lugar(a.get("caminho"))
    arquivo = _final(a.get("caminho"))

    # Verbo + alvo curto. Nada de frase. O caminho completo ja aparece na
    # linha de baixo do passo -- repetir aqui so faz a linha estourar e virar
    # "..." no meio, que e pior que informacao nenhuma.
    pasta = _final(a.get("caminho")) or ""

    frases = {
        "listar_pasta":     ("Olhando a pasta", "Olhei a pasta", pasta),
        "raio_x":           ("Mapeando o projeto", "Mapeei o projeto", pasta),
        "ler_arquivo":      ("Lendo",       "Li",         arquivo),
        "buscar":           ("Procurando",  "Encontrei",   a.get("termo", "")),
        "memoria":          ("Consultando a memória", "Consultei a memória", ""),
        "usar_habilidade":  ("Consultando o manual", "Consultei o manual", a.get("nome", "")),
        "github_repos":     ("Olhando seus repositórios", "Consultei seus repositórios", ""),
        "github_ler":       ("Lendo",       "Li",         arquivo),
        "web_buscar":       ("Pesquisando na web", "Pesquisei na web", a.get("consulta", "")),
        "web_ler":          ("Abrindo a fonte", "Li a fonte", _dominio(a.get("url", ""))),
        "escrever_arquivo": ("Editando",    "Editei",     arquivo),
        "criar_pasta":      ("Criando a pasta", "Criei a pasta", pasta),
        "mover":            ("Movendo",     "Mudei",      _final(a.get("origem"))),
        "apagar":           ("Apagando",    "Apaguei",    arquivo),
        "rodar_comando":    ("Executando o comando", "Executei o comando", ""),
        "github_criar_repo": ("Criando o repositório", "Criei o repositório", a.get("nome", "")),
        "github_commit":    ("Preparando o envio", "Enviei a alteração", arquivo),
        "github_issue":     ("Abrindo o chamado", "Abri o chamado", ""),
        "navegador":        ("Navegando",   "Naveguei",    ""),
        "navegador_ver":    ("Olhando a página", "Olhei a página", ""),
        "navegador_ir":     ("Abrindo o endereço", "Abri o endereço", a.get("url", "")),
        "navegador_clicar": ("Clicando em", "Cliquei em", "item " + str(a.get("numero", ""))),
        "navegador_escrever": ("Preenchendo o campo", "Preenchi o campo", "item " + str(a.get("numero", ""))),
        "navegador_teclar":  ("Apertando a tecla", "Apertei a tecla", a.get("tecla", "")),
        "navegador_rolar":   ("Rolando a página", "Rolei a página", a.get("direcao", "")),
        "navegador_esperar": ("Esperando a página", "Esperei a página", ""),
    }
    antes, depois, alvo = frases.get(nome, ("Trabalhando", "Terminou", ""))
    verbo = depois if concluido else antes

    alvo = str(alvo or "").strip()
    if not alvo:
        # "Lendo" sozinho parece frase cortada. Sem alvo, verbo generico.
        return "Trabalhando" if not concluido else "Terminou"
    if len(alvo) > 38:
        alvo = alvo[:37] + "…"
    return "%s %s" % (verbo, alvo)


GATILHOS = (
    "pasta", "diretorio", "diretório", "arquivo", "projeto", "codigo", "código",
    "auditoria", "auditar", "revisar", "analise", "análise", "analisar", "leia",
    "ler", "listar", "liste", "drive", "repositorio", "repositório", "github",
    "abrir", "abra", "verificar", "verifique", "corrigir", "corrija", "escrever",
    "criar", "crie", "g:\\", "d:\\", "c:\\", ".py", ".js", ".php", ".html", ".md",
    "acessar", "acesse", "acessa", "abre", "entrar no", "entre no", "estrutura",
    "conteudo", "conteúdo", "bug", "bugs", "melhoria", "melhorias", "erro",
    "erros", "readme", "package.json", "meu drive", "pendrive",
)


def pergunta_sobre_a_tela(pergunta):
    """A pergunta e sobre a pagina que o Fred esta vendo AGORA?

    Duas listas: uma de "o que ele quer" (ver, saber, dizer, que site e) e
    outra de "onde" (tela, aba, pagina, navegador, site, aqui). So conta
    quando as duas batem -- assim "abra o site da receita" nao entra, porque
    nao e sobre a tela atual, e "leia o arquivo desta pasta" tambem nao.
    """
    t = (pergunta or "").lower()
    onde = ("na tela", "minha tela", "sua tela", "da tela", "nesta pagina",
            "nesta página", "nessa pagina", "nessa página", "na pagina",
            "na página", "esta pagina", "esta página", "essa pagina",
            "essa página", "aba aberta", "minha aba", "no meu navegador",
            "do meu navegador", "que site", "qual site", "qual pagina",
            "qual página", "site estou", "site eu estou", "aqui na tela")
    if not any(p in t for p in onde):
        return False
    quer = ("o que tem", "o que ha", "o que há", "o que aparece", "o que voce ve",
            "o que você vê", "me diga", "me fala", "me fale", "descreva",
            "consegue ver", "consegue enxergar", "esta vendo", "está vendo",
            "ler", "leia", "resuma", "resumo", "analise", "analisa", "qual",
            "que site", "estou", "olhe", "olha", "ve ai", "vê aí",
            # "quero SABER o que tem na tela": ele escreveu "o qie tem" e
            # nenhum gatilho pegou. A palavra que sobrevive ao erro de
            # digitacao e o verbo do inicio da frase.
            "saber", "ver ")
    return any(p in t for p in quer)


def _quantas_acoes_pedidas(pergunta):
    """Quantas ações o Fred pediu nesta frase?

    "escreva X" -> 1.  "escreva X e clique na lupa" -> 2.

    Serve para saber se pode encerrar depois da primeira. Contamos os
    conectores que emendam pedidos ("e", "depois", "em seguida") junto de
    um verbo de ação. Na dúvida devolve 1: encerrar cedo demais é pior que
    dar um passo a mais, então só somamos quando o sinal é claro.
    """
    t = (pergunta or "").lower()
    emendas = (" e depois", " e em seguida", " em seguida", " depois disso",
               " e clique", " e clica", " e aperte", " e escreva", " e digite",
               " e salve", " e envie", " e abra", " e leia", " então clique",
               " entao clique", ", clique", ", aperte", ", escreva")
    return 1 + sum(1 for p in emendas if p in t)


def conferir_sem_o_modelo(nome, args, resultado):
    """A ação deu certo? Responde SIM/NÃO sem gastar uma chamada ao modelo.

    ═══ POR QUE ISTO EXISTE ═══════════════════════════════════════════════

    Este é o maior desperdício de tempo do Bigode hoje, e ninguém tinha
    olhado para ele.

    Quando o Fred pede "escreva X no campo de busca", acontece isto:

        1. modelo decide chamar navegador_escrever ......  75s
        2. a extensão escreve, e devolve "Escrevi X no campo [13]"
        3. modelo lê esse retorno e escreve "pronto, escrevi" .. MAIS 75s

    O passo 3 custa entre 75 e 230 segundos para produzir uma frase que o
    Python já sabia escrever no passo 2. A ação já aconteceu. O resultado
    já está em texto. Não há decisão nenhuma a tomar.

    Medido em 26/08, teste real na Shopee: a ação levou 1,4s e a resposta
    do modelo sobre ela levou 156s. **99% do tempo foi o modelo narrando
    o que o Python já sabia.**

    Então: quando a ferramenta devolve sucesso claro E o pedido do Fred era
    aquela ação e nada mais, o Python escreve a resposta e encerra. Zero
    chamadas ao modelo.

    Devolve (encerrar, texto) — encerrar=False significa "segue o laço
    normal, aqui tem coisa para o modelo pensar".
    """
    saida = (resultado or "").strip()
    if not saida:
        return False, ""

    # Sinal de fracasso em qualquer lugar do retorno: o modelo precisa ler
    # e decidir o que fazer. Não encerramos.
    ruim = ("não consegui", "nao consegui", "falha", "erro", "não encontrei",
            "nao encontrei", "negado", "não existe", "nao existe",
            "não permitido", "nao permitido", "sem retorno", "expirou",
            "não respondeu", "nao respondeu", "traceback")
    if any(p in saida.lower() for p in ruim):
        return False, ""

    # Ações de UM PASSO SÓ: fazem uma coisa, dizem que fizeram, acabou.
    # Ler arquivo e listar pasta NÃO entram aqui de propósito -- o conteúdo
    # lido é matéria-prima para o modelo responder, não a resposta.
    DE_UM_PASSO = {
        "navegador_escrever": "Escrevi na página.",
        "navegador_clicar":   "Cliquei.",
        "navegador_teclar":   "Apertei a tecla.",
        "navegador_rolar":    "Rolei a página.",
        "escrever_arquivo":   "Arquivo gravado.",
        "criar_pasta":        "Pasta criada.",
        "mover":              "Movido.",
    }
    if nome not in DE_UM_PASSO:
        return False, ""

    # A própria ferramenta já contou o que fez, com o detalhe certo
    # ("Escrevi 'seguro residencial' no campo [13] Busca na Shopee").
    # Essa frase é melhor do que qualquer resumo que o modelo faria.
    primeira = saida.splitlines()[0].strip()
    return True, (primeira if len(primeira) > 12 else DE_UM_PASSO[nome])


def pedido_de_acao_no_navegador(pergunta):
    """O Fred esta mandando MEXER na pagina aberta (clicar, escrever, salvar)?

    Serve para o mesmo fim que pergunta_sobre_a_tela: ler a pagina antes de
    falar com o modelo. Aqui o motivo e ainda mais forte -- para clicar num
    botao ele precisa do NUMERO daquele botao, e o numero so existe depois
    de navegador_ver. Sem a leitura pronta na mao, o modelo tem que lembrar
    de pedir a leitura sozinho, e ja vimos onde isso termina: ele pula a
    etapa e responde de cabeca.

    Exige verbo de acao E lugar. "escreva um e-mail para o Joao" nao entra,
    porque nao tem lugar. "escreva no campo de busca do site" entra.
    """
    return _verbo_de_acao(pergunta) and _lugar_de_navegador(pergunta)


def _verbo_de_acao(pergunta):
    t = (pergunta or "").lower()
    verbo = ("clique", "clica", "clicar", "aperte", "aperta", "escreva",
             "escrever", "digite", "digita", "digitar", "preencha",
             "preencher", "edite", "editar", "altere", "alterar", "mude",
             "mudar", "troque", "trocar", "corrija", "corrigir", "salve",
             "salvar", "envie", "enviar", "marque", "marcar", "selecione",
             "selecionar", "role", "rolar", "faca login", "faça login",
             "entre na", "entre no", "acesse", "acessar", "suba", "subir",
             "publique", "publicar", "apague", "apagar", "delete", "deletar",
             "adicione", "adicionar", "insira", "inserir", "cadastre",
             "redija", "redigir", "atualize", "atualizar")
    return any(v in t for v in verbo)


def _lugar_de_navegador(pergunta):
    t = (pergunta or "").lower()
    lugar = ("no site", "na pagina", "na página", "nesta pagina",
             "nesta página", "nessa pagina", "nessa página", "na tela",
             "no formulario", "no formulário", "no campo", "no botao",
             "no botão", "no navegador", "no chrome", "na aba", "aqui na",
             "pythonanywhere", "python anywhere", "no meu ambiente",
             "nesse ambiente", "neste ambiente", "no painel", "no console",
             "la no", "lá no", "nesse site", "neste site",
             # "role a pagina ate o fim" nao tem preposicao antes de
             # "pagina", e ficava de fora.
             "a pagina", "a página", "a tela", "a aba",
             # 24/08: "na barra de busca, escreva Cannabis" nao disparou --
             # nenhuma dessas expressoes estava aqui. Ele respondeu
             # "aguarde, abrindo a pagina de pesquisa" e nao fez nada.
             # Sao os nomes que uma pessoa da as PECAS de uma pagina.
             "barra de busca", "barra de pesquisa", "campo de busca",
             "campo de pesquisa", "caixa de busca", "caixa de pesquisa",
             "barra de endereco", "barra de endereço", "no campo",
             "no botao", "no botão", "no link", "no menu", "na caixa",
             "na barra", "no primeiro resultado", "no resultado")
    return any(p in t for p in lugar)


def precisa_agir(pergunta):
    """A pergunta pede acesso real a arquivos/projetos? Entao nao pode so conversar."""
    texto = (pergunta or "").lower()
    return any(g in texto for g in GATILHOS)


# ==========================================================================
# A segunda familia de gatilhos: perguntas sobre o MUNDO
# ==========================================================================
#
# A lista GATILHOS acima so pega pergunta sobre arquivo. Um pedido como
# "escreva um artigo sobre cannabis medicinal" nao aciona nada -- e foi assim
# que saiu um texto que errava a data da proibicao no Brasil em 150 anos,
# atribuia a planta a tradicao indigena (ela chegou com os africanos
# escravizados) e dizia faltar regulamentacao que existe desde maio de 2026.
#
# Fluente, seguro de si, e errado. Sem carimbo nenhum.
#
# Para este tipo de pergunta, ler arquivo do pendrive nao serve de evidencia:
# a unica fonte que vale e externa. E a memoria do modelo NAO e fonte.

GATILHOS_FONTE = (
    # tempo e numero -- onde modelo pequeno mais inventa
    "quando", "que ano", "em que ano", "qual ano", "data", "década", "decada",
    "quantos", "quantas", "quanto custa", "preço", "preco", "valor de",
    "percentual", "porcentagem", "estatística", "estatistica", "índice", "indice",
    # dinheiro de empresa. "faturamento" faltava, e era a primeira pergunta
    # do auditar_selo: "qual foi o faturamento da Venure em 2024?"
    "faturamento", "faturou", "receita de", "lucro", "prejuízo", "prejuizo",
    "custo de", "orçamento", "orcamento", "investimento", "market share",
    "quantos funcionários", "quantos funcionarios", "quanto vale",
    # identidade e autoridade
    #
    # "quem eh" entrou em 09/09: o Fred digitou "quem eh lampiao?" e a lista
    # so tinha "quem e" e "quem é". Uma letra de diferenca, e a trava inteira
    # ficou de fora. Ele escreve rapido e sem acento -- a lista tem que falar
    # a lingua dele, nao o contrario.
    "quem é", "quem e ", "quem eh", "quem foi", "quem inventou", "quem criou",
    "o que é", "o que e ", "o que eh", "me fale sobre", "me fala sobre",
    "fale sobre", "explique sobre", "me explique", "conte sobre",
    "presidente", "ministro", "prefeito", "governador", "ceo",
    # norma e direito
    "lei ", "artigo da lei", "decreto", "resolução", "resolucao", "portaria",
    "norma", "regulamenta", "legislaç", "legislac", "jurisprud", "constituiç",
    "anvisa", "receita federal", "cnpj de", "obrigatório", "obrigatorio",
    "é permitido", "e permitido", "é proibido", "e proibido", "é legal",
    # conhecimento que envelhece
    "atualmente", "hoje em dia", "última versão", "ultima versao", "mais recente",
    "notícia", "noticia", "aconteceu", "novidade",
    # producao de texto que afirma coisas
    "escreva um artigo", "escreva um texto", "escreva uma matéria",
    "escreva uma materia", "faça um artigo", "faca um artigo", "redija",
    "pesquise", "pesquisa sobre", "história d", "historia d", "fontes sobre",
    "compare", "diferença entre", "diferenca entre", "vantagens e desvantagens",
    # saude e dinheiro: onde errar machuca
    "sintoma", "tratamento", "medicamento", "dosagem", "efeito colateral",
    "diagnóstico", "diagnostico", "contraindicaç",
    "imposto", "aliquota", "alíquota", "juros", "financiamento", "investimento",
)


# ==========================================================================
# A EXCECAO: pergunta sobre o PROPRIO Bigode nao tem fonte externa
# ==========================================================================
#
# Medido em 23/08 com o medir_fluidez.py:
#
#   "Bom dia! Como voce esta hoje?" .................  6,2s   5 passos
#   "Quantos passos voce costuma dar?" ............   34,5s   8 passos
#   "Atualmente, qual e o seu jeito de trabalhar?" .  75,7s   8 passos
#   "Escreva um texto curto sobre a Venure" .......   99,1s   8 passos
#
# As tres lentas acionaram a trava por causa de "quantos", "atualmente" e
# "escreva um texto". Mas nenhuma delas e pergunta sobre o mundo: sao sobre
# ELE MESMO. Nao existe site nenhum que responda "quantos passos voce da".
#
# Resultado: ele gastava os OITO passos procurando uma fonte que nao existe,
# e so entao respondia. Seis segundos viravam cem.
#
# A correcao NAO enfraquece o selo. As cinco perguntas da prova
# ("faturamento da Venure", "artigo da lei", "versao do framework") continuam
# exigindo fonte, porque nenhuma fala do Bigode.

# CUIDADO com marca curta. A primeira versao desta lista tinha "te " e ela
# casou com "mais recenTE ", desligando a trava numa pergunta que PRECISAVA
# dela. Toda marca aqui tem de ser longa o bastante para nao aparecer no meio
# de outra palavra. O teste abaixo existe para pegar isso.
SOBRE_SI = (
    "voce ", "você ", "voce?", "você?",
    "seu jeito", "sua forma", "seu modo", "suas palavras", "seu nome",
    "contigo", "comigo", "com voce", "com você",
    "bom dia", "boa tarde", "boa noite", "tudo bem", "como vai",
    "obrigado", "obrigada", "valeu",
)


def pergunta_sobre_si(pergunta):
    """A pergunta e sobre o proprio Bigode, ou e conversa?

    Nesses casos a fonte externa nao existe -- mandar pesquisar so gasta os
    passos e a paciencia. Continua valendo a regra de nao inventar: se ele
    nao souber, diz que nao sabe.
    """
    texto = " %s " % (pergunta or "").lower()
    return any(m in texto for m in SOBRE_SI)


# Um ano de quatro digitos numa pergunta quase sempre e um pedido de fato
# datado -- "faturamento em 2024", "a lei de 2023", "o que aconteceu em 2019".
# E onde modelo pequeno mais inventa, e nenhuma lista de palavras cobre todas
# as formas de perguntar isso.
ANO_NA_PERGUNTA = re.compile(r"\b(19|20)\d{2}\b")


def precisa_fonte(pergunta):
    """A pergunta afirma algo sobre o mundo? Entao exige fonte externa."""
    texto = (pergunta or "").lower()
    bateu = (any(g in texto for g in GATILHOS_FONTE)
             or bool(ANO_NA_PERGUNTA.search(texto)))
    if not bateu:
        return False
    # Bateu numa palavra da lista -- mas fala do Bigode? Entao nao ha fonte.
    return not pergunta_sobre_si(pergunta)


# ═══════════════════════════════════════════════════════════════════════════
# O CARIMBO PASSA A SER O PADRAO
#
# 09/09/2026 — o pior dia do selo, e a prova de que ele estava desenhado ao
# contrario. Numa unica conversa o Bigode afirmou, com confianca e sem
# nenhum aviso:
#
#   · que Corisco e um canabinoide extraido da Corynanthe yohimbe
#     (Corisco era o cangaceiro, braco direito de Lampiao)
#   · que Lampiao se chamava Manuel Antonio Alves e era de Minas Gerais
#     (era Virgulino Ferreira da Silva, de Pernambuco)
#   · que Nelson Piquet foi campeao em 1978 pela McLaren-Honda
#     (foi 1981, 83 e 87, e o carro era Brabham)
#
# O Fred colou a pagina do Google mostrando o erro. Ele repetiu a invencao.
#
# Nada disso levou selo. Motivo: o selo so aparecia quando a pergunta batia
# numa LISTA DE PALAVRAS. "me fale sobre cannabis" nao bate. "quem eh
# lampiao" nao bate -- a lista tem "quem e" com acento, e ele escreveu "eh".
#
# Uma lista de palavras nunca vai cobrir tudo o que se pode perguntar. E o
# silencio, na tela, parece aprovacao.
#
# A logica foi invertida: **carimba por padrao, nao carimba na excecao**.
# Carimbar e de graca -- nao gasta chamada, nao atrasa nada. A unica coisa
# que custa e a confianca do Fred numa resposta inventada.
# ═══════════════════════════════════════════════════════════════════════════

# Aqui NAO cabe carimbo: nao ha o que verificar.
NAO_PRECISA_CARIMBO = (
    # conversa
    "oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "tudo bem",
    "obrigado", "obrigada", "valeu", "beleza", "certo", "entendi", "ok",
    "tchau", "ate logo", "até logo",
    # pedido de acao, nao de fato
    "escreva um codigo", "escreva um código", "crie um codigo",
    "crie um código", "faca uma funcao", "faça uma função", "refatore",
    "corrija o codigo", "corrija o código", "traduza", "resuma o texto",
    "reescreva", "melhore a frase", "escreva um email", "escreva um e-mail",
    # opiniao e criacao: nao ha fonte externa para "o que voce acha"
    "o que voce acha", "o que você acha", "na sua opiniao",
    "na sua opinião", "sugira um nome", "de ideias", "dê ideias",
    "brainstorm", "invente", "imagine",
)


def merece_carimbo(pergunta, resposta):
    """Esta resposta deve levar o carimbo NAO CONFERI se ele nao usou fonte?

    Sim, por padrao. Nao, apenas quando:
      · e conversa curta (cumprimento, agradecimento)
      · e um pedido de acao ou de criacao, nao de fato
      · e sobre o proprio Bigode
      · a resposta e curta demais para conter afirmacao arriscada
    """
    p = (pergunta or "").strip().lower()
    r = (resposta or "").strip()

    if len(r) < 180:
        return False                       # resposta curta: pouco a inventar
    if pergunta_sobre_si(pergunta):
        return False
    if len(p.split()) <= 3 and any(p.startswith(x) for x in NAO_PRECISA_CARIMBO):
        return False
    if any(x in p for x in NAO_PRECISA_CARIMBO):
        return False
    return True


def consulta_web_direta(pergunta):
    """Extrai consultas curtas que já são uma ordem clara de pesquisa.

    Isso evita gastar uma rodada do modelo perguntando por palavras-chave quando
    o usuário já disse exatamente o assunto, como em “pesquise sobre cannabis”.
    """
    texto = " ".join(str(pergunta or "").split())
    achado = re.search(
        r"\b(?:pesquise|pesquisar|pesquisa|busque|buscar)\b"
        r"(?:\s+(?:sobre|por|a respeito de|na web|na internet))?\s+(.+)$",
        texto, re.I,
    )
    if not achado:
        return ""
    consulta = achado.group(1).strip(" .?!\t\n")
    return consulta if len(consulta) >= 2 else ""


def contexto_acao(nome, args):
    """Informacao extra para a interface desenhar o cartao certo."""
    a = args or {}
    if nome in ("web_ler",):
        return {"tipo": "web", "dominio": _dominio(a.get("url", "")),
                "url": str(a.get("url", ""))}
    if nome == "web_buscar":
        return {"tipo": "busca", "consulta": str(a.get("consulta", ""))}
    if nome.startswith("github"):
        return {"tipo": "github"}
    if nome in ("listar_pasta", "ler_arquivo", "buscar", "escrever_arquivo",
                "criar_pasta", "mover", "apagar"):
        return {"tipo": "arquivo", "caminho": str(a.get("caminho") or a.get("origem") or "")}
    if nome == "memoria":
        return {"tipo": "memoria"}
    return {"tipo": "geral"}


# ==========================================================================
# Modelos (troca a quente)
# ==========================================================================

def listar_modelos():
    return PROVEDOR.listar()


def nome_modelo_atual():
    modelo = PROVEDOR.atual()
    return modelo["nome"] if modelo else ""


def estado_das_imagens():
    """O que a tela precisa saber sobre desenho, numa chamada so.

    Devolve sempre a mesma forma, mesmo quando nada existe -- assim o
    frontend nao precisa de tres caminhos diferentes para "sem modulo",
    "sem pasta" e "sem ComfyUI". Ele le `pronto` e `porque`.
    """
    vazio = {"pronto": False, "porque": "", "motor_no_ar": False,
             "pasta": "", "modelos": [], "formatos": []}
    try:
        import imagens
    except Exception as erro:
        vazio["porque"] = ("O modulo de desenho nao carregou (%s). Rode o "
                           "sincronizar-bigode.ps1." % erro)
        return vazio

    pasta = imagens.pasta_imagem()
    achados = imagens.modelos_de_imagem()
    componentes = imagens.componentes_imagem()
    no_ar = imagens.no_ar()

    porque = ""
    if not pasta:
        porque = ("Nao achei a pasta das IAs de imagem. Ela deve ficar em "
                  "Pen IA\\IA Imagem, no pendrive ou no Drive.")
    elif not achados:
        porque = "A pasta existe mas nao tem nenhum .gguf de imagem dentro."
    elif componentes.get("faltando"):
        porque = "Faltam componentes: " + ", ".join(componentes["faltando"])
    elif not no_ar:
        porque = ("As IAs estao aqui, mas o desenhista (ComfyUI) nao esta "
                  "ligado. No Colab, rode a celula 10.")

    return {"pronto": bool(pasta and achados and no_ar),
            "porque": porque,
            "motor_no_ar": no_ar,
            "pasta": str(pasta) if pasta else "",
            "modelos": achados,
            "componentes": componentes,
            "formatos": list(imagens.FORMATOS.keys())}


def ajustar_janela_se_preciso():
    """Se as instrucoes nao couberem, aumenta a janela e avisa.

    Passamos dias empurrando este numero de 425 para 243 para 43 tokens --
    cortando um pedaco aqui, desligando uma ferramenta ali, e voltando na
    conversa seguinte porque faltavam mais alguns. Enquanto isso o Bigode
    respondia "o motor derrubou a conexao", que nao ajuda ninguem.

    Isto encerra a perseguicao: o proprio Bigode confere ao abrir e, se nao
    couber, sobe a janela para o proximo tamanho. Custa memoria -- e ha
    memoria de sobra nesta maquina. Falta de espaco custava a ferramenta
    inteira.

    So aumenta. Nunca diminui sozinho: reduzir janela apaga conversa longa
    no meio, e isso o usuario tem de decidir.

    E SO AUMENTA SE ALGUEM PUDER RECARREGAR O MOTOR  (09/09, noite)
        A janela nao e um numero nosso: e o `--n_ctx` com que o motor SUBIU.
        Escrever 12288 no config.json nao faz o motor de 8192 aceitar 12288
        -- faz o Bigode mandar prompt que o motor recusa, e a resposta volta
        vazia.

        No pendrive isso nao aparecia porque quem sobe o motor e o proprio
        Bigode: salvar o config recarregava o motor com a janela nova. No
        Colab quem sobe o motor e a celula 6 do notebook. O Bigode nao tem
        como recarregar nada, e o log de 09/09 mostrou o estrago:

            21:41:53  janela ajustada de 8192 para 12288 (precisava de 8373)

        Motor em 8192, Bigode falando em 12288. Agora, quando nao ha como
        recarregar, ele nao mente sobre o tamanho: mantem a janela e corta o
        prompt -- que e o caminho que ja existe e funciona.
    """
    try:
        import ferramentas
        cfg = config()
        janela = int(cfg.get("contexto", 8192))

        # Quem sobe o motor aqui? Se for o notebook (Colab), o Bigode nao
        # manda no `--n_ctx` e aumentar so quebra.
        if os.name != "nt" and Path("/content").is_dir():
            return
        sistema, _ = montar_system("")
        precisa = (_tokens(sistema)
                   + _tokens_ferramentas(cfg, ferramentas.esquema_openai())
                   + min(int(cfg.get("max_tokens", 4096)), janela // 3)
                   + 600)                       # margem + sua pergunta
        if precisa <= janela:
            return

        for nova in (12288, 16384, 24576, 32768):
            if nova >= precisa + 1000:
                break
        else:
            nova = 32768

        print()
        print("   A janela era pequena para as instrucoes (%d de %d)."
              % (precisa, janela))
        print("   Aumentei para %d." % nova)
        salvar_config({"contexto": nova})      # ja recarrega o motor sozinho
        anotar_erro("janela ajustada de %d para %d (precisava de %d)"
                    % (janela, nova, precisa))
    except Exception as erro:
        anotar_erro("nao consegui conferir a janela", erro)


def conferir_janela():
    """O motor respeitou o que pedimos? O log dele responde.

    23/08: o Bigode pedia `--parallel 1` e o motor subia com n_parallel = 4.
    Com quatro lugares, a janela e DIVIDIDA por quatro -- `-c 8192` vira
    2.048 tokens por conversa. O prompt tem 3.600 e nunca coube. A tela
    dizia "o motor derrubou a conexao", que soa como problema do motor.

    Agora o proprio Bigode le o log ao ligar e avisa. Um aviso na hora vale
    mais que uma noite de investigacao.
    """
    registro = BASE / "motor.log"
    if not registro.is_file():
        return
    try:
        texto = registro.read_text(encoding="utf-8", errors="ignore")[:6000]
    except Exception:
        return

    achado = re.search(r"n_parallel\s*=\s*(\d+)", texto)
    if achado and int(achado.group(1)) > 1:
        n = int(achado.group(1))
        janela = int(config().get("contexto", 8192))
        print()
        print("   ATENCAO: o motor subiu com %d lugares (n_parallel = %d)." % (n, n))
        print("   Isso DIVIDE a janela: %d viram ~%d tokens por conversa."
              % (janela, janela // n))
        print("   Se as respostas falharem com 'o motor derrubou a conexao',")
        print("   e por falta de espaco -- nao e defeito do motor.")
        anotar_erro("motor com n_parallel=%d: janela util caiu para ~%d"
                    % (n, janela // n))


def aquecer():
    """Faz o motor ler as instrucoes fixas UMA vez, em segundo plano.

    O que doi nao e o tamanho do texto: e quando essa leitura cai na sua
    primeira pergunta. Medido em 19/08: 70 a 90 segundos na primeira conversa
    depois de o modelo carregar, e 5 a 6 segundos em todas as seguintes.

    Aqui a leitura acontece enquanto o modelo esta carregando de qualquer
    jeito e voce nao esta esperando nada. Usa o MESMO texto de sistema das
    conversas reais -- aquecer com outro texto nao serviria de nada, porque
    o motor guarda pelo comeco do que leu.

    Se falhar, falha em silencio: e uma otimizacao, nao uma funcionalidade.
    """
    # UM DE CADA VEZ.
    #
    # 25/08, no log do Fred: tres "Aquecido em" na mesma sessao (148s, 110s,
    # 82s) e dois `cancel task` do motor no meio. Aquecer e chamado ao abrir
    # E ao trocar de modelo; quando os dois coincidem, duas leituras de ~5
    # mil tokens disputam o mesmo lugar e uma derruba a outra. O motor fica
    # dois minutos ocupado sem produzir cache nenhum -- e se o Fred mandar
    # uma pergunta nesse meio, ela entra na fila atras disso.
    if not TRAVA_AQUECER.acquire(blocking=False):
        return
    try:
        _aquecer_de_verdade()
    finally:
        TRAVA_AQUECER.release()


def _aquecer_de_verdade():
    inicio = time.time()
    while time.time() - inicio < 900:              # ate 15 min carregando
        if modelo_online():
            break
        time.sleep(3)
    else:
        return

    try:
        system, _ = montar_system("")
        payload = {
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": "oi"}],
            "max_tokens": 1,          # nao queremos a resposta, so a leitura
            "temperature": 0,
            "stream": False,
            "cache_prompt": True,
        }

        # AS FERRAMENTAS TAMBEM PRECISAM SER AQUECIDAS
        #
        # Ate 25/08 este aquecimento mandava SO o texto do sistema, sem
        # `tools`. Parecia bastar -- o texto e o mesmo, e o motor guarda pelo
        # comeco do que leu.
        #
        # So que o motor nao ve "texto do sistema" e "ferramentas" como duas
        # coisas: ele junta tudo num prompt so, e o catalogo das ferramentas
        # entra JUNTO do system, antes da pergunta. Aquecer sem o catalogo
        # produz um comeco diferente do que a conversa real vai mandar --
        # ou seja, um aquecimento que nao aquece nada do que importa.
        #
        # Mandamos o catalogo base: as ferramentas que sobram quando a
        # pergunta nao aciona grupo nenhum (arquivos, projetos, memoria). E o
        # conjunto presente em TODA conversa, e portanto o unico pedaco que
        # vale a pena deixar pronto.
        # Tem de ser o MESMO catalogo que a conversa real manda. Aquecer com
        # um conjunto e conversar com outro produz um comeco diferente, e
        # aquecimento com comeco diferente nao aquece nada.
        try:
            cfgq = config()
            if cfgq.get("ferramentas_dinamicas", False):
                catalogo = ferramentas.para_pergunta("")
            else:
                catalogo = ferramentas.ativas()
            payload["tools"] = ferramentas.esquema_openai(catalogo)
            payload["tool_choice"] = "auto"
        except Exception:
            pass
        pedido = urllib.request.Request(
            config()["llm_url"], data=json.dumps(payload).encode("utf-8"),
            headers=cabecalhos_llm(config()))
        with urllib.request.urlopen(pedido, timeout=600) as r:
            r.read()
        print("   Aquecido em %.0fs — a primeira pergunta ja sai rapida."
              % (time.time() - inicio))
    except Exception:
        pass                          # sem aquecimento a ferramenta funciona igual


def trocar_modelo(caminho):
    resposta = PROVEDOR.carregar(caminho)
    # Em segundo plano: quem trocou de modelo ja vai esperar o carregamento,
    # e esse tempo estava sendo desperdicado.
    ajustar_janela_se_preciso()
    conferir_janela()
    threading.Thread(target=aquecer, daemon=True).start()
    return resposta


# ==========================================================================
# Tarefa (usada pela ponte MCP com o Claude - sem streaming)
# ==========================================================================

def executar_direto(nome, args):
    """Executa UMA ferramenta, sem passar pelo modelo local.

    E o que faz a ponte com o Claude valer a pena. Antes, para o Claude ler um
    arquivo do Fred, o pedido tinha que atravessar o modelo local: ele
    interpretava, escolhia a ferramenta, chamava, resumia. Lento e sujeito a
    erro - e o modelo local e justamente a parte fraca.

    Aqui o Claude escolhe a ferramenta e o Bigode so executa. O Bigode
    continua sendo o dono das regras: pasta liberada, ferramenta ligada e
    bloqueio de escrita continuam valendo.
    """
    catalogo = ferramentas.ativas()
    if nome not in catalogo:
        disponiveis = ", ".join(sorted(catalogo))
        return {"ok": False,
                "erro": "Ferramenta '%s' nao existe ou esta desligada. "
                        "Disponiveis: %s" % (nome, disponiveis)}

    if catalogo[nome].get("escrita"):
        return {"ok": False,
                "erro": "'%s' altera arquivos e esta bloqueada na ponte. "
                        "Peca ao Fred para fazer pela tela do Bigode." % nome}

    try:
        comeco = time.time()
        resultado = catalogo[nome]["fn"](**(args or {}))
        return {"ok": True, "nome": nome,
                "narracao": narrar(nome, args, True),
                "segundos": round(time.time() - comeco, 1),
                "resultado": str(resultado)}
    except TypeError as erro:
        esperado = catalogo[nome].get("args", "")
        return {"ok": False,
                "erro": "Argumentos errados para '%s'. Esperado: %s. (%s)"
                        % (nome, esperado, erro)}
    except Exception as erro:
        return {"ok": False, "erro": "Falha em '%s': %s" % (nome, erro)}


def tarefa(pergunta, contexto=""):
    """Roda o ciclo de ferramentas sem interface. Acoes de escrita sao negadas:
    pela ponte, o Bigode le, analisa e escreve codigo - mas nao altera nada.

    O SELO TAMBEM VALE AQUI  (consertado em 09/09, tarde)
        Esta funcao e um segundo cerebro, paralelo ao `_chat`: mesmo motor,
        mesmas ferramentas, laco proprio. Toda a defesa contra invencao --
        medidor, portao de evidencia, `merece_carimbo` -- morava so no
        `_chat`. Quem entrava por aqui (a ponte MCP e o /api/tarefa) recebia
        o texto limpo, sem um unico aviso.

        O teste que revelou: "quem foi Corisco no cangaco?" pelo /api/tarefa.
        Veio uma biografia inteira de um cantor de musica caipira nascido em
        1928 -- pessoa que nao existe. `fontes: []`, nenhum carimbo, HTTP 200.
        Pela tela, a MESMA pergunta carimba. Duas portas, uma trancada.

        Agora as duas usam o mesmo criterio. O aviso sai em `verificado` e
        `aviso`, e tambem no comeco do texto -- porque quem le pela ponte
        muitas vezes so olha o texto.
    """
    cfg = config()
    system, fontes = montar_system(pergunta)
    system += ("\n\n# MODO PONTE\n\nVoce esta respondendo ao Claude, nao ao Fred. "
               "Ferramentas de escrita estao bloqueadas neste modo: leia, analise e "
               "devolva o codigo ou a resposta em texto.")
    entrada = pergunta if not contexto else (contexto + "\n\n" + pergunta)
    mensagens = [{"role": "system", "content": system},
                 {"role": "user", "content": entrada}]

    # As evidencias, para o portao la embaixo. Guardamos separado porque as
    # perguntas sao diferentes: para "o que tem no meu projeto?" ler arquivo
    # basta; para "quem foi Corisco?" so vale fonte externa.
    leu_algo = []
    fonte_externa = []

    acoes, texto = [], ""
    for _ in range(int(cfg["max_passos"])):
        try:
            resposta, nativa = chamar_modelo(caber_no_contexto(mensagens, cfg),
                                             lambda _acumulado: None)
        except Exception as erro:
            return {"texto": "Falha ao falar com o motor: %s" % erro,
                    "acoes": acoes, "fontes": fontes,
                    "verificado": None, "aviso": ""}

        nome, args = nativa if nativa else extrair_chamada(resposta)
        texto = (resposta.split("<ferramenta>")[0]
                         .split("<tool_call>")[0]
                         .split("```json")[0].strip())
        if not nome:
            break

        mensagens.append({"role": "assistant", "content": resposta})
        if ferramentas.exige_autorizacao(nome):
            acoes.append("BLOQUEADA: " + resumir(nome, args))
            mensagens.append({"role": "user", "content":
                              "RESULTADO: acao de escrita bloqueada no modo ponte. "
                              "Entregue o conteudo em texto para o Claude."})
            continue

        resultado = ferramentas.executar(nome, args)
        acoes.append(resumir(nome, args))

        # Mesma classificacao que o Medidor faz no `_chat`. Repetida aqui de
        # proposito, curta: importar o Medidor inteiro para contar duas listas
        # traria cronometro, tokens e gravacao em disco que a ponte nao usa.
        if nome in ("web_buscar", "web_ler", "github_ler", "github_repos"):
            fonte_externa.append(str(args.get("url") or args.get("consulta")
                                     or args.get("repo") or "")[:120])
        elif nome in ("ler_arquivo", "raio_x", "listar_pasta", "buscar",
                      "usar_habilidade", "terminal", "rodar_comando"):
            leu_algo.append(str(args.get("caminho") or args.get("termo")
                                or args.get("nome") or "")[:120])

        mensagens.append({"role": "user", "content": "RESULTADO:\n" + resultado})

    # ═══ PORTAO DE EVIDENCIA (o mesmo da tela) ════════════════════════════
    verificado, aviso = None, ""
    quer_fonte = precisa_fonte(pergunta)
    quer_arquivo = precisa_agir(pergunta)

    # A rede de seguranca: nenhum gatilho disparou, ele nao abriu nada, e
    # mesmo assim escreveu paragrafos afirmativos. Foi por aqui que passou a
    # invencao sobre Corisco.
    if (not quer_fonte and not quer_arquivo
            and not (leu_algo or fonte_externa)
            and merece_carimbo(pergunta, texto)):
        quer_fonte = True

    if texto and (quer_fonte or quer_arquivo):
        # A ORDEM IMPORTA (consertado no mesmo dia, minutos depois)
        #
        # A primeira versao perguntava `quer_fonte` antes de tudo. Resultado:
        #
        #   "liste as pastas de G:\\Meu Drive\\projetos e diga quantas sao"
        #   -> ele listou a pasta, contou 36, acertou
        #   -> e levou carimbo de NAO CONFERIDO assim mesmo
        #
        # Porque a palavra "quantas" acordou o gatilho de fonte, e fonte so
        # aceitava web. Carimbo em resposta certa e pior do que carimbo
        # nenhum: ensina a ignorar o carimbo.
        #
        # A pergunta era sobre os arquivos DELE. Para essa, abrir o arquivo E
        # a fonte. Web so vira obrigatoria quando o assunto e o mundo la fora
        # e nao ha caminho nenhum na pergunta.
        if quer_arquivo:
            basta = bool(leu_algo or fonte_externa)
        elif quer_fonte:
            basta = bool(fonte_externa)
        else:
            basta = bool(leu_algo or fonte_externa)
        verificado = bool(basta)
        if not basta:
            if quer_fonte and not quer_arquivo:
                aviso = ("NAO CONFERIDO: afirma coisas sobre o mundo (datas, "
                         "nomes, numeros) sem consultar nenhuma fonte. "
                         "Escrito de memoria do modelo. Trate como rascunho.")
            else:
                aviso = ("NAO CONFERIDO: respondeu sem abrir arquivo, sem "
                         "listar pasta e sem rodar comando. Trate como "
                         "rascunho.")
            # No comeco do texto tambem: quem consome pela ponte costuma ler
            # so o campo `texto` e ignorar o resto do JSON.
            texto = "[" + aviso + "]\n\n" + texto

    return {"texto": texto, "acoes": acoes, "fontes": fontes,
            "verificado": verificado, "aviso": aviso,
            "evidencias": {"leu": leu_algo[:12], "web": fonte_externa[:8]}}


def sintetizar_pesquisa(prompt):
    cfg = config()
    mensagens = [{"role": "system", "content": "Você é o modo Pesquisa Profunda do Bigode IA. Seja preciso, cite evidências e não use ferramentas nesta etapa."},
                 {"role": "user", "content": prompt}]
    resposta, _ = chamar_modelo(mensagens, lambda _acumulado: None)
    return resposta


def iniciar_pesquisa_profunda(consulta):
    return pesquisa_profunda.iniciar(
        consulta,
        lambda q: ferramentas.executar("web_buscar", {"consulta": q}),
        lambda url: ferramentas.executar("web_ler", {"url": url}),
        sintetizar_pesquisa)


# ==========================================================================
# Servidor
# ==========================================================================

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    # ------------------------------ GET ------------------------------
    # ---------------- acesso pela rede ----------------
    # rotas que funcionam sem estar logado
    # O navegador pede o icone ANTES de voce entrar. Se a rota exigir login,
    # ele recebe um desvio para /login, nao entende, e continua mostrando o
    # icone velho que guardou. Por isso icone e imagem ficam livres.
    LIVRES = ("/login", "/health", "/api/health", "/api/login/estado", "/api/login/entrar",
              "/api/login/criar", "/auth/", "/icone", "/manifest.json",
              "/sw.js", "/apple-touch-icon", "/favicon", "/img/",
              "/venure.css",
              # Travado, o login tambem pode nao responder. Diagnostico que
              # exige login nao serve para diagnosticar travamento.
              "/api/diagnostico")

    def _sessao(self):
        """Quem esta falando: pelo cookie (navegador) ou pelo cabecalho.

        O cabecalho existe por causa da extensao do Chrome. Uma chamada de
        chrome-extension:// para localhost e cross-site, e o cookie de sessao
        tem SameSite=Lax -- o Chrome nao envia, por mais que se faca login.
        Cabecalho nao obedece a SameSite. E a MESMA sessao, com o mesmo login
        e a mesma validade: so muda por onde o cracha chega.
        """
        cabecalho = (self.headers.get("X-Cerebro-Sessao") or "").strip()
        if cabecalho:
            s = autenticacao.sessao_de("sessao=" + cabecalho)
            if s:
                return s
        return autenticacao.sessao_de(self.headers.get("Cookie"))

    def _autorizado(self):
        rota = self.path.split("?")[0]
        if any(rota.startswith(p) for p in self.LIVRES):
            return True
        if not config().get("exigir_login", True):
            return True
        if self._chave_extensao_ok(rota):
            return True
        return bool(self._sessao())

    def _chave_extensao_ok(self, rota):
        """A extensao do Chrome se identifica por chave, nao por cookie.

        Vale para a ponte local e para as rotas do navegador: a chave nao abre
        a interface nem as rotas de escrita. A ponte ainda bloqueia ferramentas
        de escrita em `executar_direto` e `tarefa`.
        """
        if rota not in ("/api/navegador", "/api/tarefa", "/api/ferramenta"):
            return False
        enviada = (self.headers.get("X-Cerebro-Chave") or "").strip()
        esperada = (config().get("chave_extensao") or "").strip()
        # compare_digest evita medir o tempo da comparacao para adivinhar
        import hmac
        return bool(esperada) and hmac.compare_digest(enviada, esperada)

    def _base_url(self):
        anfitriao = self.headers.get("Host") or ("localhost:%d" % config()["porta"])
        return "http://" + anfitriao

    def _ir_para(self, destino, cookie=None):
        try:
            self.send_response(302)
            self.send_header("Location", destino)
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", "0")
            self._cors()
            self.end_headers()
        except (ConnectionError, OSError):
            pass

    def _cookie_sessao(self, token):
        return ("sessao=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Lax"
                % (token, autenticacao.DIAS_SESSAO * 86400))

    def do_GET(self):
        rota = self.path.split("?")[0]

        # ---------- entrar com Google / GitHub ----------
        if rota.startswith("/auth/"):
            return self._oauth(rota)

        # Imagens da marca. Livre de login de proposito: e so o gato, e a tela
        # de entrar precisa dele antes de haver sessao. So serve o que esta
        # dentro de web/img -- ".." no caminho nao passa daqui.
        # A FOLHA DE ESTILO COMUM AS DUAS FERRAMENTAS           (13/09)
        #
        #   O venure.css carrega o vidro liquido, a marca respirando e a
        #   chancela -- tudo o que o Bigode e a Pipi tem igual. Fica fora
        #   do HTML por um motivo pratico: assim a Pipi usa o MESMO
        #   arquivo, e um conserto de estilo nao precisa ser feito duas
        #   vezes em dois projetos que ninguem lembra de sincronizar.
        #
        #   Livre de login, como as imagens: a tela de entrar precisa dele
        #   antes de existir sessao, senao o login aparece sem estilo.
        if rota == "/venure.css":
            arq = BASE / "web" / "venure.css"
            if arq.is_file():
                return self._enviar(200, "text/css; charset=utf-8",
                                    arq.read_bytes())
            return self._enviar(404, "text/plain", b"venure.css nao encontrado")

        if rota.startswith("/img/"):
            nome = rota[5:]
            alvo = (BASE / "web" / "img" / nome).resolve()
            pasta = (BASE / "web" / "img").resolve()
            if alvo.is_file() and str(alvo).startswith(str(pasta)):
                tipo = ("image/png" if alvo.suffix.lower() == ".png"
                        else "image/jpeg" if alvo.suffix.lower() in (".jpg", ".jpeg")
                        else "application/octet-stream")
                return self._enviar(200, tipo, alvo.read_bytes())
            return self._enviar(404, "text/plain", b"imagem nao encontrada")

        if rota == "/login":
            pagina_login = ler(BASE / "web" / "login.html")
            return self._enviar(200, "text/html; charset=utf-8",
                                pagina_login.encode("utf-8"))

        if rota == "/api/login/estado":
            return self._enviar(200, *self._json({
                "tem_conta": autenticacao.existe_alguem(),
                "provedores": autenticacao.disponiveis(config()),
                "logado": bool(self._sessao()),
            }))

        if not self._autorizado():
            return self._ir_para("/login")

        if rota.startswith("/api/pesquisa/job/"):
            job = pesquisa_profunda.obter(rota.rsplit("/", 1)[-1])
            return self._enviar(200 if job else 404, *self._json(job or {"ok": False, "erro": "pesquisa não encontrada"}))

        if rota.startswith("/api/imagens/job/"):
            job = runtime.get_image_job(rota.rsplit("/", 1)[-1])
            return self._enviar(200 if job else 404, *self._json(job or {"ok": False, "erro": "job não encontrado"}))

        rotas = {
            "/api/eu": lambda: self._json({
                **(self._sessao() or {}),
                "usuarios": autenticacao.listar_usuarios(),
            }),
            "/api/sair": lambda: self._json({"ok": True}),
            "/": lambda: ("text/html; charset=utf-8", pagina().encode("utf-8")),
            # A tela antiga continua alcancavel enquanto ela for a unica casa
            # de projetos, especialistas, skills, programados e memoria.
            "/antigo": lambda: ("text/html; charset=utf-8",
                                pagina(antiga=True).encode("utf-8")),
            "/manifest.json": lambda: ("application/manifest+json; charset=utf-8",
                                       json.dumps(MANIFESTO).encode("utf-8")),
            "/sw.js": lambda: ("application/javascript; charset=utf-8",
                               SERVICE_WORKER.encode("utf-8")),
            "/icone-192.png": lambda: ("image/png", icone(192)),
            "/icone-512.png": lambda: ("image/png", icone(512)),
            "/apple-touch-icon.png": lambda: ("image/png", icone(180)),
            "/apple-touch-icon-precomposed.png": lambda: ("image/png", icone(180)),
            # O icone da aba. O Chrome pede /favicon.ico sozinho, sem olhar o
            # HTML; sem esta rota ele fica com o que guardou de antes.
            "/favicon.ico": lambda: ("image/x-icon", favicon()),
            "/favicon-32.png": lambda: ("image/png", favicon(32)),
            "/favicon-48.png": lambda: ("image/png", favicon(48)),
            "/favicon-180.png": lambda: ("image/png", favicon(180)),
            "/favicon-192.png": lambda: ("image/png", favicon(192)),
            "/favicon-512.png": lambda: ("image/png", favicon(512)),
            "/api/rede": lambda: self._json({
                "ip": ip_local(), "porta": config().get("porta", 7000),
                "aberto": bool(config().get("acesso_rede", True)),
                "com_codigo": bool((config().get("codigo_acesso") or "").strip()),
            }),
            # Onde cada parte do Bigode esta parada AGORA.
            #
            # O erros.log so pega o que QUEBRA. Travamento nao quebra nada:
            # o programa fica de pe, esperando para sempre, e nao ha erro
            # nenhum para registrar. Esta rota tira uma foto de todas as
            # linhas de trabalho em andamento e mostra em que linha do
            # codigo cada uma parou. E a unica forma de ver um travamento
            # por dentro.
            "/api/diagnostico": lambda: self._json(_diagnostico()),
            "/api/logs": lambda: self._json(_logs_recentes()),
            "/health": lambda: self._json({"ok": True, "servico": "bigode", "uptime_s": round(time.time() - INICIADO_EM, 1)}),
            "/api/health": lambda: self._json(runtime.snapshot(PROVEDOR, estado_das_imagens, conexoes_publicas())),
            "/api/runtime": lambda: self._json(runtime.snapshot(PROVEDOR, estado_das_imagens, conexoes_publicas())),
            "/api/status": lambda: self._json({
                **PROVEDOR.status(),
                "iniciado_em": INICIADO_EM,
                "codigo_de": (BASE / "cerebro.py").stat().st_mtime
                if (BASE / "cerebro.py").is_file() else 0,
                "modelo": modelo_online(),
                "modelo_nome": nome_modelo_atual(),
                "erro_motor": "" if modelo_online() else PROVEDOR.erro_recente(),
                "extensao": extensao_ligada(),
                "projetos": len(list(PROJETOS.glob("*.md"))) if PROJETOS.exists() else 0,
                "conexoes": sum(1 for c in conexoes().values()
                                if isinstance(c, dict) and c.get("ativa")),
            }),
            "/api/modelos": lambda: self._json({
                "modelos": listar_modelos(),
                "mcp": "%s %s" % (
                    str(BASE / "python" / "python.exe")
                    if (BASE / "python" / "python.exe").exists() else "python",
                    str(BASE / "mcp_servidor.py")),
            }),
            # Desenho: o que existe e se da para usar agora.
            #
            # Fica separado de /api/modelos de proposito. Sao duas familias
            # diferentes -- texto le pelo llama.cpp, imagem pelo ComfyUI --
            # e ja misturamos as duas uma vez, com o resultado de o Bigode
            # tentar carregar um modelo de difusao como se fosse de conversa.
            "/api/imagens": lambda: self._json(estado_das_imagens()),
            "/api/conversas": lambda: self._json({
                "conversas": armazenamento.listar_conversas(self._param("busca"))}),
            "/api/conversa": lambda: self._json(
                armazenamento.abrir_conversa(self._param("id"))),
            "/api/projetos": lambda: self._json({
                "projetos": armazenamento.listar_projetos()}),
            "/api/voz": lambda: self._json(voz.status()),
            "/api/habilidades": lambda: self._json({
                "habilidades": habilidades.listar(),
                "texto": habilidades.texto_bruto(self._param("id")),
            }),
            # A extensao do Chrome bate aqui de segundo em segundo. Duas
            # funcoes numa chamada so: diz "estou viva" e leva o que houver
            # para fazer. Menos chamada, menos bateria do notebook.
            "/api/navegador/pendentes": lambda: self._json(self._fila_navegador()),
            "/api/especialistas": lambda: self._json({
                "especialistas": especialistas.listar(),
                "prontos": especialistas.PRONTOS,
                "rigores": especialistas.RIGORES}),
            "/api/programados": lambda: self._json({
                "tarefas": agenda.listar(), "motor": modelo_online()}),
            "/api/programado/historico": lambda: self._json(
                agenda.ver_historico(self._param("id"))),
            "/api/artefatos": lambda: self._json({
                "artefatos": agenda.artefatos()}),
            "/api/conexoes": lambda: self._json(conexoes_publicas()),
            "/api/dominios": lambda: self._json({
                "dominios": chroma_memoria.dominios_configurados()}),
            "/api/chroma/status": lambda: self._json(chroma_memoria.status()),
            "/api/config": lambda: self._json(config_publica()),
            "/api/memoria": lambda: self._json(self._memoria()),
            "/api/personalidade": lambda: self._json({
                "tracos_disponiveis": [
                    {"id": k, "texto": v} for k, v in TRACOS.items()],
                **personalidade(),
            }),
        }
        acao = rotas.get(self.path.split("?")[0])
        if not acao:
            return self._enviar(404, "text/plain", b"nao encontrado")
        tipo, corpo = acao()
        self._enviar(200, tipo, corpo)

    def _fila_navegador(self):
        """O que a extensao precisa fazer agora.

        Se nao ha nada, esta chamada NAO responde vazia na hora: ela segura
        a linha por ate 25 segundos esperando aparecer trabalho. Chamam isso
        de espera longa, e aqui ela resolve duas coisas de uma vez:

          - a acao chega na extensao no instante em que e criada, em vez de
            esperar o proximo fetch;
          - o Chrome mantem o service worker vivo enquanto ha uma chamada
            aberta. Sem isso ele dorme em ~30s, e uma extensao dormindo era
            lida pelo Bigode como extensao desligada.

        25 segundos ficam abaixo de qualquer tempo limite padrao e acima do
        alarme de 30s da extensao, entao as duas pontas se cobrem.
        """
        EXTENSAO["vista"] = time.time()

        def colher():
            fora = []
            with TRAVA:
                for ident, item in NAVEGADOR.items():
                    if item.get("entregue"):
                        continue
                    item["entregue"] = True      # so entrega uma vez
                    fora.append({"id": ident, "acao": item["acao"],
                                 "args": item["args"]})
            return fora

        pendentes = colher()
        if not pendentes:
            CHEGOU.clear()
            if CHEGOU.wait(25):
                pendentes = colher()
            EXTENSAO["vista"] = time.time()     # ficou vivo o tempo todo
        return {"acoes": pendentes}

    # ------------------------- login social --------------------------
    def _oauth(self, rota):
        partes = rota.strip("/").split("/")       # auth / provedor [/ retorno]
        provedor = partes[1] if len(partes) > 1 else ""

        if provedor == "apple":
            return self._ir_para("/login?erro=" + urllib.parse.quote(
                "Entrar com Apple exige dominio HTTPS publico e conta paga de "
                "desenvolvedor. Use e-mail e senha, Google ou GitHub."))

        if len(partes) == 2:                      # inicio: manda para o provedor
            destino = autenticacao.url_autorizacao(config(), provedor, self._base_url())
            if not destino:
                return self._ir_para("/login?erro=" + urllib.parse.quote(
                    "%s ainda nao esta configurado nos Ajustes." % provedor.title()))
            return self._ir_para(destino)

        # retorno do provedor
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        if q.get("error"):
            return self._ir_para("/login?erro=" + urllib.parse.quote("Login cancelado."))

        r = autenticacao.concluir_login(config(), provedor,
                                        (q.get("code") or [""])[0],
                                        (q.get("state") or [""])[0],
                                        self._base_url())
        if not r.get("ok"):
            return self._ir_para("/login?erro=" + urllib.parse.quote(r.get("erro", "")))

        token = autenticacao.abrir_sessao(r["email"], r["nome"], r.get("foto", ""))
        return self._ir_para("/", self._cookie_sessao(token))

    # ------------------------------ POST -----------------------------
    def do_POST(self):
        rota_post = self.path.split("?")[0]

        if rota_post in ("/api/login/entrar", "/api/login/criar"):
            tam = int(self.headers.get("Content-Length", 0))
            try:
                d = json.loads(self.rfile.read(tam).decode("utf-8") or "{}")
            except Exception:
                d = {}
            if rota_post.endswith("criar"):
                r = autenticacao.criar_conta(d.get("nome"), d.get("email"),
                                             d.get("senha"))
                if r.get("ok"):
                    r = autenticacao.conferir(d.get("email"), d.get("senha"))
            else:
                r = autenticacao.conferir(d.get("email"), d.get("senha"))

            if not r.get("ok"):
                return self._enviar(200, *self._json(r))
            token = autenticacao.abrir_sessao(r["email"], r["nome"], r.get("foto", ""))
            # O token vai TAMBEM no corpo: a extensao do Chrome nao consegue
            # ler o cookie (SameSite), entao guarda o token e manda no
            # cabecalho X-Cerebro-Sessao. Para o navegador comum nada muda --
            # ele continua usando o cookie e ignora este campo.
            tipo, corpo = self._json({"ok": True, "nome": r["nome"],
                                      "token": token})
            try:
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.send_header("Set-Cookie", self._cookie_sessao(token))
                self._cors()
                self.end_headers()
                self.wfile.write(corpo)
            except (ConnectionError, OSError):
                pass
            return

        if rota_post == "/api/sair":
            autenticacao.fechar_sessao(self.headers.get("Cookie"))
            return self._enviar(200, *self._json({"ok": True}))

        if not self._autorizado():
            return self._enviar(401, *self._json({"erro": "faca login"}))
        tamanho = int(self.headers.get("Content-Length", 0))

        if self.path.split("?")[0] == "/api/transcrever":
            audio = self.rfile.read(tamanho) if tamanho else b""
            return self._enviar(200, *self._json(voz.transcrever(audio)))

        bruto = self.rfile.read(tamanho).decode("utf-8") if tamanho else "{}"
        try:
            dados = json.loads(bruto or "{}")
        except Exception:
            dados = {}

        rota = self.path.split("?")[0]
        if rota == "/api/pesquisa/profunda":
            try:
                job = iniciar_pesquisa_profunda(dados.get("consulta", dados.get("prompt", "")))
                return self._enviar(202, *self._json(job))
            except Exception as erro:
                return self._enviar(400, *self._json({"ok": False, "erro": str(erro)}))

        if rota == "/api/chat":
            return self._chat(dados)
        if rota == "/api/tarefa":
            return self._enviar(200, *self._json(
                tarefa(dados.get("pergunta", ""), dados.get("contexto", ""))))
        if rota == "/api/imagens/job":
            try:
                import imagens
                args = dict(
                    descricao=dados.get("descricao", ""), formato=dados.get("formato", ""),
                    nome=dados.get("nome", ""), modelo=dados.get("modelo", ""),
                    negativo=dados.get("negativo", ""), passos=dados.get("passos", 4),
                    guidance=dados.get("guidance", 3.5), semente=dados.get("semente", 0),
                    pasta_saida=dados.get("pasta_saida", ""))
                job_id = runtime.start_image_job(lambda: imagens.gerar_imagem(**args))
                return self._enviar(202, *self._json({"ok": True, "job_id": job_id,
                                                       "estado": "fila"}))
            except Exception as erro:
                return self._enviar(500, *self._json({"ok": False, "erro": str(erro)}))

        if rota == "/api/imagens/gerar":
            # Caminho direto, sem passar pelo modelo de texto.
            #
            # Pedir "desenhe um cafe" no chat funciona e continua valendo --
            # mas ali o modelo precisa entender o pedido, escolher a
            # ferramenta e montar os argumentos, e um modelo de 4 GB erra
            # isso. Quando voce ja sabe o que quer, o caminho curto e mais
            # honesto: o que voce escreveu e o que vai para o desenhista.
            try:
                import imagens
            except Exception as erro:
                return self._enviar(200, *self._json(
                    {"ok": False, "erro": "modulo de desenho ausente: %s" % erro}))
            saida = imagens.gerar_imagem(
                descricao=dados.get("descricao", ""),
                formato=dados.get("formato", ""),
                nome=dados.get("nome", ""),
                modelo=dados.get("modelo", ""),
                negativo=dados.get("negativo", ""),
                passos=dados.get("passos", 4),
                guidance=dados.get("guidance", 3.5),
                semente=dados.get("semente", 0),
                pasta_saida=dados.get("pasta_saida", ""))
            # `gerar_imagem` devolve texto para o modelo ler. Aqui a tela
            # precisa saber se deu certo -- e o sinal e ter caminho de
            # arquivo no meio.
            deu_certo = ".png" in saida.lower()
            return self._enviar(200, *self._json(
                {"ok": deu_certo, "texto": saida}))

        if rota == "/api/ferramenta":
            return self._enviar(200, *self._json(
                executar_direto(dados.get("nome", ""), dados.get("args") or {})))
        if rota == "/api/autorizar":
            return self._autorizar(dados)
        if rota == "/api/conexoes":
            salvar_conexoes(dados)
            return self._enviar(200, *self._json({"ok": True}))
        if rota == "/api/dominios":
            return self._enviar(200, *self._json({
                "ok": True,
                "dominios": chroma_memoria.salvar_dominios(dados.get("dominios", dados))}))
        if rota == "/api/chroma/indexar":
            return self._enviar(200, *self._json(chroma_memoria.indexar_dominios()))
        if rota == "/api/config":
            return self._enviar(200, *self._json(salvar_config(dados)))
        if rota == "/api/conversas":
            return self._enviar(200, *self._json(armazenamento.salvar_conversa(dados)))
        if rota == "/api/conversa/renomear":
            return self._enviar(200, *self._json(armazenamento.renomear_conversa(
                dados.get("id"), dados.get("titulo"))))
        if rota == "/api/conversa/apagar":
            return self._enviar(200, *self._json(
                {"ok": armazenamento.apagar_conversa(dados.get("id"))}))
        if rota == "/api/especialistas":
            if dados.get("acao") == "apagar":
                return self._enviar(200, *self._json(
                    especialistas.apagar(dados.get("id", ""))))
            return self._enviar(200, *self._json(especialistas.salvar(dados)))
        if rota == "/api/programados":
            acao = dados.get("acao") or "salvar"
            if acao == "apagar":
                return self._enviar(200, *self._json(agenda.apagar(dados.get("id"))))
            if acao == "alternar":
                return self._enviar(200, *self._json(agenda.alternar(dados.get("id"))))
            if acao == "rodar":
                # Roda em segundo plano: a tarefa pode levar minutos e o
                # navegador nao pode ficar pendurado esperando.
                threading.Thread(
                    target=agenda.rodar,
                    args=(dados.get("id"), tarefa, modelo_online),
                    daemon=True).start()
                return self._enviar(200, *self._json(
                    {"ok": True, "rodando": True, "motor": modelo_online()}))
            return self._enviar(200, *self._json(agenda.salvar(dados)))
        if rota == "/api/projetos":
            return self._enviar(200, *self._json(armazenamento.salvar_projeto(dados)))
        if rota == "/api/projeto/apagar":
            return self._enviar(200, *self._json(
                {"ok": armazenamento.apagar_projeto(dados.get("id"))}))
        if rota == "/api/navegador":
            with TRAVA:
                item = NAVEGADOR.get(dados.get("id"))
                if item:
                    item["resultado"] = dados.get("resultado", "")
                    item["gatilho"].set()
            return self._enviar(200, *self._json({"ok": bool(item)}))
        if rota == "/api/habilidades":
            if dados.get("acao") == "criar":
                return self._enviar(200, *self._json(habilidades.criar(
                    dados.get("nome", ""), dados.get("quando", ""),
                    dados.get("conteudo", ""))))
            if dados.get("acao") == "apagar":
                return self._enviar(200, *self._json(
                    habilidades.apagar(dados.get("id", ""))))
            return self._enviar(200, *self._json(habilidades.salvar(
                dados.get("id", ""), dados.get("texto", ""))))
        if rota == "/api/login/senha":
            s = self._sessao() or {}
            return self._enviar(200, *self._json(autenticacao.trocar_senha(
                s.get("email"), dados.get("atual"), dados.get("nova"))))
        if rota == "/api/login/remover":
            return self._enviar(200, *self._json(
                autenticacao.remover(dados.get("email"))))
        if rota == "/api/personalidade":
            return self._enviar(200, *self._json(salvar_personalidade(dados)))
        if rota == "/api/modelo":
            return self._enviar(200, *self._json(trocar_modelo(dados.get("caminho", ""))))
        if rota == "/api/sincronizar":
            return self._sincronizar()
        if rota == "/api/memoria":
            arquivo = MEMORIA / (dados.get("arquivo") or "")
            if arquivo.parent == MEMORIA and arquivo.suffix == ".md":
                arquivo.write_text(dados.get("conteudo", ""), encoding="utf-8")
                return self._enviar(200, *self._json({"ok": True}))
            return self._enviar(400, *self._json({"erro": "arquivo invalido"}))
        return self._enviar(404, "text/plain", b"nao encontrado")

    # ------------------------------ chat -----------------------------
    def _chat(self, dados):
        """Rede de seguranca: qualquer defeito de programacao vira mensagem.

        24/08: uma variavel foi usada 111 linhas antes de existir. O Python
        levantou NameError, a thread morreu, e a tela mostrou... nada. Balao
        vazio, sem aviso, em 2 segundos. O `erros.log` tambem ficou mudo,
        porque o erro nem chegou perto de um try.

        Cinco perguntas do auditar_selo voltaram vazias e foram contadas como
        INVENCAO. O numero saiu 0 de 5 e quase me fez cortar o temperamento.md
        -- consertar a coisa errada, com base num numero errado, por causa de
        um erro que ficou invisivel.

        Falha silenciosa e o defeito mais caro que existe nesta base. Daqui
        para frente ela fala.
        """
        try:
            self._chat_interno(dados)
        except BaseException as erro:
            anotar_erro("falha dentro do chat", erro)
            try:
                self.wfile.write(("data: " + json.dumps(
                    {"tipo": "erro", "texto":
                     "Falha interna do Bigode: %s: %s\n\nO detalhe completo "
                     "esta em erros.log." % (type(erro).__name__, erro)},
                    ensure_ascii=False) + "\n\n").encode("utf-8"))
                self.wfile.write(b'data: {"tipo": "fim"}\n\n')
                self.wfile.flush()
            except Exception:
                pass
            raise

    def _chat_interno(self, dados):
        historico = dados.get("mensagens", [])
        pergunta = historico[-1]["content"] if historico else ""
        cfg = config()
        roteamento = roteador_semantico.classificar_consulta(pergunta)

        system, fontes = montar_system(pergunta, roteamento.get("colecao", "todas"))

        projeto = armazenamento.abrir_projeto(dados.get("projeto", "")) \
            if dados.get("projeto") else {}
        if projeto:
            system += ("\n\n# PROJETO ATIVO: %s\n\nDiretorio: %s\n\n%s"
                       % (projeto.get("nome", ""), projeto.get("diretorio", ""),
                          projeto.get("instrucoes", "")))

        # O especialista entra no FIM do system, depois do projeto. Nunca no
        # comeco: mudar o inicio do prompt obriga o motor a reler tudo e joga
        # o cache fora -- e o cache e o que evita pagar 3 minutos de leitura
        # em cada conversa nova.
        texto_esp, regras_esp = especialistas.montar(dados.get("especialista", ""))
        if texto_esp:
            system += texto_esp

        mensagens = [{"role": "system", "content": system}] + historico

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self._cors()
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        vivo = {"ok": True}

        def evento(obj):
            try:
                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False)
                                  + "\n\n").encode("utf-8"))
                self.wfile.flush()
                return True
            except Exception:
                vivo["ok"] = False      # aba fechada ou botao parar
                return False

        if fontes:
            evento({"tipo": "fontes", "fontes": fontes})

        # ═══ QUANTAS FERRAMENTAS ENTRAM NO PROMPT ═════════════════════════
        #
        # As 33 ferramentas ativas custam 2.739 tokens em TODA mensagem.
        # Filtrando pelo assunto da pergunta, caem para ~1.085. Sao 1.650
        # tokens a menos -- a 65 tokens/s de leitura, 25 SEGUNDOS por
        # mensagem.
        #
        # Por que estava desligado ate hoje: o esquema fica no inicio do
        # prompt, e mexer no inicio joga fora o cache do motor. O medo era
        # trocar 25 segundos economizados por 100 de reprocessamento.
        #
        # O que mudou em 24/08: o log do motor mostrou que o cache JA esta
        # sendo invalidado de qualquer jeito --
        #     "forcing full prompt re-processing due to lack of cache data
        #      (likely due to SWA or hybrid/recurrent memory)"
        # O Granite 4.0 h-tiny e um modelo hibrido (Mamba/SSM), e o proprio
        # llamafile aponta isso como causa. Se o cache ja nao pega, o motivo
        # de proteger o inicio do prompt caiu por terra, e sobram so os 25
        # segundos de ganho.
        #
        # Uma correcao junto: o filtro passou a olhar SO A PERGUNTA ATUAL.
        # Antes juntava 4.000 caracteres de historico -- que cresce a cada
        # mensagem, mudando o catalogo toda vez e garantindo que o cache
        # nunca pegasse. Com a pergunta atual, o catalogo fica estavel
        # enquanto o assunto for o mesmo, que e exatamente quando o cache
        # tem chance de servir para alguma coisa.
        # O NAVEGADOR GRUDA NA CONVERSA
        #
        # 24/08: depois de ler o Google e listar tudo o que dava para clicar,
        # o Fred escreveu "na barra de busca, escreva Cannabis". O Bigode
        # respondeu "Aguarde... abrindo a pagina de pesquisa" e NAO FEZ NADA.
        #
        # A frase tem verbo de acao mas nao repete onde -- porque nao
        # precisa: os dois estavam olhando a mesma pagina. Ninguem diz "na
        # barra de busca DA PAGINA QUE VOCE ACABOU DE LER". Uma vez que a
        # conversa entrou numa pagina, ela continua nela ate mudar de
        # assunto, e o verbo sozinho ja basta.
        #
        # Isto e decidido AQUI, antes do catalogo, e nao la embaixo na hora
        # de ler a tela. Motivo: se a frase nao tem palavra de navegador, o
        # filtro tiraria navegador_escrever do catalogo -- e o Bigode leria
        # a pagina para depois descobrir que nao tem como escrever nela.
        # As ultimas perguntas do Fred nesta conversa. Definida AQUI, e nao la
        # embaixo onde e usada de novo, porque o bloco abaixo precisa dela --
        # e usar antes de definir foi exatamente o defeito de 24/08: a thread
        # morria com NameError e a resposta chegava VAZIA em 2 segundos, sem
        # nenhuma mensagem de erro na tela. Segunda vez que cometo este erro
        # nesta base; a licao e conferir a ORDEM, nao so a sintaxe.
        recentes = [m.get("content", "") for m in historico[-6:]
                    if m.get("role") == "user"]

        no_navegador = any(pergunta_sobre_a_tela(t)
                           or pedido_de_acao_no_navegador(t) for t in recentes)
        quer_navegador = (pergunta_sobre_a_tela(pergunta)
                          or pedido_de_acao_no_navegador(pergunta)
                          or (no_navegador and _verbo_de_acao(pergunta)))

        # ═══ DESLIGADO EM 25/08, DEPOIS DE MEDIR ══════════════════════════
        #
        # Ontem liguei o filtro por assunto para economizar 1.650 tokens
        # (~25s) na primeira mensagem. O log de hoje mostrou o preco:
        #
        #     task 299: checkpoint [6237] contra 2325 -> reprocessa tudo   99,9s
        #     task 887: reprocessa tudo                                   144,1s
        #     task 889: checkpoint [4958] contra 2325 -> reprocessa tudo  221,9s
        #
        # Sempre "contra 2325": o prefixo comum morre nos 2.325 tokens, que
        # e onde o catalogo comeca. Como o catalogo MUDA a cada pergunta, o
        # motor nao reaproveita nada -- e paga o prompt inteiro toda vez.
        #
        # Com o catalogo FIXO, medido ontem na mesma maquina:
        #     1a 93,2s   2a 1,6s   3a 19,3s   4a 2,6s   5a 8,9s
        #
        # A conta: economizar 25 segundos na primeira custa 90 a 200 em
        # CADA uma das seguintes. Nao compensa nem de longe.
        #
        # A licao, que ja aparece tres vezes neste arquivo: o que decide
        # aqui nao e o tamanho do prompt, e a ESTABILIDADE do comeco dele.
        # Quem quiser encolher o catalogo, desligue conexoes na barra --
        # isso muda o catalogo uma vez, nao a cada frase.
        #
        # Para reativar (e refazer a medicao antes de acreditar):
        #     "ferramentas_dinamicas": true   no config.json
        if cfg.get("ferramentas_dinamicas", False):
            esquema = ferramentas.esquema_openai(ferramentas.para_pergunta(
                pergunta, garantir=("navegador",) if quer_navegador else ()))
        else:
            esquema = ferramentas.esquema_openai()

        # ── Narrar as etapas internas ────────────────────────────────────
        # Antes, enquanto o modelo pensava, a tela mostrava só "Pensando" e
        # nao dava para saber se algo estava acontecendo. Agora cada etapa do
        # preparo vira uma linha, entao ha movimento desde o primeiro segundo
        # e fica claro COM O QUE ele esta trabalhando.
        # ═══ CONVERSA CURTA NAO TEM PREPARO ══════════════════════════════
        #
        # "oi" nao precisa de "Entendi o que voce precisa", "Escolhendo o
        # melhor jeito de ajudar" e "Recursos prontos para ajudar". Quatro
        # etapas de preparo antes de um "ola" fazem a ferramenta parecer
        # burocratica -- e foi exatamente a queixa: falta de fluidez.
        #
        # Uma pessoa nao anuncia que vai pensar antes de dizer bom dia.
        #
        # O preparo continua aparecendo quando ha trabalho de verdade: ler
        # arquivo, pesquisar, mexer em projeto. Ai ele informa, porque ai
        # voce quer saber o que esta acontecendo.
        # `precisa_conferir` so e calculado mais abaixo, entao aqui usamos
        # os gatilhos direto. Testado: usar a variavel antes da hora
        # derrubava a PRIMEIRA mensagem de toda conversa.
        curta = (len((pergunta or "").split()) <= 6
                 and not precisa_fonte(pergunta)
                 and not precisa_agir(pergunta)
                 and not projeto)

        if not curta:
            evento({"tipo": "acao", "id": "prep", "estado": "ok",
                    "titulo": "Entendi o que você precisa",
                    "resumo": "Vou cuidar disso com você."})

        if projeto:
            evento({"tipo": "acao", "id": "prep-proj", "estado": "ok",
                    "titulo": "Vou trabalhar no projeto %s" % projeto.get("nome", ""),
                    "resumo": "Estou usando os arquivos deste projeto como referência."})

        if not curta:
            evento({"tipo": "acao", "id": "prep-rota", "estado": "ok",
                    "titulo": "Escolhendo o melhor jeito de ajudar",
                    "resumo": "Vou usar o contexto mais útil para este pedido."})

        if fontes:
            evento({"tipo": "acao", "id": "prep-mem", "estado": "ok",
                    "titulo": "Recuperei informações salvas",
                    "resumo": "Vou aproveitar o que já construímos juntos."})

        ligadas = [c.get("nome") for c in conexoes_publicas().values()
                   if isinstance(c, dict) and c.get("ativa")]
        if not curta:
            evento({"tipo": "acao", "id": "prep-fer", "estado": "ok",
                    "titulo": "Recursos prontos para ajudar",
                    "resumo": "Arquivos, internet, navegador e projetos ficam "
                              "disponíveis quando fizer sentido."})

        evento({"tipo": "acao", "id": "pensar", "estado": "rodando",
                "titulo": "Pensando na melhor resposta",
                "resumo": ""})

        # Cronometro do pedido inteiro. Ver a classe Medidor para o porque.
        medidor = Medidor(pergunta=pergunta,
                          modelo=(PROVEDOR.atual() or {}).get("nome", ""),
                          projeto=projeto.get("nome", "") if projeto else "")

        # Consultas curtas e inequívocas não precisam de uma rodada do modelo.
        # Se o usuário já escreveu “pesquise sobre cannabis”, usa exatamente esse
        # termo na web_buscar; não pede palavras-chave nem deixa o modelo fabricar
        # uma resposta de preenchimento. Pedidos que envolvem o navegador continuam
        # no fluxo normal, pois exigem aprovação e a extensão ativa.
        consulta_direta = consulta_web_direta(pergunta)
        pedido_browser = any(t in (pergunta or "").lower()
                             for t in ("navegador", "chrome", "aba", "clique"))
        if consulta_direta and not pedido_browser and "web_buscar" in ferramentas.ativas():
            evento({"tipo": "acao", "id": "pesquisa-direta", "estado": "rodando",
                    "titulo": "Pesquisando na web",
                    "resumo": consulta_direta[:100]})
            inicio_busca = time.time()
            resultado_direto = ferramentas.executar(
                "web_buscar", {"consulta": consulta_direta})
            medidor.anotar_ferramenta(
                "web_buscar", time.time() - inicio_busca,
                {"consulta": consulta_direta})
            texto_direto = limpar_resposta(resultado_direto)
            evento({"tipo": "acao", "id": "pesquisa-direta", "estado": "ok",
                    "titulo": "Encontrei as primeiras fontes",
                    "resumo": consulta_direta[:100]})
            evento({"tipo": "texto", "texto": texto_direto})
            evento({"tipo": "verificado", "arquivos_lidos": [],
                    "arquivos_escritos": [], "comandos": [],
                    "fontes_web": medidor.fontes_web[:8]})
            medidor.gravar(True)
            evento({"tipo": "medicao", **medidor.resumo(True)})
            evento({"tipo": "fim"})
            return

        # ═══ O ASSUNTO GRUDA NA CONVERSA ═════════════════════════════════
        # "axl ou axel?" e "veja o nome correto" nao acionam gatilho nenhum
        # sozinhas -- sao curtas demais. Mas sao continuacao de uma pergunta
        # que EXIGIA fonte, e por isso mereciam a mesma exigencia. Sem isto o
        # selo aparecia numa mensagem e sumia na seguinte, sobre o mesmo
        # assunto: e o jeito mais rapido de ensinar alguem a ignorar o selo.
        # `recentes` ja foi montada la em cima, junto com quer_navegador.
        quer_fonte_agora = any(precisa_fonte(t) for t in recentes)
        quer_arquivo_agora = any(precisa_agir(t) for t in recentes)
        if regras_esp:
            if especialistas.exige_fonte(regras_esp):
                quer_fonte_agora = True
            elif especialistas.exige_arquivo(regras_esp):
                quer_arquivo_agora = True
            elif regras_esp.get("rigor") == "livre":
                quer_fonte_agora = quer_arquivo_agora = False
        precisa_conferir = quer_fonte_agora or quer_arquivo_agora

        plano_aprovado = False
        lidos, texto = [], ""     # o que ele realmente abriu, e a resposta final
        # obrigar: proxima chamada so pode sair com ferramenta (tool_choice
        # required). usou_ferramenta: se ja tocou nos dados de verdade nesta
        # pergunta, pode voltar a responder livremente.
        obrigar, usou_ferramenta = False, False

        # ═══ OLHAR A TELA ANTES DE PENSAR ═════════════════════════════════
        # 24/08, tres vezes seguidas, com a extensao LIGADA e a ferramenta
        # navegador_ver DENTRO do catalogo que ele recebeu:
        #
        #     Fred: "quero saber o que tem na tela do meu navegador agora"
        #     Bigode: "como uma inteligencia artificial sem acesso direto ao
        #              seu computador, nao posso ver a tela do seu navegador"
        #
        # Ele tinha a ferramenta e escolheu nao usar. Instrucao no prompt nao
        # resolve isso: "sou uma IA e nao vejo sua tela" e das frases mais
        # ensaiadas que existem num modelo de linguagem, e ela ganha da nossa
        # instrucao toda vez.
        #
        # Entao paramos de pedir. Quando a pergunta e sobre a tela/aba/pagina
        # aberta AGORA, a gente le a pagina antes de falar com o modelo e
        # entrega o conteudo junto. Ele nao decide mais se olha: ja olhou.
        # E o mesmo caminho que o Claude in Chrome usa -- o conteudo da aba
        # chega como contexto, nao como escolha do modelo.
        if (ferramentas.ligada_navegador() and extensao_conhecida()
                and quer_navegador):
            evento({"tipo": "acao", "id": "olhar", "estado": "rodando",
                    "titulo": "Olhando a sua tela", "detalhe": ""})
            # 60s: o service worker pode estar dormindo e levar ate 30s para
            # acordar pelo alarme, mais o tempo de ler a pagina.
            pagina = pedir_ao_navegador("navegador_ver", {}, evento, espera=60)

            # Mostrar QUAL pagina foi lida, na narracao.
            #
            # 25/08: a aba na frente era a tela do proprio Bigode. Ele leu a
            # propria conversa, achou ali a frase "Como IA, nao posso acessar
            # seu navegador" -- escrita por ele mesmo minutos antes -- e a
            # devolveu como se fosse conteudo de site. A extensao ja foi
            # corrigida para pular a propria aba; esta linha e a segunda
            # rede: com o endereco na tela, um eco desses fica obvio na hora.
            de_onde = ""
            for linha in (pagina or "").splitlines()[:3]:
                if linha.startswith("PÁGINA:"):
                    de_onde = linha.split(":", 1)[1].strip()[:70]
                elif linha.startswith("ENDEREÇO:") and not de_onde:
                    de_onde = linha.split(":", 1)[1].strip()[:70]

            evento({"tipo": "acao", "id": "olhar", "estado": "ok",
                    "titulo": "Olhei a sua tela", "detalhe": de_onde,
                    "conteudo": (pagina or "")[:3000]})
            # A instrucao no fim nao e enfeite.
            #
            # 26/08, teste "aperte Enter": eu ja tinha lido a pagina e
            # entregado a ele. Mesmo assim ele chamou navegador_ver DE NOVO
            # -- mais 90 segundos de espera para receber o que ja estava na
            # mao -- e depois respondeu em texto, sem nunca teclar nada.
            #
            # Modelo pequeno nao infere "ja tenho isso". Tem que ser dito.
            mensagens.append({"role": "user", "content":
                              "RESULTADO de navegador_ver (a pagina que o Fred "
                              "esta vendo NESTE MOMENTO):\n" + (pagina or "")[:3500]
                              + "\n\n[Voce JA TEM a pagina acima, com os numeros "
                                "de cada elemento. NAO chame navegador_ver de "
                                "novo. Se o pedido do Fred e uma acao, execute-a "
                                "agora: navegador_clicar, navegador_escrever ou "
                                "navegador_teclar, usando os numeros da lista.]"})
            usou_ferramenta = True
            lidos.append("a página aberta no Chrome")
            evento({"tipo": "novo_bloco"})

            # Se o pedido era para AGIR, a proxima fala dele tem que ser uma
            # ferramenta, nao uma frase. Ele ja respondeu "Aguarde... abrindo
            # a pagina de pesquisa" sem abrir nada -- narrar uma acao no
            # lugar de executa-la e o pior desfecho possivel aqui, porque
            # parece que funcionou.
            if _verbo_de_acao(pergunta):
                obrigar = True

            # E TIRAMOS navegador_ver DA MESA.
            #
            # A instrucao acima ("nao chame de novo") e do mesmo tipo que ja
            # falhou duas vezes nesta base: pedir para o modelo nao fazer
            # algo nao funciona. O que funciona e nao deixar.
            #
            # A pagina ja foi lida e entregue. Sem navegador_ver no catalogo,
            # a unica coisa que ele pode fazer com o navegador e AGIR --
            # clicar, escrever ou teclar. Que e o que foi pedido.
            #
            # So tiramos quando a leitura deu certo. Se falhou, ele fica com
            # a ferramenta e pode tentar de novo por conta propria.
            leu_de_verdade = bool(pagina) and "PÁGINA:" in (pagina or "")
            if leu_de_verdade:
                esquema = [f for f in esquema
                           if f.get("function", {}).get("name") != "navegador_ver"]

        # ═══ GUARDA CONTRA LACO ═══════════════════════════════════════════
        # Medido em 19/08: tres perguntas levaram ~100 MINUTOS cada. Nao era
        # lentidao -- era o modelo pedindo a MESMA ferramenta com os MESMOS
        # parametros, sem parar, ate o limite de passos acabar.
        #
        # Um limite de passos sozinho nao resolve: ele so encurta o desastre.
        # O que resolve e perceber a repeticao e interromper com uma
        # instrucao clara. Guardamos a assinatura de cada chamada
        # (nome + parametros) para comparar.
        assinaturas = []
        travou = ""
        for passo in range(int(cfg["max_passos"])):
            if not vivo["ok"]:
                break
            estado = {"enviado": 0}

            # ═══ SEGURAR O TEXTO QUE AINDA PODE SER DESCARTADO ════════════
            #
            # 09/09: o Fred perguntou quem foi Nelson Mandela e recebeu a
            # MESMA resposta duas vezes, quase palavra por palavra.
            #
            # O que acontecia: a pergunta exige fonte, ele responde de
            # cabeca, o texto SAI INTEIRO na tela enquanto e escrito, e so
            # ENTAO a trava percebe que nao houve consulta e manda descartar.
            # Resultado: o Fred lia uma resposta, ela sumia (ou nao sumia,
            # por causa do bug da tela), e vinha outra parecida.
            #
            # Mostrar texto que pode ser apagado e pior que demorar mais um
            # pouco. Enquanto a resposta estiver sujeita a descarte, ela fica
            # retida aqui; se sobreviver, sai de uma vez.
            segurar = (precisa_conferir and not usou_ferramenta
                       and passo < int(cfg["max_passos"]) - 1)

            def ao_receber(acumulado):
                if not vivo["ok"]:
                    raise Cancelado()
                if segurar:
                    return          # acumula sem mostrar; pode ser descartado
                # `<tool_call>` entrou junto de `<ferramenta>` em 09/09: o
                # motor da nuvem escreve a chamada nesse formato, e ela
                # apareceu CRUA na tela do Fred. O que o modelo fala para as
                # ferramentas nao e conversa -- nao vai para a tela.
                visivel = (acumulado.split("<ferramenta>")[0]
                                    .split("<tool_call>")[0]
                                    .split("```json")[0])
                filtrado = limpar_resposta(visivel)

                # ═══ FREIO DE REPETICAO NO TEXTO ═══════════════════════════
                #
                # 26/08: o Fred pediu "aperte Enter". O modelo comecou a
                # responder e nao parou mais -- 941 tokens de:
                #
                #     "Resposta final: ... Nota de encerramento: ...
                #      Fim da resposta: ... Resposta final (simplificada): ...
                #      Atencao ao usuario: ... Resposta final (conclusao): ..."
                #
                # oito vezes a mesma coisa com outras palavras, ate ele
                # apertar o botao de parar. Dois minutos jogados fora.
                #
                # A guarda de laco que ja existe olha CHAMADAS DE FERRAMENTA
                # repetidas. Esta olha o TEXTO: modelo pequeno entra em ciclo
                # de encerramento e nao acha a saida sozinho. Quem tem que
                # cortar e o programa.
                #
                # Regra: uma frase de conteudo (>=25 caracteres) que aparece
                # tres vezes no mesmo texto e ciclo, nao enfase.
                if len(filtrado) - estado.get("visto_em", 0) > 400:
                    estado["visto_em"] = len(filtrado)
                    frases = [f.strip().lower() for f in
                              re.split(r"[.\n!?]+", filtrado) if len(f.strip()) >= 25]
                    if frases:
                        from collections import Counter
                        repetida, quantas = Counter(frases).most_common(1)[0]
                        if quantas >= 3:
                            anotar_erro("texto em laco: %r repetida %dx"
                                        % (repetida[:60], quantas))
                            estado["em_laco"] = True
                            raise Cancelado()

                novo = filtrado[estado["enviado"]:]
                if novo:
                    estado["enviado"] = len(filtrado)
                    evento({"tipo": "texto", "texto": novo})

            obra = {"arquivo": None, "enviado": 0}

            def ao_ferramenta(nome_f, args_parciais):
                """Mostra o codigo aparecendo enquanto o modelo escreve o arquivo."""
                if nome_f != "escrever_arquivo":
                    return
                if obra["arquivo"] is None:
                    caminho = _extrair_parcial(args_parciais, "caminho")
                    if caminho:
                        obra["arquivo"] = caminho
                        evento({"tipo": "codigo", "arquivo": caminho,
                                "nome": _final(caminho), "estado": "escrevendo"})
                corpo = _extrair_parcial(args_parciais, "conteudo")
                if corpo and len(corpo) - obra["enviado"] > 60:
                    evento({"tipo": "codigo", "arquivo": obra["arquivo"],
                            "trecho": corpo[obra["enviado"]:], "estado": "escrevendo"})
                    obra["enviado"] = len(corpo)

            if passo > 0:
                evento({"tipo": "acao", "id": "pensar%d" % passo, "estado": "rodando",
                        "titulo": "Pensando no próximo passo"})

            try:
                medidor.passos = passo + 1
                resposta, nativa = chamar_modelo(
                    caber_no_contexto(mensagens, cfg, esquema),
                    ao_receber, ao_ferramenta=ao_ferramenta, esquema=esquema,
                    obrigar_ferramenta=obrigar, medidor=medidor)
                evento({"tipo": "acao",
                        "id": "pensar%d" % passo if passo else "pensar",
                        "estado": "ok",
                        "titulo": "Decidi o que fazer" if passo == 0
                                  else "Decidi o próximo passo"})
            except Cancelado:
                # Cancelado por laco de texto: o Fred merece saber por que a
                # resposta parou no meio, senao parece que travou de novo.
                if estado.get("em_laco"):
                    aviso = ("\n\n*Parei aqui: a resposta entrou em repetição. "
                             "O modelo estava reescrevendo a mesma conclusão "
                             "sem terminar. Se faltou algo, me peça de novo em "
                             "uma frase mais direta.*")
                    texto = (texto or "") + aviso
                    evento({"tipo": "texto", "texto": aviso})
                break
            except Exception as erro:
                texto = str(erro)
                if "10054" in texto or "10061" in texto or isinstance(erro, urllib.error.URLError):
                    if not modelo_online():
                        texto = ("O motor ainda esta carregando o modelo. "
                                 "Acompanhe a janela 'Motor Bigode': quando aparecer "
                                 "'server is listening', mande de novo.")
                    else:
                        texto = ("O motor derrubou a conexao. Se acabou de trocar de modelo, "
                                 "espere ele terminar de carregar e tente outra vez.")
                else:
                    texto = "Falha: " + texto
                medidor.anotar_erro(texto)
                evento({"tipo": "erro", "texto": texto})
                break

            nome, args = nativa if nativa else extrair_chamada(resposta)

            # A pergunta pede dado real, o modelo respondeu de cabeca e ainda nao
            # tocou em nada. Descartamos essa resposta: ela seria invencao. Na
            # volta, tool_choice=required nao deixa ele escapar.
            #
            # Antes isto so valia para pergunta sobre ARQUIVO. Pergunta sobre o
            # mundo passava direto -- e foi assim que ele afirmou que o Axl Rose
            # se chama "Axel", nasceu em 1969, e substituiu um baterista que nao
            # existe. Pior: quando mandaram pesquisar, ele respondeu que "nao tem
            # acesso a internet", tendo web_buscar na mao. Modelo pequeno repete
            # o que aprendeu sobre si mesmo em vez de olhar as ferramentas.
            if not nome and not usou_ferramenta and precisa_conferir \
                    and passo < int(cfg["max_passos"]) - 1:
                evento({"tipo": "acao", "id": "check%d" % passo, "estado": "rodando",
                        "titulo": ("Pesquisando antes de responder" if quer_fonte_agora
                                   else "Conferindo nos arquivos de verdade")})
                if not obrigar:
                    mensagens.append({"role": "assistant", "content": resposta or "..."})
                    if quer_fonte_agora:
                        mensagens.append({"role": "user", "content":
                            "PARE. Voce tentou responder sem chamar ferramentas. "
                            "Chame imediatamente a ferramenta web_buscar ou buscar_no_chroma "
                            "usando o termo principal da pergunta do usuario, sem pedir palavras-chave."})
                    else:
                        mensagens.append({"role": "user", "content":
                            "Voce respondeu sem abrir nada. FACA a chamada da ferramenta "
                            "necessaria imediatamente, sem pedir palavras-chave."})
                obrigar = True
                # limpa da tela o texto inventado que ja tinha comecado a sair
                evento({"tipo": "descartar"})
                evento({"tipo": "acao", "id": "check%d" % passo, "estado": "ok",
                        "titulo": "Abrindo os arquivos"})
                continue

            if not nome:
                texto = limpar_resposta(resposta or "")  # resposta final conferida
                # Se o texto estava retido esperando o veredito e chegou ate
                # aqui, e porque sobreviveu: sai agora, de uma vez so.
                if segurar and texto:
                    evento({"tipo": "texto", "texto": texto})
                break

            # ---------- ele esta repetindo a mesma coisa? ----------
            assinatura = json.dumps([nome, args], sort_keys=True,
                                    ensure_ascii=False)[:600]
            repeticoes = assinaturas.count(assinatura)
            assinaturas.append(assinatura)

            if repeticoes >= 2:
                # Terceira vez identica. Avisar de novo seria participar do
                # laco. Encerra e conta o que aconteceu -- silencio aqui
                # vira uma espera de uma hora sem explicacao.
                travou = ("Fiquei repetindo a mesma ação (%s) e não saí do "
                          "lugar. Parei por aqui em vez de continuar tentando. "
                          "Tente reformular o pedido, ou peça um passo de cada "
                          "vez." % narrar(nome, args))
                evento({"tipo": "acao", "id": "laco", "estado": "erro",
                        "titulo": "Parei: estava repetindo a mesma ação",
                        "detalhe": resumir(nome, args)})
                break

            if repeticoes == 1:
                # Segunda vez identica: ainda da para salvar. Nao executa de
                # novo -- manda ele mudar de rumo.
                evento({"tipo": "acao", "id": "laco%d" % passo, "estado": "rodando",
                        "titulo": "Já tentei isso — mudando de caminho"})
                mensagens.append({"role": "assistant", "content": resposta or "..."})
                mensagens.append({"role": "user", "content":
                    "PARE. Voce ja chamou %s com exatamente esses parametros e o "
                    "resultado nao mudou. Repetir nao vai adiantar. Escolha UMA "
                    "coisa: (a) tente outro caminho, com outros parametros; "
                    "(b) responda com o que ja sabe; ou (c) diga que nao "
                    "conseguiu e o que falta. Nao chame a mesma ferramenta de "
                    "novo." % nome})
                obrigar = False
                continue

            usou_ferramenta = True
            obrigar = False
            mensagens.append({"role": "assistant", "content": resposta})

            # ---------- plano: mostra, espera o "pode fazer" ----------
            if nome == "apresentar_plano":
                passos = [p.strip(" -•\t") for p in
                          str(args.get("passos", "")).splitlines() if p.strip()]
                pedido_id = uuid.uuid4().hex[:10]
                gatilho = threading.Event()
                with TRAVA:
                    PENDENTES[pedido_id] = {"gatilho": gatilho, "ok": False}

                evento({"tipo": "plano", "id": pedido_id,
                        "objetivo": str(args.get("objetivo", "")).strip(),
                        "passos": passos})
                _espera = time.time()
                gatilho.wait(1800)
                medidor.anotar_autorizacao(time.time() - _espera)
                with TRAVA:
                    aprovado = PENDENTES.pop(pedido_id, {}).get("ok", False)

                if aprovado:
                    plano_aprovado = True
                    mensagens.append({"role": "user", "content":
                        "PLANO APROVADO pelo Fred. Execute agora, passo a passo, "
                        "chamando as ferramentas necessarias. Nao peca autorizacao "
                        "de novo. Ao terminar, resuma o que foi feito."})
                else:
                    mensagens.append({"role": "user", "content":
                        "O Fred NAO aprovou o plano. Pare, nao altere nada, e "
                        "pergunte a ele o que deve mudar."})
                evento({"tipo": "novo_bloco"})
                continue

            if (ferramentas.exige_autorizacao(nome) and not plano_aprovado
                    and cfg["nivel_autorizacao"] != "nunca"):
                pedido_id = uuid.uuid4().hex[:10]
                gatilho = threading.Event()
                with TRAVA:
                    PENDENTES[pedido_id] = {"gatilho": gatilho, "ok": False}
                evento({"tipo": "autorizacao", "id": pedido_id,
                        "acao": narrar(nome, args), "titulo": "Posso continuar?",
                        "nome": nome, "args": args})
                _espera = time.time()
                gatilho.wait(600)
                # A espera humana nao pode ser confundida com lentidao do
                # modelo. Sem separar, o sistema "parece" lento quando na
                # verdade estava esperando voce clicar.
                medidor.anotar_autorizacao(time.time() - _espera)
                with TRAVA:
                    aprovado = PENDENTES.pop(pedido_id, {}).get("ok", False)
                if not aprovado:
                    evento({"tipo": "recusado", "id": pedido_id})
                    mensagens.append({"role": "user", "content":
                                      "RESULTADO: o Fred recusou essa acao. "
                                      "Nao insista, siga por outro caminho ou pergunte a ele."})
                    continue

            chave = resumir(nome, args)
            extra = contexto_acao(nome, args)
            evento({"tipo": "acao", "id": chave, "estado": "rodando",
                    "titulo": narrar(nome, args), "detalhe": chave, **extra})

            comeco = time.time()
            if nome.startswith("navegador_"):
                resultado = pedir_ao_navegador(nome, args, evento)
            else:
                resultado = ferramentas.executar(nome, args)
            duracao = round(time.time() - comeco, 1)
            medidor.anotar_ferramenta(nome, time.time() - comeco, args)

            if nome in ("escrever_arquivo", "criar_projeto"):
                caminho = args.get("caminho") or args.get("nome") or ""
                evento({"tipo": "codigo", "arquivo": str(caminho),
                        "nome": _final(caminho), "estado": "pronto",
                        "linhas": len(str(args.get("conteudo", "")).splitlines()),
                        "projeto": nome == "criar_projeto"})

            linhas = [l for l in (resultado or "").strip().splitlines() if l.strip()]
            evento({"tipo": "acao", "id": chave, "estado": "ok",
                    "titulo": narrar(nome, args, True), "detalhe": chave,
                    "resumo": linhas[-1][:110] if linhas else "concluído",
                    "segundos": duracao,
                    "conteudo": "\n".join(linhas[:60])[:3000], **extra})

            if nome in ("ler_arquivo", "raio_x", "listar_pasta", "usar_habilidade"):
                lidos.append(str(args.get("caminho") or args.get("nome") or ""))

            # ═══ ENCERRAR SEM CHAMAR O MODELO DE NOVO ══════════════════════
            #
            # A ação foi de um passo só e deu certo? Então o trabalho acabou.
            # Mandar o modelo ler o resultado para escrever "pronto" custa
            # de 75 a 230 segundos e não acrescenta nada -- a ferramenta já
            # devolveu a frase certa, com o detalhe certo.
            #
            # Só encerramos quando o pedido do Fred era ESTA ação e nada
            # mais. Se ele pediu duas coisas ("escreva e clique"), o laço
            # continua para a segunda.
            fecha, frase = conferir_sem_o_modelo(nome, args, resultado)
            if fecha and passo + 1 >= _quantas_acoes_pedidas(pergunta):
                texto = frase
                usou_ferramenta = True
                # Esta frase e a MAIS confiavel que o Bigode produz: veio da
                # ferramenta que executou a acao, nao de um modelo resumindo
                # o que aconteceu. Entra como evidencia real -- e o unico
                # caso em que a resposta nao passou por nenhum modelo.
                lidos.append(narrar(nome, args, True))
                evento({"tipo": "texto", "texto": frase})
                evento({"tipo": "medicao",
                        "texto": "resposta fechada sem consultar o modelo"})
                break

            mensagens.append({"role": "user",
                              "content": "RESULTADO:\n" + resultado[:3500]})
            evento({"tipo": "novo_bloco"})

        # Laco interrompido, ou passos esgotados sem resposta final: em
        # ambos os casos e melhor dizer o que houve do que devolver vazio.
        if travou:
            texto = travou
            evento({"tipo": "texto", "texto": "\n\n" + travou})
        elif not texto and usou_ferramenta and vivo["ok"]:
            texto = ("Cheguei ao limite de %d passos sem conseguir fechar uma "
                     "resposta. O que consegui abrir está acima. Tente pedir "
                     "um passo de cada vez." % int(cfg["max_passos"]))
            evento({"tipo": "texto", "texto": "\n\n" + texto})

        # ═══ TRAVA DE EVIDENCIA ═══════════════════════════════════════════
        #
        # A regra: **afirmacao sobre o seu projeto exige evidencia de
        # ferramenta.** Se o agente fala de arquivo, pasta ou codigo sem ter
        # aberto nada, a resposta nao e um fato — e um palpite bem escrito.
        #
        # Antes isto era so um aviso amarelo para o caso especifico de bloco
        # de codigo. Agora o proprio backend classifica a resposta, e a tela
        # mostra `nao verificado` de forma inequivoca.
        #
        # Por que no backend e nao no prompt: as seis travas anteriores todas
        # dependiam de o modelo se comportar. Esta nao depende — ela olha o
        # que ele REALMENTE fez, registrado pelo medidor.
        # ═══ PORTAO DE EVIDENCIA ══════════════════════════════════════════
        # Duas perguntas diferentes, dois tipos de prova:
        #
        #   sobre os SEUS arquivos  -> vale ter aberto arquivo/rodado comando
        #   sobre o MUNDO           -> so vale fonte externa; a memoria do
        #                              modelo nao conta, por mais convincente
        #                              que o texto pareca
        #
        # A segunda faltava, e era por onde passava o pior tipo de invencao:
        # data errada, lei que nao existe, numero inventado.

        # Usa a MESMA decisao tomada la em cima, ja com o assunto grudado na
        # conversa e o rigor do especialista aplicado. Recalcular aqui so pela
        # ultima pergunta faria o selo aparecer numa mensagem e sumir na
        # seguinte, sobre o mesmo assunto.
        verificado = None
        quer_arquivo = quer_arquivo_agora
        quer_fonte = quer_fonte_agora

        # A REDE DE SEGURANCA: se nenhum gatilho disparou, mas a resposta e
        # longa e ele nao abriu nada, carimba assim mesmo. Foi a falta disto
        # que deixou passar a invencao sobre Corisco, Lampiao e Piquet em
        # 09/09 -- tres respostas longas, confiantes, 100% falsas e sem um
        # unico aviso na tela.
        if (not quer_arquivo and not quer_fonte
                and not medidor.tem_evidencia
                and merece_carimbo(pergunta, texto)):
            quer_fonte = True

        if texto and (quer_arquivo or quer_fonte):
            # `quer_arquivo` primeiro. Quando a pergunta cita um caminho, ler
            # o arquivo E a fonte -- exigir web ali carimbava resposta certa.
            # (Mesmo conserto aplicado em `tarefa`; ver o comentario longo la.)
            if quer_arquivo:
                basta = medidor.tem_evidencia
            elif quer_fonte:
                basta = medidor.tem_fonte_externa
            else:
                basta = medidor.tem_evidencia
            if basta:
                verificado = True
            else:
                verificado = False
                if quer_fonte and not quer_arquivo:
                    motivo = ("Isto afirma coisas sobre o mundo — datas, leis, "
                              "números, fatos — e ele não consultou nenhuma "
                              "fonte. Escreveu de memória.")
                    conserto = ("Peça: “pesquise na internet e me diga a fonte "
                                "de cada afirmação”.")
                else:
                    motivo = ("Ele respondeu sem abrir nenhum arquivo, sem rodar "
                              "comando e sem listar pasta.")
                    conserto = ("Para conferir, peça: “leia o arquivo e me mostre "
                                "o que está lá de verdade”.")
                if "```" in texto:
                    motivo += (" O código acima foi escrito de memória, não veio "
                               "de arquivo lido.")
                evento({"tipo": "nao_verificado",
                        "texto": motivo + " Trate como rascunho, não como fato. "
                                 + conserto,
                        "evidencias": {"arquivos_lidos": [],
                                       "arquivos_escritos": [],
                                       "comandos": []}})

        # Quando HA evidencia, mostrar qual — a pessoa precisa poder conferir
        # a fonte da resposta, nao so confiar nela.
        if verificado:
            evento({"tipo": "verificado",
                    "arquivos_lidos": medidor.arquivos_lidos[:12],
                    "arquivos_escritos": medidor.arquivos_escritos[:12],
                    "comandos": medidor.comandos[:6],
                    "fontes_web": medidor.fontes_web[:8]})

        # ═══ CRONOMETRO ═══════════════════════════════════════════════════
        # Vai para a tela e para memoria/medicoes.jsonl. E o que permite
        # comparar dois modelos com o mesmo pedido, em vez de achar que um
        # "parece mais rapido".
        medidor.gravar(verificado)
        evento({"tipo": "medicao", **medidor.resumo(verificado)})

        # ═══ ANOTAR NO DIARIO ═════════════════════════════════════════════
        # Uma linha em Markdown no Drive, para a proxima sessao saber onde
        # vocês pararam. Escrita depois de tudo, de proposito: se falhar,
        # a resposta ja chegou inteira ao Fred.
        try:
            if cfg.get("lembrar_do_passado", True) and (texto or "").strip():
                diario.anotar(
                    pergunta=pergunta,
                    resposta=texto,
                    lidos=lidos,
                    projeto=(projeto or {}).get("nome", ""),
                    especialista=(regras_esp or {}).get("nome", ""),
                    segundos=medidor.resumo(verificado).get("segundos", 0),
                    modelo=(PROVEDOR.atual() or {}).get("nome", ""),
                    config=cfg)
        except Exception as erro:
            anotar_erro("nao consegui anotar no diario", erro)

        evento({"tipo": "fim"})

    def _autorizar(self, dados):
        pedido_id = dados.get("id")
        with TRAVA:
            item = PENDENTES.get(pedido_id)
            if item:
                item["ok"] = bool(dados.get("ok"))
                item["gatilho"].set()
        return self._enviar(200, *self._json({"ok": True}))

    # ---------------------------- memoria ----------------------------
    def _memoria(self):
        projetos = []
        if PROJETOS.exists():
            for arquivo in sorted(PROJETOS.glob("*.md"),
                                  key=lambda a: a.stat().st_mtime, reverse=True):
                texto = ler(arquivo, "")
                tecnologia = ""
                achado = re.search(r"Tecnologias: ([^\n]+)", texto)
                if achado:
                    tecnologia = achado.group(1).split(",")[0].strip()
                arquivos = re.search(r"Arquivos mapeados: (\d+)", texto)
                projetos.append({
                    "nome": arquivo.stem,
                    "tec": tecnologia,
                    "arquivos": arquivos.group(1) if arquivos else "?",
                    "github": arquivo.stem.startswith("gh_"),
                })
        return {
            "identidade": ler(MEMORIA / "identidade.md"),
            "jeito": ler(MEMORIA / "jeito_de_trabalhar.md"),
            "projetos": projetos,
        }

    def _sincronizar(self):
        try:
            import importlib
            import indexar
            importlib.reload(indexar)
            threading.Thread(target=indexar.main, daemon=True).start()
            return self._enviar(200, *self._json({"ok": True, "msg": "sincronizando"}))
        except Exception as erro:
            return self._enviar(200, *self._json({"ok": False, "msg": str(erro)}))

    # ---------------------------- helpers ----------------------------
    def _param(self, nome):
        from urllib.parse import urlparse, parse_qs
        return (parse_qs(urlparse(self.path).query).get(nome) or [""])[0]

    def _json(self, obj):
        return ("application/json; charset=utf-8",
                json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _cors(self):
        """A extensao do Chrome e outra origem: sem isto o navegador bloqueia."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        # X-Cerebro-Chave e como a extensao se identifica. Sem estar nesta
        # lista, o Chrome barra a chamada na verificacao previa (preflight) e
        # ela nem chega ao servidor.
        self.send_header("Access-Control-Allow-Headers",
                         "Content-Type, X-Cerebro-Chave, X-Cerebro-Sessao")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):
        try:
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()
        except (ConnectionError, OSError):
            pass

    def _enviar(self, codigo, tipo, corpo):
        try:
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self._cors()
            if tipo.startswith("image/"):
                self.send_header("Cache-Control", "public, max-age=86400")
            else:
                self.send_header("Cache-Control", "no-store, must-revalidate")
            chave = (config().get("codigo_acesso") or "").strip()
            if chave and ("codigo=" + chave) in self.path:
                self.send_header("Set-Cookie",
                                 "acesso=%s; Path=/; Max-Age=31536000; SameSite=Lax" % chave)
            self.end_headers()
            self.wfile.write(corpo)
        except (ConnectionError, OSError):
            pass          # navegador fechou a conexao antes da hora


ERROS = BASE / "erros.log"


def _logs_recentes(limite=160):
    """Entrega somente as últimas linhas úteis para o painel de diagnóstico."""
    arquivos = [ERROS, BASE / "motor.log", BASE / "pipi.log"]
    saida = []
    for caminho in arquivos:
        if not caminho.is_file():
            continue
        try:
            linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
            saida.append({"arquivo": caminho.name, "linhas": linhas[-limite:]})
        except OSError as exc:
            saida.append({"arquivo": caminho.name, "linhas": ["Não foi possível ler: %s" % exc]})
    return {"ok": True, "quando": datetime.datetime.now().isoformat(timespec="seconds"), "arquivos": saida}


def _diagnostico():
    """Foto de todas as linhas de trabalho em andamento, agora."""
    import sys as _sys
    import traceback
    linhas = {}
    quadros = _sys._current_frames()
    for t in threading.enumerate():
        quadro = quadros.get(t.ident)
        pilha = (traceback.format_stack(quadro) if quadro else [])
        # As tres ultimas chamadas ja dizem onde parou; a pilha inteira
        # entope a tela sem acrescentar nada.
        linhas[t.name] = {
            "viva": t.is_alive(),
            "de_fundo": t.daemon,
            "parada_em": [l.strip() for l in pilha[-3:]],
        }
    return {
        "quando": datetime.datetime.now().isoformat(timespec="seconds"),
        "linhas_de_trabalho": len(linhas),
        "motor_responde": modelo_online(),
        "aguardando_sua_aprovacao": len(PENDENTES),
        "detalhe": linhas,
    }


def anotar_erro(assunto, excecao=None):
    """Grava a falha em erros.log, com data e a pilha inteira.

    Antes, `handle_error` fazia `pass`: qualquer erro dentro de uma chamada
    sumia sem deixar rastro. Em 23/08 o Bigode caiu no meio da prova do selo
    e nao sobrou UMA linha para explicar por que -- so "conexao recusada" do
    lado de fora. Sem registro, cada queda vira palpite.

    O terminal continua limpo: desconexao de navegador e barulho, nao erro.
    O arquivo guarda tudo.
    """
    import traceback
    try:
        with ERROS.open("a", encoding="utf-8") as f:
            f.write("\n" + "=" * 70 + "\n")
            f.write("%s  %s\n" % (
                datetime.datetime.now().isoformat(timespec="seconds"), assunto))
            if excecao is not None:
                f.write("".join(traceback.format_exception(
                    type(excecao), excecao, excecao.__traceback__)))
            else:
                f.write(traceback.format_exc())
    except Exception:
        pass                      # registrar falha nao pode derrubar o servidor


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Desconexao do navegador e normal: a pessoa fechou a aba ou clicou
        # em parar. Nao vira registro. Qualquer outra coisa, vira.
        import sys as _sys
        tipo, valor, _ = _sys.exc_info()
        if isinstance(valor, (ConnectionResetError, ConnectionAbortedError,
                              BrokenPipeError)):
            return
        anotar_erro("falha atendendo %s" % (client_address,), valor)


# ==========================================================================
# Interface
# ==========================================================================

def pagina(antiga=False):
    """Le do disco a cada acesso: editar o HTML e dar F5 ja mostra a mudanca.

    UMA TELA SO -- E E A DE SEMPRE   (10/09, corrigindo um erro meu)

        Eu tinha escrito uma tela nova (`colab.html`) e posto ela na porta
        de entrada. Errei em dois tempos: mudei a identidade visual sem
        precisar, e deixei para tras funcoes que ja estavam prontas e
        testadas -- voz para texto, projetos, especialistas, skills,
        programados, memoria semantica e conectores.

        A conta nao fecha. A tela nova resolvia um problema pequeno (ver o
        estado da sessao do Colab) e custava a tela inteira. O caminho certo
        e o inverso: as pecas novas vao para dentro da tela que ja existe,
        que e o que acontece hoje -- o painel de IAs lista os .gguf do Drive
        e o painel CRIAR IMAGENS fala com o ComfyUI.

        O parametro `antiga` sobrevive so para /antigo nao quebrar em quem
        salvou o endereco. As duas rotas devolvem a mesma pagina.
    """
    return (ler(BASE / "web" / "index.html")
            or "<h1>Falta o arquivo web/index.html</h1>")


def ip_local():
    """Descobre o IP do notebook na wi-fi, para o celular alcancar."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        endereco = s.getsockname()[0]
        s.close()
        return endereco
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


MANIFESTO = {
    "name": "Bigode - Venure",
    "short_name": "Bigode",
    "description": "Sua IA local da Venure",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#0A0C11",
    "theme_color": "#0A0C11",
    # Os de fundo creme sao os que aparecem na barra de tarefas e no menu
    # Iniciar. O recorte transparente sumia no fundo escuro do Windows.
    "icons": [
        {"src": "/favicon-192.png?v=3", "sizes": "192x192", "type": "image/png",
         "purpose": "any"},
        {"src": "/favicon-512.png?v=3", "sizes": "512x512", "type": "image/png",
         "purpose": "any"},
        {"src": "/icone-192.png", "sizes": "192x192", "type": "image/png",
         "purpose": "maskable"},
        {"src": "/icone-512.png", "sizes": "512x512", "type": "image/png",
         "purpose": "maskable"},
    ],
}

SERVICE_WORKER = """
const CACHE = 'cerebro-v1';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(['/'])).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api/')) return;            // API sempre ao vivo
  e.respondWith(
    fetch(e.request)
      .then(r => { const copia = r.clone();
                   caches.open(CACHE).then(c => c.put(e.request, copia)); return r; })
      .catch(() => caches.match(e.request).then(r => r || caches.match('/')))
  );
});
"""


def _icone_png(lado):
    """Gera o icone do app sem depender de biblioteca: degrade da marca com um V."""
    import struct
    import zlib

    linhas = bytearray()
    raio = lado * 0.22
    for y in range(lado):
        linhas.append(0)                       # filtro da linha
        for x in range(lado):
            # cantos arredondados
            dx = min(x, lado - 1 - x)
            dy = min(y, lado - 1 - y)
            fora = False
            if dx < raio and dy < raio:
                if ((raio - dx) ** 2 + (raio - dy) ** 2) > raio * raio:
                    fora = True
            if fora:
                linhas += bytes((0, 0, 0, 0))
                continue

            # degrade teal -> violeta na diagonal
            t = (x + y) / (2.0 * lado)
            r = int(45 + (129 - 45) * t)
            g = int(212 + (140 - 212) * t)
            b = int(191 + (248 - 191) * t)

            # desenha o "V" da Venure
            nx = (x / lado - 0.5) * 2
            ny = (y / lado - 0.28) * 2
            espessura = 0.20
            no_v = (abs(abs(nx) * 1.35 - ny) < espessura) and (-0.1 < ny < 1.25)
            if no_v:
                linhas += bytes((4, 20, 15, 255))
            else:
                linhas += bytes((r, g, b, 255))

    def bloco(tipo, dados):
        c = tipo + dados
        return (struct.pack(">I", len(dados)) + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF))

    cabecalho = struct.pack(">IIBBBBB", lado, lado, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + bloco(b"IHDR", cabecalho)
            + bloco(b"IDAT", zlib.compress(bytes(linhas), 9))
            + bloco(b"IEND", b""))


_ICONES = {}


def icone(lado):
    """O icone do app: a foto do Bigode.

    Antes era DESENHADO por codigo (_icone_png), e por isso o Chrome
    continuava mostrando a marca velha ao oferecer "instalar como app",
    mesmo depois de a foto do gato ter entrado no projeto -- as duas coisas
    nao se falavam. Agora le o arquivo, e o desenho antigo so aparece se a
    foto sumir.
    """
    if lado in _ICONES:
        return _ICONES[lado]

    # o mais proximo por cima, para nao ampliar imagem pequena
    for tamanho in sorted([180, 192, 512]):
        if tamanho >= lado:
            arquivo = BASE / "web" / "img" / ("icone-%d.png" % tamanho)
            if arquivo.is_file():
                _ICONES[lado] = arquivo.read_bytes()
                return _ICONES[lado]

    _ICONES[lado] = _icone_png(lado)      # sem a foto, o desenho antigo serve
    return _ICONES[lado]


_FAVICONS = {}


def favicon(lado=None):
    """O icone da aba do navegador.

    Diferente do icone do app: aqui o gato vem sobre um fundo creme e
    arredondado. O recorte transparente sumia na barra escura do Chrome --
    sobrava so o queixo branco e os olhos, e parecia outro desenho.

    lado=None devolve o .ico com varios tamanhos dentro.
    """
    if lado in _FAVICONS:
        return _FAVICONS[lado]

    nome = "favicon.ico" if lado is None else ("favicon-%d.png" % lado)
    arquivo = BASE / "web" / "img" / nome
    if arquivo.is_file():
        _FAVICONS[lado] = arquivo.read_bytes()
    else:
        _FAVICONS[lado] = icone(lado or 180)      # sem o arquivo, a foto serve
    return _FAVICONS[lado]


PAGINA_CODIGO = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bigode</title><style>
body{background:#0A0C11;color:#ECEFF4;font:15px/1.6 -apple-system,"Segoe UI",sans-serif;
     height:100vh;margin:0;display:grid;place-items:center}
.cx{width:300px;max-width:88vw;text-align:center}
.mk{width:56px;height:56px;border-radius:18px;margin:0 auto 16px;
    background:linear-gradient(140deg,#2DD4BF,#818CF8)}
h1{font-size:19px;margin-bottom:6px}p{color:#6E7889;font-size:13px;margin-bottom:20px}
input{width:100%;background:#11141B;border:1px solid #1D222C;border-radius:11px;
      padding:13px;color:#ECEFF4;font-size:16px;text-align:center;outline:none}
input:focus{border-color:#31445E}
button{width:100%;margin-top:10px;background:#2DD4BF;color:#04140F;border:none;
       border-radius:11px;padding:13px;font-size:15px;font-weight:600}
</style></head><body><div class="cx"><div class="mk"></div>
<h1>Bigode</h1><p>Digite o codigo de acesso</p>
<form method="GET" action="/"><input name="codigo" type="password" autofocus
 inputmode="numeric" placeholder="codigo"><button>Entrar</button></form>
</div></body></html>"""


# ==========================================================================
# Inicio
# ==========================================================================

def aguardar_modelo(segundos):
    if modelo_online():
        return
    print("  Aguardando o motor carregar", end="", flush=True)
    limite = time.time() + segundos
    while time.time() < limite:
        if modelo_online():
            print(" pronto.")
            return
        print(".", end="", flush=True)
        time.sleep(5)
    print(" ainda nao respondeu (a interface abre mesmo assim).")


def espiar_motor():
    """Mostra na tela do Bigode o que o motor esta escrevendo.

    O motor sobe numa janela propria, minimizada, e toda a saida dele vai
    parar dentro de motor.log. Isso foi feito de proposito -- assim a janela
    nao some levando o erro junto -- mas teve um custo alto: quem abre o
    Bigode nao ve NADA acontecendo. Modelo carregando, modelo falhando,
    janela de contexto errada: tudo mudo, ate alguem lembrar de abrir o
    arquivo.

    Aqui o arquivo e acompanhado linha a linha e repetido na tela, com a
    marca `motor |` na frente para nao confundir com o que o Bigode fala.
    O arquivo continua existindo. So deixou de ser o unico lugar.
    """
    registro = BASE / "motor.log"
    posicao = 0
    while True:
        try:
            if registro.is_file():
                tamanho = registro.stat().st_size
                # O .bat reescreve o arquivo do zero a cada modelo que sobe.
                # Se encolheu, e arquivo novo: volta para o comeco.
                if tamanho < posicao:
                    posicao = 0
                    print("\n  motor | ---- novo carregamento ----")
                if tamanho > posicao:
                    with registro.open("r", encoding="utf-8",
                                       errors="replace") as f:
                        f.seek(posicao)
                        novas = f.read()
                        posicao = f.tell()
                    for linha in novas.splitlines():
                        linha = linha.rstrip()
                        if linha:
                            print("  motor | " + linha[:180])
        except Exception:
            pass          # nunca derruba o Bigode por causa do espelho do log
        time.sleep(0.7)


def main():
    cfg = config()
    porta = int(cfg["porta"])
    endereco = "http://localhost:%d" % porta
    n = len(list(PROJETOS.glob("*.md"))) if PROJETOS.exists() else 0

    print("=" * 62)
    print("   V E N U R E   -   C E R E B R O")
    print("=" * 62)
    print("   Interface ..: " + endereco)
    print("   Motor ......: " + cfg["llm_url"])
    print("   Ferramentas : %d ativas" % len(ferramentas.ativas()))
    print("   Memoria ....: %d projetos" % n)
    if n == 0:
        print("                 (rode ATUALIZAR_MEMORIA.bat)")
    print("=" * 62)

    # O motor NAO sobe sozinho. A interface abre na hora e o modelo e escolhido
    # la dentro. Ligar um modelo de 8 a 19 GB a partir do pendrive leva minutos:
    # nao faz sentido segurar a tela por causa disso, ainda mais porque muitas
    # vezes o que se quer no inicio e so mexer em ajustes ou ver o historico.
    if modelo_online():
        print("   Situacao ...: motor ja esta ligado")
    else:
        print("   Situacao ...: motor desligado (a interface abre na hora)")
        print("                 escolha o modelo no canto superior direito")
    print("\n   Ctrl+C para encerrar\n")

    if cfg.get("acesso_rede", True):
        print("   No celular ..: http://%s:%d" % (ip_local(), porta))
        print("                  (mesmo Wi-Fi; adicione a Tela de Inicio)")
        print()

    # Relogio das tarefas programadas. Roda em segundo plano e so dispara o
    # que estiver marcado; se o motor estiver desligado na hora, a tarefa e
    # registrada como nao executada em vez de falhar em silencio.
    # Se o motor ja estiver de pe (voce deixou aberto de antes), aproveita e
    # aquece agora, enquanto voce ainda esta abrindo o navegador.
    threading.Thread(target=aquecer, daemon=True).start()

    # O que o motor escrever aparece aqui, marcado com `motor |`.
    threading.Thread(target=espiar_motor, daemon=True).start()

    ativas = sum(1 for t in agenda.listar() if t.get("ativa"))
    agenda.iniciar(tarefa, modelo_online)
    if ativas:
        print("   Programados : %d tarefa(s) ativa(s)" % ativas)
        print()

    threading.Timer(0.8, lambda: webbrowser.open(endereco)).start()
    host = "0.0.0.0" if cfg.get("acesso_rede", True) else "127.0.0.1"
    # Erro em thread de segundo plano (aquecimento, agenda) tambem vai para o
    # arquivo. Sem isto, thread que morre morre calada.
    def _thread_quebrou(args):
        anotar_erro("falha na tarefa de fundo", args.exc_value)
    try:
        threading.excepthook = _thread_quebrou
    except Exception:
        pass

    servidor = Servidor((host, porta), Handler)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nCerebro encerrado.")
        servidor.server_close()
    except BaseException as erro:
        # Se o processo cair, a ultima coisa que ele faz e dizer por que.
        anotar_erro("O SERVIDOR CAIU", erro)
        print("\n  O Bigode caiu. O motivo esta em %s" % ERROS)
        servidor.server_close()
        raise


if __name__ == "__main__":
    main()
