---
nome: API REST em Node
quando: api, backend, node, express, rest, endpoint, crm, cadastro
ativa: sim
---

# Como a Venure constrói uma API REST em Node

Siga esta estrutura sempre. Ela é a base de todos os SaaS da Venure.

## Estrutura de pastas

```
projeto/
├── package.json
├── .env.example
├── .gitignore
├── README.md
└── src/
    ├── index.js            entrada: sobe o servidor
    ├── config/
    │   └── banco.js        conexão com o banco
    ├── middleware/
    │   ├── auth.js         valida o token JWT
    │   └── erros.js        captura erro e devolve JSON padrão
    ├── rotas/
    │   └── clientes.js     um arquivo por recurso
    ├── controllers/
    │   └── clientes.js     recebe req, chama o serviço, devolve res
    └── servicos/
        └── clientes.js     regra de negócio e acesso ao banco
```

Regra de ouro: rota não conhece banco. Controller não tem regra de negócio.
A regra fica no serviço.

## package.json

Sempre com `"type": "module"` e os scripts:

```json
"scripts": {
  "dev": "node --watch src/index.js",
  "start": "node src/index.js"
}
```

Dependências padrão: `express`, `dotenv`, `jsonwebtoken`, `bcryptjs`, `zod`, `cors`.

## Respostas da API

Sucesso devolve o dado direto. Erro devolve sempre este formato:

```json
{ "erro": "mensagem clara em português", "codigo": "CLIENTE_NAO_ENCONTRADO" }
```

Códigos HTTP: 200 ok, 201 criado, 400 dado inválido, 401 sem token,
403 sem permissão, 404 não achou, 409 conflito, 500 erro interno.

## Segurança obrigatória

- Senha sempre com `bcryptjs`, nunca em texto puro.
- Segredo do JWT vem de `process.env.JWT_SECRET`. Nunca no código.
- Validar toda entrada com `zod` antes de tocar no banco.
- `cors` configurado com origem explícita, não `*`.
- Nenhuma query montada por concatenação de string.

## Multi-tenant

Em SaaS com vários clientes, toda tabela leva `empresa_id`, e **toda** consulta
filtra por ele. O `empresa_id` vem do token, nunca do corpo da requisição.

```js
// certo
const clientes = await db.all(
  'SELECT * FROM clientes WHERE empresa_id = ?', [req.usuario.empresa_id]);
```

Esse é o erro mais grave possível num SaaS: esquecer esse filtro faz um cliente
enxergar os dados do outro.

## .env.example

Sempre criar, com as chaves vazias:

```
PORTA=3000
JWT_SECRET=
BANCO_URL=
```

E o `.gitignore` sempre com `node_modules`, `.env` e `*.db`.
