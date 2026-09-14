"""Cliente mínimo do endpoint Modal do Bigode IA.

O endpoint remoto recebe o mesmo conjunto de mensagens usado pelo Bigode, mas
retorna uma resposta JSON normalizada. O cliente não guarda nem imprime tokens.
"""
import json
import urllib.error
import urllib.request


class ModalError(RuntimeError):
    pass


def configurado(cfg):
    modal = cfg.get("modal") or {}
    return bool(modal.get("ativo") and modal.get("url"))


def gerar(cfg, mensagens, temperatura=0.45, max_tokens=1200, timeout=1800):
    modal = cfg.get("modal") or {}
    url = (modal.get("url") or "").strip()
    if not url:
        raise ModalError("URL do Modal não configurada.")
    ultimo = mensagens[-1].get("content", "") if mensagens else ""
    payload = {
        "messages": mensagens,
        # Compatibilidade com a primeira publicação, que aceitava somente
        # `prompt`. Depois do redeploy o campo messages será usado pelo
        # endpoint atualizado, mas enviar ambos permite atualização gradual.
        "prompt": str(ultimo),
        "temperature": float(temperatura),
        "max_tokens": int(max_tokens),
        "stream": False,
    }
    token = (modal.get("token") or "").strip()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    pedido = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            bruto = resposta.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", "replace")[:500]
        raise ModalError("Modal HTTP %s: %s" % (erro.code, detalhe)) from erro
    except Exception as erro:
        raise ModalError("Não foi possível acessar o Modal: %s" % erro) from erro
    try:
        dados = json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise ModalError("Modal devolveu JSON inválido.") from erro
    if dados.get("erro"):
        raise ModalError(str(dados["erro"]))

    # A TRAVA DO ESQUELETO   (13/09)
    #
    #     O endpoint publicado hoje (`modal_api_teste.py`) nao carrega
    #     modelo nenhum. Ele devolve:
    #
    #         {"ok": true,
    #          "mensagem": "Processamento simulado com sucesso.",
    #          "media_url": "https://exemplo.invalid/..."}
    #
    #     E a leitura logo abaixo aceita justamente o campo `mensagem` como
    #     resposta do modelo. Sem esta trava, ligar `modelo_provedor: modal`
    #     fazia o Bigode responder "Processamento simulado com sucesso." a
    #     QUALQUER pergunta -- parecendo que tinha funcionado.
    #
    #     Mentir em silencio e pior do que falhar. Aqui ele falha, e diz o
    #     que falta fazer.
    if _e_esqueleto(dados):
        raise ModalError(
            "O endpoint da Modal ainda e o de teste: ele devolve uma "
            "resposta simulada, nao um modelo. Publique um endpoint de "
            "verdade (com GPU e pesos) ou volte modelo_provedor para "
            "\"local\".")

    texto = dados.get("text") or dados.get("resposta") or dados.get("mensagem")
    if not texto:
        try:
            texto = dados["choices"][0]["message"].get("content", "")
        except (KeyError, IndexError, TypeError):
            texto = ""
    return {"texto": str(texto), "raw": dados}


def _e_esqueleto(dados):
    """Reconhece a resposta do endpoint de contrato, sem carregar modelo.

    Tres marcas, qualquer uma basta -- o endpoint pode mudar um pouco sem
    deixar de ser um esqueleto:

      * ecoa de volta o que recebeu (`prompt_recebido`)
      * aponta para um dominio reservado, que nunca existira (`.invalid`)
      * diz literalmente que simulou
    """
    if not isinstance(dados, dict):
        return False
    if "prompt_recebido" in dados:
        return True
    if ".invalid" in str(dados.get("media_url", "")):
        return True
    texto = str(dados.get("mensagem", "")).lower()
    return "simulad" in texto


def status(cfg, timeout=8):
    modal = cfg.get("modal") or {}
    url = (modal.get("health_url") or modal.get("url") or "").strip()
    if not url:
        return {"configurado": False, "online": False, "erro": "URL ausente"}
    try:
        pedido = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
            return {"configurado": True, "online": 200 <= resposta.status < 500,
                    "http": resposta.status}
    except urllib.error.HTTPError as erro:
        return {"configurado": True, "online": erro.code < 500, "http": erro.code}
    except Exception as erro:
        return {"configurado": True, "online": False, "erro": str(erro)[:240]}
