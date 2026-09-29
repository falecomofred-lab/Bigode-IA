# Achados iniciais da auditoria do Bigode IA

## Evidências confirmadas

1. Os testes existentes passam: 5 testes aprovados, compilação Python aprovada e os arquivos JavaScript anexados compilam por sintaxe.
2. O catálogo atual contém 34 ferramentas, embora alguns documentos antigos ainda falem em 33.
3. O código anexado `cerebro.py` e `ferramentas.py` coincide com a versão de trabalho, mas `index.html` e `conteudo.js` anexados podem estar em versões diferentes da versão de trabalho mais recente. Isso explica por que uma alteração pode aparecer no ambiente de desenvolvimento e não aparecer no pendrive.
4. O modelo local não é o Bigode: o Bigode é o orquestrador e depende da capacidade do modelo escolhido para escolher ferramentas, interpretar resultados e redigir respostas. O código usa `temperature`, `max_tokens`, `tool_choice`, `top_p`, penalidades e `cache_prompt`.
5. A primeira chamada permite `tool_choice=auto`; apenas quando o pedido é classificado como exigindo fonte/arquivo e o modelo responde de cabeça, o código descarta a resposta, mostra um aviso e força ferramenta na próxima rodada. Portanto, a precisão depende parcialmente da classificação por gatilhos e ainda pode custar uma rodada extra.
6. O limite de passos é configurável e pode chegar a 8; há detecção de repetição da mesma chamada, mas o laço ainda pode fazer várias chamadas ao modelo antes de parar.
7. O navegador é uma ponte separada: o servidor coloca ações numa fila e a extensão consulta a fila. A extensão não é o mesmo que um navegador visual multimodal; ela lê texto visível e elementos HTML numerados.
8. O servidor escuta em `0.0.0.0` quando `acesso_rede` está ativo, permitindo acesso pela rede local. Isso precisa ser revisado junto com autenticação, CORS e exposição de tokens.
9. `requirements.txt` lista apenas ChromaDB, enquanto `psutil` é usado pelos scripts de auditoria de motor, mas como import opcional. A funcionalidade principal pode funcionar sem ele; os números de RAM não ficam completos.
10. A auditoria anterior nos documentos reconhece um problema de precisão do modelo local e um laço de ferramentas histórico; portanto, não é correto prometer que o Bigode “consegue fazer qualquer coisa” sem limites. O objetivo precisa ser maximizar execução segura e declarar limites.

## Fontes locais examinadas

- `cerebro.py`
- `ferramentas.py`
- `modelos.py`
- `chroma_memoria.py`
- `roteador_semantico.py`
- `conteudo.js`
- `README.md`
- `LEIAME.md`
- `CHECKPOINT.md`
- `AUDITORIA-MOTOR.md`
- `AUDITORIA_MANUS.md`

Este arquivo é intermediário; o relatório final deve reescrever os achados com classificação de severidade, evidência e plano de correção.
