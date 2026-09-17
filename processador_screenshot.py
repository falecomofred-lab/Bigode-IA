#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa screenshots da extensão Chrome para injetar no contexto da IA.

Converte base64 → arquivo PNG/JPEG → embed na mensagem da IA.
Com cache e otimização para múltiplas queries.
"""

import base64
import json
import re
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCREENSHOTS_TEMP = BASE / ".screenshots_temp"
CACHE_SCREENSHOTS = {}

def inicializar():
    """Cria pasta temporária para screenshots."""
    SCREENSHOTS_TEMP.mkdir(exist_ok=True)
    global CACHE_SCREENSHOTS
    CACHE_SCREENSHOTS = {}

def salvar_screenshot(base64_data, nome=None):
    """Salva screenshot base64 em arquivo PNG/JPEG.

    Args:
        base64_data: string começando com 'data:image/jpeg;base64,' ou similar
        nome: nome do arquivo (padrão: auto-gerado com timestamp)

    Returns:
        caminho do arquivo salvo ou None se falhar
    """
    try:
        # Remove header data:image/jpeg;base64, ou data:image/png;base64,
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        # Decodifica
        dados_binarios = base64.b64decode(base64_data)
        tamanho_kb = len(dados_binarios) / 1024

        # Gera nome único se não fornecido
        if not nome:
            timestamp = int(time.time() * 1000) % 1000000
            nome = f"screenshot_{timestamp}.jpg"

        # Salva
        caminho = SCREENSHOTS_TEMP / nome
        caminho.write_bytes(dados_binarios)

        # Cache para reutilizar em próximas queries
        CACHE_SCREENSHOTS[nome] = {
            "caminho": str(caminho),
            "tamanho_kb": tamanho_kb,
            "timestamp": time.time()
        }

        return str(caminho)
    except Exception as e:
        print(f"Erro ao salvar screenshot: {e}")
        return None

def processar_resposta_extensao(resposta_bruta):
    """Processa resposta da extensão que pode conter screenshot.

    Args:
        resposta_bruta: string ou dict com resultado da ação

    Returns:
        (texto, caminho_screenshot) ou (texto, None)
    """
    if isinstance(resposta_bruta, str):
        return resposta_bruta, None

    if isinstance(resposta_bruta, dict):
        texto = resposta_bruta.get("texto", str(resposta_bruta))
        screenshot = resposta_bruta.get("screenshot")

        if screenshot and resposta_bruta.get("tipo_screenshot") == "jpeg_base64":
            # Gera nome único para este screenshot
            timestamp = int(time.time() * 1000) % 1000000
            nome_arquivo = f"screen_{timestamp}.jpg"
            caminho = salvar_screenshot(screenshot, nome_arquivo)
            return texto, caminho

        return texto, None

    return str(resposta_bruta), None

def injetar_no_contexto(texto_resultado, caminho_screenshot, evento=None):
    """Injeta resultado com screenshot no contexto da IA.

    Se houver screenshot, adiciona instrução para a IA analisar a imagem.

    Args:
        texto_resultado: texto da ação realizada
        caminho_screenshot: caminho do arquivo PNG/JPEG ou None
        evento: função para enviar notificação (opcional)

    Returns:
        (mensagem_usuario, tem_screenshot)
    """
    if not caminho_screenshot:
        return texto_resultado, False

    # Lê o arquivo e codifica em base64 novamente para enviar ao modelo
    try:
        dados = Path(caminho_screenshot).read_bytes()
        tamanho_kb = len(dados) / 1024
        base64_img = base64.b64encode(dados).decode("utf-8")

        # Limita base64 a 70KB para ficar dentro do contexto
        if len(base64_img) > 70000:
            # Se ainda muito grande, não injeta (consome muitos tokens)
            print(f"Screenshot {tamanho_kb:.1f}KB muito grande, pulando injeção")
            if evento:
                evento({
                    "tipo": "acao",
                    "id": "screenshot",
                    "estado": "aviso",
                    "titulo": "Screenshot capturado",
                    "resumo": f"Imagem {tamanho_kb:.1f}KB (muita grande para injetar)"
                })
            return texto_resultado, False

        # Prepara mensagem com instrução clara
        msg = f"""{texto_resultado}

[SCREENSHOT DISPONÍVEL]
Imagem capturada ({tamanho_kb:.1f}KB)
Base64: data:image/jpeg;base64,{base64_img[:80]}...

⚠️ INSTRUÇÃO: Analise essa imagem e descreva exatamente o que vê.
Compare o resultado com o que você esperava que acontecesse.
Se algo não deu certo, tente uma abordagem diferente."""

        if evento:
            evento({
                "tipo": "acao",
                "id": "screenshot",
                "estado": "ok",
                "titulo": "Screenshot injetado",
                "resumo": f"Imagem {tamanho_kb:.1f}KB no contexto"
            })

        return msg, True
    except Exception as e:
        print(f"Erro ao injetar screenshot: {e}")
        if evento:
            evento({
                "tipo": "acao",
                "id": "screenshot",
                "estado": "erro",
                "titulo": "Falha ao injetar screenshot",
                "resumo": str(e)[:100]
            })
        return texto_resultado, False

def limpar_screenshots(manter_ultimos=5):
    """Remove screenshots antigos, mantendo os mais recentes.

    Args:
        manter_ultimos: quantos screenshots mais recentes manter (padrão: 5)
    """
    try:
        arquivos = sorted(
            SCREENSHOTS_TEMP.glob("*.jpg"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        # Remove os antigos, mantém os últimos N
        for arquivo in arquivos[manter_ultimos:]:
            arquivo.unlink()

        # Limpa cache de screenshots removidos
        global CACHE_SCREENSHOTS
        arquivos_atuais = {f.name for f in SCREENSHOTS_TEMP.glob("*.jpg")}
        CACHE_SCREENSHOTS = {k: v for k, v in CACHE_SCREENSHOTS.items()
                            if k in arquivos_atuais}
    except Exception as e:
        print(f"Erro ao limpar screenshots: {e}")

if __name__ == "__main__":
    # Teste
    inicializar()

    # Simula resposta da extensão com screenshot
    resposta_fake = {
        "texto": "Cliquei no botão",
        "screenshot": "data:image/jpeg;base64,/9j/4AAQSkZJRgABA...",  # truncado
        "tipo_screenshot": "jpeg_base64"
    }

    texto, caminho = processar_resposta_extensao(resposta_fake)
    print(f"Texto: {texto}")
    print(f"Caminho screenshot: {caminho}")

    if caminho:
        msg, tem_ss = injetar_no_contexto(texto, caminho)
        print(f"\nMensagem injetada:\n{msg[:200]}...")

    limpar_screenshots()
