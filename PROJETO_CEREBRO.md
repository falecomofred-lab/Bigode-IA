# PROJETO BIGODE IA
### Uma inteligência Venure — venure.com.br

---

## O que é

Uma plataforma de IA que roda inteiramente dentro de um pendrive. Você espeta
em qualquer computador Windows, clica em um arquivo, e tem uma IA que **conversa
e age**: entra nas suas pastas, mexe nos seus projetos, sobe código para o
GitHub, pesquisa na web e conversa com outras plataformas via MCP.

Sem mensalidade. Sem nuvem obrigatória. Sem depender de instalação na máquina.

---

## Princípios

1. **Autônoma.** Tudo no pendrive: modelo, motor, Python, Node, memória.
2. **Simples.** Uma tela de conversa e uma tela de conexões. Nada além disso.
3. **Sob controle.** Leitura é livre. Qualquer ação que altere, apague ou
   publique passa por um botão **Autorizar**.
4. **Extensível.** Você pluga MCPs e APIs pela interface, sem tocar em código.
5. **Custo zero.** O modelo é local. Conexões pagas ficam desligadas por padrão.

---

## Arquitetura

```
        VOCÊ
          │
    ┌─────▼──────────────────────────────────┐
    │   BIGODE IA  (interface web local)       │
    │   identidade · memória · autorização   │
    └─────┬───────────────────┬──────────────┘
          │                   │
    ┌─────▼─────┐      ┌──────▼──────────────┐
    │  MOTOR    │      │    CONEXÕES         │
    │ Qwen3-    │      │  Arquivos (local)   │
    │ Coder-30B │      │  GitHub  (API)      │
    │ local     │      │  Web     (busca)    │
    └───────────┘      │  MCPs    (plugáveis)│
                       └─────────────────────┘

    E na outra ponta:
    CLAUDE  ──MCP──►  BIGODE IA
    (eu mando tarefas para ele executar localmente)
```

---

## As telas

### 1. Conversa
Chat limpo. Enquanto o Bigode trabalha, mostra o que está fazendo em tempo
real: `✓ listar_pasta`, `✓ ler_arquivo`, `⚠ aguardando autorização`.

### 2. Conexões
Cards com o que ele pode acessar. Cada um com liga/desliga e configuração.
Botão **+ Nova conexão** para colar qualquer servidor MCP ou API.

### 3. Memória
Lista o que ele sabe sobre você: identidade, seu jeito de trabalhar e a memória
semântica persistente no ChromaDB. Em Ajustes, cada coleção pode apontar para
uma ou mais pastas; `codigo`, `seguros` e `cannabis` são exemplos iniciais, e
novos domínios podem ser cadastrados pelo próprio HTML.

### 4. Ajustes
Porta, temperatura, tamanho de contexto, caminho do modelo, coleções semânticas,
pastas liberadas e indexação ChromaDB.

---

## Conexões da versão 1

| Conexão | Tipo | O que faz | Custo |
|---|---|---|---|
| **Arquivos** | local | listar, ler, criar, editar, mover | zero |
| **GitHub** | API | repos, código, commit, issues, PRs | zero (token grátis) |
| **Web** | API | pesquisar e ler páginas | zero |
| **MCP externo** | plugável | Canva, Notion, Slack, o que você colar | varia |
| **Claude (API)** | API | reforço em tarefas difíceis | pago — desligado |

---

## Ferramentas do Bigode

**Leitura (livre)**
`listar_pasta` · `ler_arquivo` · `buscar_no_projeto` · `github_listar` ·
`github_ler` · `web_buscar` · `web_ler`

**Escrita (exige autorização)**
`escrever_arquivo` · `criar_pasta` · `mover_arquivo` · `apagar_arquivo` ·
`github_criar_repo` · `github_commit` · `github_issue` · `rodar_comando`

Cada ação de escrita aparece na tela com o comando exato que será executado,
e só roda depois que você clicar em Autorizar.

---

## Ligação com o Claude

O Bigode expõe um **servidor MCP**. Você cola o endereço nas configurações do
Claude e, a partir daí, nas nossas conversas eu ganho estas ferramentas:

- `cerebro_perguntar` — pergunta algo ao Bigode
- `cerebro_codificar` — passa uma tarefa de código para ele executar local
- `cerebro_memoria` — consulta o que ele sabe dos seus projetos

Na prática: eu arquiteto, reviso e decido. Ele codifica sem gastar token.

---

## Estrutura no pendrive

```
D:\
├── BIGODE.bat                 ← você clica aqui
├── llamafile.exe
├── granite-4.0-h-tiny-*.gguf
└── Bigode\
    ├── cerebro.py              servidor + interface
    ├── ferramentas.py          as mãos (arquivos, github, web)
    ├── mcp_cliente.py          fala com servidores MCP
    ├── mcp_servidor.py         expõe o Bigode para o Claude
    ├── indexar.py              sincroniza a memória
    ├── config.json
    ├── conexoes.json           suas conexões (tokens ficam aqui)
    ├── memoria\
    │   ├── identidade.md
    │   ├── jeito_de_trabalhar.md
    │   └── projetos\
    ├── python\                 Python portátil
    └── node\                   Node portátil (para os MCPs)
```

---

## Fases de entrega

**Fase 1 — Base** *(feito)*
Interface, identidade, memória dos projetos, streaming de resposta.

**Fase 2 — Mãos**
Ferramentas de arquivo, GitHub e web. Fluxo de autorização. É onde ele deixa
de conversar e começa a trabalhar.

**Fase 3 — Ponte com o Claude**
Servidor MCP para eu mandar tarefas ao Bigode daqui.

**Fase 4 — Plugues**
Cliente MCP genérico: você cola Canva, Notion, o que quiser, pela tela.

**Fase 5 — Autonomia total**
Python e Node portáteis no pendrive. Funciona em qualquer PC, do zero.

---

## Limites honestos

- O Granite 4.0 h-tiny usa ferramentas bem, mas erra mais que um modelo de
  fronteira. Espere revisar o trabalho dele.
- Rodando de pendrive, cada início leva alguns minutos para carregar o modelo.
- MCPs de nuvem (Canva, Notion) precisam de internet e login OAuth.
- Sem GPU dedicada, a resposta sai na casa de poucos tokens por segundo.
  É utilizável, não é instantâneo.

---

*Venure — venure.com.br*
