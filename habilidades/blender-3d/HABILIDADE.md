---
nome: Blender 3D
quando: blender, 3d, modelar, modelagem, cena 3d, personagem 3d, mascote, objeto 3d, animacao 3d, render
ativa: sim
---

Você cria projetos 3D no Blender do Frederico. O Blender precisa estar aberto com o add-on MCP (porta 9876).

## Qual ferramenta usar

1. **blender_cena**: leia a cena ANTES de mexer. Mostra coleções e objetos.
2. **blender_carrinho(cor)**: SÓ para carro/carrinho.
3. **blender_mascote(texto, cor, animar, pose, magro)**: macaco cartoon de corpo inteiro.
   - pose "meditando" = sentado de pernas cruzadas, polegares para cima, flutuando.
   - texto vai na camisa (ex.: Projetosoul.com.br).
4. **blender_objeto(forma, cor, animacao)**: uma forma só (macaco, cubo, esfera, cilindro, cone, rosca).
5. **blender_montar(pecas, projeto, animar)**: QUALQUER outra coisa. Descreva as peças em JSON. Não escreva Python.
6. **blender_imagem(nome)**: salva PNG da câmera.
7. **blender_olhar(pergunta)**: OLHA a cena (tira imagem e usa a visão). Use depois de montar, para conferir, e antes de continuar um projeto existente.
8. **blender_referencia(projeto)**: monta a última imagem que o Fred colou (foto de produto, desenho, print). A visão já transformou a imagem em peças.
9. **blender_biblioteca(busca, tipo, objeto)**: PRIMEIRA opção para objetos comuns. Busca na Poly Haven (grátis, CC0): tipo "modelo" (cadeira, planta, pedra, barril...), "hdri" (céu e luz de ambiente) ou "textura" (madeira, tijolo, metal... aplicada no objeto).
10. **blender_importar(caminho, altura)**: importa .glb .gltf .obj .fbx .stl .ply .svg. SVG vira placa com volume (logo, contorno).
11. **blender_referencias(frente, lado, topo, altura)**: coloca imagens como fundo para acertar proporções.
12. **blender_textura(caminho, objeto)**: aplica PNG/JPG (rótulo, estampa) num objeto.
13. **blender_gerar_3d(caminho, altura)**: foto → modelo 3D de verdade (TRELLIS.2). Use quando pedirem "idêntico", "realista", "fiel". Leva 1 a 3 min.
14. **blender_humano(ficha)**: PESSOA realista (MPFB/MakeHuman) a partir de ficha JSON: sexo, idade, etnia, rosto, cabelo, roupa. Ficha sem sexo/idade ajusta a pessoa anterior. Se o MPFB não estiver instalado, use antes **blender_instalar_humano** (uma vez, ~310 MB).
15. **blender_salvar(nome)**: salva .blend de verdade. Nunca use escrever_arquivo para .blend.
16. **blender_executar(codigo)**: último recurso. Só se nada acima resolver.

Ordem de preferência para criar algo: biblioteca (objeto comum) → gerar_3d (tem foto e quer fiel) → montar (forma simples/estilizada) → executar.

Nunca diga que fez algo sem ter chamado a ferramenta e lido o resultado.

## Como pensar em blender_montar

Quebre o objeto em formas simples. Coordenadas em metros:
- **Z é para cima.** O chão é z = 0.
- **A frente é -Y.** Rosto, texto e olhos ficam com y negativo.
- **X é a largura.** Esquerda do personagem = +X.
- `pos` é o CENTRO da peça. Uma esfera de escala [1,1,1] tem 1 metro de diâmetro.
- Para apoiar no chão: pos z = metade da altura.
- `membro` liga dois pontos: braços, pernas, pés de mesa, galhos. Use `de`, `ate`, `raio`.
- `texto` fica de pé olhando para -Y por padrão (rot [90,0,0]).
- Cores: vermelho, azul, verde, amarelo, laranja, preto, branco, prata, roxo, rosa, marrom, cinza, bege, pele, dourado, ciano. Ou [r,g,b] de 0 a 1.
- Repetir o mesmo `projeto` apaga e recria. Use isso para corrigir.

## Exemplo 1: boneco de neve

```json
[
 {"tipo":"esfera","nome":"base","pos":[0,0,0.6],"escala":[1.2,1.2,1.2],"cor":"branco"},
 {"tipo":"esfera","nome":"meio","pos":[0,0,1.5],"escala":[0.85,0.85,0.85],"cor":"branco"},
 {"tipo":"esfera","nome":"cabeca","pos":[0,0,2.2],"escala":[0.6,0.6,0.6],"cor":"branco"},
 {"tipo":"cone","nome":"nariz","pos":[0,-0.38,2.2],"escala":[0.1,0.1,0.35],"rot":[90,0,0],"cor":"laranja"},
 {"tipo":"esfera","nome":"olho_e","pos":[0.12,-0.27,2.3],"escala":[0.07,0.07,0.07],"cor":"preto"},
 {"tipo":"esfera","nome":"olho_d","pos":[-0.12,-0.27,2.3],"escala":[0.07,0.07,0.07],"cor":"preto"},
 {"tipo":"membro","nome":"braco_e","de":[0.4,0,1.6],"ate":[1.1,0,2.0],"raio":0.04,"cor":"marrom"},
 {"tipo":"membro","nome":"braco_d","de":[-0.4,0,1.6],"ate":[-1.1,0,2.0],"raio":0.04,"cor":"marrom"}
]
```
Chamada: blender_montar(pecas=<lista acima>, projeto="Boneco de neve", animar="")

## Exemplo 2: mesa com placa

```json
[
 {"tipo":"cubo","nome":"tampo","pos":[0,0,0.75],"escala":[1.6,0.9,0.06],"cor":"marrom"},
 {"tipo":"membro","nome":"pe1","de":[0.7,0.35,0],"ate":[0.7,0.35,0.72],"raio":0.04,"cor":"preto"},
 {"tipo":"membro","nome":"pe2","de":[-0.7,0.35,0],"ate":[-0.7,0.35,0.72],"raio":0.04,"cor":"preto"},
 {"tipo":"membro","nome":"pe3","de":[0.7,-0.35,0],"ate":[0.7,-0.35,0.72],"raio":0.04,"cor":"preto"},
 {"tipo":"membro","nome":"pe4","de":[-0.7,-0.35,0],"ate":[-0.7,-0.35,0.72],"raio":0.04,"cor":"preto"},
 {"tipo":"texto","nome":"placa","texto":"Venure","pos":[0,-0.46,0.6],"tamanho":0.15,"cor":"dourado"}
]
```

## Imagem para Blender

O Fred cola a imagem (Ctrl+V) com um texto que cita Blender ou 3D. A visão transforma a imagem em peças e a caixa recebe "Monte no blender a referencia da imagem: ...". Ao enviar, o Bigode monta direto.
Para ajustar depois: blender_olhar para ver como ficou, depois blender_montar com o MESMO projeto e as peças corrigidas.

## Fluxo

1. blender_cena para saber o que existe.
2. Para projeto novo e pedido vago, pense nas peças e monte de uma vez. Não peça aprovação para criar em coleção nova: nada existente é apagado.
3. Chame blender_olhar para conferir o resultado com os próprios olhos.
4. Leia o resultado. Se vier "Problemas", corrija só essas peças e chame de novo com o mesmo projeto.
5. Termine dizendo o que foi criado e lembrando: Ctrl+S no Blender para salvar.
