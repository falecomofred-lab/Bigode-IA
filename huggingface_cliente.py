"""HUGGING FACE — o motor que cobra por token, nao por segundo
Venure · venure.com.br

O QUE ESTA API E
    O Hugging Face nao aluga placa. Ele e uma PORTARIA: voce manda a
    conversa para um endereco so, com um token so, e ele encaminha para
    quem tem GPU de verdade (Together, Fireworks, Groq, Cerebras...).
    Voce escolhe o MODELO, nao o hardware.

POR QUE ISSO IMPORTA PARA O BIGODE
    A Modal cobra segundo de placa ligada. Uma conversa e quase toda feita
    de tempo em que ninguem esta falando -- voce lendo, pensando, saindo
    para o almoco. Na Modal isso e tempo pago.

    Aqui se paga token. Pausa nao custa nada.

    Medido nos numeros do Fred: 20 mensagens espalhadas no dia, numa L4 a
    $0,80/h com 5 min de espera antes de dormir, dao ~$40/mes -- acima do
    teto de $30. As mesmas 20 mensagens por token, contando generoso em
    200 mil tokens/dia, dao ~$3/mes.

O DEFEITO QUE ESTE ARQUIVO TINHA                            (17/09)
    O `chat` recebia `tools=` e devolvia so isto:

        return str(r.choices[0].message.content or "")

    Quando o modelo decide usar uma ferramenta, ele NAO escreve nada em
    `.content` -- ele preenche `.tool_calls`. Ou seja: a funcao pedia
    ferramenta ao modelo e jogava a resposta no lixo, devolvendo string
    vazia. O Bigode concluia que o modelo tinha ficado calado.

    Era o unico elo que faltava para o navegador autonomo funcionar por
    esta rota. As 7 ferramentas de navegador ja existiam, o esquema ja era
    enviado, o laco de execucao ja rodava. Faltava devolver a chamada.

    Agora quem quer a chamada usa `conversar()`. O `chat()` continua
    existindo e devolvendo texto, para nao quebrar quem so quer texto.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


class HuggingFaceError(RuntimeError):
    pass


# O PADRAO PASSOU A SER O QUE FOI MEDIDO                       (17/09)
#
#   Era Qwen2.5-Coder-32B, escolhido por raciocinio: mesma familia do motor
#   local do Fred, logo menos surpresa. Bom raciocinio, resultado errado --
#   o `--procurar` mostrou que aquele modelo CONVERSA mas nao faz chamada
#   de ferramenta nos provedores da conta dele:
#
#       meta-llama/Llama-3.3-70B-Instruct     SIM  ->  pediu web_buscar
#       Qwen/Qwen2.5-72B-Instruct             SIM  ->  pediu web_buscar
#       Qwen/Qwen2.5-Coder-32B-Instruct       conversa, mas sem ferramenta
#
#   E o pior: o padrao era justamente o que falha. Ele apertou Enter
#   confiando no padrao e caiu no unico que nao serve -- duas vezes.
#
#   Padrao tem que ser o que funciona, nao o que parece elegante.
MODELO_PADRAO = "meta-llama/Llama-3.3-70B-Instruct"


def token():
    """O token, da variavel de ambiente OU do config.json.

    VARIAVEL DE AMBIENTE SOZINHA NAO SERVE                    (17/09)
        Antes so havia `os.environ["HF_TOKEN"]`. Variavel morre quando a
        janela do Prompt fecha -- entao o Bigode funcionava na janela onde
        o token foi definido e em nenhuma outra, inclusive no atalho da
        area de trabalho. Foi o mesmo erro que o motor do Colab teve, e
        que foi resolvido gravando em arquivo.

        A variavel continua ganhando quando existe: quem a define de
        proposito esta mandando, e sobrescrever em silencio seria pior.
    """
    do_ambiente = os.environ.get("HF_TOKEN", "").strip()
    if do_ambiente:
        return do_ambiente
    try:
        import json as _json
        arq = Path(__file__).resolve().parent / "config.json"
        dados = _json.loads(arq.read_text(encoding="utf-8-sig") or "{}")
        return str((dados.get("huggingface") or {}).get("token") or "").strip()
    except Exception:
        return ""


def configurado():
    return bool(token())


def _client():
    try:
        from huggingface_hub import InferenceClient
    except ImportError as exc:
        raise HuggingFaceError(
            "Instale o huggingface_hub para usar o Hugging Face: "
            "python -m pip install huggingface_hub") from exc
    return InferenceClient(token=token() or None)


def _modelo(escolhido=None):
    return (escolhido or os.environ.get("HF_TEXT_MODEL") or MODELO_PADRAO)


def conversar(messages, model=None, temperature=0.45, max_tokens=1200,
              tools=None, ao_receber=None, fluxo=True):
    """Conversa e devolve (texto, chamada_de_ferramenta_ou_None).

    `chamada` sai no formato que o cerebro.py ja usa no motor local:
    ("nome_da_ferramenta", {dicionario de argumentos}). Assim a rota do
    Hugging Face entra no MESMO laco de execucao, sem laco paralelo.

    `ao_receber` recebe o texto acumulado a cada pedaco. A tela do Bigode
    mostra a resposta surgindo palavra por palavra; sem stream ela ficava
    calada e despejava tudo no fim.

    POR QUE REMONTAR OS PEDACOS
        Chamada de ferramenta nao chega inteira. Chega o nome num pedaco e
        o JSON dos argumentos letra por letra nos seguintes. Quem lê um
        pedaco isolado ve `{"url": "htt` e conclui que o modelo errou.
    """
    if not messages:
        raise HuggingFaceError("A conversa está vazia.")

    pedacos = []
    chamadas = {}

    # SEM FLUXO, O ERRO APARECE                                 (17/09)
    #
    #   Com stream=True, quando o roteador do Hugging Face recusa o pedido
    #   (token sem permissao de inferencia, modelo fora dos provedores da
    #   conta, credito zerado), o corpo da resposta vem vazio e o leitor de
    #   fluxo devolve so isto:
    #
    #       Attempted to read or stream content, but the stream has been closed.
    #
    #   Que nao diz nada. O codigo HTTP de verdade -- 401, 402, 404 -- fica
    #   perdido. Por isso quem esta diagnosticando chama com fluxo=False:
    #   a excecao vem com o motivo legivel.
    try:
        if not fluxo:
            r = _client().chat_completion(
                messages=messages,
                model=_modelo(model),
                stream=False,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools or None,
                tool_choice="auto" if tools else None,
            )
            msg = r.choices[0].message
            texto = str(getattr(msg, "content", "") or "")
            if texto:
                pedacos.append(texto)
                if ao_receber:
                    ao_receber(texto)
            for i, tc in enumerate(getattr(msg, "tool_calls", None) or []):
                funcao = getattr(tc, "function", None)
                chamadas[i] = {
                    "nome": str(getattr(funcao, "name", "") or ""),
                    "args": getattr(funcao, "arguments", "") or "",
                }
            return _fechar(pedacos, chamadas)

        corrente = _client().chat_completion(
            messages=messages,
            model=_modelo(model),
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools or None,
            tool_choice="auto" if tools else None,
        )

        for item in corrente:
            try:
                delta = item.choices[0].delta
            except Exception:
                continue

            texto = getattr(delta, "content", None)
            if texto:
                pedacos.append(texto)
                if ao_receber:
                    ao_receber("".join(pedacos))

            for tc in (getattr(delta, "tool_calls", None) or []):
                indice = getattr(tc, "index", 0) or 0
                atual = chamadas.setdefault(indice, {"nome": "", "args": ""})
                funcao = getattr(tc, "function", None)
                nome = getattr(funcao, "name", None) if funcao else None
                args = getattr(funcao, "arguments", None) if funcao else None
                if nome:
                    atual["nome"] = nome
                if args:
                    atual["args"] += args

    except HuggingFaceError:
        raise
    except Exception as exc:
        raise HuggingFaceError(
            _explicar(exc, _modelo(model), com_ferramentas=bool(tools))) from exc

    return _fechar(pedacos, chamadas)


def _fechar(pedacos, chamadas):
    chamada = None
    if chamadas:
        primeira = chamadas[sorted(chamadas)[0]]
        if primeira["nome"]:
            try:
                argumentos = json.loads(primeira["args"] or "{}")
            except Exception:
                # Modelo menor as vezes manda o JSON como string de string.
                try:
                    argumentos = json.loads(json.loads(primeira["args"]))
                except Exception:
                    argumentos = {}
            if not isinstance(argumentos, dict):
                argumentos = {}
            chamada = (primeira["nome"], argumentos)
    return "".join(pedacos), chamada


def _explicar(exc, modelo, com_ferramentas=False):
    """Traduz a recusa do roteador para uma frase que diz o que fazer.

    As recusas pedem acoes diferentes, e o texto cru da biblioteca nao
    separa nenhuma. Mandar a pessoa "conferir a configuracao" quando o
    problema e permissao do token e transferir trabalho sem motivo.

    O MESMO 404 QUER DIZER DUAS COISAS                        (17/09)
        Sem `tools`, 404 e "nenhum provedor serve este modelo".
        Com `tools`, 404 e quase sempre "o provedor serve o modelo, mas
        NAO aceita chamada de ferramenta".

        A diferenca importa porque a acao e outra: no primeiro caso troca-se
        o modelo por qualquer outro; no segundo, por um que faca ferramenta.

        Isto custou uma tentativa perdida: o teste de conversa passou
        ("respondeu: pronto") e logo abaixo a minha mensagem dizia que
        nenhum provedor servia o modelo -- contradizendo a linha anterior.
    """
    bruto = "%s: %s" % (type(exc).__name__, exc)
    baixo = bruto.lower()
    codigo = getattr(getattr(exc, "response", None), "status_code", None)

    if codigo == 401 or "401" in baixo or "unauthorized" in baixo or "invalid cred" in baixo:
        return ("O Hugging Face recusou o token (401). Se ele e do tipo "
                "fine-grained, ler nao basta: marque a permissao "
                "\"Make calls to Inference Providers\" em "
                "https://huggingface.co/settings/tokens e gere outro.")
    if codigo == 402 or "402" in baixo or "payment" in baixo or "credits" in baixo:
        return ("O credito de inferencia da sua conta acabou (402). Veja em "
                "https://huggingface.co/settings/billing -- conta gratuita tem "
                "uma cota pequena por mes; a PRO inclui mais.")
    if codigo == 404 or "404" in baixo or "not supported" in baixo or "no provider" in baixo:
        if com_ferramentas:
            return ("O provedor serve %s para conversar, mas NAO aceita "
                    "chamada de ferramenta (404 so com tools). Sem ferramenta "
                    "o Bigode nao le arquivo, nao busca na web e nao mexe no "
                    "navegador. Rode `python usar_huggingface.py --procurar` "
                    "para descobrir quais modelos da sua conta fazem "
                    "ferramenta." % modelo)
        return ("Nenhum provedor da sua conta serve %s (404). Abra a pagina do "
                "modelo no Hugging Face e veja a caixa \"Inference Providers\"; "
                "se estiver vazia, escolha outro modelo." % modelo)
    if codigo == 429 or "429" in baixo or "rate limit" in baixo:
        return ("Muitos pedidos em pouco tempo (429). Espere um minuto e "
                "tente de novo.")
    if "stream has been closed" in baixo:
        return ("O roteador fechou a conexao sem dizer por que. Quase sempre e "
                "uma destas tres: (1) o token nao tem a permissao \"Make calls "
                "to Inference Providers\"; (2) nenhum provedor da sua conta "
                "serve %s; (3) o credito de inferencia acabou. "
                "Rode `python usar_huggingface.py` de novo -- ele testa sem "
                "fluxo e mostra o codigo de verdade." % modelo)
    return "Hugging Face falhou (%s): %s" % (modelo, bruto[:300])


def chat(messages, model=None, temperature=0.45, max_tokens=1200, tools=None):
    """Atalho de quem so quer o texto. Ver `conversar` para ferramentas."""
    texto, _chamada = conversar(messages, model=model, temperature=temperature,
                                max_tokens=max_tokens, tools=tools)
    return texto


def text_to_image(prompt, model=None, negative_prompt=None, width=None,
                  height=None, steps=None, guidance=None, seed=None):
    """Imagem pelo Hugging Face.

    Mantido como reserva. Quem desenha na Venure e a Pipi, na Modal, onde
    cobrar por segundo e barato: 4 segundos de L40S por imagem.
    """
    if not prompt.strip():
        raise HuggingFaceError("O prompt de imagem está vazio.")
    try:
        return _client().text_to_image(
            prompt=prompt,
            model=model or os.environ.get("HF_IMAGE_MODEL"),
            negative_prompt=negative_prompt or None,
            width=width, height=height,
            num_inference_steps=steps, guidance_scale=guidance, seed=seed)
    except Exception as exc:
        raise HuggingFaceError("Hugging Face imagem falhou: %s" % exc) from exc


def download(repo_id, filename, destination, revision=None):
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise HuggingFaceError("Instale huggingface_hub para baixar modelos.") from exc
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        cached = hf_hub_download(repo_id=repo_id, filename=filename,
                                 revision=revision)
        dest.write_bytes(Path(cached).read_bytes())
        return str(dest)
    except Exception as exc:
        raise HuggingFaceError("Download Hugging Face falhou: %s" % exc) from exc


def status():
    return {
        "configurado": configurado(),
        "token_presente": bool(token()),
        "texto_modelo": _modelo(),
        "imagem_modelo": os.environ.get("HF_IMAGE_MODEL", ""),
        "ferramentas": True,      # desde 17/09: conversar() devolve tool_calls
        "fluxo": True,            # e transmite palavra por palavra
    }


if __name__ == "__main__":
    print(json.dumps(status(), ensure_ascii=False, indent=2))
