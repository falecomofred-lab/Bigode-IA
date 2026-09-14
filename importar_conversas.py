"""IMPORTAR CONVERSAS — Bigode IA

Pega as conversas que voce ja teve com Claude, ChatGPT ou Gemini e transforma
em arquivos Markdown dentro de uma pasta comum de arquivos .md,
que o Bigode já sabe ler com `buscar` e `ler_arquivo`.

Por que isso vale: o conhecimento das suas conversas hoje esta preso dentro
do site de cada empresa. Em Markdown, ele fica no seu computador, entra na
busca do Bigode, e passa a valer como FONTE -- ou seja, resposta baseada nele
sai carimbada como verificada em vez de "nao conferi".

    python importar_conversas.py                     procura na pasta Downloads
    python importar_conversas.py C:\\caminho\\arquivo.zip
    python importar_conversas.py --destino "G:\\...\\Cerebro-Memoria"

Formatos que ele entende:

    Claude ....... conversations.json (dentro do .zip da exportacao)
    ChatGPT ...... conversations.json (dentro do .zip da exportacao)
    Gemini ....... .html do Google Takeout

Nada e enviado para lugar nenhum. Tudo acontece no seu computador.

COMO EXPORTAR
    Claude   Configuracoes -> Privacidade -> Exportar dados. Chega por e-mail.
    ChatGPT  Configuracoes -> Controles de dados -> Exportar. Chega por e-mail.
    Gemini   takeout.google.com -> selecione "Meus Atividades" / Gemini.

Venure — venure.com.br · tecnologia propria
"""

import argparse
import datetime
import html
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
PADRAO_DESTINO = Path(r"G:\Meu Drive\projetos\Cerebro-Memoria")

# Quais pastas o destino de memória tem. Existir vazia e melhor que nao existir: mostra
# onde as coisas vao.
ESTRUTURA = ["Conversas/Claude", "Conversas/ChatGPT", "Conversas/Gemini",
             "Conhecimento", "Projetos", "Decisoes"]


# ==========================================================================
# Utilidades
# ==========================================================================

def limpar_nome(texto, tamanho=70):
    """Vira nome de arquivo que o Windows aceita, sem perder o sentido."""
    texto = (texto or "sem titulo").strip()
    texto = unicodedata.normalize("NFKC", texto)
    texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", texto)   # proibidos no Windows
    texto = re.sub(r"\s+", " ", texto).strip(" .")
    return (texto[:tamanho].strip() or "sem titulo")


def data_de(valor):
    """Aceita segundos, milissegundos ou texto ISO. Devolve AAAA-MM-DD."""
    if not valor:
        return "sem-data"
    try:
        if isinstance(valor, (int, float)):
            seg = valor / 1000 if valor > 1e11 else valor
            return datetime.datetime.fromtimestamp(seg).strftime("%Y-%m-%d")
        texto = str(valor).replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(texto).strftime("%Y-%m-%d")
    except Exception:
        return "sem-data"


def texto_da_mensagem(m):
    """O conteudo pode vir de tres jeitos diferentes conforme a empresa."""
    # Claude novo: content = [{"type": "text", "text": "..."}]
    partes = m.get("content")
    if isinstance(partes, list):
        fora = []
        for p in partes:
            if isinstance(p, dict):
                if p.get("type") == "text" and p.get("text"):
                    fora.append(p["text"])
            elif isinstance(p, str):
                fora.append(p)
        if fora:
            return "\n\n".join(fora)
    if isinstance(partes, str):
        return partes
    # Claude antigo
    if m.get("text"):
        return m["text"]
    # ChatGPT: content = {"parts": [...]}
    if isinstance(partes, dict) and isinstance(partes.get("parts"), list):
        return "\n\n".join(str(x) for x in partes["parts"] if x)
    return ""


# ==========================================================================
# Leitores por formato
# ==========================================================================

def ler_claude(dados):
    """A exportacao do Claude: lista de conversas com `chat_messages`."""
    for c in dados:
        if not isinstance(c, dict):
            continue
        msgs = []
        for m in c.get("chat_messages") or []:
            quem = "voce" if m.get("sender") == "human" else "assistente"
            corpo = texto_da_mensagem(m).strip()
            if corpo:
                msgs.append((quem, corpo))
        if msgs:
            yield {"id": c.get("uuid") or c.get("id") or "",
                   "titulo": c.get("name") or "",
                   "data": data_de(c.get("created_at")),
                   "mensagens": msgs}


def ler_chatgpt(dados):
    """A exportacao do ChatGPT: cada conversa e um GRAFO (`mapping`), nao uma
    lista. Ordenamos pelo horario de cada mensagem."""
    for c in dados:
        if not isinstance(c, dict) or "mapping" not in c:
            continue
        brutas = []
        for no in (c.get("mapping") or {}).values():
            m = (no or {}).get("message")
            if not m:
                continue
            papel = ((m.get("author") or {}).get("role") or "")
            if papel not in ("user", "assistant"):
                continue
            corpo = texto_da_mensagem(m).strip()
            if corpo:
                brutas.append((m.get("create_time") or 0,
                               "voce" if papel == "user" else "assistente",
                               corpo))
        brutas.sort(key=lambda x: x[0])
        if brutas:
            yield {"id": c.get("id") or c.get("conversation_id") or "",
                   "titulo": c.get("title") or "",
                   "data": data_de(c.get("create_time")),
                   "mensagens": [(q, t) for _, q, t in brutas]}


def ler_gemini_html(caminho):
    """O Takeout entrega HTML. Sem biblioteca externa, o que da para fazer com
    honestidade e separar os blocos e limpar as marcacoes -- o resultado e mais
    tosco que os outros dois, e o arquivo avisa isso."""
    try:
        bruto = Path(caminho).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    blocos = re.split(r'<div class="outer-cell', bruto)[1:]
    for i, b in enumerate(blocos, 1):
        limpo = re.sub(r"<br\s*/?>", "\n", b)
        limpo = re.sub(r"<[^>]+>", " ", limpo)
        limpo = html.unescape(re.sub(r"[ \t]+", " ", limpo)).strip()
        if len(limpo) < 40:
            continue
        achou = re.search(r"\d{1,2} de \w+ de \d{4}|\d{4}-\d{2}-\d{2}", limpo)
        yield {"id": "gemini-%d" % i,
               "titulo": limpo.split("\n")[0][:70],
               "data": data_de(achou.group(0)) if achou else "sem-data",
               "mensagens": [("registro", limpo)],
               "tosco": True}


# ==========================================================================
# Escrita
# ==========================================================================

def escrever(conversa, fonte, destino):
    """Um arquivo .md por conversa, com cabeçalho compatível com o projeto."""
    pasta = destino / "Conversas" / fonte
    pasta.mkdir(parents=True, exist_ok=True)
    nome = "%s - %s.md" % (conversa["data"], limpar_nome(conversa["titulo"]))
    destino = pasta / nome

    # Dois arquivos com o mesmo titulo no mesmo dia acontecem. Numera em vez
    # de sobrescrever: perder conversa importada e pior que ter duas.
    n = 2
    while destino.exists():
        destino = pasta / ("%s - %s (%d).md" % (
            conversa["data"], limpar_nome(conversa["titulo"]), n))
        n += 1

    linhas = [
        "---",
        "fonte: %s" % fonte,
        "data: %s" % conversa["data"],
        "id: %s" % conversa["id"],
        "tags: [conversa, %s]" % fonte.lower(),
        "---",
        "",
        "# %s" % (conversa["titulo"] or "Sem título"),
        "",
        "*Conversa com %s em %s. Importada automaticamente.*"
        % (fonte, conversa["data"]),
        "",
    ]
    if conversa.get("tosco"):
        linhas += ["> [!warning] Importação aproximada",
                   "> O Gemini exporta em HTML e a separação entre pergunta e",
                   "> resposta se perde. O texto abaixo está como veio.", ""]
    linhas.append("---")
    linhas.append("")

    for quem, corpo in conversa["mensagens"]:
        linhas.append("## %s" % ("Você" if quem == "voce"
                                 else "Assistente" if quem == "assistente"
                                 else "Registro"))
        linhas.append("")
        linhas.append(corpo)
        linhas.append("")

    destino.write_text("\n".join(linhas), encoding="utf-8")
    return destino


def ja_importados(destino):
    """Os ids que ja estao no destino de memória. Sem isso, rodar duas vezes duplica tudo."""
    vistos = set()
    pasta = destino / "Conversas"
    if not pasta.is_dir():
        return vistos
    for a in pasta.rglob("*.md"):
        try:
            for linha in a.read_text(encoding="utf-8",
                                     errors="ignore").splitlines()[:8]:
                if linha.startswith("id: ") and linha[4:].strip():
                    vistos.add(linha[4:].strip())
                    break
        except Exception:
            continue
    return vistos


# ==========================================================================
# Descoberta dos arquivos de entrada
# ==========================================================================

def jsons_de(caminho):
    """Devolve (nome_do_arquivo, dados) de cada JSON, entrando no zip se preciso."""
    caminho = Path(caminho)
    if caminho.is_dir():
        for a in sorted(caminho.rglob("*")):
            if a.is_file() and a.suffix.lower() in (".zip", ".json"):
                for par in jsons_de(a):
                    yield par
        return

    if caminho.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(caminho) as z:
                for nome in z.namelist():
                    if nome.lower().endswith(".json"):
                        try:
                            yield (caminho.name + "/" + nome,
                                   json.loads(z.read(nome).decode("utf-8", "ignore")))
                        except Exception:
                            continue
        except Exception:
            pass
        return

    if caminho.suffix.lower() == ".json":
        try:
            yield (caminho.name,
                   json.loads(caminho.read_text(encoding="utf-8", errors="ignore")))
        except Exception:
            pass


def qual_formato(dados):
    """Descobre de quem e a exportacao olhando o conteudo, nao o nome."""
    if not isinstance(dados, list) or not dados:
        return None
    amostra = next((x for x in dados if isinstance(x, dict)), None)
    if not amostra:
        return None
    if "chat_messages" in amostra:
        return "Claude"
    if "mapping" in amostra:
        return "ChatGPT"
    return None


# ==========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada", nargs="?", default="",
                    help="arquivo .zip/.json/.html, ou uma pasta")
    ap.add_argument("--destino", default=str(PADRAO_DESTINO))
    args = ap.parse_args()

    destino = Path(args.destino)
    entrada = Path(args.entrada) if args.entrada else Path.home() / "Downloads"

    print()
    print("=" * 70)
    print("  IMPORTAR CONVERSAS PARA O DESTINO")
    print("=" * 70)
    print("  Procurando em: %s" % entrada)
    print("  Destino .....: %s" % destino)

    if not entrada.exists():
        print("\n  Esse caminho não existe.\n")
        return 1

    for sub in ESTRUTURA:
        (destino / sub).mkdir(parents=True, exist_ok=True)

    vistos = ja_importados(destino)
    if vistos:
        print("  Já no destino de memória..: %d conversa(s)" % len(vistos))
    print()

    total, pulados = 0, 0

    # ---------- JSON: Claude e ChatGPT ----------
    for nome, dados in jsons_de(entrada):
        fonte = qual_formato(dados)
        if not fonte:
            continue
        print("  %s  →  %s" % (nome[:46], fonte))
        leitor = ler_claude if fonte == "Claude" else ler_chatgpt
        n = 0
        for conversa in leitor(dados):
            if conversa["id"] and conversa["id"] in vistos:
                pulados += 1
                continue
            escrever(conversa, fonte, destino)
            if conversa["id"]:
                vistos.add(conversa["id"])
            n += 1
            total += 1
        print("     %d nova(s)" % n)

    # ---------- HTML: Gemini ----------
    htmls = ([entrada] if entrada.is_file() and entrada.suffix.lower() == ".html"
             else (sorted(entrada.rglob("*.html")) if entrada.is_dir() else []))
    for a in htmls[:20]:
        n = 0
        for conversa in ler_gemini_html(a):
            escrever(conversa, "Gemini", destino)
            n += 1
            total += 1
        if n:
            print("  %s  →  Gemini: %d bloco(s)" % (a.name[:46], n))

    # ---------- resultado ----------
    print()
    print("=" * 70)
    if total:
        print("  %d conversa(s) importada(s)." % total)
        if pulados:
            print("  %d já estavam no destino de memória e foram puladas." % pulados)
        print()
        print("  Agora libere o destino de memória para o Bigode:")
        print("    Configurações → Onde ele pode entrar → acrescente a linha")
        print("    %s" % destino)
        print()
        print("  Depois pergunte a ele, por exemplo:")
        print('    "Busque no meu destino o que eu conversei sobre <assunto>"')
    else:
        print("  Não achei exportação nenhuma em %s." % entrada)
        print()
        print("  COMO EXPORTAR:")
        print("    Claude   Configurações → Privacidade → Exportar dados")
        print("    ChatGPT  Configurações → Controles de dados → Exportar")
        print("    Gemini   takeout.google.com")
        print()
        print("  Chega um .zip por e-mail. Aponte para ele:")
        print("    python importar_conversas.py C:\\...\\exportacao.zip")
    print()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n\n  Cancelado.\n")
        raise SystemExit(130)
