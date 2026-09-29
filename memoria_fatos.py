# -*- coding: utf-8 -*-
"""
MEMORIA DE FATOS DO BIGODE -- ele lembra o que voce disse    (28/09/2026)

Ideia do mem0 (github.com/mem0ai/mem0), sem instalar o mem0:

    1. Depois de cada resposta, um modelo le SO a sua mensagem e tira dela
       os fatos que valem para o futuro ("prefiro respostas curtas",
       "o site da Soul usa verde-agua", "meu cliente se chama Ana").
    2. Compara com o que ja sabia: ADICIONA o novo, ATUALIZA o que mudou,
       APAGA o que voce desmentiu. Nada de fato repetido.
    3. Na pergunta seguinte, os fatos que tem a ver com ela entram no
       prompt -- filtrados pelo especialista e pelo projeto ativos.

Onde fica:  memoria/fatos.json  (um arquivo legivel; da para abrir e editar)
Desligar:   "memoria_fatos": false  no config.json, ou pelo painel Memoria.

Por que um JSON e nao o ChromaDB: o ChromaDB deste PC ja caiu tres vezes
("Could not connect to tenant"). Fato pessoal e coisa de dezenas a poucas
centenas de linhas -- busca por palavras resolve, e se a placa de memoria
(Modal) estiver ligada, ela reordena os candidatos por significado.
"""

import json
import re
import threading
import time
import unicodedata
import uuid
from difflib import SequenceMatcher
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARQUIVO = BASE / "memoria" / "fatos.json"
TRAVA = threading.Lock()
TRAVA_EXTRAIR = threading.Lock()
LIMITE_FATOS = 400
TIPOS = ("preferencia", "pessoal", "projeto", "decisao", "contato", "outro")
MODELOS_HF = ["Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.3-70B-Instruct",
              "google/gemma-3-27b-it"]

# So vale a pena chamar o extrator quando a frase fala de voce, do que
# voce quer ou do que foi decidido. "que horas sao?" nao gera fato.
PISTAS = re.compile(
    r"\b(eu|meu|minha|meus|minhas|me chamo|sou|estou|trabalho|moro|uso|usamos|"
    r"prefiro|gosto|odeio|detesto|quero que|sempre|nunca|nosso|nossa|nossos|"
    r"lembr\w*|anot\w*|guard\w*|memoriz\w*|esquec\w*|decid\w*|vamos usar|"
    r"a partir de agora|daqui pra frente|daqui para frente|meu cliente|minha empresa)\b",
    re.I)


# ---------------------------------------------------------------- arquivo
def _config():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def ligada():
    return bool(_config().get("memoria_fatos", True))


def _ler():
    try:
        dados = json.loads(ARQUIVO.read_text(encoding="utf-8"))
        return dados if isinstance(dados, list) else []
    except Exception:
        return []


def _gravar(fatos):
    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    tmp = ARQUIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(fatos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARQUIVO)


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


PARADAS = set(_norm(
    "a o e de do da dos das em no na nos nas um uma uns umas para pra por com "
    "que se eu voce ele ela isso isto esse essa este esta ao aos as os mais "
    "muito como qual quais quando onde porque ja nao sim tem ter ser foi sao "
    "meu minha seu sua fred bigode").split())


def _palavras(t):
    return {p for p in _norm(t).split() if len(p) > 2 and p not in PARADAS}


# ---------------------------------------------------------------- CRUD
def listar():
    return sorted(_ler(), key=lambda f: f.get("atualizado", 0), reverse=True)


def adicionar(texto, tipo="outro", especialista="", projeto="", origem="manual"):
    texto = re.sub(r"\s+", " ", str(texto or "")).strip()[:300]
    if len(texto) < 4:
        return {"ok": False, "erro": "fato vazio"}
    with TRAVA:
        fatos = _ler()
        parecido = _mais_parecido(texto, fatos)
        agora = time.time()
        if parecido and parecido[1] >= 0.86:
            f = parecido[0]
            f.update(texto=texto, atualizado=agora)
            _gravar(fatos)
            return {"ok": True, "fato": f, "repetido": True}
        f = {"id": uuid.uuid4().hex[:8], "texto": texto,
             "tipo": tipo if tipo in TIPOS else "outro",
             "especialista": str(especialista or "")[:60],
             "projeto": str(projeto or "")[:80],
             "origem": origem, "criado": agora, "atualizado": agora, "usos": 0}
        fatos.append(f)
        if len(fatos) > LIMITE_FATOS:   # sai o mais velho e menos usado
            fatos.sort(key=lambda x: (x.get("usos", 0), x.get("atualizado", 0)))
            fatos = fatos[len(fatos) - LIMITE_FATOS:]
        _gravar(fatos)
        return {"ok": True, "fato": f}


def editar(ident, texto):
    texto = re.sub(r"\s+", " ", str(texto or "")).strip()[:300]
    with TRAVA:
        fatos = _ler()
        for f in fatos:
            if f.get("id") == ident:
                if not texto:
                    fatos.remove(f)
                else:
                    f.update(texto=texto, atualizado=time.time())
                _gravar(fatos)
                return {"ok": True}
    return {"ok": False, "erro": "fato nao encontrado"}


def apagar(ident):
    return editar(ident, "")


def apagar_tudo():
    with TRAVA:
        _gravar([])
    return {"ok": True}


def _mais_parecido(texto, fatos):
    alvo = _norm(texto)
    melhor, nota = None, 0.0
    for f in fatos:
        n = SequenceMatcher(None, alvo, _norm(f.get("texto"))).ratio()
        if n > nota:
            melhor, nota = f, n
    return (melhor, nota) if melhor else None


# ---------------------------------------------------------------- busca
def relevantes(pergunta, especialista="", projeto="", quantos=8):
    """Fatos para esta pergunta. Preferencias gerais entram sempre (poucas)."""
    fatos = [f for f in _ler()
             if (not f.get("especialista") or f.get("especialista") == especialista)
             and (not f.get("projeto") or f.get("projeto") == projeto)]
    if not fatos:
        return []
    chave = _palavras(pergunta)
    pontos = []
    for f in fatos:
        comuns = len(chave & _palavras(f.get("texto")))
        nota = comuns * 2.0
        if f.get("tipo") == "preferencia" and not f.get("projeto"):
            nota += 1.5                              # jeito de trabalhar vale sempre
        if projeto and f.get("projeto") == projeto:
            nota += 1.0
        if especialista and f.get("especialista") == especialista:
            nota += 0.5
        nota += min(f.get("usos", 0), 10) * 0.05
        pontos.append((nota, f.get("atualizado", 0), f))
    pontos.sort(key=lambda x: (x[0], x[1]), reverse=True)
    candidatos = [p[2] for p in pontos if p[0] > 0][:30]

    # Placa de memoria (Modal) ligada: reordena por significado, nao so palavra.
    if len(candidatos) > quantos:
        try:
            import placa_memoria
            ordem = placa_memoria.ranquear(pergunta, [c["texto"] for c in candidatos], quantos)
            if ordem:
                candidatos = [candidatos[i] for i, _n in ordem if 0 <= i < len(candidatos)]
        except Exception:
            pass
    escolhidos = candidatos[:quantos]
    if escolhidos:
        ids = {f["id"] for f in escolhidos}
        with TRAVA:
            todos = _ler()
            for f in todos:
                if f.get("id") in ids:
                    f["usos"] = f.get("usos", 0) + 1
            _gravar(todos)
    return escolhidos


def bloco_para_prompt(pergunta, especialista="", projeto=""):
    if not ligada():
        return ""
    try:
        fatos = relevantes(pergunta, especialista, projeto)
    except Exception:
        return ""
    if not fatos:
        return ""
    linhas = "\n".join("- " + f["texto"] for f in fatos)
    return ("\n\n# O QUE VOCE JA SABE SOBRE O FRED\n\n"
            "Fatos que ele mesmo disse em conversas anteriores. Use quando ajudar; "
            "nao repita a lista para ele; se ele disser algo diferente agora, vale o de agora.\n\n"
            + linhas)


# ---------------------------------------------------------------- extracao
PROMPT = """Voce organiza a memoria de longo prazo de um assistente pessoal.

Leia a MENSAGEM DO USUARIO abaixo e decida se ela traz algum FATO DURAVEL sobre
ele: preferencias (como quer as respostas, ferramentas que usa), dados pessoais
ou da empresa, clientes, decisoes de projeto, regras que ele pediu para seguir.

NAO guarde: perguntas, pedidos de uma vez so ("crie um cubo"), coisas que valem
so hoje, opinioes do assistente, nada que o usuario nao tenha DITO.
NUNCA guarde: senhas, tokens, numeros de cartao, documentos, conta bancaria,
saude, religiao, politica, orientacao sexual.

FATOS QUE JA EXISTEM (com id):
{existentes}

MENSAGEM DO USUARIO:
\"\"\"{mensagem}\"\"\"

Responda SO com JSON, sem texto antes ou depois:
{{"acoes": [
  {{"acao": "adicionar", "texto": "frase curta na 3a pessoa, ex.: Prefere respostas curtas", "tipo": "preferencia|pessoal|projeto|decisao|contato|outro", "do_projeto": true}},
  {{"acao": "atualizar", "id": "abc123", "texto": "nova versao do fato"}},
  {{"acao": "apagar", "id": "abc123"}}
]}}
"do_projeto": true so quando o fato vale apenas para o projeto em que ele esta trabalhando.
Se nada merece ser guardado: {{"acoes": []}}"""

SENSIVEL = re.compile(r"(senha|token|hf_[A-Za-z0-9]{8,}|sk-[A-Za-z0-9]{8,}|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|"
                      r"\b(?:\d[ -]?){13,19}\b|cpf|cartao de credito)", re.I)


def vale_extrair(mensagem):
    m = str(mensagem or "").strip()
    return len(m.split()) >= 4 and len(m) <= 4000 and bool(PISTAS.search(m))


def _chamar_modelo_hf(prompt):
    try:
        import clonar_site
        for modelo in MODELOS_HF:
            r = clonar_site.chat_hf(prompt, max_tokens=600, modelo=modelo)
            if r:
                return r
    except Exception:
        pass
    return None


def _json(texto):
    texto = str(texto or "")
    ini, fim = texto.find("{"), texto.rfind("}")
    if ini < 0 or fim <= ini:
        return None
    try:
        return json.loads(texto[ini:fim + 1])
    except Exception:
        return None


def extrair(mensagem, especialista="", projeto="", reserva=None):
    """Roda o extrator e aplica as acoes. Devolve a lista do que mudou."""
    if not ligada() or not vale_extrair(mensagem):
        return []
    if SENSIVEL.search(mensagem) and not re.search(r"\b(lembr|anot|guard)", mensagem, re.I):
        return []
    with TRAVA_EXTRAIR:
        existentes = listar()
        perto = sorted(existentes, key=lambda f: len(_palavras(mensagem) & _palavras(f["texto"])),
                       reverse=True)[:25]
        lista = "\n".join("[%s] %s" % (f["id"], f["texto"]) for f in perto) or "(nenhum)"
        prompt = PROMPT.format(existentes=lista, mensagem=str(mensagem)[:3000])
        resposta = _chamar_modelo_hf(prompt)
        if not resposta and reserva:
            try:
                resposta = reserva(prompt)
            except Exception:
                resposta = None
        dados = _json(resposta) or {}
        feitas = []
        for a in (dados.get("acoes") or [])[:6]:
            if not isinstance(a, dict):
                continue
            acao, texto = a.get("acao"), str(a.get("texto") or "").strip()
            if texto and SENSIVEL.search(texto):
                continue
            if acao == "adicionar" and texto:
                r = adicionar(texto, a.get("tipo", "outro"), especialista,
                              projeto if a.get("do_projeto") else "", origem="conversa")
                if r.get("ok") and not r.get("repetido"):
                    feitas.append({"acao": "anotei", "texto": texto})
            elif acao == "atualizar" and a.get("id") and texto:
                if editar(str(a["id"]), texto).get("ok"):
                    feitas.append({"acao": "atualizei", "texto": texto})
            elif acao == "apagar" and a.get("id"):
                antigo = next((f["texto"] for f in existentes if f["id"] == a["id"]), "")
                if apagar(str(a["id"])).get("ok"):
                    feitas.append({"acao": "esqueci", "texto": antigo})
        if feitas:
            _registrar(feitas)
        return feitas


# O que mudou por ultimo -- a tela mostra "Anotei: ..." depois da resposta.
_ULTIMAS = {"quando": 0, "itens": []}


def _registrar(itens):
    _ULTIMAS.update(quando=time.time(), itens=itens)


def ultimas(desde=0.0):
    if _ULTIMAS["quando"] > float(desde or 0):
        return {"quando": _ULTIMAS["quando"], "itens": _ULTIMAS["itens"]}
    return {"quando": _ULTIMAS["quando"], "itens": []}


def extrair_em_segundo_plano(mensagem, especialista="", projeto="", reserva=None, ao_erro=None):
    if not ligada() or not vale_extrair(mensagem):
        return False

    def _rodar():
        try:
            extrair(mensagem, especialista, projeto, reserva)
        except Exception as erro:
            if ao_erro:
                try:
                    ao_erro("[memoria de fatos] extracao falhou", erro)
                except Exception:
                    pass
    threading.Thread(target=_rodar, daemon=True).start()
    return True
