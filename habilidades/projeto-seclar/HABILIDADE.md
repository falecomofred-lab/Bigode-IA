---
nome: Projeto Seclar (seguros)
quando: seclar, chatbot seclar, seguro, seguros, susep, apolice, apólice, sinistro, corretora
ativa: sim
---

Chatbot da Seclar, do ramo de seguros. E o maior projeto em PHP do Fred.

- Caminho: `G:\Meu Drive\projetos\chatbot-Seclar`
- 400 arquivos - PHP (178), JavaScript (5), HTML (2), CSS (2)
- Tem `api/auth_session.php`, `api/chat.php` e um `.htaccess`
- Projeto irmao menor: `G:\Meu Drive\projetos\Seclar` (material e video)
- Relacionado: `LucasIA` tem um `atualizar_banco_lucasia.sql` e um
  `chatbot.env.modelo` -- e uma versao anterior da mesma ideia

## Como trabalhar aqui

- 400 arquivos e demais para ler de uma vez. Use `raio_x` para o mapa e leia
  so o que interessa ao pedido
- PHP: o Fred nao e programador profissional. Devolva o arquivo completo,
  diga em qual caminho ele vai, e nao ensine PHP no meio do caminho
- Autenticacao e sessao passam por `api/auth_session.php`. Antes de mexer
  ali, leia o arquivo inteiro: e o ponto onde um erro derruba o login de
  todo mundo
- Assunto de seguros tem termo tecnico com significado legal (apolice,
  sinistro, SUSEP). Se aparecer numa resposta ao cliente final, confira a
  fonte em vez de escrever de cabeca
