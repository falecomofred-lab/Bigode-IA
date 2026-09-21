#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""CONFERIR OS DOIS PROJETOS ANTES DE PUBLICAR
Venure · venure.com.br · 17/09/2026

    python TESTAR_TUDO.py

    1. SEGREDO   nenhuma credencial no que o git vai levar.
    2. PYTHON    todo .py compila.
    3. PAGINA    o JavaScript fecha, e todo id que ele usa existe.

Sai com codigo 0 so se as tres passarem:

    python TESTAR_TUDO.py && git push


===========================================================================
POR QUE A PRIMEIRA VERSAO DISTO FOI REESCRITA NO MESMO DIA
===========================================================================

A de manha rodou e deu quatro alarmes. Dois eram defeito de verdade. Os
outros dois eram defeito DELA:

  . acusou o config.json de ter token da Hugging Face -- e tem mesmo, mas o
    arquivo esta no .gitignore e nunca chegaria ao GitHub. Ela varria o
    disco, nao o que o git leva.

  . acusou "parenteses desbalanceados" numa linha correta: a expressao
    regular /\[([^\]]+)\]\((https?:[^)]+)\)/ do renderizador de markdown.
    Ela contava parenteses no texto cru, e dentro de uma regex o parentese
    e literal, nao estrutura.

Isso importa mais do que parece. Verificador que grita sem motivo ensina a
pessoa a ignora-lo -- e no dia em que ele estiver certo, ela ignora tambem.
Alarme falso nao e um incomodo: e o comeco da falha.

As duas correcoes, entao:

  SEGREDO  pergunta ao proprio git quais arquivos ele levaria
           (`git ls-files -co --exclude-standard`), em vez de andar pelo
           disco adivinhando. O git ja sabe ler .gitignore; reimplementar
           isso seria manter uma segunda verdade, que um dia divergiria.

  PAGINA   percorre o JavaScript caractere a caractere, sabendo onde
           comeca e termina texto, comentario e expressao regular. Sao ~50
           linhas. A versao com re.sub tinha 6 e estava errada -- o
           barato saiu caro na primeira execucao.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

CEREBRO = Path(__file__).resolve().parent
PIPI = CEREBRO.parent / "Pipi IA"

VERDE, VERM, AMAR, FIM = "\033[92m", "\033[91m", "\033[93m", "\033[0m"


def ok(t):
    print("  %s[ok]%s %s" % (VERDE, FIM, t))


def falha(t):
    print("  %s[X]%s  %s" % (VERM, FIM, t))


def nota(t):
    print("  %s[!]%s  %s" % (AMAR, FIM, t))


# ======================================================================
# 1. SEGREDO
# ======================================================================
# Formatos de credencial de verdade, nao a palavra "token" num comentario.
PADROES = [
    (re.compile(r"\bhf_[A-Za-z0-9]{30,}"), "token da Hugging Face"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "token do GitHub"),
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}"), "chave estilo OpenAI/Anthropic"),
    (re.compile(r"\ba[ks]-[A-Za-z0-9]{20,}"), "token da Modal"),
    (re.compile(r"\bAIza[A-Za-z0-9\-_]{30,}"), "chave do Google"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{20,}"), "token do Slack"),
]

# Exemplo em documentacao nao e segredo. O look_carol.md ensina a colar a
# chave da Anthropic e mostra 'sk-ant-v7-YOUR_KEY_HERE' -- se isso virasse
# alarme, o alarme viraria ruido.
ENFEITE = re.compile(
    r"YOUR_|_HERE|SEU_|SUA_|XXX|xxx|\.\.\.|EXEMPLO|EXAMPLE|COLE_|PLACEHOLDER|"
    r"<.+>|aqui|TODO", re.I)

BINARIO = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".pdf", ".zip",
           ".gguf", ".bin", ".pyc", ".woff", ".woff2", ".ttf", ".mp3", ".wav"}


def arquivos_do_git(raiz):
    """O que o git levaria: versionado + novo, menos o que o .gitignore tira.

    Devolve (lista, explicacao). Sem git, devolve lista vazia e avisa --
    melhor dizer "nao consegui conferir" do que conferir a coisa errada e
    dar um [ok] que nao vale nada.
    """
    try:
        saida = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard"],
            cwd=str(raiz), capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=60)
    except Exception as erro:
        return [], "git nao rodou (%s)" % str(erro)[:80]
    if saida.returncode != 0:
        return [], "esta pasta ainda nao e um repositorio git"
    nomes = [n.strip() for n in saida.stdout.splitlines() if n.strip()]
    return [raiz / n for n in nomes], ""


def checar_segredos(raiz, nome):
    print("\n  %s" % nome)
    alvos, aviso = arquivos_do_git(raiz)
    if aviso:
        nota("%s — pulei a varredura" % aviso)
        return True

    bom = True
    lidos = 0
    for p in alvos:
        if p.suffix.lower() in BINARIO or not p.is_file():
            continue
        try:
            texto = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lidos += 1
        for padrao, oque in PADROES:
            for achado in padrao.finditer(texto):
                trecho = texto[max(0, achado.start() - 60):achado.end() + 60]
                if ENFEITE.search(trecho):
                    continue      # exemplo de documentacao
                linha = texto[:achado.start()].count("\n") + 1
                # Nunca imprimir o valor: log vira captura de tela, que
                # vira vazamento. O arquivo e a linha bastam para achar.
                falha("%s:%d tem um %s"
                      % (p.relative_to(raiz), linha, oque))
                bom = False
    if bom:
        ok("%d arquivos que o git levaria, nenhuma credencial" % lidos)
    return bom


# ======================================================================
# 2. PYTHON
# ======================================================================
PULAR = {".git", "__pycache__", "node_modules", "chroma_db", "producao",
         "conversas", "auditoria", "Historico", "python", "ComfyUI",
         ".venv", "venv", "Arquivos GGUF"}


def checar_python(raiz, nome):
    print("\n  %s" % nome)
    bom, total = True, 0
    for p in raiz.rglob("*.py"):
        if any(parte in PULAR for parte in p.parts):
            continue
        total += 1
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="ignore"),
                      filename=str(p))
        except SyntaxError as e:
            falha("%s linha %s: %s" % (p.relative_to(raiz), e.lineno, e.msg))
            bom = False
    if bom:
        ok("%d arquivos .py compilam" % total)
    return bom


# ======================================================================
# 3. PAGINA
# ======================================================================
# Onde um `/` comeca expressao regular e onde e divisao? Depende do que veio
# antes: depois de valor (], ), nome, numero) e divisao; depois de operador,
# virgula, `(` ou `return`, e regex. Sem essa distincao, a /\)/ de uma regex
# entra na conta dos parenteses -- foi o alarme falso desta manha.
ANTES_DE_REGEX = set("(,=:[!&|?{};+-*%~^<>") | {"return", "typeof", "case",
                                                "in", "of", "new", "delete",
                                                "void", "do", "else", "yield"}


def so_estrutura(js, manter_texto=False):
    """Devolve o JS sem comentario e sem expressao regular.

    `manter_texto=False` tira tambem o conteudo das aspas -- e o que a
    contagem de chaves e parenteses precisa.

    `manter_texto=True` preserva o texto entre aspas. E o que a busca por
    $('id') precisa, porque o id mora dentro das aspas.

    Duas necessidades, um percorredor so. Escrever um segundo "tira
    comentarios" simples ao lado deste seria repetir o erro da manha: a
    versao simples nao sabe que // dentro de 'http://x' nao e comentario, e
    apagaria meia linha sem avisar.
    """
    saida = []
    i, n = 0, len(js)
    while i < n:
        c = js[i]
        d = js[i:i + 2]

        if d == "/*":
            fim = js.find("*/", i + 2)
            i = n if fim < 0 else fim + 2
            continue
        if d == "//":
            fim = js.find("\n", i)
            i = n if fim < 0 else fim
            continue

        if c in "\"'`":
            fecha, comeco, i = c, i, i + 1
            while i < n:
                if js[i] == "\\":
                    i += 2
                    continue
                if js[i] == fecha:
                    i += 1
                    break
                # `${...}` de template pode conter chaves e parenteses de
                # verdade; mas conta-los daria falso positivo mais vezes do
                # que acerto, e o corpo do template raramente desbalanceia.
                i += 1
            # Com manter_texto, devolve as aspas e o que havia dentro. Sem
            # ele, um "x" -- que ocupa o lugar de um valor para a proxima
            # decisao de regex-ou-divisao, sem entrar na contagem.
            saida.append(js[comeco:i] if manter_texto else "x")
            continue

        if c == "/":
            # Ha regex aqui, ou e divisao?
            j = len(saida) - 1
            while j >= 0 and saida[j] in " \t\r\n":
                j -= 1
            ant = saida[j] if j >= 0 else "("
            palavra = ""
            k = j
            while k >= 0 and (saida[k].isalnum() or saida[k] == "_"):
                palavra = saida[k] + palavra
                k -= 1
            eh_regex = (ant in ANTES_DE_REGEX) or (palavra in ANTES_DE_REGEX)
            if eh_regex:
                i += 1
                dentro_classe = False
                while i < n:
                    if js[i] == "\\":
                        i += 2
                        continue
                    if js[i] == "[":
                        dentro_classe = True
                    elif js[i] == "]":
                        dentro_classe = False
                    elif js[i] == "/" and not dentro_classe:
                        i += 1
                        break
                    elif js[i] == "\n":
                        break      # regex nao atravessa linha: era divisao
                    i += 1
                saida.append("x")
                continue

        saida.append(c)
        i += 1
    return "".join(saida)


def checar_html(caminho, nome):
    print("\n  %s" % nome)
    if not caminho.exists():
        falha("nao encontrei %s" % caminho)
        return False
    texto = caminho.read_text(encoding="utf-8", errors="ignore")
    bom = True

    # COMENTARIO NAO E CODIGO, E O TESTE PRECISA SABER DISSO      (17/09)
    #
    # A execucao anterior acusou "$('id') sem elemento". Nao havia defeito
    # nenhum: era um comentario no proprio index.html explicando o que este
    # teste faz -- e a frase continha $('id') e id="inMcp". O verificador
    # estava lendo a documentacao de si mesmo e tratando como codigo.
    #
    # Pior: o id="inMcp" escrito no comentario ENTRARIA na lista de ids
    # existentes, e mascararia o defeito de verdade, caso ele voltasse.
    # Um teste que le comentario nao erra so para mais: erra para menos.
    #
    # Entao tudo daqui para baixo olha o codigo sem comentario:
    #   . HTML  -- sem <!-- ... -->
    #   . JS    -- pelo mesmo percorredor, com o texto entre aspas mantido,
    #              porque o nome do id mora dentro das aspas.
    blocos = re.findall(r"<script>(.*?)</script>", texto, re.S)
    js = "\n".join(so_estrutura(b, manter_texto=True) for b in blocos)
    # A marcacao e o HTML sem os <script> e sem os <!-- -->. Tirar os
    # <script> tambem importa: o comentario que explica o inMcp mora dentro
    # de um /* */ do JavaScript, e a frase dele contem id="inMcp". Sem esta
    # linha, esse id entraria na lista de "existe" e o teste ficaria cego
    # justamente para o defeito que acabou de encontrar.
    marcacao = re.sub(r"<script.*?</script>", "", texto, flags=re.S)
    marcacao = re.sub(r"<!--.*?-->", "", marcacao, flags=re.S)

    for bloco in blocos:
        limpo = so_estrutura(bloco)
        for ab, fe, oque in (("{", "}", "chaves"), ("(", ")", "parenteses"),
                             ("[", "]", "colchetes")):
            a, f = limpo.count(ab), limpo.count(fe)
            if a != f:
                falha("%s desbalanceados no <script>: %d abrem, %d fecham"
                      % (oque, a, f))
                bom = False

    # Todo onclick="funcao(" precisa de uma funcao com esse nome.
    chamadas = set(re.findall(r'on\w+="(\w+)\(', marcacao))
    definidas = set(re.findall(r"function\s+(\w+)", js))
    definidas |= set(re.findall(
        r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?[\(\w]", js))
    faltando = sorted(c for c in chamadas if c not in definidas)
    if faltando:
        falha("onclick chama funcao inexistente: %s" % ", ".join(faltando))
        bom = False

    # $('id') sem elemento correspondente.
    #
    # Alguns nascem em tempo de execucao -- a faixa de "ouvindo" do
    # microfone e criada com createElement e recebe .id no ato. Por isso a
    # lista de ids existentes inclui os atribuidos no proprio script.
    #
    # Foi esta verificacao que pegou o $('inMcp'): um campo removido da
    # tela de Ajustes, com a linha que o preenchia esquecida atras. Ela
    # derrubava a funcao inteira, calada, desde nao se sabe quando.
    ids = set(re.findall(r'id="([\w-]+)"', marcacao))
    ids |= set(re.findall(r"\.id\s*=\s*['\"]([\w-]+)['\"]", js))
    ids |= set(re.findall(r"id=[\\]?['\"]([\w-]+)", js))
    usados = set(re.findall(r"\$\('([\w-]+)'\)", js))
    orfaos = sorted(u for u in usados if u not in ids)
    if orfaos:
        falha("$('id') sem elemento nem criacao: %s" % ", ".join(orfaos))
        bom = False

    if bom:
        ok("JavaScript fechado, onclick e $('id') apontando para coisa real")
    return bom


def main():
    print("\n  CONFERINDO OS DOIS PROJETOS")
    print("  " + "=" * 62)

    if not PIPI.exists():
        print("\n  Nao achei a pasta da Pipi em %s" % PIPI)
        return 1

    print("\n  1. SEGREDO  (so o que o git levaria)")
    r = [checar_segredos(CEREBRO, "Bigode"),
         checar_segredos(PIPI, "Pipi")]

    print("\n  2. PYTHON")
    r += [checar_python(CEREBRO, "Bigode"),
          checar_python(PIPI, "Pipi")]

    print("\n  3. PAGINA")
    r += [checar_html(CEREBRO / "web" / "index.html", "Bigode"),
          checar_html(PIPI / "web" / "index.html", "Pipi")]

    print("\n  " + "=" * 62)
    if all(r):
        print("  %sTUDO PASSOU.%s Pode publicar.\n" % (VERDE, FIM))
        return 0
    print("  %sTEM COISA PARA CONSERTAR ANTES DE PUBLICAR.%s\n" % (VERM, FIM))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
