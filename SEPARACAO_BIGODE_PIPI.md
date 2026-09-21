# Separação Bigode IA e Pipi IA

## Bigode IA

O HTML principal do Bigode foi limpo da interface Pipi e do painel legado de criação de imagens. A experiência principal permanece dedicada a conversa, dados, arquivos, tarefas, programação, MCP, GitHub, navegador, skills e memória.

As rotas de imagem ainda podem existir no backend por compatibilidade de scripts antigos, mas não são mais carregadas pela interface do Bigode. A geração de imagem deve ser iniciada pela aplicação Pipi.

## Pipi IA

A Pipi possui interface, servidor, catálogo de motores, pasta de modelos e pasta de produção próprios. Ela roda em `http://127.0.0.1:7300` e não precisa iniciar o processo do Bigode para abrir sua interface, consultar saúde, listar motores e preparar jobs.

A geração real depende de ComfyUI e de um workflow configurado. O servidor não cria respostas falsas quando o motor está ausente: informa claramente a pendência. Essa separação preserva VRAM e reduz o acoplamento do Bigode com modelos de difusão.

## Motores iniciais

O catálogo contém FLUX.1 Schnell, Stable Diffusion XL Base 1.0 e SDXL Refiner 1.0, com links oficiais, licenças, arquivos esperados e observações de VRAM em `PPIA/motores.json`.

## Validação

Foram validados: sintaxe Python do Bigode e da Pipi, JSON dos catálogos, JavaScript embutido do Bigode, inexistência dos marcadores da Pipi no HTML principal, servidor HTTP da Pipi e endpoint `/api/health` independente.
