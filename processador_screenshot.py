#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Processa screenshots da extensão Chrome para injetar no contexto da IA.

Converte base64 → arquivo PNG → embed na mensagem da IA.
"""

import base64
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCREENSHOTS_TEMP = BASE / ".screenshots_temp"

def inicializar():
    """Cria pasta temporária para screenshots."""
    SCREENSHOTS_TEMP.mkdir(exist_ok=True)

def salvar_screenshot(base64_data, nome="screenshot.png"):
    """Salva screenshot base64 em arquivo PNG.

    Args:
        base64_data: string começando com 'data:image/jpeg;base64,'
        nome: nome do arquivo (padrão: screenshot.png)

    Returns:
        caminho do arquivo salvo ou None se falhar
    """
    try:
        # Remove header data:image/jpeg;base64, ou data:image/png;base64,
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        # Decodifica
        dados_binarios = base64.b64decode(base64_data)

        # Salva
        caminho = SCREENSHOTS_TEMP / nome
        caminho.write_bytes(dados_binarios)

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
            caminho = salvar_screenshot(screenshot, "navegador_feedback.png")
            return texto, caminho

        return texto, None

    return str(resposta_bruta), None

def injetar_no_contexto(texto_resultado, caminho_screenshot, evento=None):
    """Injeta resultado com screenshot no contexto da IA.

    Se houver screenshot, adiciona instrução para a IA analisar a imagem.

    Args:
        texto_resultado: texto da ação realizada
        caminho_screenshot: caminho do arquivo PNG ou None
        evento: função para enviar notificação (opcional)

    Returns:
        (mensagem_usuario, tem_screenshot)
    """
    if not caminho_screenshot:
        return texto_resultado, False

    # Lê o arquivo e codifica em base64 novamente para enviar ao modelo
    try:
        dados = Path(caminho_screenshot).read_bytes()
        base64_img = base64.b64encode(dados).decode("utf-8")

        msg = f"""{texto_resultado}

[SCREENSHOT DISPONÍVEL]
Arquivo: {caminho_screenshot}
Base64: data:image/png;base64,{base64_img[:100]}...

Analise a imagem acima e compare com o que esperava acontecer.
Se algo não deu certo, corrija ou tente outra abordagem."""

        if evento:
            evento({
                "tipo": "acao",
                "id": "screenshot",
                "estado": "ok",
                "titulo": "Screenshot capturado",
                "resumo": f"Imagem da página após ação ({len(base64_img)//1024}KB)"
            })

        return msg, True
    except Exception as e:
        print(f"Erro ao injetar screenshot: {e}")
        return texto_resultado, False

def limpar_screenshots():
    """Remove arquivos temporários de screenshot."""
    try:
        for arquivo in SCREENSHOTS_TEMP.glob("*.png"):
            arquivo.unlink()
    except Exception:
        pass

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
