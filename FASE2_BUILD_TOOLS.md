# Fase 2: Integração de Build Tools + Testes

**Status:** ✅ Implementado  
**Data:** 17/09/2026

---

## O que foi implementado

### 1. Novo módulo: `validador.py`

Detecta e executa ferramentas de validação do projeto:

- **Detecta tipo de projeto:** Python, Node.js, Ruby, Go
- **Valida sintaxe:** flake8/ruff (Python), eslint (JavaScript)
- **Formata código:** black/autopep8 (Python), prettier (JavaScript)
- **Roda testes:** pytest (Python), npm test (Node.js)

### 2. Integração com loop de resposta

Após escrever arquivo, o Bigode agora:

1. Detecta qual tipo de projeto é
2. Roda linters/formatadores/testes automaticamente
3. Se houver erro, mostra na tela **em tempo real**
4. Re-injeta erro no contexto para que a IA corrija
5. Força a IA a chamar `escrever_arquivo` novamente com código corrigido

---

## Como funciona

### Fluxo normal (sem erro):

```
Você: "Escreva um arquivo Python com função para calcular fatorial"
↓
Bigode escreve arquivo
↓
Validador roda flake8
↓
"✓ Código validado (sem erros)"
↓
Resposta pronta
```

### Fluxo com erro:

```
Você: "Escreva função que ordena lista"
↓
Bigode escreve:
    def ordena(lista)  # ← falta :
        return sorted(lista)
↓
Validador roda flake8
↓
Flake8 retorna:
    "E999: SyntaxError: invalid syntax"
↓
Bigode re-injeta no contexto:
    "VALIDAÇÃO: Erro de sintaxe na linha 1...
     Corrija os erros acima. Use escrever_arquivo de novo."
↓
IA corrige e escreve novamente
↓
Validador passa
↓
Resposta pronta
```

---

## Ferramentas suportadas

### Python

| Tipo | Ferramenta | Como instalar |
|---|---|---|
| Linter | `ruff` (preferido) | `pip install ruff` |
| Linter | `flake8` (fallback) | `pip install flake8` |
| Formatador | `black` (preferido) | `pip install black` |
| Formatador | `autopep8` (fallback) | `pip install autopep8` |
| Testes | `pytest` | `pip install pytest` |

### JavaScript/TypeScript

| Tipo | Ferramenta | Como instalar |
|---|---|---|
| Linter | `eslint` | `npm install --save-dev eslint` |
| Formatador | `prettier` | `npm install --save-dev prettier` |
| Testes | `npm test` | Qualquer test runner em package.json |

### Não suportado

- Ruby, Go, Java (por enquanto)
- Projetos sem ferramentas de validação (continua funcionando normalmente)

---

## Exemplos de uso

### Exemplo 1: Python com erro de sintaxe

```python
# Código gerado (com erro):
def calcula_media(notas)  # ← falta :
    return sum(notas) / len(notas)

# Validador detecta:
# E999: SyntaxError: invalid syntax (:1:20)

# IA corrige automaticamente na próxima rodada
```

### Exemplo 2: JavaScript com warnings

```javascript
// Código gerado:
function greet(name) {
  var x = 5;  // ← var não deveria ser usado
  console.log("Oi " + name);
}

// ESLint encontra:
// warning: 'x' is assigned a value but never used

// IA corrige removendo a linha desnecessária
```

---

## Limitações e futuros aprimoramentos

### Atuais

1. **Não roda testes automaticamente** — Só sintaxe/formatação por enquanto
   - Razão: testes podem ser lentos (>60s)
   - Solução futura: rodar só testes relevantes ao arquivo escrito

2. **Não mostra diff** — Mostra só erros, não o que foi formatado
   - Razão: evita poluir a tela
   - Solução futura: mostrar `git diff` se houver mudanças

3. **Timeout de 30s** — Se validação demorar mais, aborta
   - Razão: não pode travar a resposta
   - Ajustável em `validador.py`

### Roadmap

- [ ] Integração com Git para mostrar `git diff`
- [ ] Testes seletivos (só rodar se arquivo.py está em `tests/`)
- [ ] Suporte a Rust, Go, Java
- [ ] Pre-commit hooks automáticos
- [ ] Coverage report integrado

---

## Como testar

### Teste 1: Gerar código Python com erro

```
Você: "Escreva função para somar dois números"
```

**Se Python/flake8 estiver instalado:**
- Bigode escreve o arquivo
- Flake8 valida
- Se houver erro, mostra na tela

**Se não estiver instalado:**
- Código é escrito mesmo assim
- Nenhuma validação acontece (fallback silencioso)

### Teste 2: Ativar validação

```bash
# No seu projeto Python:
pip install ruff

# Agora validador vai usar ruff automaticamente
```

### Teste 3: Ver o validador em ação direto

```bash
cd /seu/projeto/python
python validador.py
```

Isso mostra:
- Tipo de projeto detectado
- Qual linter/formatador está sendo usado
- Erros encontrados

---

## Código relevante

- `validador.py` — Módulo de validação (novo)
- `cerebro.py` linhas ~3685-3720 — Integração com loop de resposta

---

## Próximo passo

Depois de testar a Fase 2, podemos passar para **Fase 3: Browser feedback visual** (screenshots em tempo real).

Mas antes, a Fase 2 deve rodar stável durante ~20 mensagens sem erros de compilação.
