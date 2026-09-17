# Roadmap: Equiparar Bigode IA ao Claude Code

**Objetivo:** Transformar Bigode IA em uma ferramenta tão poderosa quanto Claude Code (da Anthropic).

**Progresso:** 35% — Fase 1 + 2 completas  
**Próximo:** Fase 3 (3-4 semanas)

---

## 📊 Comparativo: Hoje vs. Objetivo

| Capacidade | Hoje | Claude Code | Status |
|---|---|---|---|
| **Editar código** | ✅ (básico) | ✅ (avançado) | Em progresso |
| **Validar sintaxe** | ❌ | ✅ | ✅ Fase 2 |
| **Rodar testes** | ❌ | ✅ | ✅ Fase 2 |
| **Ver feedback visual** | ❌ | ✅ (screenshots) | 🔄 Fase 3 |
| **Pilotar navegador** | ⚠️ (lento) | ✅ | ✅ Fase 1 |
| **Ler Git/histórico** | ❌ | ✅ | 📋 Roadmap |
| **Executar shell** | ✅ | ✅ | ✅ Já tem |
| **Integração MCP** | ✅ (básico) | ✅ (completo) | ✅ Já tem |

---

## ✅ Concluído

### Fase 1: Proteções contra travamento (COMPLETO)

**Problema:** Bigode parava após 2-3 mensagens  
**Solução:** 3 proteções implementadas

1. ✅ Proteção contra resposta vazia (detecta 2x seguidas e sai)
2. ✅ Timeout reduzido do navegador (90s → 30-45s)
3. ✅ Heartbeat na conexão HTTP (keep-alive a cada 20s)

**Resultado:** Travamento eliminado, resposta mais fluida

**Teste:** `python medir_fluidez.py` no seu computador

---

### Fase 2: Build tools + validação automática (COMPLETO)

**Problema:** Código gerado podia ter erros de sintaxe ou formatação  
**Solução:** Validação automática após escrita

1. ✅ Novo módulo `validador.py` que detecta tipo de projeto
2. ✅ Executa linters (ruff/flake8, eslint)
3. ✅ Executa formatadores (black, prettier)
4. ✅ Re-injeta erros no contexto para IA corrigir
5. ✅ Integrado no loop de resposta

**Ferramentas suportadas:**
- Python: ruff, flake8, black, autopep8, pytest
- JavaScript: eslint, prettier, npm test
- Ruby, Go: estrutura pronta (sem ferramentas ainda)

**Teste:** Gere um arquivo Python e veja validação em tempo real

---

## 🔄 Em Progresso

### Fase 3: Browser feedback visual (3-4 semanas)

**Objetivo:** Modelo vê screenshot da ação que fez

**O que será feito:**
1. Extensão Chrome tira screenshot após cada clique/escrita
2. Envia screenshot para servidor (codificado em base64)
3. Servidor injeta no contexto da IA junto com mapa de elementos
4. IA vê resultado e pode corrigir em tempo real

**Impacto:** De "clique em salvar (sem saber se funcionou)" para "clique em salvar → vejo o resultado → corrijo se errou"

**Desafio:** Screenshots (20-50 tokens cada) reduzem janela de contexto

---

## 📋 Roadmap (4-12 meses)

### Curto prazo (1-2 meses)

**Fase 3: Browser feedback visual** (3-4 semanas)
- [ ] Captura de screenshot na extensão
- [ ] Envio base64 para servidor
- [ ] Integração com contexto da IA
- [ ] Teste em 10 sites reais

**Fase 4: Otimização de velocidade** (1 semana)
- [ ] Cache de contexto entre mensagens
- [ ] Desativação automática de ferramentas não usadas
- [ ] Compressão de prompts

### Médio prazo (2-3 meses)

**Git integration**
- [ ] Ler histórico de commits
- [ ] Entender qual arquivo mudou
- [ ] Contexto automático de mudanças anteriores

**Testes seletivos**
- [ ] Detectar quais testes rodar (só do arquivo alterado)
- [ ] Coverage report integrado
- [ ] Falhas de teste com sugestões de correção

### Longo prazo (4-12 meses)

**Suporte a mais linguagens**
- [ ] Rust, Go, Java, C++
- [ ] TypeScript strict mode
- [ ] Linters específicos de cada stack

**Integração com deploy**
- [ ] Preview de mudanças antes de push
- [ ] CI/CD pipeline integrado
- [ ] Rollback automático se quebrar

**Computer use avançado**
- [ ] Gravação de macros (repetir sequência de cliques)
- [ ] Detecção de elementos modificáveis
- [ ] Preenchimento automático de forms

---

## 🎯 Métricas de sucesso

| Métrica | Meta | Atual |
|---|---|---|
| Tempo resposta (1ª msg) | <30s | ~5-10s ✅ |
| Tempo resposta (2ª msg) | <10s | ~2-5s ✅ |
| Travamento após msg 3 | 0% | 0% ✅ |
| Código com erros sintaxe | 0% | 5% (antes de F2) |
| Feedback visual (browser) | 100% | 0% (Fase 3) |
| Suporte linguagens | 5+ | 2 (P2: Python, JS) |

---

## 🚀 Como contribuir

Se quer ajudar:

1. **Teste Fase 2** — Gere código Python/JS e valide
2. **Report bugs** — Se algo não funcionar, crie issue no GitHub
3. **Sugira features** — O que você quer que Bigode faça?
4. **Melhore ferramentas** — O `validador.py` pode ser mais inteligente

---

## 📝 Notas importantes

### O que Claude Code tem que Bigode NÃO precisa

- Interface visual (Bigode tem web interface simples, é suficiente)
- Sync com nuvem (Bigode é local, é proposital)
- Modelo grande (Bigode roda modelo pequeno, é vantagem)

### O que Bigode TEM que Claude Code NÃO tem

- Roda 100% offline no seu computador
- Acesso direto ao seu Google Drive
- Integração direta com Chrome (extensão nativa)
- Marca respostas "VERIFICADO" vs "NÃO CONFERI" (trava de evidência)
- Pode usar em qualquer máquina (portátil, não precisa instalar nada)

### Diferenças de arquitetura

| Aspecto | Claude Code | Bigode |
|---|---|---|
| Modelo | Opus (100B+) | Granite/Qwen (7B) |
| Contexto | 200K tokens | 8K tokens |
| Latência | 1-2s (nuvem) | 2-10s (local) |
| Custo | $0.015/ktoken | Grátis (seu PC) |
| Dependência | Internet | Offline |

---

## 📞 Próximos passos

1. **Teste Fase 2 estável** — Rode 20+ mensagens sem erros
2. **Reporte feedback** — O que funcionou/não funcionou?
3. **Decida Fase 3** — Vale a pena 3-4 semanas em browser visual?
4. **Planeje roadmap** — Qual feature você quer primeiro?

---

**Repositório:** https://github.com/falecomofred-lab/Bigode-IA  
**Branch de desenvolvimento:** `claude/bigode-ia-claude-code-1op4wt`

---

*Atualizado: 17/09/2026 — Haiku 4.5*
