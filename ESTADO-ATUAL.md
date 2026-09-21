# Bigode IA — como está hoje

**23 de agosto de 2026.** Leitura de todos os arquivos do projeto, depois das
mudanças que você fez nos últimos dias.

Escrito para quem não é desenvolvedor.

---

## O tamanho da coisa

**78 arquivos · 19.626 linhas** de código e texto. Um ano atrás isso seria um
produto de empresa pequena.

---

## O que eu aprovo, e por quê

### 1. A busca semântica (ChromaDB) — aprovada, com ressalva

Quem implementou fez o que eu teria feito e acertou o detalhe difícil: **o
trecho recuperado entra no FIM do texto de instruções**, nunca no começo. Isso
preserva o que a gente lutou para conseguir — o motor não relê tudo a cada
pergunta.

Testei sem o ChromaDB instalado: o Bigode **sobe normalmente**, a ferramenta
devolve *"ChromaDB não está instalado"* como texto em vez de estourar, e nada
quebra. Isso é trabalho cuidadoso.

**A ressalva:** o checkpoint dizia, em negrito, *"nenhum banco de dados, nada
para instalar"*. Instalar o ChromaDB traz uma árvore grande de dependências, e
o modelo de embedding padrão **baixa da internet** no primeiro uso. Não é
errado — é uma troca. Só precisa ser uma decisão sua, consciente, e não um
detalhe que passou.

### 2. O roteador semântico — aprovado

Classifica a pergunta em `codigo`, `seguros` ou `cannabis` por palavra-chave.
Simples, rápido, sem depender de modelo. É a "roteamento semântico" que aquele
plano pedia, feita do jeito leve. Bom.

Um desperdício pequeno: ele é chamado **duas vezes** por pergunta
(`cerebro.py`, linhas 436 e 1757). Não quebra nada.

### 3. O `temperamento.md` reescrito — aprovado no texto, com uma perda

Ficou muito melhor de ler. As dez "regras de ferro" são mais claras que a
versão anterior.

**Mas sumiu uma regra que estava funcionando:** *"VOCÊ TEM ACESSO À INTERNET —
nunca diga que não pode buscar"*. Ela existia por um motivo registrado: o
modelo respondeu *"não tenho acesso à internet"* tendo `web_buscar` na mão.

### 4. A extensão do Chrome — **eu estava errado sobre ela**

Ontem eu disse que ela estava "longe" da extensão do Claude e que alcançar
seria um projeto. **Li o código hoje e me corrijo.**

O `conteudo.js` faz exatamente o que eu disse que faltava:

| O que a extensão já faz | |
|---|---|
| `mapear()` | numera até 120 elementos clicáveis da página, com rótulo e tipo, mais o texto visível |
| `pegar()` | se o modelo tentar agir com uma lista velha, **remapeia antes de tocar** |
| `irAte()` | rola até o elemento antes de clicar |
| `criarEnfeites()` | destaca visualmente o que está sendo feito |
| `acaoCritica()` | detecta ação perigosa — comprar, pagar, excluir, campo de senha, CPF, cartão |
| `aprovarNaPagina()` | **pede sua aprovação na própria página** antes de fazer |

Essa última é notável. A extensão do Claude também pede confirmação, mas o
detector aqui está afinado para o Brasil — CPF, cartão, "contratar", "pedido".

**O que ainda separa das duas:** não é engenharia, é o modelo. O Granite 7B
erra mais que o Claude ao decidir *qual* dos 120 elementos clicar. Nenhuma
melhoria minha no código muda isso. A mecânica está pronta; o julgamento é que
é menor.

**Veredito:** a extensão está bem mais perto do que eu disse. Vale testar de
verdade num site real antes de qualquer outra mudança.

---

## Dois problemas que eu encontrei

### 1. O `temperamento.md` está duplicado — e você pode ter editado o errado

| Arquivo | Tamanho | O Bigode lê? |
|---|---|---|
| `memoria/temperamento.md` | 4.099 bytes | **SIM** |
| `temperamento.md` (na raiz) | 4.302 bytes | **não** |

Os dois têm conteúdo **diferente**. O da raiz não é lido por nada — nem pelo
`cerebro.py`, nem pelo `medir_prompt.py`. Se alguma edição foi feita nele,
**não teve efeito nenhum**.

Isso precisa ser resolvido antes de qualquer ajuste de comportamento: senão a
gente mede uma coisa e edita outra.

### 2. O Bigode para de responder — e é o problema mais grave

Em dois testes seguidos, o mesmo padrão: responde a primeira, demora muito na
segunda, e **para** a partir da terceira. O motor continua saudável ao lado,
respondendo em 3 a 4 segundos.

Isso não é lentidão nem trava de evidência. É travamento ou queda.

**Ainda não sei a causa** e não vou chutar. Instalei duas formas de capturar:

- `erros.log` — grava queda, com a pilha inteira
- `/api/diagnostico` — mostra onde cada parte parou, para o caso de travamento
- o `medir_fluidez.py` agora tira essa foto **sozinho**, no instante da falha

---

## O que eu afirmei e a medição desmentiu

Registro, porque errar em silêncio é pior que errar.

**Eu disse que a trava de evidência estava atrapalhando a fluidez.** O
`medir_fluidez.py` mostrou `trava: não` em todas as seis frases. Nenhuma
resposta foi descartada. Minha hipótese estava errada.

**Eu disse que a extensão estava longe da do Claude.** Estava, sim, na minha
leitura antiga do projeto. Não está mais.

---

## Os números que ainda valem

| | |
|---|---|
| Modelo em uso | Qwen2.5-Coder 7B Q4 |
| Melhor medido | **Granite 4.0 h-tiny 7B Q4** — 10/10/10, 16 palavras/s |
| Invenção, modelo cru | 5 em 5 |
| Invenção, pelo Bigode | **1 em 5** |
| Instruções fixas | 2.851 tokens |
| Conversa nova | 5 a 6 segundos |
| Ferramentas | 34 ativas |
| Projetos indexados | 43 |

**Atenção:** os números de invenção são de 19/08, com o `temperamento.md`
antigo. O texto mudou desde então. **Eles precisam ser refeitos.**

---

## O que eu faria agora, nesta ordem

1. **Resolver o `temperamento.md` duplicado.** Apagar o da raiz ou entender por
   que ele existe. Sem isso, toda medição de comportamento é suspeita.

2. **Achar a causa do travamento.** Rodar o `medir_fluidez.py` e me mandar o
   `TRAVAMENTO-*.json` que ele gerar. É o único problema que faz a ferramenta
   ficar inutilizável.

3. **Refazer a prova do selo** com o temperamento novo. Se caiu de 4/5, a regra
   da internet é a primeira suspeita.

4. **Testar a extensão num site real** — ela está mais pronta do que a gente
   pensava, e nunca foi exercitada de verdade.

5. **Trocar para o Granite 7B Q4.** Está medido, é duas vezes e meia mais
   rápido, e tira 10 onde o Qwen tira 8.

Item 1 e 2 antes de qualquer coisa nova. Ferramenta que trava é pior que
ferramenta incompleta.

---

*Venure — venure.com.br · tecnologia própria*
