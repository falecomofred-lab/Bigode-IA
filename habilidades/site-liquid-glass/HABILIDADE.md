---
nome: Site com efeito Liquid Glass
quando: liquid glass, vidro liquido, vidro fosco, glassmorphism, efeito de vidro, frosted glass, apple glass, transparencia desfocada
ativa: sim
---

Você cria interfaces com efeito de VIDRO LÍQUIDO (liquid glass): painéis translúcidos que
desfocam e "dobram" o que está atrás, com brilho na borda. Entregue sempre HTML + style.css
completos, prontos para colar, sem frameworks.

## As 4 camadas do efeito (use nesta ordem)

1. **Fundo com conteúdo** atrás do vidro (foto, gradiente, formas coloridas). Vidro sobre fundo liso não aparece.
2. **Desfoque + saturação**: `backdrop-filter: blur(14px) saturate(160%)` (com `-webkit-` para Safari).
3. **Brilho de borda**: `border: 1px solid rgba(255,255,255,.35)` + `box-shadow: inset 0 1px 0 rgba(255,255,255,.5)`.
4. **Refração (o "líquido")**: filtro SVG `feDisplacementMap` aplicado ao fundo do painel. Funciona no Chrome/Edge;
   no Safari e Firefox cai para o vidro fosco normal — ESSE fallback é obrigatório.

## Código base (copie e adapte)

```html
<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <filter id="liquido" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.008 0.012" numOctaves="2" seed="7" result="ruido"/>
    <feGaussianBlur in="ruido" stdDeviation="2" result="suave"/>
    <feDisplacementMap in="SourceGraphic" in2="suave" scale="40" xChannelSelector="R" yChannelSelector="G"/>
  </filter>
</svg>

<div class="vidro">
  <h2>Título</h2>
  <p>Conteúdo sobre o vidro.</p>
  <button class="vidro-botao">Ação</button>
</div>
```

```css
:root{
  --vidro-fundo: rgba(255,255,255,.14);
  --vidro-borda: rgba(255,255,255,.35);
  --vidro-texto: #0f172a;
  --raio: 24px;
}
.vidro{
  position:relative; isolation:isolate; overflow:hidden;
  border-radius:var(--raio); padding:24px;
  background:var(--vidro-fundo);
  border:1px solid var(--vidro-borda);
  box-shadow: 0 10px 30px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.55),
              inset 0 -1px 0 rgba(255,255,255,.15);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
          backdrop-filter: blur(14px) saturate(160%);
  color:var(--vidro-texto);
}
/* reflexo de luz no topo */
.vidro::before{
  content:""; position:absolute; inset:0; z-index:-1; pointer-events:none;
  background:linear-gradient(135deg, rgba(255,255,255,.45) 0%, rgba(255,255,255,0) 40%);
  mix-blend-mode:overlay;
}
/* refração só onde o navegador suporta (Chrome/Edge) */
@supports (backdrop-filter: url(#liquido)) {
  .vidro{ backdrop-filter: url(#liquido) blur(10px) saturate(160%); }
}
.vidro-botao{
  border:1px solid var(--vidro-borda); border-radius:999px; padding:12px 22px;
  background:rgba(255,255,255,.22); color:inherit; font:inherit; cursor:pointer;
  -webkit-backdrop-filter: blur(8px); backdrop-filter: blur(8px);
  transition: transform .2s ease, background .2s ease;
}
.vidro-botao:hover{ background:rgba(255,255,255,.34); transform:translateY(-1px); }
.vidro-botao:focus-visible{ outline:2px solid #fff; outline-offset:3px; }

/* modo escuro */
@media (prefers-color-scheme: dark){
  :root{ --vidro-fundo: rgba(20,24,33,.35); --vidro-borda: rgba(255,255,255,.18); --vidro-texto:#f1f5f9; }
}
/* acessibilidade: quem pede menos transparência ou menos movimento */
@media (prefers-reduced-transparency: reduce){
  .vidro,.vidro-botao{ -webkit-backdrop-filter:none; backdrop-filter:none; background:rgba(255,255,255,.92); }
}
@media (prefers-reduced-motion: reduce){ .vidro-botao{ transition:none; } }
/* navegador sem backdrop-filter: vidro "opaco" legível */
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))){
  .vidro{ background:rgba(255,255,255,.85); }
}
```

## Regras que não podem faltar

- **Contraste**: texto sobre vidro precisa de contraste mínimo 4,5:1 (WCAG AA). Se o fundo varia muito,
  aumente a opacidade do `--vidro-fundo` ou ponha uma leve sombra no texto. Confira no pior ponto do fundo.
- **Desempenho**: `backdrop-filter` pesa no celular. No máximo 3 a 5 painéis de vidro visíveis ao mesmo tempo;
  nunca em listas longas; não anime o `blur` (anime `transform`/`opacity`).
- **Mobile first**: estilos base para celular; `@media (min-width:768px)` para telas maiores.
- **Fallbacks**: sempre os blocos `@supports` e `prefers-reduced-transparency` acima.
- **Nada de framework** a não ser que o Fred peça.

## Padrões de uso

- Barra de navegação fixa: `.vidro` com `position:sticky; top:12px; margin:12px;`.
- Card de preço / destaque sobre foto do produto.
- Painel de login sobre gradiente animado (gradiente anima, o vidro não).
- Dock de botões arredondados no rodapé (estilo iOS).

Diga ao Fred quando o efeito de refração não vai aparecer (Safari/Firefox) — o layout continua bonito com o vidro fosco.
