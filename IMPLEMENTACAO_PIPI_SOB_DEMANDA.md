# Implementação Bigode IA + Pipi IA

## Escopo entregue

O HTML principal do Bigode foi preservado como a casa da aplicação. Foi acrescentado um espaço separado chamado **Pipi IA**, acessível pela barra lateral e pelo painel de configurações. O novo espaço usa quatro famílias de rosa — rosa claro, rosa principal, magenta e neon — sem remover a identidade escura, verde e técnica do Bigode. A gata enviada foi publicada como ativo da interface em `web/img/pipi_gata.jpeg`.

A Pipi permite escolher o motor de imagem detectado, informar prompt positivo e negativo, definir formato, quantidade de passos, guidance e semente. A ação é feita pelo caminho direto `/api/imagens/gerar`, sem passar pelo modelo de texto. Isso reduz latência e evita que um modelo pequeno precise interpretar uma intenção que já está explícita na tela.

As imagens agora são gravadas, por padrão, em `Pipi IA/produção` dentro da primeira pasta liberada. A tela também aceita a pasta do projeto ativo. O backend só aceita esse destino se ele estiver dentro de uma pasta liberada; caso contrário, cai na pasta interna do aplicativo. Isso evita que um campo de interface vire um caminho arbitrário para escrita.

## Arquivos principais alterados

| Arquivo | Alteração |
| --- | --- |
| `web/index.html` | Painel Pipi, paleta rosa, gata no topo, seleção de engine, controles de geração, estado de carregamento e play visual. |
| `web/img/pipi_gata.jpeg` | Ativo visual fornecido pelo usuário. |
| `imagens.py` | Seleção de motor, prompt negativo, passos, guidance, semente e destino por projeto. |
| `ferramentas.py` | A ferramenta `gerar_imagem` aceita as novas opções também quando acionada pelo Bigode. |
| `cerebro.py` | `/api/imagens` expõe componentes e `/api/imagens/gerar` recebe as opções completas. |
| `modelos.py` | Desligamento prioriza o processo aberto pelo próprio provedor, reduzindo o risco de matar outro runtime no Colab. |
| `Bigode_Colab_Pipi_IA.ipynb` | Notebook novo e limpo com células separadas para Drive, dependências, cópia local, motor de texto, Pipi/ComfyUI e diagnóstico. |

## Operação sob demanda

O Bigode já mantém a regra de não iniciar um modelo de texto automaticamente. A implementação preserva essa decisão. O usuário liga o modelo escolhido pelo painel e aguarda o estado de carregamento antes de conversar. A Pipi segue o mesmo princípio: o backend não sobe ComfyUI sozinho no acesso à tela; a célula de imagem do Colab deve ser executada quando o usuário quiser desenhar.

No notebook, o modelo é copiado do Drive para o disco local da sessão antes do uso. Isso é importante para velocidade: os arquivos GGUF não devem ser lidos repetidamente através do Drive montado. Texto e imagem são processos separados, e o notebook recomenda manter apenas um deles ocupando a VRAM quando a T4 estiver no limite.

## Check-up de endpoints e conexões

Foi feita uma verificação estática das chamadas do HTML contra as rotas do servidor. As chamadas encontradas para chat, modelo, configuração, projetos, conversas, conexões, Drive local, ChromaDB, imagem, voz, navegador e autorização possuem correspondência no servidor. A chamada direta de imagem `/api/imagens/gerar` também está registrada no POST e recebe as opções da Pipi.

O painel principal já permite ligar e desligar sob demanda o conjunto de ferramentas do Google Drive montado, GitHub, navegador, terminal, web e dados. O token de GitHub e os tokens de conexões são preservados no arquivo local e nunca são devolvidos ao navegador em texto puro. Foi acrescentado um atalho **Cloud via MCP** no catálogo visual para cadastrar endpoint ou comando pelo mesmo formulário.

Há uma distinção importante para o desenvolvedor: o código atual **configura e liga/desliga a conexão MCP no catálogo**, mas não implementa ainda um cliente MCP genérico para importar dinamicamente as ferramentas de qualquer endpoint cloud. A ponte existente é o `mcp_servidor.py`, que expõe o Bigode para clientes MCP como Claude. Para que “Cloud via MCP” execute ferramentas externas dentro do chat do Bigode, será necessário adicionar um runtime MCP client (transporte stdio/HTTP, descoberta `tools/list`, chamada `tools/call`, timeouts, armazenamento de sessão e filtragem por conexão). O painel agora deixa essa intenção configurada sem afirmar falsamente que o endpoint externo já está sendo executado.

## Colab

Não havia um arquivo `.ipynb` versionado no diretório do projeto no momento da auditoria. Por isso foi criado `Bigode_Colab_Pipi_IA.ipynb`, em vez de afirmar que células antigas foram editadas. Ele contém nove células, com função única e comentários sobre o que cada uma faz. O notebook usa variáveis editáveis (`TEXT_MODEL_FILE`, portas e caminhos) e grava logs separados em `/content/llama.log` e `/content/comfyui.log`.

Os dois GGUF de imagem ainda precisam estar na pasta `projetos/Cerebro/IA Imagem` do Google Drive para aparecerem no seletor. O inventário local disponível durante esta implementação não continha esses dois GGUF; o arquivo `DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf` encontrado é de texto e não foi tratado como modelo de imagem.

## Validação

A validação executada confirmou que `imagens.py`, `ferramentas.py`, `cerebro.py` e `modelos.py` compilam, que o notebook é JSON válido, que o painel contém a rota de geração e que o ativo da gata existe. Os testes pytest existentes não foram executados porque `pytest` não está instalado no ambiente atual; isso deve ser feito no ambiente de desenvolvimento antes do merge.

## Próximos passos do desenvolvedor

Primeiro, coloque os GGUF corretos na pasta de imagem e confirme os nomes de `imagem_unet` e `imagem_t5` no `config.json` quando a detecção automática não for suficiente. Em seguida, confirme no ComfyUI se os nós `UnetLoaderGGUF` e `DualCLIPLoaderGGUF` correspondem à versão instalada do custom node. Por fim, execute os testes do projeto e faça um teste manual de ponta a ponta: abrir Pipi, ligar o desenhista, gerar uma imagem com semente fixa e conferir o arquivo dentro de `Pipi IA/produção` no projeto ativo.

A interface atual não inventa uma integração automática com Google Drive API. Ela grava na pasta do Drive montada pelo Colab/Windows, que é a solução de menor latência e menor superfície de credenciais para a arquitetura atual. Uma integração Drive API pura pode ser adicionada depois, mas deve ser avaliada contra o custo de upload, autenticação e latência por geração.

**Venure — venure.com.br**
