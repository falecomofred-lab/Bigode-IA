# Diagnóstico do Travamento — Bigode IA

**Data:** 17/09/2026  
**Problema:** Bigode responde a primeira mensagem normalmente, demora muito na segunda, para completamente na terceira.

---

## Três problemas encontrados no código

### 1. **Loop de passos sem proteção contra resposta vazia** (CRÍTICO)

**Localização:** `cerebro.py`, linhas 3355-3600 (função `_chat_interno`)

**O problema:**
```python
for passo in range(int(cfg["max_passos"])):
    if not vivo["ok"]:
        break
    # ... código que chama chamar_modelo ...
    if not texto:  # ← AQUI NAO TEM GUARDA
        # Se texto vem vazio, continua pro proximo passo
        # Se isso acontecer 3 vezes, gasta 3 chamadas pro motor
```

Se o modelo devolver uma resposta vazia (ou só tags vazias), o código continua tentando:
- Passo 1: Vazio → continua
- Passo 2: Vazio → continua  
- Passo 3: Vazio → sai do loop
- Resultado: travado aparenta, mas é lentidão acumulada + timeout

**Correção proposta:**
Adicionar escape se `texto` ficar vazio 2 vezes seguidas ou se `primeiro_token` nunca chegar.

---

### 2. **Gerenciamento de threads na extensão do Chrome**

**Localização:** `cerebro.py`, linhas 838-912 (função `pedir_ao_navegador`)

**O problema:**
```python
gatilho = threading.Event()
# ...
if not gatilho.wait(espera):  # espera até 90 segundos
    # timeout, mas...
    # Se houver múltiplas chamadas paralelas:
    # - thread 1 espera navegador_ver (90s)
    # - thread 2 espera navegador_clicar (90s)
    # - ambas expiram, ambas tentam de novo
    # = 180+ segundos de espera
```

Se a extensão não responder, cada `pedir_ao_navegador()` trava 90s. Com múltiplas requisições na mesma thread HTTP, a timeout acumula.

---

### 3. **Falta de heartbeat na thread de resposta HTTP**

**Localização:** `cerebro.py`, linhas 3026-3044 (função `_chat_interno`)

**O problema:**
```python
self.send_response(200)
self.send_header("Content-Type", "text/event-stream; charset=utf-8")
# ...
self.end_headers()

# Agora começa a enviar eventos
def evento(obj):
    try:
        self.wfile.write(...)  # ← Se der erro aqui, não há retry
        self.wfile.flush()
```

Se a conexão HTTP cair (navegador fecha a aba, perde wifi, etc.), `self.wfile.write()` falha silenciosamente, `vivo["ok"]` vira False, e o loop quebra — mas a thread pode ficar aberta esperando pelo GC.

---

## Dados que faltam

Para ter certeza, preciso rodar:
```bash
python medir_fluidez.py
```

Isso vai gerar `TRAVAMENTO-*.json` se houver travamento real. **Você consegue rodar isso no seu computador com o Bigode aberto?**

Enquanto isso, vou implementar as correções preventivas para os 3 problemas acima.

---

## Plano de correção

1. **Proteção contra resposta vazia** — Sair do loop se `texto` ficar vazio 2x
2. **Timeout separado para navegador** — Se demorar >30s, abortar em vez de esperar 90
3. **Heartbeat na resposta HTTP** — Enviar ping a cada 15s se não há novo conteúdo

Todas as correções são defensivas — não mudam a lógica, só adicionam proteção contra timeout.
