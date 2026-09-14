"""Integração opcional com Hugging Face Hub e Inference Providers.

Segredos são lidos somente de HF_TOKEN. O módulo não imprime tokens e não baixa
pesos sem uma chamada explícita.
"""
from __future__ import annotations
import os
from pathlib import Path

class HuggingFaceError(RuntimeError):
    pass

def token():
    return os.environ.get("HF_TOKEN", "").strip()

def configurado():
    return bool(token())

def _client():
    try:
        from huggingface_hub import InferenceClient
    except ImportError as exc:
        raise HuggingFaceError("Instale huggingface_hub para usar a API Hugging Face.") from exc
    return InferenceClient(token=token() or None)

def chat(messages, model=None, temperature=0.45, max_tokens=1200, tools=None):
    if not messages:
        raise HuggingFaceError("A conversa está vazia.")
    try:
        r = _client().chat_completion(messages=messages, model=model or os.environ.get("HF_TEXT_MODEL"),
                                      stream=False, temperature=temperature,
                                      max_tokens=max_tokens, tools=tools or None)
        return str(r.choices[0].message.content or "")
    except Exception as exc:
        raise HuggingFaceError(f"Hugging Face chat falhou: {exc}") from exc

def text_to_image(prompt, model=None, negative_prompt=None, width=None, height=None,
                  steps=None, guidance=None, seed=None):
    if not prompt.strip():
        raise HuggingFaceError("O prompt de imagem está vazio.")
    try:
        image = _client().text_to_image(prompt=prompt, model=model or os.environ.get("HF_IMAGE_MODEL"),
            negative_prompt=negative_prompt or None, width=width, height=height,
            num_inference_steps=steps, guidance_scale=guidance, seed=seed)
        return image
    except Exception as exc:
        raise HuggingFaceError(f"Hugging Face imagem falhou: {exc}") from exc

def download(repo_id, filename, destination, revision=None):
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise HuggingFaceError("Instale huggingface_hub para baixar modelos.") from exc
    dest = Path(destination); dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        cached = hf_hub_download(repo_id=repo_id, filename=filename, revision=revision)
        dest.write_bytes(Path(cached).read_bytes())
        return str(dest)
    except Exception as exc:
        raise HuggingFaceError(f"Download Hugging Face falhou: {exc}") from exc

def status():
    return {"configurado": configurado(), "token_presente": bool(token()),
            "texto_modelo": os.environ.get("HF_TEXT_MODEL", ""),
            "imagem_modelo": os.environ.get("HF_IMAGE_MODEL", "")}

if __name__ == "__main__":
    print(status())
