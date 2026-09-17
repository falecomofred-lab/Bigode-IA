# Como testar as correções de travamento

Essas mudanças foram feitas para evitar que o Bigode "congele" após a segunda/terceira mensagem. Aqui está como verificar se funcionam.

---

## Teste 1: Conversa de 5 mensagens seguidas (rápido)

**Setup:**
- Abra o Bigode normalmente
- Entre com seu email/senha
- Não use o navegador por enquanto

**Teste:**
```
Mensagem 1: "Oi, tudo bem?"
Mensagem 2: "Quem foi Albert Einstein?"
Mensagem 3: "E Marie Curie?"
Mensagem 4: "Cite 3 contribuições dela para ciência"
Mensagem 5: "Obrigado!"
```

**Esperado:**
- Cada resposta deve chegar em 2-10 segundos
- Nenhuma travada (cada mensagem progride)
- Se alguma falhar, vira erro explícito, não silêncio

**Se falhar:**
Se a terceira ou quarta message mostrar "O modelo parou de responder", é porque o modelo está retornando resposta vazia — anote isso no DIAGNOSTICO_TRAVAMENTO.md

---

## Teste 2: Navegador com timeout reduzido (opcional)

**Setup:**
- Abra o Chrome com a extensão do Bigode instalada
- Acesse um site normal (ex: Google)

**Teste:**
```
Mensagem 1: "O que tem nesta página agora?"
```

**Esperado:**
- Se a extensão responder: chega em 5-30 segundos
- Se a extensão NÃO responder: aviso de "navegador não respondeu em 30s" aparece em ~32 segundos (em vez de esperar 90s)
- A resposta NOT TRAVA - avança mesmo sem a tela

---

## Teste 3: Múltiplas ferramentas (se aplicável)

```
Mensagem 1: "Pesquise sobre Claude Code"
Mensagem 2: "Agora sobre Bigode IA"
Mensagem 3: "Qual é a diferença?"
```

**Esperado:**
- Cada pesquisa web volta em <20s
- Respostas fluem sem travamento
- Se houver timeout de navegador, é reportado, não silencioso

---

## Dados de sucesso

Se conseguir fazer essas 3 sequências sem nenhuma mensagem travar invisível, as correções funcionaram.

**Envie para Venure:**
- Quantas mensagens de teste conseguiu fazer?
- Se alguma falhou, qual foi a 1ª?
- Qual erro apareceu (ou sumiu)?
- Quanto tempo cada uma demorou?

---

## Se continuar travando

Se ainda houver travamento (principalmente na 3ª mensagem), rode:

```bash
python medir_fluidez.py
```

Isso vai gerar um arquivo `TRAVAMENTO-YYYYMMDD-HHMMSS.json` mostrando em que linha do código cada parte parou. **Esse arquivo é a evidência de que não é lentidão — é travamento real.**

Envie esse arquivo para Venure para próximas correções.

---

## O que mudou tecnicamente

1. **Resposta vazia** — Se o modelo der resposta vazia 2x, sai do loop em vez de continuar
2. **Timeout navegador** — Reduzido de 90s → 45s, evita acúmulo
3. **Heartbeat HTTP** — Mantém conexão viva a cada 20s

Nenhuma dessas mudanças afeta a qualidade das respostas — só evitam que o programa fique travado esperando algo que nunca vem.
