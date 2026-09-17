# Teste Fase 3: Feedback Visual com Screenshots

**Status:** ✅ Implementação integrada  
**Data:** 2026-09-17  
**Próximo passo:** Validar em navegador real

---

## ✅ O que foi implementado

### 1. Captura de screenshot (`extensao-chrome/screenshot.js`)
- Função `tirarScreenshot()` que captura a página usando html2canvas
- Converte para JPEG com compressão ajustável
- Redimensiona se > 1000x1000px
- Limita tamanho a 100KB

### 2. Processamento (`processador_screenshot.py`)
- `inicializar()` - cria pasta `.screenshots_temp`
- `salvar_screenshot()` - decodifica base64 → PNG
- `processar_resposta_extensao()` - extrai screenshot de resposta
- `injetar_no_contexto()` - adiciona instrução para IA analisar
- `limpar_screenshots()` - remove temporários ao encerrar

### 3. Integração no servidor (`cerebro.py`)
- Import de `processador_screenshot` (linha 69)
- Inicialização no startup (linha 4366)
- Processamento após ação de navegador (linhas 3672-3680)
- Limpeza ao desligar (linhas 4393, 4399)

### 4. Extensão Chrome
- `manifest.json` carrega `screenshot.js` antes de `conteudo.js`
- `conteudo.js` chama `anexarScreenshot()` em cada ação
- Retorna objeto com `{texto, screenshot, tipo_screenshot: 'jpeg_base64'}`

---

## 📋 Checklist de Teste

### Teste 1: Extensão captura screenshot
```
1. Abrir página simples (exemplo: google.com)
2. No console de developer da extensão, verificar se window.BigodeScreenshot existe
3. Executar: window.BigodeScreenshot.tirar(0.7)
4. Resultado esperado: string começando com "data:image/jpeg;base64,"
```

### Teste 2: conteudo.js envia screenshot
```
1. Abrir o Bigode na extensão
2. Pedir: "Clique no botão de pesquisa"
3. Verificar em cerebro.py logs se screenshot foi recebido
4. Esperado: RESULTADO com [SCREENSHOT DISPONÍVEL]
```

### Teste 3: IA vê e analisa screenshot
```
1. Pedir: "Tire um screenshot e diga o que vê"
2. Aguardar resposta
3. Esperado: IA descreve conteúdo da página baseado na imagem
```

### Teste 4: Screenshots temporários limpam
```
1. Abrir e fechar Bigode várias vezes
2. Verificar pasta: /home/user/Bigode-IA/.screenshots_temp
3. Esperado: pasta vazia quando Bigode encerrado (Ctrl+C)
```

---

## 🔧 Possíveis problemas e soluções

### Problema: "html2canvas is not defined"
**Solução:** A biblioteca pode não estar disponível. O código tem fallback para Canvas API nativa (menos preciso).

**Para adicionar html2canvas:**
1. Baixe de CDN: https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js
2. Coloque em `extensao-chrome/html2canvas.min.js`
3. No manifest.json, adicione antes de screenshot.js:
```json
"content_scripts": [{
  "js": ["html2canvas.min.js", "screenshot.js", "conteudo.js"],
  ...
}]
```

### Problema: "TypeError: processador_screenshot is not a module"
**Solução:** Fazer `git pull` para pegar `processador_screenshot.py` do servidor.

### Problema: Screenshot muito grande (> 3KB de mensagem)
**Solução:** Reduz qualidade automaticamente de 0.7 → 0.5 → 0.3. Se ainda > 100KB, descarta.

### Problema: IA não analisa screenshot
**Solução:** Verificar se `injetar_no_contexto()` está adicionando a instrução:
```
[SCREENSHOT DISPONÍVEL]
Arquivo: ...
Base64: data:image/png;base64,...
```

---

## 📊 Métricas esperadas

| Métrica | Meta | Status |
|---|---|---|
| Screenshot capturado | 100% | 🔄 Teste |
| Tamanho < 50KB | 95% | 🔄 Teste |
| IA vê imagem | 100% | 🔄 Teste |
| Limpeza automática | 100% | ✅ Código |

---

## 🚀 Próximos passos após validação

1. **Otimizar imagem** - ajustar qualidade/dimensão conforme resultado
2. **Testar em 10 sites reais** - validar compatibilidade com pages dinâmicas
3. **Documentar edge cases** - screenshot em modal, lazy-loading, etc.
4. **Fase 4** - otimizar velocidade com cache de contexto

---

## 📝 Notas técnicas

**Fluxo de dados:**
```
navegador_ver/clicar/escrever
  ↓
conteudo.js: anexarScreenshot(resultado)
  ↓
retorna: {texto, screenshot: "data:image/jpeg;base64,..."}
  ↓
cerebro.py: processador_screenshot.processar_resposta_extensao()
  ↓
salva PNG em .screenshots_temp/
  ↓
injetar_no_contexto() lê arquivo e re-encoda para base64
  ↓
injeta instrução + base64 na mensagem
  ↓
IA vê [SCREENSHOT DISPONÍVEL] + imagem + instrução "analise"
```

**Limite de contexto:**
- Cada screenshot ≈ 20-50 tokens
- Se usar 5 screenshots, já consome 250 tokens
- O caber_no_contexto() remove mensagens antigas se necessário

---

**Código pronto em:** https://github.com/falecomofred-lab/Bigode-IA  
**Branch:** `claude/bigode-ia-claude-code-1op4wt`  
**Commit:** `abed054`
