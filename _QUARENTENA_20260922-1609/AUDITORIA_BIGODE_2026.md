# Auditoria do Bigode IA — precisão, fluidez e execução

## Escopo

Foram revisados os arquivos enviados do núcleo Python, catálogo de ferramentas, ChromaDB, roteador, extensão Chrome, inicialização do Windows, autenticação, armazenamento local, ponte MCP, interface HTML, documentação e testes. A auditoria distingue o que está implementado no código do que é apenas descrito em documentos.

## Diagnóstico principal

O Bigode não é um modelo de linguagem independente. Ele é um orquestrador em volta do modelo GGUF local. A qualidade final depende de quatro partes: o modelo escolhido, as instruções enviadas a ele, a decisão de usar ferramentas e a qualidade dos resultados que voltam ao contexto. Hoje essas partes existem, mas algumas instruções se contradizem e algumas funções são heurísticas. Por isso o sistema pode ser tecnicamente capaz de executar uma ação, mas ainda responder de forma curta, técnica, imprecisa ou escolher o caminho errado.

## Achados críticos e altos

| Severidade | Achado | Evidência | Impacto |
|---|---|---|---|
| Alta | As instruções antigas obrigavam o modelo a usar ferramenta em quase todo tipo de pergunta e mandavam responder em duas ou três frases. | `cerebro.py`, `PROTOCOLO` e `PROTOCOLO_CURTO`; `temperamento.md`, regras 1 e 2. | Saudações e explicações simples ganham etapas artificiais; tarefas complexas podem ser cortadas antes de explicar o necessário. |
| Alta | O roteador chamado de semântico não usa embeddings; ele conta palavras que coincidem. | `roteador_semantico.py`, linhas 27–50. | Perguntas com sinônimos ou contexto implícito podem ir para `todas` ou para o domínio errado; a confiança exibida é uma proporção de palavras, não uma probabilidade calibrada. |
| Alta | O ChromaDB indexa somente Markdown e ignora falhas de consulta no contexto. | `chroma_memoria.py`, `_arquivos_markdown` e `contexto_relevante`. | Código `.py`, `.js`, `.tsx`, `.json` e outros documentos podem não entrar na memória; uma falha pode parecer simplesmente ausência de conhecimento. |
| Alta | O motor local é um Qwen 7B de CPU, com contexto e saída limitados para tarefas longas. | `config.json`: contexto 8192 e `max_tokens` 4096, mas `cerebro.py` reduz a saída para no máximo 1200 tokens; `modelos.py` registra baixa velocidade medida. | O modelo pode perder instruções, resumir demais ou parar antes de entregar código completo. |
| Alta | A ponte MCP descrita para o Claude não envia sessão nem chave de extensão. | `mcp_servidor.py`, função `chamar`, linhas 47–54; o servidor exige login por padrão. | A ponte pode falhar com `401` mesmo que a documentação diga que está pronta. |
| Alta | O `config.json` completo é devolvido em `/api/config`, incluindo campos sensíveis. | `cerebro.py`, rota `/api/config`; o objeto contém `github_token`, `login_social.client_secret` e `chave_extensao`. | Qualquer conta autenticada que consulte essa rota pode receber segredos ou a chave da extensão. |
| Alta | A agenda passa um aviso textual de “modo leitura”, mas a restrição efetiva depende do loop de ferramentas. | `agenda.py` e caminho `tarefa()`; não há uma política de ferramentas aplicada na própria agenda. | Uma evolução futura pode permitir escrita em execução programada sem que a regra fique garantida em um único lugar. |

## Achados médios

| Severidade | Achado | Impacto |
|---|---|---|
| Média | `buscar()` troca silenciosamente uma pasta não autorizada pela primeira pasta liberada. | O Bigode pode pesquisar em outro lugar e dar a impressão de que não encontrou o projeto solicitado. |
| Média | `rodar_comando()` também usa a pasta-base quando a pasta fornecida não é autorizada. | O comando pode rodar em um diretório diferente do que Frederico imaginou. |
| Média | A trava de evidência só é aplicada quando gatilhos textuais identificam uma pergunta factual ou sobre arquivos. | Sinônimos e pedidos implícitos podem escapar da verificação. |
| Média | O fluxo de navegação depende de polling de um segundo e de um mapa HTML de até 120 elementos visíveis. | Páginas dinâmicas, iframes, shadow DOM e elementos sem rótulo podem não ser operáveis. |
| Média | A extensão anexada contém `conteudo.js`, mas não contém todos os arquivos da extensão necessários para auditar o pacote completo, especialmente o fundo/ponte. | O conjunto recebido não é suficiente para provar que a extensão instalada no Windows é a mesma versão do núcleo. |
| Média | O instalador baixa Python embutido e tenta instalar ChromaDB, mas o Python embutido pode não vir com pip. | A instalação portátil pode parecer concluída, mas a memória semântica ficar indisponível. |

## O que está implementado de fato

| Área | Situação real |
|---|---|
| ChromaDB persistente | Implementado para coleções configuráveis, com indexação incremental por arquivo e busca por distância. Não cobre todos os tipos de arquivo e falhas de contexto ficam silenciosas. |
| Domínios | Implementados em configuração e na interface. O roteamento é por sobreposição de palavras, não por classificação semântica por embeddings. |
| Skills | Implementadas como manuais Markdown carregados no prompt. Não há validação profunda do conteúdo nem isolamento contra instruções maliciosas dentro dos manuais. |
| Ferramentas | Catálogo, schema OpenAI, filtro por conexão e execução implementados. Há 34 entradas no catálogo, mas a capacidade real varia conforme conexões e modelo. |
| Aprovação | Implementada para escrita do núcleo e ações sensíveis reconhecidas. A ponte MCP bloqueia escrita, enquanto a interface principal espera aprovação. |
| Chrome | Implementado como fila local + extensão que lê elementos HTML e executa ações. Não é controle multimodal completo do navegador e não cobre todas as tecnologias de páginas modernas. |
| Comunicação humanizada | Parcialmente implementada. Os textos de eventos foram humanizados, mas as regras de prompt ainda tinham conflito entre “ser humano” e “responder em duas ou três frases”; a tela antiga do pendrive pode continuar exibindo uma versão anterior. |
| Portabilidade | Implementada por scripts e caminhos Windows, mas o teste final com o Python e o Chrome instalados no `D:\Cerebro` não pode ser comprovado dentro do Linux. |

## Correções prioritárias aplicadas nesta rodada

1. Tornar o uso de ferramentas proporcional: conversa simples pode responder diretamente; fatos atuais, arquivos, código, leis, internet e dados reais exigem evidência.
2. Remover a obrigação de limitar toda resposta a duas ou três frases.
3. Manter a verificação de fatos e arquivos sem transformar cada saudação em uma tarefa técnica.
4. Preservar as regras de aprovação e a linguagem humana.

## Correções ainda necessárias antes de chamar o sistema de completo

1. Reduzir ou proteger os dados retornados por `/api/config`.
2. Corrigir a ponte MCP para autenticar de forma segura quando o login estiver ativado.
3. Fazer o ChromaDB indexar extensões de código e mostrar erros de consulta ao usuário.
4. Trocar o fallback silencioso de caminhos por uma negativa explícita.
5. Criar testes para perguntas ambíguas, falhas do motor, memória vazia, ação Chrome, autorização recusada, login e MCP.
6. Validar no Windows com o mesmo conjunto de arquivos e confirmar que o processo antigo não ficou rodando.

## Conclusão provisória

O Bigode possui uma base funcional, mas ainda não é correto afirmar que “faz qualquer coisa” ou que todas as capacidades estão completas. O problema de respostas que não correspondem ao pedido é explicado principalmente por: modelo local pequeno, prompt excessivamente prescritivo, roteamento baseado em palavras, memória limitada a Markdown, corte de contexto/saída e caminhos alternativos pouco testados. A correção de prompt melhora a fluidez; as correções de memória, autenticação, MCP e testes são necessárias para aumentar a precisão operacional.
