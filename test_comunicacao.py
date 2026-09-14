import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from cerebro import limpar_resposta, consulta_web_direta


def test_remove_ps_e_convites_repetidos():
    texto = (
        "Encontrei o arquivo e vou revisar.\n\n"
        "P.S.: Se você tiver alguma outra pergunta, estou pronto para ajudar.\n"
        "P.S.2: Se você tiver alguma outra pergunta, estou pronto para ajudar.\n"
    )
    assert limpar_resposta(texto) == "Encontrei o arquivo e vou revisar."


def test_preserva_conteudo_tecnico():
    texto = "Corrigi o endpoint /api/skills.\n\nA validação passou."
    assert limpar_resposta(texto) == texto


def test_detecta_pesquisa_direta_sem_pedir_palavras_chave():
    assert consulta_web_direta("pesquisar sobre cannabis") == "cannabis"
    assert consulta_web_direta("pesquise sobre regulamentação da cannabis") == "regulamentação da cannabis"
    assert consulta_web_direta("abra uma aba") == ""


# ---------------------------------------------------------------------------
# A excecao "pergunta sobre o proprio Bigode" nao pode enfraquecer o selo.
#
# Existe porque a primeira versao dela tinha a marca "te ", que casou com
# "mais recenTE" e desligou a trava numa pergunta que precisava dela.
# ---------------------------------------------------------------------------

def test_excecao_sobre_si_nao_enfraquece_o_selo():
    import cerebro
    import auditar_selo
    for codigo, pergunta in auditar_selo.PERGUNTAS:
        pela_lista = any(g in pergunta.lower() for g in cerebro.GATILHOS_FONTE)
        if pela_lista:
            assert cerebro.precisa_fonte(pergunta), (
                "%s deixou de exigir fonte: alguma marca de SOBRE_SI casou "
                "no meio de outra palavra." % codigo)


def test_conversa_sobre_o_bigode_nao_manda_pesquisar():
    import cerebro
    for frase in ("Quantos passos você costuma dar antes de responder?",
                  "Atualmente, qual é o seu jeito de trabalhar comigo?",
                  "Bom dia! Como você está hoje?"):
        assert not cerebro.precisa_fonte(frase), frase
