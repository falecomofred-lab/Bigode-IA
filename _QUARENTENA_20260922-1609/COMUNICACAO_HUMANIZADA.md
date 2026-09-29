# Atualização de comunicação do Bigode IA

## Objetivo

Esta atualização aproxima a conversa do Bigode de um assistente de trabalho calmo, claro, colaborativo e transparente. A inspiração é comportamental: respostas proporcionais, explicações naturais, honestidade sobre limites e respeito ao ritmo do usuário. Não é uma cópia literal de identidade ou textos de outro produto.

## Arquivos alterados

`memoria/temperamento.md` recebeu a voz conversacional, regras contra bordões, P.S. repetidos, pedidos desnecessários e simulação de progresso. As regras de evidência, fontes, leitura de arquivos e aprovação do Frederico foram preservadas.

`cerebro.py` recebeu mensagens de progresso mais naturais e uma limpeza conservadora das respostas finais. Ela remove linhas repetidas de P.S. e convites genéricos sem apagar conteúdo técnico normal. A extensão recebeu mensagens mais claras para login, conexão, navegação e erros em `extensao-chrome/painel.js` e `extensao-chrome/fundo.js`.

## Validação

Foram executados `python3 -m py_compile`, quatro testes determinísticos de comunicação e ChromaDB, e `node --check` nos três arquivos JavaScript da extensão. O resultado foi aprovado.

## Aplicação no pendrive

Copie os arquivos deste pacote para a pasta correspondente em `D:\Cerebro`, mantendo a estrutura de diretórios. Feche o Bigode antes de substituir os arquivos e abra novamente o `BIGODE.bat` depois da cópia. A extensão do Chrome também precisa ser recarregada em `chrome://extensions` usando o botão de recarregar da extensão.
