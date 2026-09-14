"""Estado operacional central do Bigode IA.

Este módulo não inicia motores: registra e expõe um retrato único do runtime,
evita que o frontend confunda configuração com prontidão e mantém jobs de
imagem fora da requisição longa.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

_LOCK = threading.RLock()
_STARTED = time.time()
_IMAGE_JOBS: dict[str, dict[str, Any]] = {}


def _copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_copy(v) for v in value]
    return value


def update_text(provider: Any, *, backend: str = "local") -> dict[str, Any]:
    """Atualiza o estado textual sem expor segredos."""
    try:
        status = provider.status() or {}
    except Exception as exc:
        status = {"erro": str(exc)}
    try:
        modelo = provider.atual() or {}
    except Exception:
        modelo = {}
    online = False
    try:
        online = bool(provider.online())
    except Exception:
        pass
    estado = "pronto" if online else ("erro" if status.get("erro") else "parado")
    with _LOCK:
        _TEXT.update({
            "modelo": modelo.get("nome") or modelo.get("arquivo") or "",
            "modelo_id": modelo.get("id", ""),
            "estado": estado,
            "backend": backend,
            "atualizado_em": time.time(),
            "status": _copy(status),
        })
        return _copy(_TEXT)


_TEXT: dict[str, Any] = {
    "modelo": "", "modelo_id": "", "estado": "parado",
    "backend": "local", "atualizado_em": _STARTED, "status": {},
}


def snapshot(provider: Any, image_state: Callable[[], Any] | None = None,
             connections: Any = None) -> dict[str, Any]:
    text = update_text(provider)
    try:
        image = image_state() if image_state else {}
    except Exception as exc:
        image = {"estado": "erro", "erro": str(exc)}
    if not isinstance(image, dict):
        image = {"estado": "desconhecido", "valor": image}
    return {
        "ok": True,
        "servidor": {"estado": "pronto", "uptime_s": round(time.time() - _STARTED, 1)},
        "texto": text,
        "imagem": _copy(image),
        "conexoes": _copy(connections or {}),
        "jobs_imagem": list_jobs(),
    }


def create_image_job() -> str:
    job_id = "img_" + uuid.uuid4().hex[:12]
    with _LOCK:
        _IMAGE_JOBS[job_id] = {
            "id": job_id, "estado": "fila", "criado_em": time.time(),
            "atualizado_em": time.time(), "resultado": None, "erro": "",
        }
    return job_id


def update_image_job(job_id: str, **values: Any) -> None:
    with _LOCK:
        if job_id in _IMAGE_JOBS:
            _IMAGE_JOBS[job_id].update(values, atualizado_em=time.time())


def get_image_job(job_id: str) -> dict[str, Any] | None:
    with _LOCK:
        item = _IMAGE_JOBS.get(job_id)
        return _copy(item) if item else None


def list_jobs() -> list[dict[str, Any]]:
    with _LOCK:
        itens = sorted(_IMAGE_JOBS.values(), key=lambda x: x["criado_em"], reverse=True)
        return [_copy(x) for x in itens[:20]]


def run_image_job(job_id: str, worker: Callable[[], Any]) -> None:
    update_image_job(job_id, estado="gerando")
    try:
        resultado = worker()
        ok = isinstance(resultado, str) and ".png" in resultado.lower()
        update_image_job(job_id, estado="concluido" if ok else "erro",
                         resultado=resultado, erro="" if ok else str(resultado))
    except Exception as exc:
        update_image_job(job_id, estado="erro", erro=str(exc))


def start_image_job(worker: Callable[[], Any]) -> str:
    job_id = create_image_job()
    threading.Thread(target=run_image_job, args=(job_id, worker),
                     name=f"imagem-{job_id}", daemon=True).start()
    return job_id
