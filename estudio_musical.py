"""
ESTUDIO MUSICAL DO BIGODE -- separar instrumentos e mixar de novo.

    separar:  musica.mp3 -> voz, bateria, baixo, outros (e guitarra/piano no modo 6)
    mixar:    escolhe o volume de cada parte (ou muta) -> nova musica .mp3/.wav

Motor: Demucs (Meta, licenca MIT) -- o mesmo usado por muitos apps de
karaoke. Roda no SEU PC, com o PyTorch que o gerador 3D local ja instalou
(pasta %LOCALAPPDATA%\\bigode_3d\\libs). Uma musica de 3 min leva ~2 a 6 min
no processador. Nada sai do seu computador.

Arquivos:  <pasta_projetos>\\Estudio\\<nome>\\
             original.<ext>, voz.mp3, bateria.mp3, baixo.mp3, outros.mp3 ...
             mix_<hora>.mp3   (cada mixagem nova)

Uso responsavel: separe musicas suas, de clientes que autorizaram ou para
estudo. Publicar trecho de musica de terceiros depende de licenca.
"""

import base64
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parent
NOMES = {"vocals": "voz", "drums": "bateria", "bass": "baixo", "other": "outros",
         "guitar": "guitarra", "piano": "piano", "instrumental": "instrumental"}
MODOS = {"rapido": "htdemucs", "melhor": "htdemucs_ft", "seis": "htdemucs_6s", "voz": "htdemucs"}
PACOTES = ["demucs", "einops", "julius", "lameenc", "pyyaml", "safetensors", "sphn", "tqdm"]

JOBS = {}

SCRIPT = r'''
import sys, os, json
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "libs"))
import torch
torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
from demucs.audio import save_audio

acao = sys.argv[1]
if acao == "separar":
    entrada, pasta, modelo, so_voz = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == "1"
    from demucs.api import Separator
    sep = Separator(model=modelo, progress=False)
    _orig, partes = sep.separate_audio_file(entrada)
    os.makedirs(pasta, exist_ok=True)
    nomes = json.loads(sys.argv[6])
    feitos = []
    if so_voz:
        voz = partes["vocals"]
        inst = sum(v for k, v in partes.items() if k != "vocals")
        partes = {"vocals": voz, "instrumental": inst}
    for k, wav in partes.items():
        destino = os.path.join(pasta, nomes.get(k, k) + ".mp3")
        save_audio(wav, destino, samplerate=sep.samplerate, bitrate=256)
        feitos.append(destino)
    print(json.dumps({"ok": True, "arquivos": feitos, "taxa": sep.samplerate}))
elif acao == "mixar":
    pasta, volumes, saida = sys.argv[2], json.loads(sys.argv[3]), sys.argv[4]
    import sphn, numpy as np
    total, taxa = None, 44100
    for nome, ganho in volumes.items():
        arq = os.path.join(pasta, nome + ".mp3")
        if float(ganho) <= 0 or not os.path.exists(arq):
            continue
        dados, taxa = sphn.read(arq)
        dados = dados * float(ganho)
        if total is None:
            total = dados
        else:
            n = min(total.shape[-1], dados.shape[-1])
            total = total[..., :n] + dados[..., :n]
    if total is None:
        print(json.dumps({"ok": False, "erro": "todas as partes estao mudas"})); sys.exit(0)
    save_audio(torch.from_numpy(np.ascontiguousarray(total)).float(), saida, samplerate=taxa,
               bitrate=320, clip="rescale")
    print(json.dumps({"ok": True, "arquivo": saida}))
'''


def _config():
    try:
        return json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def pasta_estudio():
    raiz = str(_config().get("pasta_projetos") or "").strip()
    p = Path(raiz) / "Estudio" if raiz else BASE / "estudio"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _nome(n):
    n = re.sub(r"[^\w\- ]", "", str(n or ""), flags=re.U).strip().replace(" ", "-")
    return (n or "musica-" + time.strftime("%Y%m%d-%H%M%S"))[:60]


def _local():
    import gerador_local_3d as g
    return g


def pronto():
    g = _local()
    return g.pronto() and (g.LIBS / "demucs").exists()


def _preparar():
    """Usa o PyTorch do gerador 3D local; so acrescenta o Demucs (~5 MB)."""
    g = _local()
    if not g.pronto():
        raise RuntimeError("O motor local ainda nao esta instalado. Abra o painel Blender 3D e "
                           "clique em 'Instalar agora' (ele instala o PyTorch que o estudio usa).")
    if not (g.LIBS / "demucs").exists() or not (g.LIBS / "sphn").exists():
        g._rodar([str(g.PY), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                  "--no-deps", "--target", str(g.LIBS)] + PACOTES, limite=900)
    script = g.PASTA / "estudio.py"
    if not script.exists() or script.read_text(encoding="utf-8") != SCRIPT:
        script.write_text(SCRIPT, encoding="utf-8")
    return g, script


def _ultima_linha_json(texto):
    for linha in reversed((texto or "").strip().splitlines()):
        linha = linha.strip()
        if linha.startswith("{"):
            try:
                return json.loads(linha)
            except ValueError:
                pass
    return None


def listar():
    itens = []
    for p in sorted(pasta_estudio().glob("*/info.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:30]:
        try:
            info = json.loads(p.read_text(encoding="utf-8"))
            info["nome"] = p.parent.name
            info["partes"] = [a.stem for a in sorted(p.parent.glob("*.mp3"))
                              if not a.stem.startswith(("mix_", "original"))]
            info["mixes"] = [a.name for a in sorted(list(p.parent.glob("mix_*.mp3")) + list(p.parent.glob("mix_*.wav")),
                                                    key=lambda x: x.stat().st_mtime, reverse=True)]
            itens.append(info)
        except Exception:
            pass
    return itens


def arquivo(nome, arq):
    pasta = (pasta_estudio() / _nome(nome)).resolve()
    alvo = (pasta / str(arq)).resolve()
    if not str(alvo).startswith(str(pasta)) or not alvo.is_file():
        return None
    return alvo


def status(jid):
    j = JOBS.get(jid)
    if not j:
        return {"ok": False, "erro": "Pedido nao encontrado (o Bigode foi reiniciado?)."}
    return {"ok": True, **j, "segundos": round(time.time() - j["inicio"])}


def separar(nome_arquivo, dados_b64, modo="rapido", nome=""):
    jid = uuid.uuid4().hex[:10]
    nm = _nome(nome or Path(str(nome_arquivo or "musica")).stem)
    JOBS[jid] = {"id": jid, "estado": "rodando", "etapa": "Recebendo o audio", "erro": "",
                 "nome": nm, "inicio": time.time()}
    threading.Thread(target=_rodar_separar, args=(jid, nome_arquivo, dados_b64, modo), daemon=True).start()
    return {"ok": True, "id": jid, "nome": nm}


def _rodar_separar(jid, nome_arquivo, dados_b64, modo):
    j = JOBS[jid]
    try:
        ext = Path(str(nome_arquivo or "a.mp3")).suffix.lower() or ".mp3"
        if ext not in (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"):
            raise RuntimeError("Formato nao suportado. Use MP3, WAV, FLAC ou OGG.")
        b64 = str(dados_b64 or "")
        if b64.startswith("data:"):
            b64 = b64.partition(",")[2]
        dados = base64.b64decode(b64)
        if len(dados) > 150 * 1024 * 1024:
            raise RuntimeError("Arquivo grande demais (maximo 150 MB).")
        pasta = pasta_estudio() / j["nome"]
        pasta.mkdir(parents=True, exist_ok=True)
        original = pasta / ("original" + ext)
        original.write_bytes(dados)
        _separar_arquivo(j, original, pasta, modo)
    except Exception as erro:
        j.update(estado="erro", erro=str(erro)[:500])


def _separar_arquivo(j, original, pasta, modo):
    """Parte comum: arquivo de audio ja na pasta -> partes separadas."""
    j["etapa"] = "Preparando o separador (so na primeira vez demora mais)"
    g, script = _preparar()
    modelo = MODOS.get(modo, "htdemucs")
    j["etapa"] = "Separando os instrumentos (%s) -- 2 a 6 min para 3 min de musica" % modelo
    r = subprocess.run([str(g.PY), str(script), "separar", str(original), str(pasta), modelo,
                        "1" if modo == "voz" else "0", json.dumps(NOMES)],
                       capture_output=True, text=True, timeout=3600,
                       creationflags=0x08000000 if sys.platform == "win32" else 0)
    resp = _ultima_linha_json(r.stdout)
    if not resp or not resp.get("ok"):
        raise RuntimeError("O separador falhou: " + (r.stderr or r.stdout or "")[-400:])
    info = {"original": Path(original).name, "modo": modo, "modelo": modelo,
            "quando": time.strftime("%d/%m %H:%M")}
    if j.get("fonte"):
        info["fonte"] = j["fonte"]
    (Path(pasta) / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    j.update(estado="pronto", etapa="Pronto", pasta=str(pasta),
             partes=[Path(a).stem for a in resp["arquivos"]])


# ══════════════════════════════════════════════════════════════════════
# LINK DE VIDEO -> MP3 -> SEPARAR                                   (28/09)
#
#   yt-dlp (licenca Unlicense) baixa so o AUDIO do video e o ffmpeg que vem
#   no pacote imageio-ffmpeg converte para MP3. Desde nov/2025 o YouTube
#   exige um interpretador de JavaScript para liberar os formatos: vai o
#   Deno, que tambem existe como pacote pip (nada para instalar a mao).
#
#   Tudo numa pasta separada (bigode_3d\libs_video) para nao misturar
#   versoes com o PyTorch do separador. Primeira vez: ~150 MB, uma vez so.
#   A cada 7 dias o yt-dlp e atualizado sozinho -- o YouTube muda sempre e
#   yt-dlp velho e a causa numero 1 de "nao consegui baixar".
#
#   Uso responsavel: so videos seus, de quem autorizou, ou para estudo. Os
#   termos do YouTube nao permitem baixar conteudo de terceiros sem
#   autorizacao.
# ══════════════════════════════════════════════════════════════════════
PACOTES_VIDEO = ["yt-dlp[default]", "deno", "imageio-ffmpeg"]
LIMITE_MIN = 20          # minutos; video maior que isso nao e musica

SCRIPT_VIDEO = r"""
import sys, os
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "libs_video"))
import yt_dlp
sys.exit(yt_dlp.main(sys.argv[1:]))
"""

_TRAVA_VIDEO = threading.Lock()


def _preparar_video(j=None):
    g = _local()
    libs = g.PASTA / "libs_video"
    marca = libs / ".atualizado"
    with _TRAVA_VIDEO:
        velho = (not marca.exists()) or (time.time() - marca.stat().st_mtime > 7 * 86400)
        if not (libs / "yt_dlp").exists() or velho:
            if j is not None:
                j["etapa"] = ("Instalando o leitor de links (so na primeira vez, ~150 MB)"
                              if not (libs / "yt_dlp").exists() else "Atualizando o leitor de links")
            libs.mkdir(parents=True, exist_ok=True)
            g._rodar([str(g.PY), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                      "--upgrade", "--target", str(libs)] + PACOTES_VIDEO, limite=1800)
            marca.write_text(time.strftime("%Y-%m-%d %H:%M"), encoding="utf-8")
    script = g.PASTA / "baixar_video.py"
    if not script.exists() or script.read_text(encoding="utf-8") != SCRIPT_VIDEO:
        script.write_text(SCRIPT_VIDEO, encoding="utf-8")
    deno = libs / "bin" / ("deno.exe" if sys.platform == "win32" else "deno")
    ffmpeg = ""
    bins = libs / "imageio_ffmpeg" / "binaries"
    for arq in sorted(bins.glob("ffmpeg*")) if bins.exists() else []:
        if arq.is_file() and arq.suffix.lower() not in (".md", ".py", ".txt"):
            ffmpeg = str(arq)
            if sys.platform != "win32":
                try:
                    arq.chmod(0o755)
                except OSError:
                    pass
            break
    return g, script, (str(deno) if deno.exists() else ""), ffmpeg


RE_LINK = re.compile(r"https?://[^\s<>\"']+", re.I)


def achar_link(texto):
    m = RE_LINK.search(str(texto or ""))
    return m.group(0).rstrip(".,;)") if m else ""


def separar_url(url, modo="voz", nome=""):
    url = achar_link(url)
    if not url:
        return {"ok": False, "erro": "Cole um link que comece com http:// ou https://"}
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "estado": "rodando", "etapa": "Lendo o link", "erro": "",
                 "nome": _nome(nome) if nome else "", "inicio": time.time(), "fonte": url}
    threading.Thread(target=_rodar_url, args=(jid, url, modo, nome), daemon=True).start()
    return {"ok": True, "id": jid, "nome": JOBS[jid]["nome"]}


def _rodar_url(jid, url, modo, nome):
    j = JOBS[jid]
    tmp = pasta_estudio() / ("_baixando_" + jid)
    try:
        g, script, deno, ffmpeg = _preparar_video(j)
        if not ffmpeg:
            raise RuntimeError("Nao achei o conversor de audio (ffmpeg). Tente de novo; se repetir, "
                               "apague a pasta %LOCALAPPDATA%\\bigode_3d\\libs_video.")
        tmp.mkdir(parents=True, exist_ok=True)
        j["etapa"] = "Baixando o audio do video e convertendo para MP3"
        cmd = [str(g.PY), str(script), url,
               "--no-quiet", "--no-playlist", "--no-progress", "--no-warnings",
               "-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0",
               "--ffmpeg-location", ffmpeg,
               "--match-filter", "!is_live & duration <? %d" % (LIMITE_MIN * 60),
               "--max-filesize", "400M",
               "-o", str(tmp / "original.%(ext)s"),
               "--print", "before_dl:TITULO=%(title)s",
               "--print", "after_move:ARQUIVO=%(filepath)s"]
        if deno:
            cmd[3:3] = ["--js-runtimes", "deno:" + deno]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=1800, creationflags=0x08000000 if sys.platform == "win32" else 0)
        titulo, arquivo = "", ""
        for linha in (r.stdout or "").splitlines():
            if linha.startswith("TITULO="):
                titulo = linha[7:].strip()
            elif linha.startswith("ARQUIVO="):
                arquivo = linha[8:].strip()
        mp3 = Path(arquivo) if arquivo and Path(arquivo).exists() else next(iter(tmp.glob("original.mp3")), None)
        if not mp3 or not mp3.exists():
            erro = (r.stderr or r.stdout or "").strip()
            if "does not pass filter" in erro or "skipping" in erro.lower():
                raise RuntimeError("Video longo demais (limite %d min) ou transmissao ao vivo." % LIMITE_MIN)
            if "Sign in" in erro or "confirm you" in erro:
                raise RuntimeError("O YouTube pediu login para este video (idade, privado ou "
                                   "bloqueio anti-robo). Tente outro link ou mande o MP3.")
            raise RuntimeError("Nao consegui baixar o audio: " + erro[-400:])
        # pasta final com o nome do video (sem sobrescrever outra)
        base = _nome(nome or titulo or "video")
        final, n = pasta_estudio() / base, 2
        while final.exists():
            final = pasta_estudio() / ("%s-%d" % (base, n))
            n += 1
        tmp.rename(final)
        j["nome"] = final.name
        if titulo:
            j["titulo"] = titulo
        _separar_arquivo(j, final / "original.mp3", final, modo)
    except subprocess.TimeoutExpired:
        j.update(estado="erro", erro="Demorou demais para baixar (30 min). Confira a internet.")
    except Exception as erro:
        j.update(estado="erro", erro=str(erro)[:600])
    finally:
        try:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


def mixar(nome, volumes, formato="mp3"):
    """volumes: {"voz": 0.0-2.0, "bateria": 1.0, ...}. 0 = mudo."""
    g, script = _preparar()
    pasta = pasta_estudio() / _nome(nome)
    if not pasta.exists():
        return {"ok": False, "erro": "Projeto nao encontrado."}
    vol = {re.sub(r"[^\w]", "", str(k)): max(0.0, min(2.0, float(v))) for k, v in (volumes or {}).items()}
    saida = pasta / ("mix_%s.%s" % (time.strftime("%H%M%S"), "wav" if formato == "wav" else "mp3"))
    r = subprocess.run([str(g.PY), str(script), "mixar", str(pasta), json.dumps(vol), str(saida)],
                       capture_output=True, text=True, timeout=900,
                       creationflags=0x08000000 if sys.platform == "win32" else 0)
    resp = _ultima_linha_json(r.stdout)
    if not resp or not resp.get("ok"):
        return {"ok": False, "erro": (resp or {}).get("erro") or (r.stderr or "")[-300:]}
    return {"ok": True, "arquivo": saida.name, "pasta": str(pasta)}
