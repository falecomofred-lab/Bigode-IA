"""OS MOTORES QUE EXISTEM NA MODAL — só a tabela, sem nenhuma dependência
Venure · venure.com.br · 18/09/2026

POR QUE ESTE ARQUIVO NASCEU

    A tabela morava dentro do `modal_motor.py`, que começa com
    `import modal`. Para a tela do Bigode saber quais modelos existem na
    placa, o `cerebro.py` importava aquele arquivo -- e junto vinha a
    exigência da biblioteca `modal`.

    O Bigode roda no Python portátil do projeto, onde a `modal` NÃO está
    instalada. O import falhava, o meu `try/except` devolvia dicionário
    vazio, e a tela mostrava os cartões SEM o botão da placa -- sem erro
    nenhum, sem aviso, como se a Modal não existisse.

    O Fred recarregou, viu "AQUI" em todos os cartões e perguntou onde
    estava o botão roxo. A resposta era: escondido atrás de um import que
    falha em silêncio.

    A lição, que já apareceu outras vezes hoje: `except Exception: pass`
    transforma "está quebrado" em "não existe". Quando o dado é uma
    TABELA, ele não precisa de biblioteca nenhuma para ser lido -- basta
    não estar no mesmo arquivo que precisa dela.

QUEM USA

    modal_motor.py   importa daqui e publica o app do perfil escolhido
    cerebro.py       importa daqui para marcar os cartões da tela
    motor_perfil.py  usa os nomes para validar o que você pediu

    Um lugar só. Acrescentar um modelo novo é acrescentar uma entrada
    aqui, e os três passam a conhecê-lo.
"""

PERFIS = {
    # O que voce ja media como mais confiavel para codigo nesta maquina, e
    # que faz chamada de ferramenta NATIVA -- o template dele tem secao de
    # tools. E o padrao por isso.
    "conversa": {
        "app": "bigode-motor",
        "repo": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "arquivo": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        "janela": 16384,
        # Apache 2.0, "gated": false -- conferido em 14/09 na API do HF.
        "nota": "Qwen2.5-Coder 7B · Apache 2.0 · ferramenta nativa",
    },
    # DeepSeek-Coder-V2-Lite: 15,7B no papel, mas MoE -- so ~2,4B ativos por
    # token. Numa PLACA isso o deixa rapido; na CPU do Fred, medido em
    # 18/09, escreve a 1,5 tok/s (o Qwen 7B faz 3,8). MoE em processador
    # paga o trafego de memoria do modelo inteiro sem a economia de conta.
    #
    # DUAS RESSALVAS, E AS DUAS IMPORTAM:
    #
    #   1. NAO FAZ CHAMADA DE FERRAMENTA NATIVA. O chat template dele e o
    #      formato antigo "User: / Assistant:", sem secao de tools. O
    #      cerebro.py cai no protocolo de texto, que funciona e erra mais.
    #
    #   2. A LICENCA NAO E APACHE. E a "deepseek-license": permite uso
    #      comercial, mas com restricoes que o Apache nao tem. Para
    #      escrever codigo seu, tranquilo. Vale ler antes de embutir a
    #      saida dele em produto que voce vende.
    "codigo": {
        "app": "bigode-coder",
        "repo": "bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF",
        "arquivo": "DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf",
        # 10,4 GB de pesos numa L4 de 24: da para abrir a janela.
        "janela": 32768,
        "nota": "DeepSeek-Coder-V2-Lite · deepseek-license · SEM ferramenta nativa",
    },
}

NOMES = tuple(PERFIS)


def por_arquivo():
    """{nome_do_gguf_em_minusculas: (perfil, dados)} — para casar com o disco.

    O amarrador entre a placa e a maquina e o NOME DO ARQUIVO .gguf: e o
    mesmo nos dois lados, e e a mesma chave que o `listar()` do modelos.py
    ja usa para deduplicar copias.
    """
    return {str(d.get("arquivo", "")).lower(): (nome, d)
            for nome, d in PERFIS.items() if d.get("arquivo")}
