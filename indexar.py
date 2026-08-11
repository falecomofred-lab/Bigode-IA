#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INDEXAR - alimenta a memoria do Cerebro

Le a pasta de projetos (Google Drive) e, opcionalmente, seus repositorios do
GitHub, e gera um arquivo .md por projeto dentro de memoria/projetos/.

Uso:  python indexar.py
"""

import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
DESTINO = BASE / "memoria" / "projetos"

IGNORAR_PASTAS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".idea",
    ".vscode", "dist", "build", ".next", "vendor", ".cache", "site-packages",
    ".pytest_cache", "coverage", ".claude",
}
IGNORAR_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".mp4", ".mov",
    ".mp3", ".wav", ".zip", ".rar", ".7z", ".exe", ".dll", ".gguf", ".bin",
    ".pdf", ".psd", ".ai", ".ttf", ".woff", ".woff2", ".pyc", ".db", ".sqlite",
}
ARQUIVOS_CHAVE = [
    "readme.md", "readme.txt", "package.json", "requirements.txt",
    "composer.json", "pyproject.toml", "docker-compose.yml", "index.html",
    "app.py", "main.py", "index.php", "manifest.json",
]
STACKS = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "React", ".tsx": "React/TS", ".php": "PHP", ".html": "HTML",
    ".css": "CSS", ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell",
    ".java": "Java", ".go": "Go", ".rb": "Ruby", ".dart": "Dart",
}


def limpar_nome(texto):
    return re.sub(r"[^a-zA-Z0-9_\-]+", "_", texto).strip("_")[:80]


def ler_trecho(caminho, limite=2500):
    try:
        return caminho.read_text(encoding="utf-8", errors="ignore")[:limite].strip()
    except Exception:
        return ""


def varrer(pasta, limite_arquivos=400):
    arquivos, stacks = [], {}
    for caminho in pasta.rglob("*"):
        if len(arquivos) >= limite_arquivos:
            break
        if any(parte in IGNORAR_PASTAS for parte in caminho.parts):
            continue
        if not caminho.is_file():
            continue
        ext = caminho.suffix.lower()
        if ext in IGNORAR_EXT:
            continue
        arquivos.append(caminho)
        if ext in STACKS:
            stacks[STACKS[ext]] = stacks.get(STACKS[ext], 0) + 1
    return arquivos, stacks


def indexar_projeto(pasta):
    arquivos, stacks = varrer(pasta)
    if not arquivos:
        return None

    linhas = []
    linhas.append("# PROJETO: " + pasta.name)
    linhas.append("")
    linhas.append("- Caminho: `" + str(pasta) + "`")
    linhas.append("- Arquivos mapeados: " + str(len(arquivos)))

    if stacks:
        ordenado = sorted(stacks.items(), key=lambda x: x[1], reverse=True)
        linhas.append("- Tecnologias: " + ", ".join(
            "%s (%d)" % (nome, qtd) for nome, qtd in ordenado[:6]
        ))

    try:
        recente = max(arquivos, key=lambda a: a.stat().st_mtime)
        data = datetime.fromtimestamp(recente.stat().st_mtime).strftime("%d/%m/%Y")
        linhas.append("- Ultima alteracao: " + data + " (" + recente.name + ")")
    except Exception:
        pass

    linhas.append("")
    linhas.append("## Estrutura")
    linhas.append("")
    mostrados = 0
    for arquivo in sorted(arquivos, key=lambda a: str(a).lower()):
        if mostrados >= 120:
            linhas.append("- ... (+%d arquivos)" % (len(arquivos) - mostrados))
            break
        try:
            relativo = arquivo.relative_to(pasta)
        except ValueError:
            continue
        linhas.append("- " + str(relativo).replace("\\", "/"))
        mostrados += 1

    principais = [a for a in arquivos if a.name.lower() in ARQUIVOS_CHAVE][:5]
    if principais:
        linhas.append("")
        linhas.append("## Conteudo dos arquivos principais")
        for arquivo in principais:
            trecho = ler_trecho(arquivo)
            if not trecho:
                continue
            linhas.append("")
            linhas.append("### " + arquivo.name)
            linhas.append("")
            linhas.append("```")
            linhas.append(trecho)
            linhas.append("```")

    return "\n".join(linhas)


def indexar_drive(config):
    raiz = Path(config.get("pasta_projetos", ""))
    if not raiz.exists():
        print("  [!] Pasta nao encontrada: " + str(raiz))
        return 0

    print("  Lendo: " + str(raiz))
    total = 0
    for pasta in sorted(raiz.iterdir()):
        if not pasta.is_dir() or pasta.name in IGNORAR_PASTAS:
            continue
        conteudo = indexar_projeto(pasta)
        if not conteudo:
            continue
        destino = DESTINO / (limpar_nome(pasta.name) + ".md")
        destino.write_text(conteudo, encoding="utf-8")
        print("  + " + pasta.name)
        total += 1
    return total


def api_github(url, token):
    cabecalhos = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Cerebro-Venure",
    }
    if token:
        cabecalhos["Authorization"] = "Bearer " + token
    pedido = urllib.request.Request(url, headers=cabecalhos)
    with urllib.request.urlopen(pedido, timeout=25) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def indexar_github(config):
    usuario = (config.get("github_usuario") or "").strip()
    token = (config.get("github_token") or "").strip()
    if not usuario and not token:
        print("  (sem github_usuario/github_token no config.json — pulando)")
        return 0

    try:
        if token:
            url = "https://api.github.com/user/repos?per_page=100&sort=updated"
        else:
            url = "https://api.github.com/users/%s/repos?per_page=100&sort=updated" % usuario
        repositorios = api_github(url, token)
    except urllib.error.HTTPError as erro:
        print("  [!] GitHub respondeu %s — verifique usuario/token" % erro.code)
        return 0
    except Exception as erro:
        print("  [!] Falha ao falar com o GitHub: " + str(erro))
        return 0

    total = 0
    for repo in repositorios:
        nome = repo.get("name", "")
        linhas = []
        linhas.append("# REPOSITORIO GITHUB: " + nome)
        linhas.append("")
        linhas.append("- URL: " + repo.get("html_url", ""))
        linhas.append("- Descricao: " + (repo.get("description") or "sem descricao"))
        linhas.append("- Linguagem: " + (repo.get("language") or "nao identificada"))
        linhas.append("- Visibilidade: " + ("privado" if repo.get("private") else "publico"))
        linhas.append("- Atualizado em: " + (repo.get("updated_at") or "")[:10])

        try:
            leiame = api_github(
                "https://api.github.com/repos/%s/%s/readme"
                % (repo["owner"]["login"], nome), token
            )
            import base64
            texto = base64.b64decode(leiame.get("content", "")).decode("utf-8", "ignore")
            if texto.strip():
                linhas.append("")
                linhas.append("## README")
                linhas.append("")
                linhas.append(texto[:3000])
        except Exception:
            pass

        destino = DESTINO / ("gh_" + limpar_nome(nome) + ".md")
        destino.write_text("\n".join(linhas), encoding="utf-8")
        print("  + gh:" + nome)
        total += 1
    return total


def main():
    config = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    DESTINO.mkdir(parents=True, exist_ok=True)

    print("=" * 58)
    print("  INDEXANDO A MEMORIA DO CEREBRO")
    print("=" * 58)

    print("\n[1] Google Drive")
    n1 = indexar_drive(config)

    print("\n[2] GitHub")
    n2 = indexar_github(config)

    print("\n" + "=" * 58)
    print("  Concluido: %d projetos do Drive + %d repositorios" % (n1, n2))
    print("  Memoria em: " + str(DESTINO))
    print("=" * 58)


if __name__ == "__main__":
    main()
