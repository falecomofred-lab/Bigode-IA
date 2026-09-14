# Project TODO — Arquitetura V2

- [x] Substituir o índice do Obsidian por ingestão persistente no ChromaDB
- [x] Adicionar coleções `codigo`, `seguros` e `cannabis`
- [x] Implementar busca semântica por coleção e roteador de domínio
- [x] Integrar contexto ChromaDB ao system prompt do Cerebro
- [x] Preservar `tool_choice: required`
- [x] Adicionar aprovação humana para ações críticas da extensão
- [x] Validar ingestão, busca, roteamento, sintaxe e auditoria
- [x] Preparar pacote final de alterações sem segredos
- [x] Preservar a grafia oficial Venure e o rodapé `venure.com.br` em todos os templates

## Evolução produto — parceiro de desenvolvimento e automação

- [ ] Definir backlog priorizado de skills para programação e atendimento de clientes
- [x] Auditar o registro atual de skills e o catálogo de ferramentas
- [x] Criar skills prontas para briefing, site, aplicativo, suporte a profissionais liberais
- [ ] Fortalecer navegação, preenchimento e confirmação de ações críticas no Chrome
- [ ] Integrar fluxo de briefing com geração e acompanhamento de projetos
- [ ] Validar segurança, testes e compatibilidade sem quebrar o funcionamento atual

## Evolução portátil e controle do Frederico

- [ ] Documentar execução local a partir do pendrive em outros computadores
- [x] Criar skills iniciais: transcrição, briefing de cliente, criar site, criar aplicativo, editar projeto, pesquisa e revisão antes de publicar
- [ ] Garantir que toda ação sensível exija aprovação explícita do Frederico
- [ ] Exibir alternativas e permitir que o Frederico altere o rumo antes da execução
- [ ] Validar carregamento manual da extensão Chrome e continuidade das sessões locais

## Comunicação humanizada

- [x] Auditar copies, status e mensagens repetitivas do chat e da extensão
- [x] Definir uma voz calma, clara, colaborativa e transparente
- [x] Remover pedidos robóticos, P.S. repetidos e explicações desnecessárias
- [x] Ajustar mensagens de aprovação, erro, progresso e conclusão
- [x] Validar que a nova voz preserve evidências, limites e aprovação do Frederico

## Correção do fluxo de pesquisa

- [x] Localizar todas as cópias do texto antigo de palavras-chave e emoji
- [x] Corrigir o fallback para consultas curtas como “pesquisar sobre cannabis”
- [x] Garantir execução de `web_buscar` sem pedir informação já fornecida
- [x] Validar o fluxo no Python portátil usado pelo `BIGODE.bat`

## Navegador e comunicação para Frederico

- [x] Documentar em linguagem simples o que as 34 ferramentas fazem
- [x] Mapear por que a extensão ainda não acompanha a navegação como esperado
- [x] Fazer o Bigode ler a página antes de clicar ou preencher
- [x] Fazer o Bigode navegar, preencher e devolver o resultado pela extensão
- [x] Exigir aprovação do Frederico em toda ação sensível e mostrar alternativas
- [x] Humanizar os status da interface para não expor termos técnicos desnecessários
- [ ] Validar o fluxo portátil no `D:\Cerebro`

## Auditoria minuciosa de precisão e execução

- [x] Inventariar os arquivos enviados e identificar versões desencontradas
- [x] Auditar o caminho completo da pergunta até a resposta final
- [x] Auditar ferramentas, memória ChromaDB, roteador e loop de execução
- [x] Auditar motor local, parâmetros, contexto, latência e qualidade
- [x] Auditar segurança, prompt injection, terminal, autorizações e Chrome
- [x] Executar testes estáticos e determinísticos adicionais
- [x] Corrigir problemas de alto impacto encontrados na auditoria
- [x] Produzir relatório final com fatos, limitações e prioridades
