from pathlib import Path

import chroma_memoria
import cerebro
import ferramentas


def test_arquivo_sensivel_nao_entra_nas_ferramentas():
    assert ferramentas._sensivel("config.json")
    assert ferramentas._sensivel(".env")
    assert ferramentas._sensivel("credencial.pem")
    assert not ferramentas._sensivel("README.md")


def test_busca_nao_troca_silenciosamente_pasta_nao_autorizada():
    assert "NEGADO" in ferramentas.buscar("qualquer coisa", "/fora-do-projeto")


def test_config_publica_remove_segredos():
    original = cerebro.config
    try:
        cerebro.config = lambda: {
            "porta": 7000,
            "github_token": "segredo",
            "codigo_acesso": "codigo",
            "chave_extensao": "chave",
            "login_social": {
                "google": {"client_id": "id", "client_secret": "secret"},
                "github": {"client_id": "", "client_secret": ""},
            },
        }
        publico = cerebro.config_publica()
        assert "github_token" not in publico
        assert "codigo_acesso" not in publico
        assert "chave_extensao" not in publico
        assert publico["login_social"]["google"] == {"configurado": True}
    finally:
        cerebro.config = original


def test_indexador_inclui_codigo_e_exclui_credenciais(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "interface.tsx").write_text("export default 1", encoding="utf-8")
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".env.local").write_text("TOKEN=x", encoding="utf-8")
    nomes = {p.name for p in chroma_memoria._arquivos_indexaveis([str(tmp_path)])}
    assert {"main.py", "interface.tsx"} <= nomes
    assert "config.json" not in nomes
    assert ".env.local" not in nomes
