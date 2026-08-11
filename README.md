# Cérebro

Uma IA que roda inteira no pendrive. Sem nuvem, sem mensalidade, sem enviar
nada para fora do computador.

Feito pela **[Venure](https://venure.com.br)**.

---

## O que é

O Cérebro é uma plataforma de IA local. Você espeta o pendrive, dá um duplo
clique, e abre no navegador uma conversa parecida com a do ChatGPT — só que o
modelo roda na sua máquina e as ferramentas mexem nos seus arquivos de verdade.

Ele lê e escreve nas pastas que você libera, navega na internet, consulta APIs
brasileiras (CEP, CNPJ, clima, feriados, câmbio), controla o Chrome e conversa
com o Claude por MCP. Tudo com autorização, e sempre mostrando na tela o que
está fazendo.

## O que ele faz

| | |
|---|---|
| **Conversa** | interface de chat com streaming, copiar, editar e refazer |
| **Ferramentas** | 33 ferramentas: arquivos, busca, web, GitHub, terminal, navegador |
| **Mostra o trabalho** | "Lendo README.md", "Escrevendo app.py" — em português, ao vivo |
| **Pede permissão** | antes de escrever, mover ou apagar, apresenta o plano e espera |
| **Habilidades** | manuais especializados que carregam sob demanda, como as Skills do Claude |
| **Memória** | conhece seus projetos e o seu jeito de trabalhar |
| **Voz** | ditado por Whisper local |
| **Celular** | instala como app no iPhone pela rede Wi-Fi |
| **Extensão Chrome** | painel lateral com automação de navegador |
| **Ponte MCP** | o Claude enxerga seus arquivos através do Cérebro |
| **Login** | e-mail e senha, mais Google, Apple e GitHub |

## Como funciona por dentro

```
CEREBRO.bat  ──►  cerebro.py  ──►  llamafile (motor do modelo, porta 8082)
                      │
                      ├── ferramentas.py   as mãos: arquivos, web, terminal
                      ├── modelos.py       liga e desliga os modelos GGUF
                      ├── habilidades.py   manuais sob demanda
                      ├── memoria/         identidade, temperamento, projetos
                      ├── autenticacao.py  login e sessões
                      ├── mcp_servidor.py  ponte para o Claude
                      └── web/index.html   a interface inteira, num arquivo
```

O modelo nunca é chamado direto por ninguém além do `modelos.py`. Trocar de
motor — llamafile, llama-server, outro — é escrever outro adaptador ali, sem
tocar no resto.

## Instalação

Você precisa de um pendrive (32 GB ou mais), Python 3.11+, um
[llamafile](https://github.com/Mozilla-Ocho/llamafile/releases) e pelo menos um
modelo no formato **GGUF**.

```powershell
git clone https://github.com/falecomofred-lab/cerebro.git
cd cerebro
Copy-Item config.example.json config.json
Copy-Item conexoes.example.json conexoes.json
```

Abra o `config.json` e ajuste `pastas_liberadas` para as pastas que o Cérebro
pode acessar. Depois:

```powershell
.\INSTALAR_NO_PENDRIVE.ps1
```

O instalador copia tudo para o pendrive junto com um Python portátil, para o
Cérebro rodar em qualquer máquina Windows sem instalar nada.

Coloque o `llamafile` e o arquivo `.gguf` na **raiz** do pendrive, e dê um
duplo clique em `CEREBRO.bat`.

### Modelos que funcionam bem

Testados num Ryzen 7 5825U, 32 GB de RAM, **sem placa de vídeo**:

| Modelo | Tamanho | Velocidade | Ferramentas |
|---|---|---|---|
| Granite 4.0 H-Tiny (7B-A1B) | 4,2 GB | rápido | nativas |
| Qwen2.5-Coder 7B | 4,7 GB | 3,8 tok/s | nativas |
| Qwen3-Coder 30B-A3B | 19 GB | 2,9 tok/s | nativas |

Modelos MoE (aqueles com poucos parâmetros ativos por token) rendem muito mais
sem GPU do que modelos densos do mesmo tamanho.

## O que fica de fora do Git

Estes arquivos são seus e não sobem:

- `usuarios.json` — seu login
- `conexoes.json` — os tokens que você colar nas conexões
- `config.json` — os caminhos da sua máquina
- `conversas/`, `projetos/` — seu histórico
- `*.gguf` — os modelos, que têm gigabytes

Os `.example.json` mostram o formato de cada um.

## Licença

Uso pessoal e interno da Venure. Se quiser usar em outro contexto, fale comigo.

---

*Venure — [venure.com.br](https://venure.com.br)*
