# Bigode IA

**Sua IA, na sua máquina.**

Assistente de texto que roda no seu computador, lê suas pastas, usa seu
navegador e não manda conversa nenhuma para fora.

Plataforma da **Venure** — [venure.com.br](https://venure.com.br)

---

## O que ele faz

| | |
|---|---|
| **Conversa** | Interface web em português, com histórico e projetos. |
| **Motor** | llama.cpp local, ou a mesma coisa numa placa sob demanda. |
| **Ferramentas** | Lê e escreve arquivos, pesquisa na web, controla o Chrome, desenha (via Pipi IA). |
| **Voz** | Whisper large-v3. Fala e para sozinho quando você cala. |
| **Extensão** | Barra lateral do Chrome: lê a página aberta, digita, clica. |

## Onde o motor roda — você escolhe

**Na sua máquina.** llama.cpp com um modelo GGUF. Nada sai do computador.
Custo zero, velocidade do seu processador.

**Numa placa sob demanda.** O mesmo llama.cpp, a mesma API, numa L4 da
Modal. Liga quando você pergunta, desliga sozinha depois. Respostas em
segundos em vez de minutos.

Trocar entre os dois é uma linha no `config.json` — não há dois códigos
para manter. Foi decisão de projeto: caminho duplicado diverge sozinho.

## Instalação

```bash
git clone https://github.com/falecomofred-lab/Bigode-IA.git
cd Bigode-IA
pip install -r requirements.txt
cp config.example.json config.json
```

Baixe um modelo GGUF (Qwen2.5-Coder 7B Q4_K_M é o recomendado) e aponte
o caminho no `config.json`. Depois:

```bash
BIGODE.bat            # Windows
python cerebro.py     # qualquer sistema — abre em http://localhost:7000
```

Para usar a placa sob demanda:

```bash
python -m modal secret create bigode-token BIGODE_TOKEN=<uma-senha-longa>
python -m modal deploy modal_motor.py
python usar_modal_motor.py
```

E para a voz:

```bash
python -m modal deploy modal_voz.py
python usar_modal_voz.py
```

## Extensão do Chrome

`chrome://extensions` → Modo do desenvolvedor → Carregar sem compactação
→ escolha a pasta `extensao-chrome`.

Ela pede aprovação antes de qualquer ação que mexa na página: clicar,
digitar, enviar formulário. Comando destrutivo e campo de senha aparecem
destacados no pedido.

## Segurança

O servidor escuta só em `127.0.0.1`. Conversas, projetos e memória ficam
no seu disco.

Credenciais moram em `config.json`, `conexoes.json` e `usuarios.json` —
todos fora do controle de versão pelo `.gitignore`. Este repositório é
privado e não contém segredo nenhum.

## Conferir antes de publicar

```bash
python TESTAR_TUDO.py
```

Procura credencial em todo arquivo versionável, compila todos os `.py` e
verifica a estrutura das duas páginas. Sai com código 0 só se tudo passar.

## Direitos

© 2026 Venure. Bigode IA é uma marca da Venure. Todos os direitos
reservados.

Os modelos de linguagem usados têm licença própria (Apache 2.0 no caso do
Qwen2.5 e do Granite) e não são redistribuídos aqui.

---

**Venure** · [venure.com.br](https://venure.com.br) · *Tecnologia que muda vidas*
