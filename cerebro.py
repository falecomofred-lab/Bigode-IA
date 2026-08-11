#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CEREBRO - plataforma de IA da Venure (venure.com.br)

Interface + identidade + memoria + ferramentas sobre um modelo local (llamafile).
Usa apenas a biblioteca padrao do Python.

Uso:  python cerebro.py
"""

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

import armazenamento
import autenticacao
import ferramentas
import habilidades
import modelos
import voz

BASE = Path(__file__).resolve().parent
MEMORIA = BASE / "memoria"
PROJETOS = MEMORIA / "projetos"

PENDENTES = {}
NAVEGADOR = {}          # acoes esperando a extensao do Chrome executar
TRAVA = threading.Lock()


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
    dados.setdefault("acesso_rede", True)      # permite abrir pelo celular na mesma wi-fi
    dados.setdefault("codigo_acesso", "")      # legado: substituido pelo login
    dados.setdefault("exigir_login", True)     # pede e-mail e senha para entrar
    dados.setdefault("login_social", {         # opcional: ver LEIAME para configurar
        "google": {"client_id": "", "client_secret": ""},
        "github": {"client_id": "", "client_secret": ""},
    })
    dados.setdefault("pastas_liberadas", ["G:\\Meu Drive\\projetos"])
    dados.setdefault("aguardar_modelo_seg", 900)
    
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


def salvar_config(novo):
    atual = config()
    atual.update(novo)
    (BASE / "config.json").write_text(
        json.dumps(atual, ensure_ascii=False, indent=2), encoding="utf-8")
    return atual


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

Voce EXECUTA, nao descreve. Tudo que voce enxerga ja esta autorizado: nunca
pergunte "posso acessar?" nem peca um caminho que voce mesmo pode descobrir.
Tente; se falhar, diga o erro e siga.

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
    "objetivo": "Va direto ao ponto. Responda o que foi perguntado e pare.",
    "conciso": "Frases curtas. Se da para cortar uma palavra sem perder sentido, corte.",
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
    dados.setdefault("tracos", ["objetivo", "conciso", "sem_bajulacao", "sem_devaneio"])
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

Converse como uma pessoa, nao como manual. Resposta curta: duas ou tres frases
resolvem quase tudo. Sem repetir o que ja disse, sem reformular a mesma ideia,
sem "como mencionei anteriormente".

Nao recite as regras acima nem descreva seu proprio funcionamento.
Terminou de responder? Pare. Nao ofereca resumo do que acabou de dizer.
"""


def prompt_pequeno():
    """Modelo pequeno se perde com muita instrucao: entrega melhor com pouco."""
    modelo = PROVEDOR.atual() or {}
    return float(modelo.get("gb", 99)) < 12


def montar_system(pergunta):
    cfg = config()
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
        partes.append(habilidades.resumo_para_prompt())

    # A memoria so entra no prompt se voce pedir. Mantendo o prompt do sistema
    # identico entre as mensagens, o cache do motor e reaproveitado e a resposta
    # comeca muito mais rapido. Sem isso, o Cerebro busca pela ferramenta memoria().
    fontes = []
    if cfg.get("injetar_memoria"):
        contexto, fontes = memoria_relevante(
            pergunta, int(cfg.get("memorias_por_pergunta", 3)))
        if contexto:
            partes.append("# MEMORIA DOS PROJETOS\n\nUse como fato apenas o que "
                          "estiver abaixo.\n\n" + contexto)

    return "\n\n".join(p.strip() for p in partes if p and p.strip()), fontes


# ==========================================================================
# Modelo
# ==========================================================================

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


def pedir_ao_navegador(nome, args, evento, espera=90):
    """Manda a acao para a extensao do Chrome e espera ela devolver o resultado.
    Quem executa e o navegador; o Python so orquestra."""
    pedido = uuid.uuid4().hex[:10]
    gatilho = threading.Event()
    with TRAVA:
        NAVEGADOR[pedido] = {"gatilho": gatilho, "resultado": None}

    evento({"tipo": "navegador", "id": pedido,
            "acao": nome.replace("navegador_", ""), "args": args or {}})

    if not gatilho.wait(espera):
        with TRAVA:
            NAVEGADOR.pop(pedido, None)
        return ("O navegador nao respondeu em %ds. Verifique se o painel do Cerebro "
                "esta aberto no Chrome e se ha uma aba ativa." % espera)

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


class Cancelado(Exception):
    """O usuario apertou parar ou fechou a aba."""


def chamar_modelo(mensagens, ao_receber, com_ferramentas=True, ao_ferramenta=None,
                  esquema=None, obrigar_ferramenta=False):
    """Stream do modelo. Devolve (texto, chamada_de_ferramenta_ou_None).

    Usa function calling nativo quando disponivel: modelos menores seguem o
    padrao oficial muito melhor do que um protocolo inventado em texto.
    """
    cfg = config()
    payload = {
        "messages": mensagens,
        "temperature": float(cfg["temperatura"]),
        "max_tokens": int(cfg["max_tokens"]),
        "stream": True,

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
            # "required" nao e sugestao: o motor so aceita como resposta uma
            # chamada de ferramenta. E o unico jeito confiavel de impedir que um
            # modelo pequeno responda de cabeca sobre arquivo que nunca leu.
            payload["tool_choice"] = "required" if obrigar_ferramenta else "auto"
            if obrigar_ferramenta:
                payload["temperature"] = 0.2
    pedido = urllib.request.Request(
        cfg["llm_url"],
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    completo = []
    chamadas = {}
    comeco = time.time()
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

            pedaco = delta.get("content", "")
            if pedaco:
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
    PROVEDOR.registrar_velocidade(len(completo), time.time() - comeco)

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


def extrair_chamada(texto):
    for padrao in (PADRAO_FERRAMENTA, PADRAO_ALT):
        achado = padrao.search(texto or "")
        if achado:
            try:
                dados = json.loads(achado.group(1))
                if isinstance(dados, dict) and dados.get("nome"):
                    return dados.get("nome"), dados.get("args") or dados.get("argumentos") or {}
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


def _dominio(url):
    from urllib.parse import urlparse
    try:
        alvo = url if str(url).startswith("http") else "https://" + str(url)
        return urlparse(alvo).netloc.replace("www.", "")
    except Exception:
        return str(url)[:40]


def narrar(nome, args, concluido=False):
    """Traduz a chamada tecnica para uma frase que qualquer um entende."""
    a = args or {}
    ger = "Analisando"
    frases = {
        "listar_pasta":     ("Abrindo a pasta", "Abri a pasta", _final(a.get("caminho"))),
        "ler_arquivo":      ("Lendo", "Li", _final(a.get("caminho"))),
        "buscar":           ("Procurando", "Procurei", '"%s"' % a.get("termo", "")),
        "memoria":          ("Consultando a memória", "Consultei a memória", ""),
        "github_repos":     ("Vendo seus repositórios", "Vi seus repositórios", ""),
        "github_ler":       ("Lendo no GitHub", "Li no GitHub",
                             "%s/%s" % (a.get("repo", ""), _final(a.get("caminho")))),
        "web_buscar":       ("Pesquisando na web", "Pesquisei na web",
                             '"%s"' % a.get("consulta", "")),
        "web_ler":          ("Acessando", "Acessei", _dominio(a.get("url", ""))),
        "escrever_arquivo": ("Escrevendo", "Escrevi", _final(a.get("caminho"))),
        "criar_pasta":      ("Criando a pasta", "Criei a pasta", _final(a.get("caminho"))),
        "mover":            ("Movendo", "Movi", _final(a.get("origem"))),
        "apagar":           ("Apagando", "Apaguei", _final(a.get("caminho"))),
        "rodar_comando":    ("Executando", "Executei",
                             str(a.get("comando", ""))[:48]),
        "github_criar_repo": ("Criando o repositório", "Criei o repositório",
                              a.get("nome", "")),
        "github_commit":    ("Enviando para o GitHub", "Enviei para o GitHub",
                             _final(a.get("caminho"))),
        "github_issue":     ("Abrindo uma issue em", "Abri uma issue em", a.get("repo", "")),
    }
    antes, depois, alvo = frases.get(nome, (ger, ger, nome))
    verbo = depois if concluido else antes
    return (verbo + (" " + alvo if alvo else "")).strip()


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


def precisa_agir(pergunta):
    """A pergunta pede acesso real a arquivos/projetos? Entao nao pode so conversar."""
    texto = (pergunta or "").lower()
    return any(g in texto for g in GATILHOS)


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


def trocar_modelo(caminho):
    return PROVEDOR.carregar(caminho)


# ==========================================================================
# Tarefa (usada pela ponte MCP com o Claude - sem streaming)
# ==========================================================================

def tarefa(pergunta, contexto=""):
    """Roda o ciclo de ferramentas sem interface. Acoes de escrita sao negadas:
    pela ponte, o Cerebro le, analisa e escreve codigo - mas nao altera nada."""
    cfg = config()
    system, fontes = montar_system(pergunta)
    system += ("\n\n# MODO PONTE\n\nVoce esta respondendo ao Claude, nao ao Fred. "
               "Ferramentas de escrita estao bloqueadas neste modo: leia, analise e "
               "devolva o codigo ou a resposta em texto.")
    entrada = pergunta if not contexto else (contexto + "\n\n" + pergunta)
    mensagens = [{"role": "system", "content": system},
                 {"role": "user", "content": entrada}]

    acoes, texto = [], ""
    for _ in range(int(cfg["max_passos"])):
        try:
            resposta, nativa = chamar_modelo(caber_no_contexto(mensagens, cfg),
                                             lambda _acumulado: None)
        except Exception as erro:
            return {"texto": "Falha ao falar com o motor: %s" % erro,
                    "acoes": acoes, "fontes": fontes}

        nome, args = nativa if nativa else extrair_chamada(resposta)
        texto = resposta.split("<ferramenta>")[0].split("```json")[0].strip()
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
        mensagens.append({"role": "user", "content": "RESULTADO:\n" + resultado})

    return {"texto": texto, "acoes": acoes, "fontes": fontes}


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
    LIVRES = ("/login", "/api/login/estado", "/api/login/entrar",
              "/api/login/criar", "/auth/", "/icone", "/manifest.json",
              "/sw.js", "/apple-touch-icon")

    def _sessao(self):
        return autenticacao.sessao_de(self.headers.get("Cookie"))

    def _autorizado(self):
        rota = self.path.split("?")[0]
        if any(rota.startswith(p) for p in self.LIVRES):
            return True
        if not config().get("exigir_login", True):
            return True
        return bool(self._sessao())

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

        rotas = {
            "/api/eu": lambda: self._json({
                **(self._sessao() or {}),
                "usuarios": autenticacao.listar_usuarios(),
            }),
            "/api/sair": lambda: self._json({"ok": True}),
            "/": lambda: ("text/html; charset=utf-8", pagina().encode("utf-8")),
            "/manifest.json": lambda: ("application/manifest+json; charset=utf-8",
                                       json.dumps(MANIFESTO).encode("utf-8")),
            "/sw.js": lambda: ("application/javascript; charset=utf-8",
                               SERVICE_WORKER.encode("utf-8")),
            "/icone-192.png": lambda: ("image/png", icone(192)),
            "/icone-512.png": lambda: ("image/png", icone(512)),
            "/apple-touch-icon.png": lambda: ("image/png", icone(180)),
            "/apple-touch-icon-precomposed.png": lambda: ("image/png", icone(180)),
            "/api/rede": lambda: self._json({
                "ip": ip_local(), "porta": config().get("porta", 7000),
                "aberto": bool(config().get("acesso_rede", True)),
                "com_codigo": bool((config().get("codigo_acesso") or "").strip()),
            }),
            "/api/status": lambda: self._json({
                **PROVEDOR.status(),
                "modelo": modelo_online(),
                "modelo_nome": nome_modelo_atual(),
                "erro_motor": "" if modelo_online() else PROVEDOR.erro_recente(),
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
            "/api/conexoes": lambda: self._json(conexoes_publicas()),
            "/api/config": lambda: self._json(config()),
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
            tipo, corpo = self._json({"ok": True, "nome": r["nome"]})
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
        if rota == "/api/chat":
            return self._chat(dados)
        if rota == "/api/tarefa":
            return self._enviar(200, *self._json(
                tarefa(dados.get("pergunta", ""), dados.get("contexto", ""))))
        if rota == "/api/autorizar":
            return self._autorizar(dados)
        if rota == "/api/conexoes":
            salvar_conexoes(dados)
            return self._enviar(200, *self._json({"ok": True}))
        if rota == "/api/config":
            return self._enviar(200, *self._json(salvar_config(dados)))
        if rota == "/api/conversas":
            return self._enviar(200, *self._json(armazenamento.salvar_conversa(dados)))
        if rota == "/api/conversa/apagar":
            return self._enviar(200, *self._json(
                {"ok": armazenamento.apagar_conversa(dados.get("id"))}))
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
        historico = dados.get("mensagens", [])
        pergunta = historico[-1]["content"] if historico else ""
        cfg = config()

        system, fontes = montar_system(pergunta)

        projeto = armazenamento.abrir_projeto(dados.get("projeto", "")) \
            if dados.get("projeto") else {}
        if projeto:
            system += ("\n\n# PROJETO ATIVO: %s\n\nDiretorio: %s\n\n%s"
                       % (projeto.get("nome", ""), projeto.get("diretorio", ""),
                          projeto.get("instrucoes", "")))

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

        # O esquema das ferramentas fica no INICIO do prompt. Se ele mudar de
        # conversa para conversa, o motor perde o cache e reprocessa tudo -
        # custa mais tempo do que os tokens economizados. Por isso a lista e
        # fixa: quem controla o tamanho e voce, ligando e desligando conexoes.
        if cfg.get("ferramentas_dinamicas"):
            assunto = " ".join(m.get("content", "") for m in historico
                               if m.get("role") == "user")[-4000:]
            esquema = ferramentas.esquema_openai(ferramentas.para_pergunta(assunto))
        else:
            esquema = ferramentas.esquema_openai()

        plano_aprovado = False
        # obrigar: proxima chamada so pode sair com ferramenta (tool_choice
        # required). usou_ferramenta: se ja tocou nos dados de verdade nesta
        # pergunta, pode voltar a responder livremente.
        obrigar, usou_ferramenta = False, False
        for passo in range(int(cfg["max_passos"])):
            if not vivo["ok"]:
                break
            estado = {"enviado": 0}

            def ao_receber(acumulado):
                if not vivo["ok"]:
                    raise Cancelado()
                visivel = acumulado.split("<ferramenta>")[0].split("```json")[0]
                novo = visivel[estado["enviado"]:]
                if novo:
                    estado["enviado"] = len(visivel)
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

            try:
                resposta, nativa = chamar_modelo(
                    caber_no_contexto(mensagens, cfg, esquema),
                    ao_receber, ao_ferramenta=ao_ferramenta, esquema=esquema,
                    obrigar_ferramenta=obrigar)
            except Cancelado:
                break
            except Exception as erro:
                texto = str(erro)
                if "10054" in texto or "10061" in texto or isinstance(erro, urllib.error.URLError):
                    if not modelo_online():
                        texto = ("O motor ainda esta carregando o modelo. "
                                 "Acompanhe a janela 'Motor Cerebro': quando aparecer "
                                 "'server is listening', mande de novo.")
                    else:
                        texto = ("O motor derrubou a conexao. Se acabou de trocar de modelo, "
                                 "espere ele terminar de carregar e tente outra vez.")
                else:
                    texto = "Falha: " + texto
                evento({"tipo": "erro", "texto": texto})
                break

            nome, args = nativa if nativa else extrair_chamada(resposta)

            # A pergunta pede dado real, o modelo respondeu de cabeca e ainda nao
            # tocou em nenhum arquivo. Descartamos essa resposta: ela seria
            # invencao. Na volta, tool_choice=required nao deixa ele escapar.
            if not nome and not usou_ferramenta and precisa_agir(pergunta) \
                    and passo < int(cfg["max_passos"]) - 1:
                evento({"tipo": "acao", "id": "check%d" % passo, "estado": "rodando",
                        "titulo": "Conferindo nos arquivos de verdade"})
                if not obrigar:
                    mensagens.append({"role": "assistant", "content": resposta or "..."})
                    mensagens.append({"role": "user", "content":
                        "Voce respondeu sem abrir nada. Nao descreva o que faria: "
                        "FACA. Comece por listar_pasta na pasta mais provavel e so "
                        "responda depois de ver o conteudo real."})
                obrigar = True
                # limpa da tela o texto inventado que ja tinha comecado a sair
                evento({"tipo": "descartar"})
                evento({"tipo": "acao", "id": "check%d" % passo, "estado": "ok",
                        "titulo": "Abrindo os arquivos"})
                continue

            if not nome:
                break

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
                gatilho.wait(1800)
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
                        "acao": resumir(nome, args), "titulo": narrar(nome, args),
                        "nome": nome, "args": args})
                gatilho.wait(600)
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

            mensagens.append({"role": "user",
                              "content": "RESULTADO:\n" + resultado[:3500]})
            evento({"tipo": "novo_bloco"})

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
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass              # nao polui o terminal com desconexoes do navegador


# ==========================================================================
# Interface
# ==========================================================================

def pagina():
    """Le do disco a cada acesso: editar o HTML e dar F5 ja mostra a mudanca."""
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
    "name": "Cerebro - Venure",
    "short_name": "Cerebro",
    "description": "Sua IA local da Venure",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#0A0C11",
    "theme_color": "#0A0C11",
    "icons": [
        {"src": "/icone-192.png", "sizes": "192x192", "type": "image/png",
         "purpose": "any maskable"},
        {"src": "/icone-512.png", "sizes": "512x512", "type": "image/png",
         "purpose": "any maskable"},
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
    if lado not in _ICONES:
        _ICONES[lado] = _icone_png(lado)
    return _ICONES[lado]


PAGINA_CODIGO = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cerebro</title><style>
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
<h1>Cerebro</h1><p>Digite o codigo de acesso</p>
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

    threading.Timer(0.8, lambda: webbrowser.open(endereco)).start()
    host = "0.0.0.0" if cfg.get("acesso_rede", True) else "127.0.0.1"
    servidor = Servidor((host, porta), Handler)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nCerebro encerrado.")
        servidor.server_close()


if __name__ == "__main__":
    main()
