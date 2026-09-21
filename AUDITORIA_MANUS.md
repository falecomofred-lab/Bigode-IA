# PROMPT PARA MANUS IA — AUDITORIA TÉCNICA DO PROJETO BIGODE IA

> Cole este documento inteiro no Manus, junto com o repositório `falecomofred-lab/Bigode`.

---

## 1. QUEM É O AUTOR

Fred, Venure. **Não sou programador profissional** — Python e PHP em nível intermediário.
Preciso de **solução pronta**: arquivo completo, caminho exato onde salvar, e como testar.
Não quero tutorial de como programar.

**Seja duro.** Se minha premissa está errada, diga na primeira linha. Não quero validação.

---

## 2. O QUE É O BIGODE IA (fatos, não suposições)

Plataforma de IA **100% local**, que roda de um pendrive. Chat no navegador, modelo local
via llamafile, 34 ferramentas que mexem em arquivos de verdade, memória de projetos, voz
(Whisper), extensão Chrome, app no celular via Wi-Fi, e uma ponte MCP para o Claude.

**Premissa fundadora:** nada sai do computador, sem nuvem, sem mensalidade, custo zero por
mensagem.

### Stack real

- **Python 3.11+, ZERO dependências externas** — só biblioteca padrão (`http.server`,
  `urllib`, `subprocess`, `threading`). Sem `requests`, sem framework.
- **4.382 linhas** em 9 módulos. `cerebro.py` (1.731) é orquestrador + servidor HTTP.
  `ferramentas.py` (1.068) são as 34 ferramentas. `modelos.py` (341) é a camada de
  abstração do motor.
- Frontend: `web/index.html` — a interface inteira num arquivo só.
- Motor: **llamafile** em `localhost:8082`, API compatível com OpenAI
  (`/v1/chat/completions`), com `stream: true` e function calling nativo.
- Loop de agente: `max_passos = 8`, com `tool_choice: "required"` forçado quando o modelo
  tenta responder de cabeça sobre arquivos.

### Configuração atual

```
contexto: 8192      max_tokens: 1000    temperatura: 0.45
threads: 8 (-t)     threads_leitura: todos os núcleos (-tb)
--parallel 1        timeout: 1800s      porta: 7000
```

### Hardware

**Ryzen 7 5825U, 32 GB RAM, SEM PLACA DE VÍDEO.** Modelo carregado de um pendrive USB.

### Desempenho medido

| Modelo | Tamanho | Velocidade | Ferramentas |
|---|---|---|---|
| Qwen2.5-Coder 7B | 4,7 GB | **3,8 tok/s** | nativas |
| Qwen3-Coder 30B-A3B (MoE) | 19 GB | **2,9 tok/s** | nativas |
| Granite 4.0 H-Tiny (7B-A1B) | 4,2 GB | rápido, inventa mais | nativas |
| DeepSeek-Coder-V2 | 8,9 GB | descartado (sem tool template, respondia em chinês) | — |

**Uma resposta de dez linhas leva quase um minuto.**

### O que JÁ foi otimizado (não repita isso)

- Prompt fixo caiu de 4.826 → ~2.000 tokens.
- Nada é acrescentado ao fim do system prompt (preserva o cache de prefixo do motor).
- Lista de ferramentas fixa, não varia por pergunta.
- `--parallel 1`, `-tb` com todos os núcleos (geração é limitada por banda de memória).
- Streaming já implementado ponta a ponta (SSE).
- Ponte MCP não passa mais pelo modelo local — o Claude escolhe a ferramenta, o Bigode só executa.

**Minha conclusão atual:** "software chegou ao limite; 3,8 tok/s é o teto físico dessa
máquina sem GPU." **Sua primeira tarefa é confirmar ou destruir essa conclusão.**

### Problemas conhecidos

1. **Lentidão** (acima).
2. **O modelo local inventa** quando não sabe. Foram construídas 6 travas contra isso
   (`tool_choice: required`, `raio_x` sem participação do modelo, sugestão de nomes
   parecidos, aviso de código sem leitura, `temperamento.md` com 620 tokens de disciplina).
3. **Contexto de 8192 estoura** em prompts longos e corta mensagens.
4. **Não é cliente MCP** — não consome MCPs externas.

---

## 3. O QUE EU QUERO

Um agente que recebe minha solicitação e **executa sozinho** — no Drive, no meu computador,
onde eu pedir. Principalmente desenvolvimento e programação. Semelhante ao Claude Code.

Hoje a divisão de trabalho é: Claude pensa e escreve código longo; Bigode lê, lista, roda
comando. **Quero que o Bigode assuma mais dessa fatia.**

---

## 4. FASE 1 — A PERGUNTA QUE VEM ANTES DE TUDO

> **A premissa "100% local, de pendrive, sem GPU" é compatível com o objetivo "agente
> autônomo que programa como o Claude Code"?**

Responda isso com números antes de qualquer recomendação. Se for incompatível, diga
claramente **qual das duas coisas eu tenho que abandonar** e apresente o custo de cada
caminho. Não tente agradar aos dois.

Decomponha o tempo de resposta atual:

- Tempo de carga do modelo **a partir do pendrive** (USB 3.0 ≈ 100–400 MB/s — quanto disso
  é I/O? Um GGUF de 19 GB via `mmap` em USB é gargalo real ou o llamafile carrega tudo em
  RAM antes?)
- Prompt processing (prefill) vs. token generation
- Tempo gasto fora do LLM: ferramentas, I/O, parsing
- Tempo perdido em passos do loop de agente que poderiam ser evitados ou paralelizados
- Quantas das 8 iterações de `max_passos` são realmente usadas na prática

Entregue **tabela em milissegundos** e o percentual que é inferência pura.

---

## 5. FASE 2 — ACELERAÇÃO, EM TRÊS FAIXAS

### Faixa A — Sem trocar hardware nem quebrar a premissa local

Avalie especificamente, com número estimado de ganho:

- **Speculative decoding** (`--model-draft` no llama.cpp): um modelo rascunho de 0.5B
  puxando o Qwen 7B. Quanto rende em CPU? Vale?
- **llamafile vs. llama-server compilado nativo** — o llamafile ainda é competitivo ou
  já ficou para trás das builds atuais do llama.cpp?
- **Quantização**: hoje qual quant está em uso? Q4_K_M vs IQ4_XS vs Q4_0 com repacking
  para AVX2 — o Ryzen 5825U (Zen 3, AVX2 sem AVX-512) se beneficia de qual?
- **Rodar o modelo do SSD interno em vez do pendrive**, mantendo só o código no pendrive.
- **KV cache quantizado** (`-ctk q8_0 -ctv q8_0`) para subir o contexto de 8192 → 16384
  sem estourar RAM nem perder velocidade.
- **`-t` ideal**: 8 threads num 5825U (8 núcleos / 16 threads) é o ótimo? Meça 6, 8, 12, 16.
- **Reduzir passos do agente**: quantas chamadas ao modelo uma tarefa típica consome, e
  quantas dá para eliminar com melhor prompt de ferramentas.

### Faixa B — Roteamento por tarefa (a mudança que a arquitetura já permite)

`modelos.py` já isola o motor do resto do sistema — escrever outro adaptador não toca em
mais nada. Avalie:

- **Modelo pequeno e rápido para tarefas curtas** (listar, buscar, classificar) e modelo
  forte só quando o pedido exige raciocínio ou código.
- **Adaptador de nuvem opcional, desligado por padrão**, para quando eu conscientemente
  quiser velocidade em vez de privacidade. Compare com dados e **link de fonte de agosto
  de 2026**: Groq, Cerebras, Together, Fireworks, DeepInfra, OpenRouter — tokens/s reais,
  custo por milhão de tokens, e quais modelos abertos de código eles servem.
- Diga honestamente **quanto custaria por mês** no meu volume de uso, e se "custo zero"
  ainda se justifica quando o preço é um minuto por resposta.

### Faixa C — Hardware

- **eGPU ou desktop com GPU usada.** Quanto uma RTX 3060 12 GB / 4060 Ti 16 GB entrega
  em tok/s com Qwen2.5-Coder 7B e com Qwen3-Coder 30B-A3B? Qual o custo no Brasil hoje?
- Compare: **quantos meses de API paga** equivalem ao preço da GPU.
- Um 5825U é um chip de notebook de baixo consumo — diga se o problema é arquitetural
  (banda de memória DDR4 dual-channel) e se existe teto que nenhum software resolve.

**Para cada recomendação: ganho estimado, esforço em horas, risco, e o arquivo completo
já pronto com o caminho de destino.**

---

## 6. FASE 3 — AGENTE AUTÔNOMO

Audite o loop atual em `cerebro.py` (`max_passos`, `tool_choice`, tratamento de erro de
ferramenta) contra o estado da arte, e responda:

1. **O que falta** no loop para ele se autocorrigir a partir de erro de execução e saber
   quando parar.
2. **Bigode como cliente MCP** — hoje ele é só servidor. Quanto custa virar cliente e o
   que isso destrava (usar as MCPs que já existem em vez de escrever 34 ferramentas à mão).
3. **Comparação honesta com o que já existe pronto**: Claude Agent SDK, OpenHands, Aider,
   Cline, Goose, Continue. **Diga o que dessas eu deveria simplesmente adotar** em vez de
   reconstruir — e o que o Bigode tem que nenhuma delas tem (rodar de pendrive, offline,
   em português, com memória de projeto e travas contra invenção). Se a resposta for
   "adote X e mantenha só a sua camada", diga isso sem rodeio.
4. **Modelos abertos que programam bem e cabem em 32 GB sem GPU** — levantamento atualizado
   de agosto de 2026, com foco em MoE de poucos parâmetros ativos, suporte nativo a tool
   calling e desempenho em benchmarks de código. Cubra no mínimo Qwen3, GLM, Granite,
   Devstral, Mistral, Gemma, Phi, Kimi, DeepSeek — com link de fonte.
5. **Segurança.** O Bigode escreve em disco, roda terminal e controla o Chrome. Avalie:
   sandbox de execução, escopo de `pastas_liberadas`, e principalmente **prompt injection**
   vinda de arquivo lido ou página web — um agente autônomo com terminal liberado é
   superfície de ataque séria. Trate como requisito, não como observação.

---

## 7. FASE 4 — CRÍTICA (seção obrigatória)

- Qual premissa minha está errada?
- Que oportunidade óbvia eu estou deixando passar?
- O que no Bigode deveria ser **deletado** ou trocado por ferramenta pronta?
- As 6 travas contra invenção são engenharia legítima ou sintoma de que o modelo é pequeno
  demais para a tarefa — e eu estou compensando limitação de modelo com código?
- Vale continuar construindo, ou o custo de manter supera o de assinar algo pronto?
- Qual o maior risco técnico que eu ainda não vi?

---

## 8. FORMATO DA ENTREGA

1. **Sumário executivo** — 10 linhas, os 3 achados que mais importam.
2. **Veredito sobre a premissa** (Fase 1), com números.
3. **Tabela de latência** — etapa, ms, causa, ação, ganho estimado.
4. **Roadmap** — Esta semana / Este mês / Trimestre, ordenado por impacto ÷ esforço.
5. **Código pronto** — arquivos completos, caminho exato, como validar.
6. **Comparativos** — modelos, provedores, frameworks: em tabela, **link de fonte em cada
   número**. Sem fonte, marque como estimativa.
7. **Riscos e plano de reversão.**

**Regras:** preserve a estrutura atual e a filosofia de zero dependências externas.
Prefira sempre a solução mais simples e estável. Não proponha refatoração grande antes de
esgotar as de baixo impacto. Se faltar informação essencial, pergunte o mínimo.

---

*Venure — venure.com.br*
