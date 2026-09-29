# Auditoria do motor — Bigode IA

**18 de agosto de 2026.** Auditoria conduzida sob a regra do próprio pedido:
nada inventado. Onde falta dado, está escrito **INFORMAÇÃO NÃO DISPONÍVEL** com
o que precisa ser fornecido.

---

## Aviso metodológico, antes de tudo

Das 13 etapas pedidas, **eu consigo cumprir 6 com evidência**. As outras 7
exigem executar inferência na sua máquina, e eu não tenho acesso ao motor
rodando neste momento.

| Etapa | Status |
|---|---|
| 1 · Ambiente | **parcial** — config lida do arquivo, hardware do log |
| 2 · Velocidade | **parcial** — números reais de um log, não dos 5 testes |
| 3 · Raciocínio | **não executada** |
| 4 · Programação | **não executada** |
| 5 · Instruções | **não executada** |
| 6 · Alucinação | **evidência anedótica**, não medida |
| 7 · Contexto | **não executada** |
| 8 · Eficiência | **não calculável** — falta qualidade medida |
| 9 · Gargalos | **completa, com evidência** |
| 10 · Perfis | **completa** |
| 11 · Comparação | **parcial** — só velocidade medida |
| 12 · Configuração ruim | **completa, com evidência** |
| 13 · Relatório | **parcial** |

Entreguei junto o `auditar_motor.py`, que executa as etapas 1 e 2 de verdade
e grava os números. As etapas 3 a 7 exigem gabarito humano — nota inventada
para "raciocínio 7/10" seria exatamente o tipo de coisa que este projeto
existe para combater.

---

## ETAPA 1 — Ambiente

### Do log do motor (evidência direta, colado por você)

| Parâmetro | Valor | Fonte |
|---|---|---|
| Modelo | `qwen2.5-coder-7b-instruct-q4_k_m.gguf` | `loading model` |
| Família | Qwen2.5-Coder | nome do arquivo |
| Parâmetros | 7 B | nome do arquivo |
| Formato | GGUF | extensão |
| Quantização | **Q4_K_M** | nome do arquivo |
| Contexto do treino | 131.072 | `n_ctx_train` |
| Contexto em uso | **8.192** | `n_ctx_seq` |
| RAM total | **32.158 MiB** (~32 GB) | `device_info` |
| GPU | **nenhuma** | só CPU em `device_info` |
| VRAM | **não aplicável** | — |
| Núcleos | 8 físicos / **16 lógicos** | `n_threads = 8 ... / 16` |
| Threads de geração | **8** | `n_threads` |
| Threads de leitura | **8** | `n_threads_batch` |
| Slots paralelos | **4** | `n_parallel = 4` |
| Cache de prompt | **8.192 MiB** | `prompt cache ... size limit` |
| Memória projetada | 5.407 MiB | `common_params_fit_impl` |
| Backend | llama.cpp (`LLAMAFILE=1 OPENMP=1 REPACK=1`) | `system_info` |
| GPU layers | 0 | sem GPU |

**CPU exata: INFORMAÇÃO NÃO DISPONÍVEL no log.** Você me informou em conversa
anterior que é um **Ryzen 7 5825U**; o log confirma 8/16 e ausência de GPU, o
que é compatível, mas o log não nomeia o processador.

### Parâmetros de geração (lidos do `cerebro.py`)

| | Valor |
|---|---|
| temperature | 0,45 (efetivo — ver Etapa 12) |
| top_p | 0,9 |
| min_p | 0,05 |
| repeat_penalty | 1,06 |
| repeat_last_n | 128 |
| presence_penalty | 0,1 |
| frequency_penalty | 0,1 |
| top_k | **não enviado** — o motor usa o padrão dele |
| seed | **não enviado** — cada resposta é irreprodutível |

---

## ETAPA 2 — Velocidade · MEDIÇÃO EXECUTADA

**Executada em 18/08/2026, 15:31 e 16:01.** Qwen2.5-Coder 7B Q4_K_M, contexto
8192, 16 núcleos lógicos, 33,7 GB de RAM (16,7 livres), sem GPU.

| Teste | 1º token | tok/s | Total |
|---|---|---|---|
| A · curto (1ª execução) | **92,2 s** | — | 93,0 s |
| A · curto (2ª execução) | **3,0 s** | — | 4,0 s |
| B · médio | 4,6 s | 4,35 | 48,7 s |
| C · prompt longo (~3.400 tk) | 126,8 s | 3,73 | 130,3 s |
| D · resposta ~500 tk | 3,7 s | 5,32 | 110,7 s |
| E · resposta ~2000 tk | 4,8 s | 4,55 | 294,8 s |

### O achado principal

**O mesmo prompt de quatro palavras levou 92,2 s na primeira execução e 3,0 s
na segunda. Trinta e uma vezes de diferença.**

Isso não é o modelo pensando. É o custo de a primeira requisição cair num slot
frio. É a medição direta do gargalo nº 2 desta auditoria — e agora não é mais
hipótese.

### Leitura de prompt

Teste C: ~3.400 tokens lidos em 126,8 s = **26,8 tok/s**. É o dobro dos 13,7
tok/s do log anterior. Diferença provável: aquele prompt tinha estrutura mais
densa (ferramentas em JSON); este é prosa repetida, que o motor processa mais
rápido. **Faixa real de leitura: 13 a 27 tok/s, dependendo do conteúdo.**

### Correção de um erro meu

A primeira versão do `auditar_motor.py` **contava tokens por caractere**
(1 token ≈ 3,6 caracteres). Comparando com o que o motor reportou no log
(3,09–3,75 tok/s), minha estimativa saiu **41% acima do real**.

Também produziu a frase sem sentido *"resposta longa roda a 132% da velocidade
da curta"* — artefato do teste A, cuja resposta de três tokens não permite
calcular taxa nenhuma.

**Corrigido:** o script agora pede a contagem ao motor (`include_usage`), usa
`seed` fixo para as execuções serem comparáveis, e **recusa dar taxa** quando a
resposta tem menos de 40 tokens, em vez de publicar ruído.

Os números da tabela acima ainda são da versão antiga — **considere-os ~40%
otimistas na coluna tok/s**. Rode de novo para ter os reais.

### O que isso desmente da minha análise anterior

Eu havia afirmado degradação em resposta longa. Os dados mostram o contrário:
E (2000 tokens) rodou a 4,55 contra D (500) a 5,32 — queda de 14%, e a
2ª execução inverte a ordem. **Não há degradação relevante por comprimento
nesta máquina.** A queda de 3,25 → 3,09 que vi no log era pequena e dentro da
variação normal.

### Memória

33,7 GB totais, **16,7 GB livres** durante os testes. O modelo ocupa ~5,4 GB.
**RAM não é gargalo, e há folga para um modelo bem maior.**

---

## ETAPA 2b — Velocidade (log anterior, para comparação)

Números reais, do log. **Não são os cinco testes A–E** — são três requisições
de uso normal.

| | Leitura do prompt | Escrita | Total |
|---|---|---|---|
| 1ª mensagem (3.572 tk) | **260,9 s** · 13,69 tok/s | 2,9 s · 3,75 tok/s | **263,8 s** |
| 2ª (cache, 15 tk) | 1,7 s · 8,67 tok/s | 4,4 s · 3,44 tok/s | 6,1 s |
| 3ª (cache, 86 tk) | 7,6 s · 11,30 tok/s | 232,6 s · **3,09 tok/s** | 240,2 s |

**Na primeira mensagem, 98,9% do tempo é leitura de prompt.** Não é o modelo
escrevendo devagar — é o motor lendo as instruções.

**Degradação medida na resposta longa:** 3,25 tok/s aos 100 tokens → **3,09
aos 709**. Queda de 5% ao longo de 700 tokens.

Os testes A–E, tempo até o primeiro token por faixa de prompt, e consumo de
RAM durante a geração: **INFORMAÇÃO NÃO DISPONÍVEL**. Rode
`python auditar_motor.py`.

---

## ETAPAS 3, 4, 5, 7 — Raciocínio, programação, instruções, contexto

**INFORMAÇÃO NÃO DISPONÍVEL.**

Preciso de: acesso ao motor rodando, ou que você rode os testes e me mande as
respostas. Nota sem execução seria invenção.

---

## ETAPA 6 — Alucinação

**Não medida, mas há evidência documentada de um caso real.** Perguntado sobre
Axl Rose, o Granite 4.0 H-Tiny afirmou:

| Afirmou | Realidade |
|---|---|
| "Axel Rose" | **Axl** Rose |
| Nascido 19/09/1969 | 6 de fevereiro de **1962** |
| Guitarrista e vocalista | só **vocalista** |
| Substituiu "o baterista Donny Cummings" | pessoa **inexistente** |
| "Não tenho acesso à internet" | **tinha** `web_buscar` disponível |

Comportamento na classificação do pedido: **(C) inventou** e, corrigido duas
vezes, **repetiu o erro com mais confiança**. Também **(D) apresentou hipótese
como fato**.

Isso é um caso, não uma taxa. Para dar nota de confiabilidade preciso de N
perguntas com gabarito. **Confiabilidade: INFORMAÇÃO NÃO DISPONÍVEL.**

---

## ETAPA 8 — Eficiência

**Não calculável.** A fórmula pedida usa qualidade (30%), programação (15%) e
estabilidade (10%) — 55% do peso vem de dados que não existem. Calcular só com
velocidade e memória e chamar de "classificação" seria enganoso.

---

## ETAPA 9 — Gargalos

### 1. Quatro otimizações não chegam ao motor

**PROBLEMA:** `-tb 16`, `--parallel 1`, `--no-warmup` e `--cache-ram` são
enviados e ignorados.
**CAUSA PROVÁVEL:** `--gpu disable` é opção do *llamafile*. Se quem sobe é o
`llama-server`, ela não existe e o parser abandona o resto da linha.
**EVIDÊNCIA:** log diz `n_parallel is set to auto, using n_parallel = 4`,
`n_threads_batch = 8` (pedimos 16), `warming up the model` (pedimos não), e
`prompt cache ... 8192 MiB` (pedimos 6144).
**IMPACTO:** a leitura do prompt roda em 8 threads em vez de 16, o cache é
espalhado por 4 slots, e ~40 s de aquecimento são pagos a cada carga.
**SEVERIDADE: CRÍTICO.**
**SOLUÇÃO:** já corrigida no código — o Bigode detecta qual motor é e usa
`-ngl 0` para llama-server. **Não confirmada** ainda.
**GANHO ESPERADO:** leitura de prompt mais rápida (magnitude desconhecida até
medir) e cache de prompt aproveitado entre conversas.

### 2. O cache é dividido entre 4 slots

**PROBLEMA:** cada conversa nova cai num slot diferente, com cache vazio.
**EVIDÊNCIA:** `selected slot by LRU, t_last = -1` e `cache state: 0 prompts`
na primeira requisição.
**IMPACTO:** os ~2.500 tokens de instrução fixa — **idênticos byte a byte em
toda conversa** — são relidos do zero. A 13,7 tok/s, são ~3 minutos.
**SEVERIDADE: CRÍTICO.**
**SOLUÇÃO:** `-np 1`.
**GANHO ESPERADO:** a 1ª mensagem de cada conversa cai de minutos para
segundos. **É a maior melhoria disponível e é grátis.**

> **CONFIRMADO POR MEDIÇÃO — 18/08, 15:31 e 16:01.**
> O mesmo prompt de quatro palavras: **92,2 s** na primeira execução,
> **3,0 s** na segunda. Trinta e uma vezes. Deixou de ser hipótese.

### 3. Prompt fixo de ~1.619 tokens só de instrução

**PROBLEMA:** identidade + temperamento + jeito de trabalhar.
**EVIDÊNCIA:** medido nos arquivos: 378 + 828 + 413 tokens.
**IMPACTO:** a 13,7 tok/s são ~118 s. Com o catálogo de ferramentas (~1.467),
o total fixo passa de 3.000 tokens.
**SEVERIDADE: ALTO** — mas cai para BAIXO se o cache funcionar (item 2).
**SOLUÇÃO:** resolver o cache primeiro. Cortar texto só depois.

### 4. Sem GPU, o teto é físico

**PROBLEMA:** 3–10 tok/s de escrita é o limite da CPU.
**EVIDÊNCIA:** `device_info` lista só CPU.
**SEVERIDADE: ALTO**, e **sem solução por software.**
**SOLUÇÃO:** hardware. Custo não avaliado nesta auditoria.

### 5. `seed` não é enviado

**PROBLEMA:** duas execuções do mesmo teste dão resultados diferentes.
**IMPACTO:** impossível comparar duas configurações com rigor.
**SEVERIDADE: MÉDIO** — atrapalha a própria auditoria.
**SOLUÇÃO:** enviar `"seed": 42` durante testes.

---

## ETAPA 12 — Configuração que parece boa e não é

Encontrei **três casos onde o arquivo diz uma coisa e o código aplica outra.**
Isso é pior que estar errado: você acha que configurou.

| Parâmetro | No `config.json` | Aplicado de fato | Por quê |
|---|---|---|---|
| `temperatura` | **0,3** | **0,45** | o código eleva qualquer valor < 0,35 |
| `max_tokens` | **4096** | **1200** | teto = contexto ÷ 5, limitado a 1200 |
| `threads_leitura` | `null` | todos os núcleos lógicos | `null` = automático |

**A temperatura é o caso grave.** Você configurou 0,3 querendo respostas mais
determinísticas — e recebe 0,45. A trava existe porque temperatura baixa
causava repetição, mas ela **silenciosamente desobedece** você. Deveria avisar
na tela.

**`contexto: 8192`** está correto e não deve subir. Você já testou 16.384 e
ficou mais lento — o custo de reler o prompt cresce com o tamanho. Com o cache
quebrado (gargalo 2), aumentar contexto só piora.

---

## ETAPA 10 — Três perfis

Todos assumem os gargalos 1 e 2 corrigidos.

### PERFIL 1 — VELOCIDADE

| | |
|---|---|
| Modelo | Granite 4.0 H-Tiny (4,2 GB) |
| Contexto | 8192 |
| `-t` / `-tb` | 8 / 16 |
| `-np` | 1 |
| `max_tokens` | 600 |
| temperatura | 0,45 |
| Aceita | erra mais — depende do selo NÃO VERIFICADO |

### PERFIL 2 — EQUILIBRADO *(recomendado)*

| | |
|---|---|
| Modelo | Granite para o dia a dia, **Qwen2.5-Coder 7B para código** |
| Contexto | 8192 |
| `-t` / `-tb` | 8 / 16 |
| `-np` | 1 |
| `max_tokens` | 1000 |
| temperatura | 0,45 |
| `--cache-ram` | 6144 |

### PERFIL 3 — QUALIDADE

| | |
|---|---|
| Modelo | Qwen2.5-Coder 7B (não o 30B — ver abaixo) |
| Contexto | 8192 |
| `max_tokens` | 1200 |
| temperatura | 0,35 |
| Aceita | ~3 tok/s; resposta de 700 tokens leva 4 min |

**Por que não o 30B no perfil de qualidade:** 2,9 tok/s medidos e 19 GB de
carga do pendrive. O ganho de qualidade não paga a espera no seu uso.

---

## ETAPA 11 — Comparação

Só a coluna de velocidade tem medição. As outras: **INFORMAÇÃO NÃO
DISPONÍVEL.**

| Modelo | Tam. | Escrita | Raciocínio | Program. | Alucinação |
|---|---|---|---|---|---|
| Granite 4.0 H-Tiny | 4,2 GB | **9,6 tok/s** | ? | ? | 1 caso grave |
| Qwen2.5-Coder 7B | 4,7 GB | 3,8 tok/s | ? | ? | ? |
| Qwen 14B | 18,8 GB | **não medido** | ? | ? | ? |
| Qwen3-Coder 30B-A3B | 18,6 GB | 2,9 tok/s | ? | ? | ? |

**Ranking honesto: não é possível.** Ordenar por velocidade daria o Granite em
1º — o mesmo que inventou a biografia inteira do Axl Rose. Seria o pior
conselho possível.

Note o Qwen 14B: **nunca foi medido**, e ocupa 18,8 GB. Vale medir.

---

## ETAPA 13 — Relatório

### Diagnóstico executivo

**O principal problema deste sistema é que ele lê as próprias instruções de
novo, do zero, em cada conversa nova — e isso leva minutos.**

Não é o modelo pensando devagar. Na primeira mensagem, **98,9% do tempo é o
motor lendo o texto que você já mandou centenas de vezes**, e que é idêntico
todas as vezes. O cache existe para evitar isso e está sendo desperdiçado,
porque o motor abriu 4 compartimentos em vez de 1.

Em segundo lugar: quatro ajustes de desempenho estão sendo enviados e
ignorados por causa de uma opção incompatível na linha de comando.

### Nota geral

**Não atribuo nota.** Uma nota de 0 a 100 precisaria de qualidade medida, e
55% dos critérios não têm dado. Um número aqui seria a mesma invenção que o
projeto combate.

### Desempenho

| | |
|---|---|
| Tokens/s (escrita) | 3,09 a 3,75 medido no Qwen 7B · 9,6 no Granite |
| Latência 1º token | **260,9 s** sem cache · **1,7 s** com cache |
| Consumo | 5.407 MiB projetados de 32 GB — **RAM não é gargalo** |

### Qualidade

Raciocínio, programação, instruções, contexto: **INFORMAÇÃO NÃO DISPONÍVEL.**
Confiabilidade: um caso grave documentado, sem taxa medida.

### Cinco melhorias por impacto ÷ esforço

| # | Mudança | Esforço | Ganho |
|---|---|---|---|
| 1 | **`-np 1`** — um slot só, cache reaproveitado | 1 linha, feito | 1ª mensagem: minutos → segundos |
| 2 | Confirmar que as opções chegam (`motor.log`) | 30 s de leitura | destrava o resto |
| 3 | `-tb 16` na leitura do prompt | 1 linha, feito | leitura mais rápida |
| 4 | Avisar quando a config for sobrescrita | 5 linhas | para de enganar você |
| 5 | `seed` fixo nos testes | 1 linha | torna comparação possível |

### Configuração recomendada

```
-ngl 0 -c 8192 -t 8 -tb 16 -b 2048 -ub 512 -np 1 --no-warmup --cache-ram 6144
```

### Configuração de teste (para comparar)

```
-ngl 0 -c 8192 -t 16 -tb 16 -b 4096 -ub 1024 -np 1 --no-warmup --cache-ram 6144
```

Muda `-t` de 8 para 16 e dobra os lotes. **Hipótese: não vai ajudar** — a
escrita é limitada por memória, não por cálculo, e mais threads costumam
piorar. Vale medir para provar em vez de acreditar.

---

## Conclusão

> **Se eu pudesse mudar apenas UMA coisa: `-np 1`.**

Porque é uma linha, é grátis, e ataca o número mais chocante desta auditoria:
**260,9 segundos lendo o prompt contra 2,9 escrevendo a resposta.** Esses
2.500 tokens de instrução são idênticos em toda conversa e deveriam sair do
cache instantaneamente. Com 4 slots, cada conversa nova cai num compartimento
frio e paga tudo de novo.

Nenhuma troca de modelo, nenhuma quantização e nenhuma placa de vídeo
resolveria isso — o tempo não está sendo gasto onde todos procuram.

---

## O que eu preciso de você

1. **Rode `python auditar_motor.py`** com o motor ligado — preenche as etapas
   1 e 2 com números reais
2. **Me mande o `motor.log` novo** — a primeira linha agora é o comando exato,
   e confirma ou desmente o gargalo nº 1
3. **Instale `psutil`** (`pip install psutil`) para medir RAM de verdade
4. **Confirme o modelo da CPU** — o log não nomeia
5. **Rode o mesmo teste no Granite e no Qwen** e me mande os dois arquivos

Sem o item 2, o gargalo mais importante desta auditoria continua sendo
**hipótese**, e está marcado como tal.

---

*Venure — venure.com.br · tecnologia própria*
