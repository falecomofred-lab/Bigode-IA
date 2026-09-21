# Alterações aplicadas ao Cerebro

Esta pasta contém os arquivos modificados conforme o prompt recebido. A aplicação foi feita sobre uma cópia de trabalho extraída de `Cerebro.zip`; o arquivo original enviado permanece intacto.

## Arquivos alterados

| Arquivo | Alteração |
| --- | --- |
| `cerebro.py` | O payload nativo agora sempre define `tool_choice` como `required` quando há ferramentas disponíveis. |
| `memoria/temperamento.md` | Foram adicionadas as cinco Regras de Ferro anti-invenção e a exigência de `navegador_ver`. |
| `ferramentas.py` | Foi adicionada `buscar_no_vault`, registrada no catálogo, nos parâmetros e nos campos obrigatórios do schema de function calling. |
| `indexar_vault.py` | Novo indexador de arquivos Markdown do Obsidian, gerando `vault_index.json` ao lado do vault. |
| `config.json` | Foi adicionada a chave `vault_path` com o valor `G:\\Meu Drive\\projetos\\Bigode-Vault`. |
| `auditar_selo.py` | Foi adicionada uma verificação local que confirma a presença da trava real no `cerebro.py`; o script não tinha payload próprio do LLM para alterar. |

## Validação realizada

A compilação dos quatro arquivos Python passou. Um teste determinístico criou um vault temporário, executou `indexar_vault.py`, importou `ferramentas.py`, confirmou que `buscar_no_vault` aparece no catálogo e no schema OpenAI e encontrou um trecho indexado. Resultado: `VALIDACAO_PROMPT_OK`.

Também foi executado `python auditar_selo.py --help` com sucesso. A execução completa do auditor foi iniciada e confirmou a trava local, mas não pôde fazer as cinco perguntas porque não havia um servidor Bigode escutando em `http://localhost:7000` no sandbox. Resultado de runtime: `Connection refused`.

## Como aplicar no seu computador

Substitua os arquivos correspondentes na pasta real do projeto, mantendo primeiro uma cópia de segurança. Depois confirme o caminho real do vault em `config.json` e execute:

```powershell
python indexar_vault.py
python auditar_selo.py
```

O comando completo de `auditar_selo.py` precisa ser executado com `cerebro.py` em funcionamento, o motor LLM disponível e uma conta válida para login. O backup criado durante a edição está em `/home/ubuntu/cerebro-backup-before-20260821` dentro do ambiente de trabalho desta sessão.
