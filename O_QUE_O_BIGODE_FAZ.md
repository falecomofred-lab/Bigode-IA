# O que o Bigode IA faz hoje

## Em uma frase

O Bigode é um assistente local que conversa com você, consulta os arquivos autorizados do pendrive, pesquisa informações, entende projetos de software e pode comandar uma aba do Chrome por meio de uma extensão. Ele não deve tomar decisões importantes sozinho: a ideia é trabalhar como um parceiro que prepara, mostra e espera a sua confirmação quando há risco.

## O que significa “34 ferramentas ativas”

Essa mensagem não quer dizer que 34 programas estão trabalhando ao mesmo tempo. Ela significa que o Bigode tem 34 capacidades disponíveis para usar quando forem necessárias. Algumas ficam ligadas apenas se a conexão correspondente estiver ativa, como GitHub, internet, arquivos, terminal e navegador.

| Área | Capacidades disponíveis | Em palavras simples |
|---|---|---|
| Conversa e organização | `usar_habilidade`, `apresentar_plano`, `criar_projeto`, `buscar_no_chroma` | Carrega um manual especializado, apresenta como pretende trabalhar, cria a estrutura inicial de um projeto e procura informações relacionadas na memória semântica. |
| Arquivos e projetos | `listar_pasta`, `ler_arquivo`, `buscar`, `raio_x`, `memoria` | Vê quais arquivos existem, lê arquivos, procura palavras dentro deles, faz um inventário real do projeto e recupera o que já foi salvo sobre trabalhos anteriores. |
| Internet | `web_buscar`, `web_ler` | Pesquisa na internet e lê o conteúdo de uma página. Isso é diferente de controlar o Chrome: aqui o Bigode consulta a web diretamente, sem abrir uma aba visível para você. |
| GitHub | `github_repos`, `github_ler`, `github_criar_repo`, `github_commit`, `github_issue` | Consulta seus repositórios, lê arquivos, cria repositórios, envia alterações e abre issues. As ações que alteram ou publicam algo precisam de confirmação. |
| Navegador Chrome | `navegador_ver`, `navegador_ir`, `navegador_clicar`, `navegador_escrever`, `navegador_teclar`, `navegador_rolar`, `navegador_esperar` | Enxerga a página aberta, abre endereços, clica, preenche campos, aperta teclas, rola a página e espera carregamentos. A extensão é quem executa essas ações no Chrome. |
| Informações úteis | `agora`, `clima`, `cep`, `cnpj`, `feriados`, `cotacao` | Consulta data e hora, previsão do tempo, endereço por CEP, dados de empresa, feriados nacionais e câmbio. |
| Arquivos que podem ser alterados | `escrever_arquivo`, `criar_pasta`, `mover`, `apagar` | Cria ou altera arquivos, cria pastas, move itens e apaga conteúdo. Essas operações são protegidas e não devem acontecer sem a sua aprovação. |
| Terminal e automações de projeto | `rodar_comando` | Executa um comando na pasta autorizada, por exemplo instalar dependências, rodar testes ou gerar uma versão do projeto. Também exige aprovação. |

## Por que o Bigode ainda não é exatamente igual à extensão do Claude

A extensão atual já possui a base necessária, mas trabalha de forma mais controlada e simples. O Bigode envia uma ação para uma fila local; a extensão consulta essa fila, executa a ação na aba ativa e devolve o resultado. Esse mecanismo é seguro e portátil, mas não é o mesmo sistema de navegação visual e multimodal usado por produtos comerciais mais avançados.

Hoje o Bigode consegue observar o texto visível e uma lista numerada de elementos — links, botões, campos, abas e menus. Por isso, ele precisa transformar a página em algo como “item 3 é o botão Entrar”. Ele não compreende cada detalhe visual da tela da mesma maneira que uma pessoa olha para uma página inteira. Quando a página é dinâmica, protegida ou muda depois de um clique, pode ser necessário olhar novamente.

A extensão também não controla páginas internas do Chrome, como `chrome://extensions`, e não deve ultrapassar telas de login, pagamento, publicação, envio, exclusão ou aprovação sem a sua confirmação. Essa limitação é intencional: ela protege você contra uma ação errada.

## O que foi melhorado agora

Depois de uma ação, a extensão devolve uma nova visão da página para o Bigode. Assim, ele não precisa continuar usando uma lista antiga depois de clicar ou rolar. Se ele tentar agir sem ter uma visão recente, a extensão atualiza a leitura antes de tocar no elemento.

Campos de senha, login, e-mail, CPF, cartão e token passam a ser tratados como sensíveis. Abertura de endereços relacionados a login, checkout, pagamento ou administração também passou a exigir confirmação. Teclas como Enter e Tab são protegidas porque podem enviar, confirmar ou avançar um formulário.

A conversa deixou de mostrar nomes internos como “Qwen 7B”, “roteado para cannabis” e “34 ferramentas à disposição” como se fossem informações importantes para você. A interface agora usa frases como “Entendi o que você precisa”, “Escolhendo o melhor jeito de ajudar”, “Recursos prontos para ajudar” e “Pensando na melhor resposta”.

## Como deve ser o uso ideal

Você pode escrever: “Abra uma aba, pesquise sobre cannabis e me mostre o que encontrou”. O Bigode deve abrir ou usar a aba, pesquisar, ler o resultado e conversar com você sobre o que encontrou.

Você pode também escrever: “Entre no painel do cliente, mas pare antes do login”. O Bigode deve navegar até a página e parar. Se precisar preencher uma senha, enviar um formulário, publicar, comprar, apagar ou confirmar, ele deve mostrar o que pretende fazer, apresentar as alternativas e esperar sua autorização.

> O navegador não deve ser um piloto automático. Ele deve ser um braço do Bigode sob o seu comando.

## O que ainda depende da configuração local

Para o controle do Chrome funcionar, a extensão precisa estar carregada em `chrome://extensions`, o Chrome precisa estar aberto, o painel da extensão precisa ter o endereço `http://localhost:7000` e a extensão precisa estar conectada com a mesma conta do Bigode. Sem essa ponte, o Bigode pode pesquisar diretamente pela internet, mas não consegue clicar ou preencher a aba real do seu navegador.

O projeto continua local e portátil. O código do Bigode, a memória e a extensão podem ficar no pendrive. O Chrome, por segurança, precisa ser instalado e a extensão carregada em cada computador que você usar.
