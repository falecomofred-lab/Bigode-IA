# Como auditar cada modelo — as 13 etapas

Roteiro para rodar a auditoria completa em **cada LLM**, com os mesmos testes,
e terminar com uma tabela comparando todos.

Tempo por modelo: **35 a 50 minutos**, quase tudo esperando.

---

## Antes de começar

```powershell
pip install psutil
```

Sem isso, a medição de RAM sai como INFORMAÇÃO NÃO DISPONÍVEL.

---

## O ciclo, para CADA modelo

### 1. Escolha o modelo no Bigode IA

Canto superior direito → clique no modelo → espere carregar. Leva minutos se
for grande.

### 2. Espere ficar realmente pronto

Na janela do motor, espere aparecer `server is listening`. Rodar antes disso
contamina a medição — foi o que fez o teste A marcar 92 s na primeira vez.

### 3. Aqueça

```powershell
python auditar_motor.py --rapido
```

**Jogue este resultado fora.** Ele existe só para tirar o custo do cache frio
da conta. Sem ele, o primeiro teste de cada modelo carrega um peso que não
tem nada a ver com o modelo.

### 4. Meça velocidade — etapas 1, 2, 9

```powershell
python auditar_motor.py
```

~12 minutos. Preenche: ambiente, tempo até o primeiro token, tokens/s,
leitura de prompt, RAM.

### 5. Meça qualidade — etapas 3, 4, 5, 6

```powershell
python auditar_qualidade.py
```

~20 minutos. 19 questões com gabarito:

| Área | Questões | Como é corrigido |
|---|---|---|
| Raciocínio | 5 | resposta numérica ou palavra exata |
| Programação | 5 | **o código é executado** contra casos de teste |
| Instruções | 4 | formato conferido por regra |
| Alucinação | 5 | pergunta sobre coisa inexistente — acerto é admitir |

### 6. Anote o que a máquina não vê

Abra o arquivo `auditoria/QUALIDADE-*.json` e leia as respostas. Anote:

- o código estava **legível**, ou só passava nos testes?
- a explicação fazia sentido para você?
- ele **repetiu** o erro quando foi corrigido? (questão R5)
- o texto degringolou no fim da resposta longa?

Isso é a etapa 4 e parte da 3 que **nenhum script mede**. Cinco minutos de
leitura valem mais que qualquer nota automática.

### 7. Repita do passo 1 com o próximo modelo

---

## Depois de todos

```powershell
python comparar_modelos.py
```

Monta a tabela e a classificação ponderada — etapas 8 e 11.

**Ele se recusa a classificar modelo com dado faltando.** Se um ficar de fora,
é porque falta rodar uma das duas provas nele, não porque ele é ruim.

---

## As 13 etapas — quem cobre o quê

| Etapa | Coberta por | Automática? |
|---|---|---|
| 1 · Ambiente | `auditar_motor.py` | sim |
| 2 · Velocidade | `auditar_motor.py` | sim |
| 3 · Raciocínio | `auditar_qualidade.py` | sim + sua leitura |
| 4 · Programação | `auditar_qualidade.py` | sim (executa o código) |
| 5 · Instruções | `auditar_qualidade.py` | sim |
| 6 · Alucinação | `auditar_qualidade.py` | sim |
| 7 · Contexto | **manual** — ver abaixo | não |
| 8 · Eficiência | `comparar_modelos.py` | sim |
| 9 · Gargalos | `auditar_motor.py` + `motor.log` | parcial |
| 10 · Perfis | `AUDITORIA-MOTOR.md` | já escrito |
| 11 · Comparação | `comparar_modelos.py` | sim |
| 12 · Config ruim | `AUDITORIA-MOTOR.md` | já escrito |
| 13 · Relatório | `AUDITORIA-MOTOR.md` | você fecha com os dados |

---

## Etapa 7 · Contexto — a que não dá para automatizar bem

O contexto está travado em **8.192**. Testar 16k e 32k exige **recarregar o
motor** com outro valor, o que leva minutos por vez.

Faça assim, e só depois de resolver o gargalo do cache:

1. Configurações → Memória por conversa → **Grande** (16384) → salve
2. Reinicie o motor
3. `python auditar_motor.py`
4. Compare o **tempo até o primeiro token** com o de 8192

Você já testou 16k uma vez e ficou mais lento. A pergunta agora é **quanto**,
com número. Se o primeiro token dobrar, 8192 é o ponto ótimo e está encerrado.

---

## Por que a prova é a mesma para todos

Temperatura **0,2** e **seed 42** fixos nas duas provas. Sem isso, o mesmo
modelo dá respostas diferentes a cada execução e a comparação vira sorteio.

É o motivo de você não dever mudar as perguntas entre um modelo e outro. Se
quiser acrescentar questões, acrescente — mas rode **todos** de novo.

---

## Ordem sugerida

Comece pelo **Qwen 14B**, que nunca foi medido e é o único candidato
desconhecido. Depois Granite, depois Qwen 7B. Os dois últimos já têm número de
velocidade; falta a qualidade, que é o que decide.

---

*Venure — venure.com.br · tecnologia própria*
