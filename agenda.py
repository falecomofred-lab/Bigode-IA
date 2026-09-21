#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AGENDA - tarefas programadas e artefatos

Duas coisas que andam juntas porque uma alimenta a outra:

  Programados - perguntas que o Bigode responde sozinho na hora marcada,
                sem ninguem na frente da tela.
  Artefatos   - os arquivos que ele criou ou alterou, reunidos num lugar so.

Regra de seguranca das tarefas programadas: elas rodam em modo leitura.
Uma tarefa que dispara as 7 da manha com voce dormindo nao pode apagar,
sobrescrever nem criar arquivo. Ela le, analisa e escreve a resposta no
historico da tarefa. Se voce quiser que algo seja gravado, abre o resultado
e manda gravar - acordado.

Venure - venure.com.br
"""

import datetime
import json
import threading
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
MEMORIA = BASE / "memoria"
ARQUIVO_TAREFAS = MEMORIA / "tarefas.json"
ARQUIVO_MEDICOES = MEMORIA / "medicoes.jsonl"

TRAVA = threading.Lock()

DIAS = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]


# ==========================================================================
# Leitura e gravacao
# ==========================================================================

def _ler():
    if not ARQUIVO_TAREFAS.exists():
        return []
    try:
        dados = json.loads(ARQUIVO_TAREFAS.read_text(encoding="utf-8"))
        return dados if isinstance(dados, list) else []
    except Exception:
        # Arquivo corrompido nao pode derrubar o Bigode inteiro. Guarda o
        # estragado do lado para nao perder o conteudo e comeca limpo.
        try:
            ARQUIVO_TAREFAS.rename(ARQUIVO_TAREFAS.with_suffix(".json.quebrado"))
        except Exception:
            pass
        return []


def _gravar(lista):
    MEMORIA.mkdir(parents=True, exist_ok=True)
    # Grava num temporario e so entao troca: se faltar energia no meio, o
    # arquivo bom continua la em vez de virar meio arquivo.
    temp = ARQUIVO_TAREFAS.with_suffix(".json.novo")
    temp.write_text(json.dumps(lista, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    temp.replace(ARQUIVO_TAREFAS)


# ==========================================================================
# Quando roda de novo
# ==========================================================================

def _hoje_as(hora_texto, base=None):
    """'07:30' vira um datetime de hoje nesse horario."""
    base = base or datetime.datetime.now()
    try:
        h, m = (hora_texto or "07:00").split(":")[:2]
        return base.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    except Exception:
        return base.replace(hour=7, minute=0, second=0, microsecond=0)


def proxima_vez(tarefa, depois=None):
    """Calcula quando a tarefa deve rodar da proxima vez.

    Sempre devolve um horario no FUTURO. Se a hora de hoje ja passou, joga
    para amanha (ou para a proxima semana). Sem isso, uma tarefa das 7h
    criada as 9h dispararia na hora, o que assusta.
    """
    agora = depois or datetime.datetime.now()
    tipo = tarefa.get("tipo", "diario")

    if tipo == "intervalo":
        minutos = max(5, int(tarefa.get("minutos") or 60))
        return agora + datetime.timedelta(minutes=minutos)

    if tipo == "uma_vez":
        try:
            quando = datetime.datetime.fromisoformat(tarefa.get("data_hora"))
            return quando if quando > agora else None      # ja passou: nao repete
        except Exception:
            return None

    if tipo == "semanal":
        alvo = tarefa.get("dia_semana", "segunda")
        indice = DIAS.index(alvo) if alvo in DIAS else 0
        candidato = _hoje_as(tarefa.get("hora"), agora)
        # weekday(): segunda=0 ... domingo=6, mesma ordem da lista DIAS
        falta = (indice - agora.weekday()) % 7
        if falta == 0 and candidato <= agora:
            falta = 7
        return candidato + datetime.timedelta(days=falta)

    # diario
    candidato = _hoje_as(tarefa.get("hora"), agora)
    if candidato <= agora:
        candidato += datetime.timedelta(days=1)
    return candidato


def descrever(tarefa):
    """Frase curta para a tela, no lugar de codigo de agendamento."""
    tipo = tarefa.get("tipo", "diario")
    if tipo == "intervalo":
        # Arredondar 90 minutos para "2 horas" seria mentira pequena, mas e
        # mentira: a pessoa marcou 90 e ia ler 120.
        m = int(tarefa.get("minutos") or 60)
        if m < 60:
            return "a cada %d minutos" % m
        horas, resto = divmod(m, 60)
        if resto:
            return "a cada %dh%02d" % (horas, resto)
        return "a cada hora" if horas == 1 else "a cada %d horas" % horas
    if tipo == "semanal":
        return "toda %s às %s" % (tarefa.get("dia_semana", "segunda"),
                                  tarefa.get("hora", "07:00"))
    if tipo == "uma_vez":
        try:
            q = datetime.datetime.fromisoformat(tarefa.get("data_hora"))
            return "uma vez, em %s" % q.strftime("%d/%m às %H:%M")
        except Exception:
            return "uma vez"
    return "todo dia às %s" % tarefa.get("hora", "07:00")


# ==========================================================================
# CRUD
# ==========================================================================

def listar():
    lista = _ler()
    for t in lista:
        t["descricao"] = descrever(t)
        # Nao devolve o historico inteiro para a tela: so o ultimo resultado,
        # que e o que interessa de relance. O resto vem em ver_historico().
        h = t.get("historico") or []
        t["execucoes"] = len(h)
        t["ultimo"] = h[-1] if h else None
        t.pop("historico", None)
    lista.sort(key=lambda t: (not t.get("ativa", True), t.get("proxima") or "z"))
    return lista


def salvar(dados):
    with TRAVA:
        lista = _ler()
        ident = (dados.get("id") or "").strip()
        tarefa = None
        for t in lista:
            if t.get("id") == ident:
                tarefa = t
                break

        if tarefa is None:
            tarefa = {"id": uuid.uuid4().hex[:12],
                      "criada": datetime.datetime.now().isoformat(timespec="seconds"),
                      "historico": []}
            lista.append(tarefa)

        tarefa["nome"] = (dados.get("nome") or "Tarefa sem nome").strip()[:80]
        tarefa["pergunta"] = (dados.get("pergunta") or "").strip()
        tarefa["projeto"] = (dados.get("projeto") or "").strip()
        tarefa["tipo"] = dados.get("tipo") or "diario"
        tarefa["hora"] = dados.get("hora") or "07:00"
        tarefa["dia_semana"] = dados.get("dia_semana") or "segunda"
        tarefa["minutos"] = int(dados.get("minutos") or 60)
        tarefa["data_hora"] = dados.get("data_hora") or ""
        tarefa["ativa"] = bool(dados.get("ativa", True))

        if not tarefa["pergunta"]:
            return {"ok": False, "erro": "escreva o que ele deve fazer"}

        proxima = proxima_vez(tarefa)
        tarefa["proxima"] = proxima.isoformat(timespec="seconds") if proxima else ""
        _gravar(lista)
        return {"ok": True, "id": tarefa["id"], "proxima": tarefa["proxima"]}


def apagar(ident):
    with TRAVA:
        lista = [t for t in _ler() if t.get("id") != ident]
        _gravar(lista)
        return {"ok": True}


def alternar(ident):
    with TRAVA:
        lista = _ler()
        for t in lista:
            if t.get("id") == ident:
                t["ativa"] = not t.get("ativa", True)
                if t["ativa"]:
                    p = proxima_vez(t)
                    t["proxima"] = p.isoformat(timespec="seconds") if p else ""
                _gravar(lista)
                return {"ok": True, "ativa": t["ativa"]}
        return {"ok": False, "erro": "tarefa nao encontrada"}


def ver_historico(ident, quantos=20):
    for t in _ler():
        if t.get("id") == ident:
            return {"ok": True, "nome": t.get("nome"),
                    "historico": (t.get("historico") or [])[-quantos:][::-1]}
    return {"ok": False, "historico": []}


# ==========================================================================
# Execucao
# ==========================================================================

def _anotar_resultado(ident, resultado):
    with TRAVA:
        lista = _ler()
        for t in lista:
            if t.get("id") == ident:
                hist = t.get("historico") or []
                hist.append(resultado)
                t["historico"] = hist[-30:]     # nao deixa o arquivo crescer sem fim
                t["ultima"] = resultado["quando"]
                if t.get("tipo") == "uma_vez":
                    t["ativa"] = False          # ja cumpriu o que tinha de fazer
                    t["proxima"] = ""
                else:
                    p = proxima_vez(t)
                    t["proxima"] = p.isoformat(timespec="seconds") if p else ""
                _gravar(lista)
                return


def rodar(ident, executor, motor_ligado):
    """Roda uma tarefa agora. `executor` e a funcao tarefa() do cerebro.py."""
    alvo = None
    for t in _ler():
        if t.get("id") == ident:
            alvo = t
            break
    if not alvo:
        return {"ok": False, "erro": "tarefa nao encontrada"}

    quando = datetime.datetime.now().isoformat(timespec="seconds")

    if not motor_ligado():
        # Nao e erro da tarefa: e o motor desligado. Registra assim, com todas
        # as letras, para nao parecer que a tarefa esta com defeito.
        resultado = {"quando": quando, "ok": False, "segundos": 0,
                     "texto": "O motor estava desligado nesta hora. "
                              "A tarefa não rodou e vai tentar de novo na próxima.",
                     "motivo": "motor_desligado"}
        _anotar_resultado(ident, resultado)
        return {"ok": False, **resultado}

    comeco = time.time()
    try:
        saida = executor(alvo.get("pergunta", ""),
                         "Esta é uma tarefa programada chamada \"%s\". "
                         "Ninguém está na frente da tela: responda de forma "
                         "completa e independente." % alvo.get("nome", ""))
        resultado = {"quando": quando, "ok": True,
                     "segundos": round(time.time() - comeco, 1),
                     "texto": (saida or {}).get("texto", ""),
                     "acoes": (saida or {}).get("acoes", [])}
    except Exception as erro:
        resultado = {"quando": quando, "ok": False,
                     "segundos": round(time.time() - comeco, 1),
                     "texto": "Falhou: %s" % erro, "motivo": "erro"}

    _anotar_resultado(ident, resultado)
    return {"ok": resultado["ok"], **resultado}


def _laco(executor, motor_ligado, parar):
    """Confere de minuto em minuto quem esta na hora de rodar.

    Uma tarefa por vez, de proposito: o motor roda com --parallel 1, entao
    duas ao mesmo tempo so fariam as duas ficarem lentas.
    """
    while not parar.is_set():
        try:
            agora = datetime.datetime.now()
            for t in _ler():
                if not t.get("ativa", True) or not t.get("proxima"):
                    continue
                try:
                    quando = datetime.datetime.fromisoformat(t["proxima"])
                except Exception:
                    continue
                if quando <= agora:
                    rodar(t["id"], executor, motor_ligado)
        except Exception:
            pass                                 # o laco nunca pode morrer
        parar.wait(30)


def iniciar(executor, motor_ligado):
    """Sobe o relogio em segundo plano. Chamado uma vez, na subida do servidor."""
    parar = threading.Event()
    linha = threading.Thread(target=_laco, args=(executor, motor_ligado, parar),
                             daemon=True, name="agenda")
    linha.start()
    return parar


# ==========================================================================
# Artefatos
# ==========================================================================

def artefatos(limite=200):
    """Os arquivos que o Bigode criou ou alterou, do mais novo para o antigo.

    A fonte e o registro de medicoes: cada pedido grava ali o que foi escrito.
    Nao e uma lista do que existe na pasta - e a lista do que ELE fez. Sao
    coisas diferentes, e a segunda e a que voce quer ver aqui.
    """
    if not ARQUIVO_MEDICOES.exists():
        return []

    vistos = {}
    try:
        for linha in ARQUIVO_MEDICOES.read_text(encoding="utf-8",
                                                errors="ignore").splitlines():
            linha = linha.strip()
            if not linha:
                continue
            try:
                reg = json.loads(linha)
            except Exception:
                continue
            for caminho in (reg.get("arquivos_escritos") or []):
                if not caminho:
                    continue
                # O mesmo arquivo mexido tres vezes aparece uma vez so, com a
                # data da ultima. Repetir polui e nao informa nada.
                vistos[caminho] = {
                    "caminho": caminho,
                    "quando": reg.get("quando", ""),
                    "pergunta": (reg.get("pergunta") or "")[:120],
                    "projeto": reg.get("projeto") or "",
                    "vezes": vistos.get(caminho, {}).get("vezes", 0) + 1,
                }
    except Exception:
        return []

    saida = []
    for item in vistos.values():
        p = Path(item["caminho"])
        item["nome"] = p.name or item["caminho"]
        item["pasta"] = str(p.parent)
        try:
            if p.is_file():
                item["existe"] = True
                item["kb"] = round(p.stat().st_size / 1024, 1)
            else:
                # Pode ter sido apagado ou movido depois. Dizer isso e melhor
                # que mostrar um item que nao abre.
                item["existe"] = False
                item["kb"] = 0
        except Exception:
            item["existe"] = False
            item["kb"] = 0
        saida.append(item)

    saida.sort(key=lambda x: x.get("quando", ""), reverse=True)
    return saida[:limite]
