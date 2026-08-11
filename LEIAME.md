# CÉREBRO — Venure

Sua IA no pendrive. Identidade própria, memória dos seus projetos, e mãos para
agir: ler pastas, escrever arquivos, mexer no GitHub e pesquisar na web.

---

## Instalar (uma vez)

1. Confirme que o pendrive tem, na raiz: `llamafile-0.10.3.exe` e o `.gguf`.
2. Dê dois cliques em **INSTALAR.bat**.
3. Responda três perguntas: letra do pendrive, baixar Python portátil, indexar
   os projetos.

O instalador copia tudo para `D:\Cerebro`, cria o `D:\CEREBRO.bat` na raiz e,
se você quiser, leva um Python portátil junto — assim funciona em qualquer PC
Windows, mesmo sem Python instalado.

## Usar

Dois cliques em **`D:\CEREBRO.bat`**.

Ele liga o motor sozinho, espera carregar e abre a interface em
`http://localhost:7000`.

---

## As quatro telas

**Conversa** — onde você fala com ele. Enquanto trabalha, mostra cada ação que
executa. Se a ação altera algo, para e pede autorização.

**Conexões** — o que ele pode acessar. Liga e desliga cada uma. O botão
*Nova conexão* aceita servidores MCP, APIs ou pastas locais.

**Memória** — identidade e seu jeito de trabalhar (editáveis ali mesmo) e o
índice dos projetos, com botão de sincronizar com o Drive.

**Ajustes** — motor, temperatura, nível de autorização e pastas liberadas.

---

## O que ele consegue fazer

**Sem pedir nada** — listar pastas, ler arquivos, buscar texto dentro dos
projetos, consultar a memória, ler repositórios do GitHub, pesquisar na web.

**Pedindo autorização** — criar e editar arquivos, mover, apagar, criar
repositório, commitar, abrir issue, rodar comando no terminal.

Ele só enxerga o que estiver nas **pastas liberadas** (Ajustes). Fora delas,
não lê nem escreve.

---

## Ligar o GitHub

1. Gere um token em https://github.com/settings/tokens
2. Na tela **Conexões**, abra o card do GitHub e cole o token.
3. Ligue a chave.

## Ligar o Terminal

Vem desligado de propósito — com ele ligado, o Cérebro pode executar qualquer
comando (sempre pedindo autorização). Ligue se quiser que ele rode `npm install`,
`git`, testes e afins.

---

## Ponte com o Claude

O Cérebro pode virar uma ferramenta do Claude. Nas configurações de conectores
MCP do Claude, adicione:

```json
{
  "mcpServers": {
    "cerebro": {
      "command": "D:\\Cerebro\\python\\python.exe",
      "args": ["D:\\Cerebro\\mcp_servidor.py"]
    }
  }
}
```

Se não instalou o Python portátil, troque o `command` por `"python"`.

A partir daí, numa conversa com o Claude você pode dizer:

> *"Manda o Cérebro ler o projeto GolCam e escrever o módulo de login."*

O Claude arquiteta e revisa; o Cérebro executa localmente, sem gastar tokens.
Nesse modo as ações de escrita ficam bloqueadas — ele lê, analisa e devolve o
código em texto.

---

## Estrutura

```
D:\
├── CEREBRO.bat              ← você clica aqui
├── llamafile-0.10.3.exe
├── Qwen3-Coder-30B...gguf
└── Cerebro\
    ├── cerebro.py           servidor + rotas
    ├── ferramentas.py       as mãos
    ├── mcp_servidor.py      ponte com o Claude
    ├── indexar.py           sincroniza a memória
    ├── config.json          motor, segurança, pastas
    ├── conexoes.json        suas conexões e tokens
    ├── web\index.html       a interface
    ├── memoria\             identidade + projetos
    └── python\              Python portátil
```

---

## Se algo der errado

**"Motor carregando..." não sai disso** — o modelo tem 18,7 GB e leva alguns
minutos para subir do pendrive. Veja a janela minimizada "Motor Cerebro".

**Ele inventa nome de arquivo** — normal em modelo local. Peça: *"use a
ferramenta listar_pasta antes de responder"*.

**Não acha meus projetos** — vá em Memória e clique em Sincronizar. Confira em
Ajustes se o caminho do Drive está nas pastas liberadas.

**Respostas lentas** — sem placa de vídeo dedicada, são poucos tokens por
segundo. Reduza o contexto em Ajustes se precisar de mais velocidade.

---

*Venure — venure.com.br*
