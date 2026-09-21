# Como ligar e usar — Bigode IA e Pipi IA

*Venure · venure.com.br · 13/09/2026*

---

## Antes de tudo: os dois projetos são coisas diferentes

| | **Bigode IA** | **Pipi IA** |
|---|---|---|
| serve para | conversar, ler e editar seus arquivos, pesquisar, mexer no Chrome | criar imagens |
| motor | `llama.cpp` lendo um `.gguf` de texto | ComfyUI lendo um `.gguf` de imagem |
| tela | `http://localhost:7000` | `http://localhost:7300` |
| pasta | `G:\Meu Drive\projetos\Cerebro` | `G:\Meu Drive\projetos\Pipi IA` |

Eles **não compartilham motor**. Um `.gguf` de texto não desenha, e um de imagem não conversa.

---

## Primeiro: confira se está tudo no lugar

Na pasta do Cerebro:

```
python conferir_tudo.py
```

Ele compila todos os arquivos das duas pastas, procura as correções uma a uma e termina com **PASSOU** ou a lista do que falta. Não liga nada e não precisa de internet. Se der vermelho, me mande a saída.

---

## BIGODE IA

### Escolha o modo antes de começar

| modo | ele alcança seus arquivos? | velocidade | quando usar |
|---|---|---|---|
| **A — tudo no Colab** | só o Google Drive | rápido (placa T4) | conversar, pesquisar, mexer em coisa que está no Drive |
| **B — híbrido** | **tudo: C:, G:, o Chrome** | rápido (placa T4) | editar seus projetos de verdade — é o modo que você pediu |
| **C — tudo no PC** | tudo | 2 a 5 palavras/segundo | quando o Colab não conecta |

### Modo A — tudo no Colab

Abra o notebook **Bigode IA.ipynb** e rode as células **1 a 8**, em ordem:

| célula | o que faz | quanto leva |
|---|---|---|
| 1 | escolhe a IA e mostra a tabela do que cabe | 15s |
| 2 | diz se tem placa | 1s |
| 3 | traz o código e o `.gguf` para o Colab | 1 a 3 min |
| 4 | instala o motor | 40s |
| 5 | adapta a configuração para Linux | 1s |
| 6 | **liga o motor** | 30s a 2 min |
| 7 | liga o Bigode | 20s |
| 8 | **imprime o seu link** | 40s |

Abra o link, entre com e-mail e senha. Pronto.

Para trocar de IA sem perder o link: edite `NOVA` na célula **9** e rode só ela.

### Modo B — híbrido (cérebro no PC, placa no Colab)

É o modo que resolve *"quero que ele edite meus arquivos"*. O cérebro roda no seu Windows e enxerga tudo; só a conta pesada viaja para a placa do Colab. **Seus arquivos nunca saem da sua máquina** — pelo túnel passa só texto.

**No Colab:** rode as células **1 a 6** (pare na 6, não precisa da 7 nem da 8). Depois rode a célula **8-B**:

```python
exec(open('/content/drive/MyDrive/projetos/Cerebro/tunel_motor.py').read())
```

Ela imprime uma linha começando com `{"llm_url": ...`. Copie inteira.

**No seu Windows,** na pasta do Cerebro:

```
python usar_motor_do_colab.py
```

Cole a linha quando ele pedir. Ele **testa antes de gravar** — se o endereço estiver errado, não mexe em nada e diz por quê.

Agora abra o Bigode de sempre. Ele pensa com a T4 e mexe nos seus arquivos.

Quando o Colab desligar:

```
python usar_motor_do_colab.py --local
```

### Sobre a chave

O motor agora sobe com uma chave própria. Sem ela, o endereço publicado ficaria aberto: qualquer um que topasse com o link gastaria a sua placa e a sua cota. A chave é gerada sozinha a cada sessão e viaja dentro daquela linha que você cola. **Não publique essa linha.**

---

## PIPI IA

### O problema de hoje

A Pipi precisa do ComfyUI, que precisa de uma placa NVIDIA. A sua máquina não tem CUDA disponível — por isso a porta 8188 nunca responde e a Pipi fica sem motor.

A saída é a mesma do Bigode: **usar a placa do Colab**.

### Ligando

**No Colab,** com a sessão já de pé (células 1 a 7 do Bigode), rode a célula **10**:

```python
exec(open('/content/drive/MyDrive/projetos/Cerebro/desenhista.py').read())
```

Ela instala o ComfyUI, o leitor de GGUF e baixa o FLUX. Na primeira vez da sessão leva alguns minutos.

Depois a célula **8-C**:

```python
exec(open('/content/drive/MyDrive/projetos/Cerebro/tunel_desenhista.py').read())
```

Copie o endereço.

**No seu Windows,** na pasta da Pipi IA:

```
python usar_desenhista_do_colab.py
```

Cole o endereço. Ele testa e mostra qual placa respondeu — se aparecer **Tesla T4**, chegou no lugar certo.

Depois:

```
pipi.bat
```

A Pipi abre em `http://localhost:7300` e desenha usando a T4.

Quando o Colab desligar:

```
python usar_desenhista_do_colab.py --local
```

### Um aviso sério sobre a Pipi

**O ComfyUI não tem senha. Nenhuma.** Enquanto o túnel da célula 8-C estiver de pé, quem tiver o endereço manda desenhar na sua placa e vê as imagens que você gerou.

O endereço é sorteado e muda a cada sessão, mas isso é obscuridade, não proteção. Não cole em grupo, e rode a célula **13** quando terminar.

O Bigode é diferente: ele tem tela de login, e o motor tem chave.

---

## Os três túneis agora convivem

Até ontem, ligar um derrubava os outros — cada script matava *todos* os túneis da máquina, não só o seu.

| porta | o quê | célula |
|---|---|---|
| 7000 | o Bigode inteiro | 8 |
| 8082 | o motor, para o modo híbrido | 8-B |
| 8188 | o ComfyUI, para a Pipi | 8-C |

Agora cada um mata só o seu antecessor. Você pode ter o Bigode no Colab **e** a Pipi puxando a placa ao mesmo tempo.

---

## O que não funciona, e por quê

**O provedor Modal.** O endpoint publicado hoje é um esqueleto: ele não carrega modelo nenhum e devolve `"Processamento simulado com sucesso."`. Antes, ligar `modelo_provedor: "modal"` fazia o Bigode responder isso para qualquer pergunta, parecendo que tinha funcionado. Agora ele recusa e diz o que falta. Deixe em `"local"` até publicar um endpoint de verdade.

**O Colab desliga sozinho.** 90 minutos sem você mexer na aba, ou 12 horas no total. Quando desliga, todos os links morrem e é preciso rodar tudo de novo.

**O link muda a cada sessão.** Túnel gratuito não tem nome fixo. Por isso a extensão do Chrome e a Pipi precisam ser reapontadas a cada vez — e por isso os dois scripts `usar_*_do_colab.py` existem.
