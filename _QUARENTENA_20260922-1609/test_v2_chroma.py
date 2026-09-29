# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

import chroma_memoria
import roteador_semantico


def configurar_tmp(tmp_path: Path) -> None:
    chroma_memoria.BASE = tmp_path
    (tmp_path / "config.json").write_text(json.dumps({
        "chroma_path": "./chroma_db",
        "dominios": {
            "codigo": {"nome": "Código", "pastas": [str(tmp_path / "codigo")], "palavras": ["python"], "ativo": True},
            "seguros": {"nome": "Seguros", "pastas": [str(tmp_path / "seguros")], "palavras": ["apólice"], "ativo": True},
            "cannabis": {"nome": "Cannabis", "pastas": [str(tmp_path / "cannabis")], "palavras": ["cannabis"], "ativo": True},
        },
    }), encoding="utf-8")
    for nome, texto in {
        "codigo": "FastAPI em Python deve validar o contrato da API.",
        "seguros": "A apólice define a cobertura e a franquia do seguro.",
        "cannabis": "A Anvisa regula o uso medicinal de cannabis.",
    }.items():
        pasta = tmp_path / nome
        pasta.mkdir()
        (pasta / f"{nome}.md").write_text(texto, encoding="utf-8")


def test_ingestao_busca_e_roteamento(tmp_path):
    configurar_tmp(tmp_path)
    resumo = chroma_memoria.indexar_dominios()
    assert resumo["colecoes"]["codigo"]["blocos"] == 1
    assert "FastAPI" in chroma_memoria.buscar_no_chroma("como validar uma API em Python", "codigo")
    assert roteador_semantico.classificar_consulta("qual a cobertura da apólice?")["colecao"] == "seguros"
    assert roteador_semantico.classificar_consulta("como usar cannabis medicinal?")["colecao"] == "cannabis"


def test_novo_dominio_configuravel(tmp_path):
    configurar_tmp(tmp_path)
    nova = tmp_path / "juridico"
    nova.mkdir()
    (nova / "contratos.md").write_text("Cláusulas de contrato e responsabilidade civil.", encoding="utf-8")
    dominios = chroma_memoria.dominios_configurados()
    dominios["juridico"] = {"nome": "Jurídico", "pastas": [str(nova)], "palavras": ["contrato"], "ativo": True}
    chroma_memoria.salvar_dominios(dominios)
    assert "juridico" in chroma_memoria.dominios_configurados()
    assert roteador_semantico.classificar_consulta("revisar contrato")["colecao"] == "juridico"
