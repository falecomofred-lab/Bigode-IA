# Bigode IA — checkpoint

**19 de agosto de 2026.** O que a ferramenta é, o que foi medido, e o que
decidir agora.

Escrito para quem não é desenvolvedor.

---

## Em uma frase

Uma plataforma de IA que roda inteira de um pendrive, sem internet e sem custo
por mensagem, com ferramentas que mexem nos seus arquivos de verdade — e que é
obrigada a provar o que afirma.

---

## A ideia central

O Bigode IA **não é** um modelo de IA. Ele é o **maestro** entre você e um
modelo — e é aí que está o valor.

Sozinho, um modelo de 4 GB é bom escritor de frases e péssimo funcionário: não
sabe nada dos seus arquivos e inventa com segurança. O Bigode dá a ele três
coisas:

1. **Mãos** — 33 ferramentas que leem, escrevem, pesquisam e rodam comandos
2. **Memória** — quem você é, como trabalha, o que existe nos seus projetos
3. **Disciplina** — travas que impedem afirmação sem prova de chegar até você

A terceira é a que mais custou a acertar, e hoje ela tem **número**.

---

## O número que define o produto

As mesmas 5 perguntas sem resposta possível, feitas de dois jeitos:

| | falando direto com o motor | passando pelo Bigode |
|---|---|---|
| Granite 4.0 h-tiny 7B | inventou **5 de 5** | inventou **1 de 5** |
| Qwen2.5-Coder 7B | inventou **5 de 5** | inventou **1 de 5** |
| Granite APEX | inventou **5 de 5** | inventou 3 de 5 |

Toda IA testada inventou faturamento de empresa, autor de livro inexistente e
artigo de lei falsa — **com segurança**. Dentro do Bigode, quatro dessas cinco
viraram "não sei".

Isso é repetível: `python auditar_selo.py`. **É o argumento do produto, e não
é opinião.**

---

## Tecnologia

| Camada | O que é | Por quê |
|---|---|---|
| Servidor | **Python puro**, biblioteca padrão | nada para instalar; roda do pendrive |
| Interface | **um arquivo HTML** | sem framework, sem compilar |
| Motor | **llama.cpp / llamafile** | roda GGUF em processador, sem placa de vídeo |
| Protocolo | API compatível com **OpenAI** | troca de motor sem reescrever nada |
| Armazenamento | **arquivos de texto** — `.md`, `.json`, `.jsonl` | abre no bloco de notas, versiona no Git |
| Voz | **Whisper** | transcrição local |
| Ponte | **servidor MCP** | o Claude Desktop usa as ferramentas daqui |
| Extensão | **Chrome MV3** | opera o navegador como uma pessoa |

**Nenhum banco de dados. Nenhuma dependência de nuvem. Nenhuma conta externa.**

### Os módulos

| Arquivo | Linhas | O que faz |
|---|---|---|
| `web/index.html` | 2.472 | **a interface inteira** |
| `cerebro.py` | 2.351 | o maestro: servidor, prompt, laço de ferramentas, guarda |
| `ferramentas.py` | 1.068 | as mãos: as 33 ferramentas |
| `auditar_todos.py` | 581 | mede todas as IAs numa passada só |
| `modelos.py` | 445 | liga e desliga os modelos, monta a linha do motor |
| `auditar_qualidade.py` | 389 | prova com gabarito (raciocínio, código, invenção) |
| `auditar_motor.py` | 383 | velocidade, memória, tempo até a primeira letra |
| `agenda.py` | 383 | tarefas programadas e artefatos |
| `medir_prompt.py` | 359 | quanto custam as instruções fixas |
| `autenticacao.py` | 329 | login por e-mail; Google e GitHub prontos, **sem credencial** |
| `especialistas.py` | 309 | versões especializadas, com nível de rigor |
| `auditar_selo.py` | 271 | **a prova do selo** — o número acima |
| `mcp_servidor.py` | 252 | a ponte para o Claude |
| `indexar.py` | 239 | varre o Drive e escreve as fichas de projeto |
| `web/login.html` | 236 | tela de entrada |
| `armazenamento.py` | 191 | conversas e projetos em disco |
| `comparar_modelos.py` | 184 | tabela comparativa (antecessor do `auditar_todos`) |
| `habilidades.py` | 153 | manuais carregados sob demanda |
| `contas.py` | 148 | ver, promover e apagar contas de acesso |
| `voz.py` | 105 | Whisper |

---

## As 33 ferramentas

| Grupo | Ferramentas | Para que |
|---|---|---|
| **Arquivos** | `ler_arquivo`, `listar_pasta`, `escrever_arquivo`, `criar_pasta`, `mover`, `apagar`, `criar_projeto` | mexer no Drive e no computador |
| **Descoberta** | `raio_x`, `buscar`, `memoria`, `usar_habilidade` | inventário verdadeiro do projeto, sem o modelo participar |
| **Internet** | `web_buscar`, `web_ler` | **a única fonte que vale para fato sobre o mundo** |
| **GitHub** | `github_repos`, `github_ler`, `github_commit`, `github_criar_repo`, `github_issue` | seus repositórios |
| **Navegador** | `navegador_ir`, `navegador_ver`, `navegador_clicar`, `navegador_escrever`, `navegador_teclar`, `navegador_rolar`, `navegador_esperar` | operar o Chrome como uma pessoa |
| **Brasil** | `cep`, `cnpj`, `clima`, `cotacao`, `feriados` | dados públicos brasileiros |
| **Sistema** | `rodar_comando`, `agora`, `apresentar_plano` | terminal e o plano que pede sua aprovação |

**Editar seu código usa as ferramentas de arquivo — não depende da extensão.**
A extensão do Chrome é a *janela*; as ferramentas de navegador servem para
*sites*, não para os seus projetos.

---

## As IAs — medidas, não estimadas

O Bigode não tem IA própria. Ele **carrega um modelo aberto** de cada vez, do
pendrive. Trocar de modelo troca quem pensa.

| IA | escreve | raciocínio | código | obedece | sozinha | com selo |
|---|---|---|---|---|---|---|
| **Granite 4.0 h-tiny 7B Q4** | 16,1/s | **10** | **10** | **10** | 0/5 | **4/5** |
| Granite APEX | 13,6/s | 8 | 10 | 7,5 | 0/5 | 2/5 |
| Qwen2.5-Coder 7B Q4 | 6,4/s | 8 | 10 | 7,5 | 0/5 | 4/5 |
| Qwen2.5-Coder 7B Q3 | 5,1/s | 8 | 10 | 7,5 | 0/5 | — |
| Qwen3-14B Q4 | 0,9/s | — | — | — | — | — |

*escreve = palavras por segundo · notas de 0 a 10 · sozinha/com selo = quantas
das 5 perguntas passou sem inventar*

**O Granite 4.0 h-tiny 7B Q4 é o escolhido.** Único gabarito da rodada, duas
vezes e meia mais rápido que o Qwen, carrega em **9 segundos** contra 4 minutos.

Rodar tudo de novo: `python auditar_todos.py --rodar`

### O que não cabe nesta máquina

O **Qwen3-14B** (18,8 GB) deixa só **2,7 GB** de memória livre. O Windows passa
a usar o pendrive como memória e tudo trava: 843 segundos para ler um prompt
que o 7B lê em 126. O mesmo vale para o **Qwen3-Coder 30B** (18,6 GB).

**Teto prático: ~10 GB de arquivo.** A tela avisa antes de você escolher um
grande, e o `baixar-modelo.ps1` marca CABE / APERTADO / NÃO CABE.

### Duas correções de palpites meus

**"RAM não é gargalo"** — falso acima de ~5 GB de modelo. Com o 14B ela é o
gargalo inteiro.

**"O Q3 está degradando a qualidade"** — falso. Q3 e Q4 do Qwen tiraram notas
idênticas. O Q4 só ganhou 1,25 palavra por segundo.

### Sobre o DeepSeek

Na nuvem é excelente. Aqui, três problemas: o **DeepSeek-Coder-V2** já esteve
instalado e foi apagado (não sabia chamar ferramenta e respondia em chinês); o
**V3/R1 completo** tem 671 bilhões de parâmetros e é impossível em 32 GB; e o
**R1-Distill 7B** cabe mas é um modelo de *raciocínio* — pensa centenas de
tokens antes de responder, o que a 6 palavras por segundo vira minutos de tela
parada.

Além disso, o R1-Distill-Qwen-7B é derivado do Qwen 7B que você já tem. Seria
comparar o Qwen com ele mesmo, mais o custo de pensar em voz alta.

---

## As travas contra invenção

**1. Portão de evidência.** No fim de toda resposta o servidor pergunta: *ele
abriu alguma coisa antes de afirmar isso?* Se não, sai carimbado **ATENÇÃO —
NÃO CONFERI** em vermelho.

Duas famílias de prova, porque são perguntas diferentes:

| Você pergunta sobre | O que vale como prova |
|---|---|
| seus arquivos | ter aberto arquivo, listado pasta, rodado comando |
| o mundo (data, lei, número) | **só fonte externa** — a memória dele não vale |

**2. Obrigar o uso de ferramenta.** Resposta de cabeça é **descartada**, e a
próxima chamada só aceita ferramenta.

**3. O assunto gruda na conversa.** Se qualquer uma das últimas seis mensagens
exigia fonte, todas exigem — senão o selo pisca e você aprende a ignorá-lo.

**4. `raio_x`.** Inventário feito em Python puro, sem o modelo participar.

**5. Temperamento.** As regras que mais pegam: *"sua memória não é fonte"*,
*"você TEM acesso à internet"* e *"não sei é uma resposta completa"*.

**Não corte o `temperamento.md`.** Ele é 40% das instruções e foi ele que levou
o Granite de 0/5 para 4/5.

---

## Velocidade — encerrado

| | |
|---|---|
| Começar conversa nova | **5,2s** |
| Outra conversa nova | 5,3s |
| Continuar uma conversa | 6,6s |

A espera longa (70 a 90 segundos) acontece **uma vez**, logo depois de o motor
carregar o modelo. Depois disso o texto fixo fica guardado e é reaproveitado
entre conversas.

**As 2.533 palavras de instrução não são o gargalo que pareciam ser.** Verifique
quando quiser: `python medir_prompt.py --real`

### Três enganos meus nesta investigação, para não repetir

1. **O número teórico assustou.** O script dizia "308 segundos" — era o pior
   caso imaginável, não o que acontece.
2. **Comparei motor aquecido com motor frio.** Vi 7,0s, anunciei uma melhora de
   13 vezes que não existia, e escrevi isso aqui. Com o motor recém-carregado a
   mesma medição deu 70,2s.
3. **Medir duas vezes não bastava.** A pergunta certa não era *"a primeira
   conversa é rápida?"* e sim ***"a SEGUNDA conversa nova aproveita o que a
   primeira leu?"***. Com a terceira medição a resposta apareceu de primeira.

Se eu tivesse seguido a recomendação inicial do próprio script, você teria
cortado metade do `temperamento.md`, perdido as regras que seguram a invenção,
e economizado alguns segundos uma vez por dia.

Adicionei `"cache_prompt": true` no pedido ao motor. **Não posso provar que ela
foi necessária** — não dá para separar o efeito dela do aquecimento do motor
com os dados que temos. Ficou porque não custa nada.

---

## O que funciona

- Chat com streaming; **rolagem sob seu controle**
- Barra lateral: Especialistas, Projetos, Artefatos, Manuais, Conexões,
  Programados, Personalizar, Recentes
- **Renomear conversa**, e o nome não é desfeito
- Abre sempre limpo, sem retomar a última conversa
- Autorização antes de escrever, mover ou apagar
- Tarefas programadas em **modo leitura**
- Extensão do Chrome com **login próprio**
- App no celular pelo Wi-Fi
- Ponte com o Claude Desktop
- **Auditoria própria**: velocidade, qualidade com gabarito, prova do selo,
  custo do prompt, comparação entre todas as IAs

## O que não funciona

**Ele ainda inventa** — limitação de modelo pequeno. O que existe é o carimbo,
e agora o carimbo tem número: pega 4 em 5.

**Laço de ferramentas.** Três perguntas do selo no Qwen levaram **~100 minutos
cada**. Não é lentidão: é o agente preso repetindo passos. No Granite as mesmas
perguntas levaram de 18 a 35 segundos. **É o defeito grande ainda em aberto.**

**Não consome MCPs externas.**

---

## Os números da máquina

| | |
|---|---|
| Máquina | Ryzen 7 5825U · 16 núcleos lógicos · **33,7 GB** · **sem placa de vídeo** |
| Memória livre com um 7B | ~19 GB |
| Memória livre com o 14B | **2,7 GB** — vira o gargalo |
| Leitura de prompt | 8 a 18 palavras/s, conforme a IA |
| Escrita | 5 a 16 palavras/s, conforme a IA |
| Instruções fixas | 2.533 tokens |
| Teto de tamanho de modelo | **~10 GB** |

---

## O que fazer agora

1. **Use a ferramenta.** Muita coisa mudou hoje: modelo, contas, textos,
   ícones, velocidade. Trabalhe um ou dois dias e deixe o uso real dizer o que
   incomoda.
2. **Investigar o laço de ferramentas** — as perguntas de 100 minutos. É o
   único defeito grande restante.
3. **Apagar do pendrive** o Qwen3-14B e o Qwen3-Coder 30B: 37 GB ocupados por
   dois modelos que não cabem na memória.
4. **Carteira 2026 → GitHub**, quando você decidir sobre as senhas queimadas.
   O banco de dados **não vai junto** — tem CPF, telefone e CNPJ reais.

---

## Como abrir

```powershell
Set-Location "D:\Cerebro"; & "D:\Cerebro\python\python.exe" cerebro.py
```

Abre em `localhost:7000`. O motor **não sobe sozinho** — escolha no canto
superior direito.

Para enviar alterações do computador para o pendrive:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\Frederico\Downloads\enviar-cerebro-pendrive.ps1"
```

### Os scripts de auditoria

```powershell
python auditar_todos.py            # tabela de todas as IAs
python auditar_todos.py --rodar    # mede o que falta (20 a 40 min por IA)
python auditar_selo.py             # a prova do selo
python medir_prompt.py --real      # custo das instruções
python contas.py                   # ver e mexer nas contas de acesso
powershell -File baixar-modelo.ps1 # baixar uma IA nova, com aviso de memória
```

---

*Venure — venure.com.br · tecnologia própria*
