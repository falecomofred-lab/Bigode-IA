# Como iniciar o Bigode IA e a Pipi IA

## Regra principal

O **Bigode IA** executa modelos de texto, dados e programação através do `llamafile/llama.cpp`. A **Pipi IA** executa geração e edição de imagens através do ComfyUI. Apesar de ambos os modelos poderem usar a extensão `.gguf`, são famílias diferentes e não devem ser misturados.

## Bigode IA

1. Confirme que o modelo textual GGUF está no Pen IA. O inicializador usa por padrão `qwen3-14b-Q4_K_M.gguf` quando ele existe; para trocar, defina `BIGODE_MODELO` antes de executar o BAT.
2. Dê duplo clique em `bigode.bat` dentro da pasta do Bigode. Ele localiza o `llamafile-0.10.3.exe.exe`, inicia o motor textual na porta 8082, aguarda a porta responder e só então abre `cerebro.py`.
3. Abra a interface em `http://127.0.0.1:7000` se ela não abrir automaticamente.
4. Para trocar o modelo numa sessão PowerShell: `$env:BIGODE_MODELO='G:\Outros computadores\USB e dispositivos externos\Pen IA\qwen2.5-coder-7b-instruct-q4_k_m.gguf'; .\bigode.bat`.
5. O log do motor fica em `motor.log`. O endpoint público de saúde é `/health`; `/api/health` mostra texto, imagem, runtime e conexões.

## Pipi IA

1. O ComfyUI deve estar instalado em `G:\Outros computadores\USB e dispositivos externos\Pen IA\ComfyUI`.
2. O workflow precisa estar em `workflow.json` na pasta da Pipi.
3. Os modelos de imagem devem ser instalados conforme o workflow. Para FLUX GGUF, use `ComfyUI-GGUF`, coloque `flux1-dev-Q5_1.gguf` em `ComfyUI\models\unet` e instale os componentes T5, CLIP e VAE correspondentes.
4. Dê duplo clique em `pipi.bat`. Ele verifica o workflow, localiza a pasta de modelos, inicia o ComfyUI na porta 8188 e depois inicia a Pipi na porta 7300.
5. Abra `http://127.0.0.1:7300`.
6. O log do ComfyUI fica em `comfyui.log`. Os jobs da Pipi podem ser consultados em `/api/logs`.

## Endpoints de diagnóstico

| Projeto | Endpoint | Função |
|---|---|---|
| Bigode | `GET /health` | Saúde mínima sem autenticação |
| Bigode | `GET /api/health` | Runtime, motores e conexões |
| Bigode | `GET /api/status` | Status da sessão/interface |
| Bigode | `GET /api/modelos` | Catálogo de modelos textuais |
| Pipi | `GET /api/health` | ComfyUI, Hugging Face e pasta de modelos |
| Pipi | `GET /api/imagens` | Catálogo de motores e arquivos |
| Pipi | `POST /api/imagens/job` | Cria um job de imagem |
| Pipi | `GET /api/imagens/job/<id>` | Acompanha o job |
| Pipi | `GET /api/logs` | Jobs e diagnóstico recente |

## Se algo falhar

- Bigode sem motor: confirme o caminho do `llamafile` e o valor de `BIGODE_MODELO`.
- Pipi sem ComfyUI: confirme a pasta `ComfyUI`, o Python e a porta 8188.
- Workflow ausente: coloque o arquivo `workflow.json` na raiz da Pipi.
- `UnetLoaderGGUF` ausente: instale o custom node `ComfyUI-GGUF` e reinicie o ComfyUI.
- CUDA indisponível: o ComfyUI pode ser iniciado com `--cpu`, mas a geração será lenta; para velocidade, use uma GPU remota no Modal.

## Limite conhecido

A instalação atual do Modal anteriormente criada é um endpoint de teste e não deve ser considerada gerador real até que um modelo seja instalado no container e os pesos sejam carregados por Volume. O Bigode e a Pipi locais não baixam modelos grandes automaticamente.
