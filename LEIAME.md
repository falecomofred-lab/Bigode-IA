# BIGODE IA — Venure

Sua IA no pendrive. Roda inteira no seu computador, sem nuvem e sem enviar
nada para fora. Lê seus projetos, escreve arquivos, controla o Chrome e
carimba o que não conferiu.

---

## Usar

Dois cliques em **`D:\Cerebro\BIGODE.bat`**.

Ele abre a tela em `http://localhost:7000` e **para por aí**.

**Ele não liga IA nenhuma sozinha** — isso é de propósito. Você escolhe o
modelo no canto superior direito da tela. Ligar um modelo de 4,7 GB a partir
do pendrive leva alguns minutos, e não faz sentido segurar a tela por causa
disso quando muitas vezes você só quer ver o histórico ou mexer num ajuste.

A janela preta que fica aberta é parte do programa. Ela mostra o que o motor
está fazendo, linha a linha, marcado com `motor |`. Feche essa janela e o
Bigode fecha junto.

**Do pendrive, abrir leva de 15 a 40 segundos** antes de qualquer coisa
aparecer. É o Python subindo. Não é travamento — não aperte Ctrl+C.

---

## Escolher a IA

Quatro modelos disponíveis, medidos nesta máquina:

| Modelo | Lê o prompt | Escreve | Escolha |
|---|---:|---:|---|
| **Granite 4.0 h-tiny** | ~68 tok/s | ~9 tok/s | **o melhor aqui** |
| Granite 7B Q4_K_M | ~68 tok/s | ~9,6 tok/s | equivalente |
| Qwen 7B Q4_K_M | lento | 3,8 tok/s | só se precisar de código muito preciso |
| Qwen 7B Q3_K_M | ~25 tok/s | 2,8 tok/s | o pior desta máquina |

O que decide o tempo de resposta **não é a velocidade de escrever, é a de
ler**. Por isso o Granite ganha, apesar de errar mais.

**Primeira mensagem de uma conversa: ~65 segundos.** As seguintes: 2 a 9
segundos. Se vai trabalhar em algo, **fique na mesma conversa** — abrir uma
nova custa o preço cheio de novo.

---

## As conexões, na barra acima do texto

Cada uma é um **interruptor**. Clique e alterna, na hora. Passe o mouse e ela
diz quanto custa:

> *Ligada · 1448 tokens (~21s) por mensagem · clique para desligar*

Isso não é enfeite: **cada conexão ligada é relida em toda mensagem que você
manda**. Desligar o que não está usando encurta a espera de forma direta.

Vêm ligadas: **Google Drive, Web, Navegador Chrome e Terminal**.
Vêm desligadas: GitHub e Dados do Brasil — juntas custam ~18 segundos.

O Claude não aparece na barra: é ponte, não ferramenta, e custa zero.

---

## O selo — o que diferencia o Bigode

Toda resposta é carimbada:

- **VERIFICADO** — ele abriu arquivo, rodou comando ou leu página. Diz a fonte.
- **NÃO CONFERI** — respondeu de memória. Trate como rascunho.

Medido: o modelo cru inventa em **5 de 5** perguntas armadilha. Através do
Bigode, **1 de 5** passa. Para conferir você mesmo:

```powershell
python auditar_selo.py
```

O carimbo **avisa, não corrige**. "VERIFICADO" quer dizer que ele leu algo,
não que interpretou certo.

---

## Controlar o Chrome

Ele lê a página que você está vendo, numera tudo que dá para clicar, e age.

Precisa da extensão: `chrome://extensions` → modo desenvolvedor → carregar
sem compactação → `D:\Cerebro\extensao-chrome`. Depois, em Detalhes →
Opções, entre com o mesmo e-mail e senha da tela.

Peça como falaria com uma pessoa:

> *o que tem nesta página?*
> *clique no botão Save*
> *escreva meu nome no campo de busca*

Ele lê a tela antes de agir — você não precisa pedir. Páginas `chrome://` não
aceitam automação: é regra do navegador, não limitação dele.

---

## Ponte com o Claude

O Bigode vira ferramenta do Claude Desktop. Em
`%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "Bigode": {
      "command": "D:\\Cerebro\\python\\python.exe",
      "args": ["D:\\Cerebro\\mcp_servidor.py"]
    }
  }
}
```

Feche o Claude **pela bandeja** (ao lado do relógio) e abra de novo.

O caminho do Python vai inteiro de propósito: dizer só `"python"` depende de
haver um Python instalado no Windows, e o seu é o portátil do pendrive.

Funciona no **Claude Desktop** e no Claude Code. **Não funciona** no
claude.ai pelo navegador — o Bigode vive em `localhost`, e só alcança quem
está na mesma máquina.

---

## Quando algo der errado

**A resposta veio vazia** → a tela agora diz o motivo. Se não disser:
```powershell
type D:\Cerebro\erros.log
```

**"O motor derrubou a conexão"** → quase sempre é o modelo ainda carregando,
ou a janela de contexto pequena demais para o prompt. Olhe as linhas
`motor |` na janela preta.

**Ele inventou coisas sobre um projeto** → veja se a resposta está carimbada
como NÃO CONFERI. Peça: *"leia o README e me mostre o que está lá de
verdade"*.

**Está lento** → desligue conexões que não está usando, e não abra conversa
nova a cada pergunta.

**Auditoria completa, sem alterar nada:**
```powershell
python auditar_tudo.py
```

---

## Os outros arquivos

| Arquivo | Para quê |
|---|---|
| `BIGODE.bat` | abrir — é o único que você usa no dia a dia |
| `ATUALIZAR_MEMORIA.bat` | reler seus projetos do Drive |
| `INSTALAR.bat` | montar o pendrive num computador novo |
| `auditar_tudo.py` | conferir tudo de uma vez |
| `auditar_selo.py` | provar que o selo pega invenção |
| `medir_maquina.py` | a máquina aguenta este modelo? |

---

## Estrutura

```
D:\
├── llamafile-0.10.3.exe
├── granite-4.0-h-tiny-*.gguf      as IAs
├── qwen2.5-coder-7b-*.gguf
└── Cerebro\
    ├── BIGODE.bat                 ← você clica aqui
    ├── cerebro.py                 servidor, prompt, ferramentas
    ├── ferramentas.py             as mãos
    ├── modelos.py                 liga e desliga o motor
    ├── mcp_servidor.py            ponte com o Claude
    ├── indexar.py                 lê seus projetos do Drive
    ├── config.json                motor, segurança, pastas
    ├── conexoes.json              o que está ligado
    ├── erros.log                  o que falhou, com data
    ├── motor.log                  o que o motor disse
    ├── habilidades\               manuais dos seus projetos
    ├── memoria\                   identidade e temperamento
    ├── web\                       a interface
    ├── extensao-chrome\           a extensão
    └── python\                    Python portátil
```

---

*Venure — venure.com.br · tecnologia própria*
