---
nome: Padrão Venure
quando: projeto, auditoria, revisar, criar, estrutura, api, backend, frontend, tela, banco, seguranca, segurança, deploy, saas, crm
ativa: sim
---

# Padrão Venure

Vale para **todos** os projetos da Venure. Quando o Fred falar de um projeto
específico, leia também o `PROJETO.md` na pasta dele — lá estão as decisões
particulares daquele sistema, que sempre têm prioridade sobre este documento.

## Antes de qualquer coisa

Chame `raio_x` na pasta do projeto. Trabalhe só com os arquivos que aparecerem
na lista. Nunca cite arquivo que você não leu.

---

## 1. Estrutura

Um projeto Venure tem sempre, na raiz:

```
projeto/
├── PROJETO.md          o que o sistema faz, decisões, o que falta
├── README.md           como instalar e rodar
├── .env.example        chaves vazias, uma por linha
├── .gitignore
└── (backend / frontend / src, conforme a stack)
```

**Regra de camadas**, em qualquer linguagem:

- **rota / router** — recebe a requisição, valida a entrada, devolve resposta.
  Não sabe o que é banco.
- **service** — regra de negócio. É onde mora a inteligência.
- **model / schema** — forma dos dados.

Rota que faz `SELECT` está errada. Service que monta HTML está errado.

## 2. Segurança — não é negociável

| Item | Regra |
|---|---|
| Senha | sempre com hash (`bcrypt`, `werkzeug.security`). Nunca texto puro. |
| Segredo, token, chave de API | só em `.env`. Nunca no código, nunca no Git. |
| Query | sempre parametrizada (`?` ou `:nome`). Nunca concatenar string. |
| Entrada do usuário | validar antes de tocar no banco (`zod`, `pydantic`). |
| CORS | origem explícita. Nunca `*` em produção. |
| Erro na tela | mensagem clara. Nunca stack trace, nunca nome de tabela. |
| Log | nunca registrar senha, token, CPF ou cartão. |

### Multi-tenant — o erro mais grave possível

Em sistema com vários clientes (imobiliária, seguradora, SaaS), **toda** tabela
tem `empresa_id` e **toda** consulta filtra por ele. O `empresa_id` vem do
token de autenticação, nunca do corpo da requisição — senão o cliente manda o
número que quiser e lê os dados do vizinho.

```python
# certo
produtos = db.query(Produto).filter(Produto.empresa_id == usuario.empresa_id).all()

# errado — vaza dado entre clientes
produtos = db.query(Produto).all()
```

Ao auditar, procure por consulta sem esse filtro. É o achado mais importante.

## 3. Dado fictício é bug

Nenhum projeto vai para produção com dado inventado. Ao auditar, procure e
aponte:

- nome, preço, endereço ou telefone escrito direto no código
- `João Silva`, `Rua Exemplo, 123`, `R$ 1.234,56`, `teste@teste.com`
- credencial de teste, token de exemplo, senha `123456`
- `placeholder.jpg` ou imagem de exemplo em tela de produção
- seed e fixture com mercadoria de mentira (estrutura pode ficar, dado não)

Todo dado exibido vem do banco ou da API. Sem exceção.

## 4. API

Sucesso devolve o dado direto. Erro devolve sempre:

```json
{ "erro": "mensagem clara em português", "codigo": "CLIENTE_NAO_ENCONTRADO" }
```

Códigos: `200` ok · `201` criado · `400` dado inválido · `401` sem token ·
`403` sem permissão · `404` não achou · `409` conflito · `422` validação ·
`500` erro interno.

Nome de rota no plural e em minúsculas: `/clientes`, `/clientes/{id}`.

## 5. Banco

- Toda tabela tem `id`, `criado_em` e `atualizado_em`.
- Campo usado em filtro ou `JOIN` tem índice.
- Nada de consulta dentro de laço (problema N+1) — traga tudo de uma vez.
- Dinheiro nunca em `float`. Use inteiro em centavos ou `Decimal`.
- Data sempre com fuso definido.

## 6. Telas

### A regra de contraste — inegociável

**Fundo escuro, letra clara. Fundo claro, letra escura. Sempre.**

Parece óbvio, e é justamente por isso que quebra sem ninguém ver. O jeito
errado é fixar a cor num seletor solto:

```css
/* ERRADO — não acompanha o container */
p { color: #0f172a; }
```

Dentro de uma caixa escura, esse `p` continua escuro: texto invisível. Foi
assim que a frase do login da Carteira 2026 sumiu — azul escuro sobre azul
escuro.

O jeito certo é **herdar**:

```css
/* CERTO — segue quem contém */
p, h2, h3, li, td { color: inherit; }

/* e a superfície escura declara a cor uma vez */
.painel-escuro { background: #0a1628; color: #ffffff; }
```

Três armadilhas que já apareceram:

- **`-webkit-text-fill-color: transparent`** (usado para texto com gradiente)
  ignora qualquer `color`, até com `!important`. Se o gradiente for claro e o
  fundo também, o texto some. Use só onde o fundo é conhecido.
- **Cor de borda como cor de texto.** `color: var(--color-border)` sobre
  branco dá contraste de 1,5:1. Borda é borda; texto tem token próprio.
- **Dois CSS com os mesmos nomes de variável.** Quem carrega por último
  vence, e ninguém percebe até a tela mudar de cara. Design system novo usa
  prefixo próprio nas variáveis.

Contraste mínimo: **4,5:1** para texto normal, **3:1** para texto grande.
Na dúvida, confira no WebAIM Contrast Checker.

### Demais regras de tela

- Todo campo tem `label` visível. `placeholder` não substitui label.
- Toda imagem tem `alt`.
- Contraste de texto no mínimo 4.5:1.
- Botão com área clicável de pelo menos 44×44 px.
- Funciona no celular sem barra de rolagem horizontal.
- Nada de estilo escrito dentro da tag (`style="..."`).
- Cor não é a única forma de sinalizar erro — use ícone ou texto também.

**Linguagem das telas:** português comum, nunca jargão. Mensagem de erro diz o
que fazer, não o que falhou. `"E-mail não encontrado"`, não `"ERR_404"`.

## 7. Como falar com o Fred

Ele não é desenvolvedor e não quer virar um. Ao encontrar problema, diga:

1. **o que está errado** — em português, sem termo técnico solto
2. **o que isso causa** na prática, para o negócio ou para o usuário
3. **o que você faria** para corrigir

Se a correção é clara, ofereça-se para editar o arquivo: apresente o plano com
os arquivos reais que leu e espere ele aprovar.

Não entregue lista de boas práticas genéricas. Não entregue "estrutura
sugerida" quando o projeto já existe. Fale do código que você leu.

## 8. Ordem da auditoria

1. `raio_x` na pasta — inventário verdadeiro
2. Ler os arquivos de configuração e de banco primeiro (é onde vaza segredo)
3. Ler os models — entender os dados
4. Ler os services — entender as regras
5. Ler os routers — conferir validação e autenticação
6. Ler os templates — dado fictício e acessibilidade
7. Só então escrever a conclusão, do mais grave para o menos

Achados em três níveis: **grave** (vaza dado, quebra em produção),
**importante** (vai dar problema em breve), **melhoria** (deixa melhor).
