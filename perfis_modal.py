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
        # L4 de 24 GB: o modelo tem 4,7 GB, sobra memória de sobra.
        "placa": "L4",
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
        "placa": "L4",
        "nota": "DeepSeek-Coder-V2-Lite · deepseek-license · SEM ferramenta nativa",
    },
}

# ══════════════════════════════════════════════════════════════════════
# O GURU FOI RETIRADO                                     (21/09/2026)
# ══════════════════════════════════════════════════════════════════════
#
#   Ele esta abaixo, fora do dicionario, de proposito: o codigo nao le,
#   o cartao nao aparece na tela, e o texto fica para quem quiser retomar
#   um dia sabendo o que ja deu errado.
#
#   POR QUE SAIU
#       Foi sugestao minha, nao pedido do Fred. A prioridade dele sempre
#       foi o Qwen 7B e o DeepSeek, os dois que ja funcionavam. O guru
#       consumiu duas rodadas de erro meu -- o perfis_modal que nao ia
#       junto na imagem, e o BIGODE_PERFIL que nao viaja para dentro do
#       conteiner -- e nao entregou nada em troca.
#
#   O QUE ELE ENSINOU, E QUE FICA VALENDO
#       As duas correcoes que ele obrigou estao no modal_motor.py e valem
#       para os outros perfis tambem: a tabela viaja na imagem, e o perfil
#       escolhido no deploy e gravado na imagem em vez de depender de uma
#       variavel de ambiente que morre na fronteira.
#
#   SE UM DIA VOLTAR
#       Bastaria mover este bloco para dentro do PERFIS. Mas antes:
#       apagar o volume, porque o que ficou la dentro foi o Qwen de 7B.
#
# "guru": {
#     "app": "bigode-guru",
#     "repo": "bartowski/Qwen2.5-32B-Instruct-GGUF",
#     "arquivo": "Qwen2.5-32B-Instruct-Q4_K_M.gguf",
#     "janela": 32768,
#     "placa": "L40S",
#     "nota": "Qwen2.5 32B Instruct · Apache 2.0 · o guru",
#     "so_na_placa": True,
# }
_GURU_RETIRADO = """
    #
    #   O teto da maquina do Fred e 7B: acima disso nao cabe na memoria, e
    #   o que cabe roda a 1,5 palavra por segundo. Na placa esse teto nao
    #   existe, e e ai que a conversa muda de qualidade -- nao "um pouco
    #   melhor", outra categoria de resposta.
    #
    #   POR QUE 32B E NAO 72B
    #       O 72B em Q4 pede ~47 GB. Caberia numa L40S de 48 raspando, sem
    #       espaco para a janela de contexto -- e "raspando" na nuvem
    #       significa container que morre no meio da resposta, cobrando.
    #       O 32B em Q4_K_M tem ~20 GB: sobra metade da placa para janela
    #       grande e para o cache do llama.cpp.
    #
    #   POR QUE Instruct E NAO Coder
    #       Os outros dois ja sao de codigo. O papel deste e ser o guru:
    #       seguro, consorcio, cannabis, texto corrido em portugues. O
    #       Instruct e muito melhor nisso, e continua escrevendo codigo bem.
    #
    #   CUSTO, SEM ENFEITE
    #       L40S a $0.000542/s = ~US$ 1,95 por hora LIGADA. Com
    #       scaledown_window de 5 min, uma conversa de 20 minutos custa
    #       cerca de 80 centavos de dolar. Nao e o Qwen 7B na L4; tambem
    #       nao e caro perto do que e.
    #
    #   O Volume dele guarda ~20 GB, e isso e cobrado por mes mesmo parado.
    #   Se voce parar de usar:
    #       python -m modal volume delete bigode-modelos-guru
    "guru": {
        "app": "bigode-guru",
        "repo": "bartowski/Qwen2.5-32B-Instruct-GGUF",
        "arquivo": "Qwen2.5-32B-Instruct-Q4_K_M.gguf",
        "janela": 32768,
        "placa": "L40S",
        # Apache 2.0 -- a familia Qwen2.5 inteira e Apache, exceto o 72B
        # e o 3B. Este pode ir para dentro de produto que voce vende.
        "nota": "Qwen2.5 32B Instruct · Apache 2.0 · o guru",
        # Nao existe copia deste modelo no seu disco, e nem deve existir:
        # sao 20 GB que a sua maquina nao roda. A tela precisa saber disso
        # para mostrar o cartao mesmo sem achar o .gguf em pasta nenhuma.
        "so_na_placa": True,
    },
"""

NOMES = tuple(PERFIS)


def por_arquivo():
    """{nome_do_gguf_em_minusculas: (perfil, dados)} — para casar com o disco.

    O amarrador entre a placa e a maquina e o NOME DO ARQUIVO .gguf: e o
    mesmo nos dois lados, e e a mesma chave que o `listar()` do modelos.py
    ja usa para deduplicar copias.
    """
    return {str(d.get("arquivo", "")).lower(): (nome, d)
            for nome, d in PERFIS.items() if d.get("arquivo")}
