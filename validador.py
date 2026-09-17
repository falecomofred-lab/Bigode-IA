#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VALIDADOR — Executa linters, formatadores e testes no código gerado.

Detecta o tipo de projeto (Python, Node.js, etc) e valida:
- Sintaxe (flake8, eslint, etc)
- Formatação (black, prettier, etc)
- Testes (pytest, jest, etc)

Retorna erros para que a IA possa corrigir antes de enviar ao usuário.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

def ler(caminho, padrao=""):
    try:
        return Path(caminho).read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return padrao

def rodar_comando(cmd, timeout=30, cwd=None):
    """Executa comando e captura stdout/stderr."""
    try:
        resultado = subprocess.run(
            cmd if isinstance(cmd, list) else cmd.split(),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or Path.cwd(),
        )
        return {
            "ok": resultado.returncode == 0,
            "stdout": resultado.stdout[:2000],
            "stderr": resultado.stderr[:2000],
            "codigo": resultado.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stderr": f"Timeout após {timeout}s", "codigo": -1}
    except FileNotFoundError as e:
        return {"ok": False, "stderr": f"Comando não encontrado: {e}", "codigo": -1}
    except Exception as e:
        return {"ok": False, "stderr": f"Erro: {e}", "codigo": -1}

class ValidadorProjeto:
    def __init__(self, raiz=None):
        self.raiz = Path(raiz or Path.cwd())
        self.tipo = self._detectar_tipo()
        self.tem_testes = self._tem_testes()

    def _detectar_tipo(self):
        """Detecta qual tipo de projeto é."""
        if (self.raiz / "pyproject.toml").exists():
            return "python"
        if (self.raiz / "requirements.txt").exists():
            return "python"
        if (self.raiz / "package.json").exists():
            return "nodejs"
        if (self.raiz / "Gemfile").exists():
            return "ruby"
        if (self.raiz / "go.mod").exists():
            return "go"
        return None

    def _tem_testes(self):
        """Verifica se há testes configurados."""
        if self.tipo == "python":
            return (
                (self.raiz / "pytest.ini").exists()
                or (self.raiz / "tests").is_dir()
                or (self.raiz / "test_*.py").glob("test_*.py")
            )
        if self.tipo == "nodejs":
            package = json.loads(ler(self.raiz / "package.json", "{}"))
            return "test" in package.get("scripts", {})
        return False

    def validar_sintaxe(self):
        """Valida sintaxe do código."""
        if self.tipo == "python":
            return self._validar_python()
        elif self.tipo == "nodejs":
            return self._validar_nodejs()
        return {"ok": True, "msg": "Tipo de projeto não suportado para validação"}

    def _validar_python(self):
        """Valida Python com flake8 ou ruff."""
        # Tenta ruff (mais rápido), depois flake8
        for ferramenta in ["ruff", "flake8"]:
            resultado = rodar_comando(f"{ferramenta} .", timeout=20, cwd=self.raiz)
            if not resultado["stderr"].startswith("command not found"):
                return {
                    "ok": resultado["ok"],
                    "ferramenta": ferramenta,
                    "erros": resultado["stderr"] if not resultado["ok"] else "",
                    "tipo": "python",
                }
        return {"ok": True, "msg": "Nenhum linter Python encontrado"}

    def _validar_nodejs(self):
        """Valida JavaScript/TypeScript com eslint."""
        resultado = rodar_comando("npx eslint . --max-warnings 0", timeout=20, cwd=self.raiz)
        return {
            "ok": resultado["ok"],
            "ferramenta": "eslint",
            "erros": resultado["stderr"] if not resultado["ok"] else "",
            "tipo": "nodejs",
        }

    def formatar(self):
        """Formata o código automaticamente."""
        if self.tipo == "python":
            return self._formatar_python()
        elif self.tipo == "nodejs":
            return self._formatar_nodejs()
        return {"ok": True, "msg": "Tipo de projeto não suportado para formatação"}

    def _formatar_python(self):
        """Formata com black ou autopep8."""
        for ferramenta in ["black", "autopep8"]:
            if ferramenta == "black":
                resultado = rodar_comando("black . --quiet", timeout=30, cwd=self.raiz)
            else:
                resultado = rodar_comando(
                    "autopep8 --in-place --aggressive --aggressive -r .",
                    timeout=30,
                    cwd=self.raiz
                )
            if not resultado["stderr"].startswith("command not found"):
                return {
                    "ok": resultado["ok"],
                    "ferramenta": ferramenta,
                    "alteracoes": resultado["stdout"][:500],
                }
        return {"ok": True, "msg": "Nenhum formatador Python encontrado"}

    def _formatar_nodejs(self):
        """Formata com prettier."""
        resultado = rodar_comando(
            "npx prettier --write .",
            timeout=30,
            cwd=self.raiz
        )
        return {
            "ok": resultado["ok"],
            "ferramenta": "prettier",
            "alteracoes": resultado["stdout"][:500],
        }

    def rodar_testes(self):
        """Executa testes se houver."""
        if not self.tem_testes:
            return {"ok": True, "msg": "Nenhum teste configurado"}

        if self.tipo == "python":
            return self._testes_python()
        elif self.tipo == "nodejs":
            return self._testes_nodejs()
        return {"ok": True, "msg": "Tipo de teste não suportado"}

    def _testes_python(self):
        """Roda pytest."""
        resultado = rodar_comando("pytest -q --tb=short", timeout=60, cwd=self.raiz)
        return {
            "ok": resultado["ok"],
            "ferramenta": "pytest",
            "saida": resultado["stdout"][:1000],
            "erros": resultado["stderr"][:1000],
        }

    def _testes_nodejs(self):
        """Roda npm test."""
        resultado = rodar_comando("npm test -- --passWithNoTests", timeout=60, cwd=self.raiz)
        return {
            "ok": resultado["ok"],
            "ferramenta": "npm test",
            "saida": resultado["stdout"][:1000],
            "erros": resultado["stderr"][:1000],
        }

    def validar_completo(self):
        """Valida sintaxe, formata e roda testes."""
        etapas = {
            "sintaxe": self.validar_sintaxe(),
            "formato": self.formatar(),
            "testes": self.rodar_testes(),
        }
        # Se alguma etapa falhou, retorna tudo
        algum_erro = any(not e.get("ok", True) for e in etapas.values())
        return {
            "ok": not algum_erro,
            "etapas": etapas,
            "tipo_projeto": self.tipo,
        }

def resumir_validacao(resultado):
    """Converte resultado de validação em texto para mostrar na tela."""
    if resultado.get("ok"):
        return "✓ Código validado (sintaxe OK, formato OK, testes passaram)"

    msg = "⚠ Problemas encontrados:\n"
    for etapa, detalhe in resultado.get("etapas", {}).items():
        if detalhe.get("ok") is False:
            ferramenta = detalhe.get("ferramenta", "?")
            erros = detalhe.get("erros", detalhe.get("saida", ""))[:300]
            msg += f"\n**{etapa.title()}** ({ferramenta}):\n{erros}\n"
    return msg

if __name__ == "__main__":
    # Teste
    proj = ValidadorProjeto(".")
    print(f"Tipo: {proj.tipo}")
    resultado = proj.validar_completo()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print("\nResumo:")
    print(resumir_validacao(resultado))
