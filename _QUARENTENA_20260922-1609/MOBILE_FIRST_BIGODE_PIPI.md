# Mobile-first — Bigode IA e Pipi IA

O HTML principal foi ajustado para priorizar celulares sem retirar a experiência desktop. O layout usa altura dinâmica `100dvh`, áreas compatíveis com teclado virtual, safe areas de iPhone, rolagem nativa, alvos de toque maiores e composição sem zoom automático em campos.

## Bigode IA

No celular, a barra lateral vira um menu deslizante acionado pelo botão no topo. O cabeçalho mantém o nome da conversa e o estado do motor. O compositor fica fixado na parte inferior com controles de toque de 44px, campo de texto com fonte de 16px para evitar zoom no iOS e chips de conexão roláveis horizontalmente.

Mensagens, tabelas e blocos de código podem rolar horizontalmente quando necessário. O menu de ações abre acima do teclado e ocupa a largura disponível, evitando controles pequenos ou fora da tela.

## Pipi IA

A Pipi permanece uma tela cheia, não uma janelinha lateral. No celular, a gata fica centralizada, solta e com proporção preservada; o formulário passa a uma única coluna, os campos têm altura confortável, o guia de três passos se empilha e o botão **Criar imagem** ocupa toda a largura.

A rolagem respeita a área segura do aparelho e o resultado da imagem se adapta à largura da tela. A identidade rosa, magenta e neon permanece separada da identidade verde do Bigode.

## Validação

A interface foi validada com o verificador de HTML/JavaScript do projeto e renderizada em viewport de 390×844 pixels. A versão desktop continua coberta pelas regras existentes acima do breakpoint móvel.
