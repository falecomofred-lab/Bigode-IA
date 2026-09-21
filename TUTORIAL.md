# Tutorial — Bigode IA

*Venure · venure.com.br · 14/09/2026*

> Este arquivo substitui o `COMO-USAR.md`, que ficou para trás. Se os dois existirem na sua pasta, o bom é este.

---

## Parte 0 — As peças, em três minutos

### O Bigode não pensa sozinho

Ele é o **cérebro**: conversa, lê e escreve os seus arquivos, pesquisa, mexe no Chrome. Mas quem *pensa* é um **motor** — um programa que lê um arquivo enorme, o **modelo** (`.gguf`), e devolve texto.

```
você  →  Bigode (cérebro)  →  motor  →  modelo .gguf
```

Separar os dois é o que permite trocar de IA sem reiniciar nada.

### Motor precisa de placa de vídeo

Sem placa ele funciona, a **2 a 5 palavras por segundo**. Com uma T4, ~90. A sua máquina não tem placa utilizável, e é daí que vem toda a complicação a seguir.

### Os três modos

| modo | ele alcança seus arquivos? | velocidade | quando usar |
|---|---|---|---|
| **A** — tudo no Colab | só o Google Drive | rápido | conversar, pesquisar |
| **B** — híbrido | **tudo: C:, G:, Chrome** | rápido | **editar seus projetos** |
| **C** — tudo no PC | tudo | muito devagar | quando o Colab não conecta |

Se você quer que ele mexa nos seus projetos de verdade, é o **modo B**.

---

## Parte 1 — Modo A: o mais simples

**1.** Abra o **Bigode IA.ipynb** no Google Colab.

**2.** *Ambiente de execução → Alterar o tipo → **T4 GPU** → Salvar*

> Se disser *"não é possível conectar ao back-end da GPU"*, a cota grátis do dia acabou. Siga assim mesmo — funciona, devagar.

**3.** Rode as células **1 a 8**, em ordem. Clique no ▶ e espere cada uma terminar.

| célula | o que faz | tempo |
|---|---|---|
| 1 | mostra a tabela de IAs e quais cabem | 15s |
| 2 | diz se tem placa | 1s |
| 3 | traz o código e o `.gguf` | 1 a 3 min |
| 4 | instala o motor | 40s |
| 5 | adapta a configuração | 1s |
| 6 | **liga o motor** | 30s a 2 min |
| 7 | liga o Bigode | 20s |
| 8 | **imprime o seu link** | 40s |

> Na célula 1 o Google pede permissão para o Drive. Clique em **Conectar ao Google Drive**. É normal e acontece toda vez que a máquina do Colab é nova.

> Se a célula 6 reclamar de `No module named 'llama_cpp'`, é a 4 que não terminou. Espere ela imprimir **PRONTO PARA LIGAR O MOTOR**.

**4.** Abra o link, entre com e-mail e senha.

**5.** Deixe a aba do Colab aberta e passe por lá de vez em quando — rolar a página já conta.

---

## Parte 2 — Modo B: mexendo nos seus arquivos

O cérebro roda no seu Windows e enxerga tudo. Só a conta pesada viaja para a placa do Colab. **Pelo túnel passa só texto** — a pergunta vai, a resposta volta. Seus arquivos não saem da máquina.

**1.** No Colab, rode as células **1 a 6**. Pare na 6.

**2.** Rode a célula **8-B**. Ela imprime uma linha começando com `{"llm_url":`. Copie **inteira**.

**3.** No Windows, abra a pasta do Bigode. Clique na barra de endereço do Explorador, digite `cmd`, Enter.

**4.**
```
python usar_motor_do_colab.py
```

Cole a linha. Ele **testa antes de gravar**: endereço errado não vira configuração quebrada.

**5.** Abra o Bigode de sempre.

**Quando o Colab desligar:**
```
python usar_motor_do_colab.py --local
```

### Sobre a chave

O motor sobe com uma chave própria. Sem ela, o endereço publicado ficaria aberto e qualquer um gastaria a sua placa. A chave nasce a cada sessão e viaja dentro daquela linha que você cola. **Não publique essa linha.**

---

## Parte 3 — Imagens pelo Bigode

Peça na tela dele, em português:

> *"crie uma imagem de um café ao amanhecer, luz quente, vista de cima, formato story"*

Para isso funcionar, rode antes a célula **10** do notebook — ela sobe o ComfyUI com o FLUX.

**A placa é uma só.** O desenho precisa de ~7,5 GB e o motor de texto já está lá dentro. Com o `granite` cabe; com o `deepseek` não. A ferramenta avisa antes de tentar.

Formatos: `quadrado`, `retrato`, `paisagem`, `story`, `capa`. Saída em `Criativos/`, PNG em alta, sem marca d'água, **Apache 2.0** — uso comercial liberado.

---

## Parte 3-B — O motor na Modal (endereço fixo, sem Colab)

O Colab é gratuito e caduca: 12 horas no máximo, endereço novo a cada sessão, e o túnel do Cloudflare às vezes simplesmente não sobe. A Modal resolve isso — endereço fixo, que não expira e não some quando você fecha a aba.

### O que havia antes, e por que não servia

O único app do Bigode na Modal era o `modal_api_teste.py`: 32 linhas que devolviam `"Processamento simulado com sucesso"` e uma `media_url` apontando para `exemplo.invalid`. Reservava uma T4 e não carregava modelo nenhum. O `modal_cliente.py` tem uma trava que reconhece essa resposta e recusa — senão o Bigode responderia *"Processamento simulado com sucesso"* a qualquer pergunta, parecendo que funcionou.

Pode parar esse app: **modal.com/apps → `cerebro-modal-api` → Stop app**.

### Publicar o motor de verdade

```
python -m pip install --upgrade modal
python -m modal setup

python -m modal secret create bigode-token BIGODE_TOKEN=escolha-uma-senha-longa
python -m modal deploy modal_motor.py
```

O `deploy` demora na primeira vez: ele baixa os 4,7 GB do Qwen2.5-Coder 7B Q4_K_M **durante a construção**, não na hora do primeiro pedido. É de propósito — baixar no arranque estouraria o tempo de partida e daria um erro que não explica nada.

> O repositório foi escolhido a dedo: a API do Hugging Face confirma `"gated": false`. O gerador da Pipi passou um dia inteiro em crash-loop porque o repositório do FLUX exige aceite de licença. Aqui não há formulário no caminho.

### Apontar o Bigode

```
python usar_modal_motor.py
```

Cole o endereço (termina em `-servidor.modal.run`) e o token. Ele **conversa de verdade** com o modelo antes de gravar, usando o mesmo `modal_cliente` que o Bigode usa — se o formato do pedido não servir, a falha aparece agora e não no meio de uma conversa sua.

Um ping não bastaria: o roteador da Modal responde mesmo com o container morto por baixo. Foi exatamente assim que a Pipi ficou um dia publicada, com endereço vivo, sem gerar nada.

### Voltar ao motor local

```
python usar_modal_motor.py --remover
```

### O que muda na prática

| | local (CPU) | Modal (L4) |
|---|---|---|
| velocidade | 6,4 tok/s medidos | muitas vezes mais |
| endereço | não precisa | fixo, não expira |
| ferramentas | sim | **não** — ver abaixo |

**As ferramentas continuam no motor local, de propósito.** Esta rota ainda não faz tool calling, e executar ação sua sem confirmação seria pior do que não executar. Para trabalho com ferramentas, use o motor local ou o híbrido.

---

## Parte 4 — Os três túneis convivem

| porta | o quê | célula |
|---|---|---|
| 7000 | o Bigode inteiro | 8 |
| 8082 | o motor, modo híbrido | 8-B |
| 8188 | o ComfyUI, para a Pipi | 8-C |

Até 13/09 ligar um derrubava os outros: cada script matava **todos** os túneis da máquina. Agora cada um mata só o seu.

---

## Parte 5 — Manutenção

### Conferir se está tudo no lugar
```
python conferir_tudo.py
```
Compila todos os arquivos e confere cada correção. Não liga nada, não precisa de internet. Termina com **PASSOU** ou a lista do que falta.

### Igualar as três cópias
```
powershell -ExecutionPolicy Bypass -File .\SINCRONIZAR.ps1
```
Drive → C: e pendrive. **Nunca apaga** e **nunca toca** no que é de cada cópia: `config.json`, conversas, histórico, chaves e o Python portátil do pendrive.

### Enviar para o GitHub
```
powershell -ExecutionPolicy Bypass -File .\ENVIAR_GITHUB.ps1 -Ensaio
powershell -ExecutionPolicy Bypass -File .\ENVIAR_GITHUB.ps1
```
Ele **confere antes de enviar** e para se achar `config.json`, `usuarios.json`, `conversas/` ou `memoria/projetos/` na lista.

---

## Parte 6 — Quando der errado

**"Não é possível conectar ao back-end da GPU"** — cota esgotada. Espere horas ou siga sem placa.

**A célula 1 diz que a IA "NAO" cabe** — memória ocupada. *Ambiente de execução → Reiniciar sessão* e rode tudo de novo. Sessão nova tem ~12 GB.

**O link da célula 8 dá erro** — confira se a 7 terminou com **BIGODE DE PE**. Se sim, rode a 8 de novo; o endereço muda.

**"O motor derrubou a conexão"** — ainda carregando, ou caiu. Rode a 6 e espere **MOTOR DE PE**.

**A extensão do Chrome não conecta** — o endereço muda a cada sessão. `chrome://extensions` → Bigode → Detalhes → Opções → cole o link novo.

---

## Parte 7 — Duas coisas para levar a sério

**O que você digita sai do seu computador** e vai para uma máquina do Google, no modo A. No modo B, só o texto da conversa viaja — os arquivos ficam com você.

**O provedor "Modal" do Bigode não funciona ainda.** O endpoint publicado é um esqueleto que devolve *"Processamento simulado com sucesso"* para qualquer pergunta. Hoje o Bigode **recusa** essa resposta em vez de repassar como verdade. Deixe `modelo_provedor` em `"local"`.

*(A Pipi é outra história: lá a Modal já roda de verdade. Veja o tutorial dela.)*

---

## Resumo de uma página

**Modo A:** Colab → T4 → células 1 a 8 → abre o link → login.

**Modo B:** Colab → células 1 a 6 → célula 8-B → copia a linha → no Windows `python usar_motor_do_colab.py` → cola → abre o Bigode de sempre.

**Imagens:** célula 10, depois peça na tela.

**Conferir:** `python conferir_tudo.py`

**Sincronizar:** `SINCRONIZAR.ps1`
