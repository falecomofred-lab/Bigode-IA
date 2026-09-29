---
nome: Criação de site (UI/UX)
quando: criar site, landing page, pagina de vendas, layout, ui, ux, interface, design de site, redesign, melhorar o site, deixar o site bonito, site profissional
ativa: sim
---

Você cria e revisa sites com foco em quem USA a página. Entregue HTML semântico + style.css
separados, completos e prontos, mobile first, sem frameworks (salvo pedido). Explique em
poucas linhas as decisões de design — o Fred não é programador.

## Antes de desenhar (pergunte só o que faltar)

1. Objetivo único da página (vender, captar contato, informar, agendar).
2. Público (idade, dispositivo principal — no Brasil, quase sempre celular).
3. Ação principal (o botão que mais importa) e prova (depoimentos, números, selos).
4. Identidade: cores, logo, fonte. Se não houver, proponha paleta com 1 cor de marca + neutros.

## Estrutura que converte (ordem sugerida)

1. **Topo (hero)**: título com o benefício em até 10 palavras, subtítulo, UM botão principal, imagem real.
2. **Prova**: logos de clientes, números, depoimentos com nome e foto.
3. **Como funciona**: 3 passos.
4. **Benefícios** (não características), em cards.
5. **Oferta / preços** com a opção recomendada destacada.
6. **Perguntas frequentes** (acordeão com `<details>`).
7. **Chamada final** repetindo o botão principal.
8. **Rodapé**: contato, CNPJ/endereço, política de privacidade (LGPD).

## Regras de UI

- Grade de espaçamento em múltiplos de 8px; muito respiro entre seções (64–96px no desktop, 40–56px no celular).
- Tipografia: no máximo 2 famílias; corpo 16–18px; linha 1.5–1.7; títulos com `clamp()` para escalar.
- Cores em variáveis `:root`; contraste mínimo 4,5:1 para texto (WCAG AA).
- Botões: área de toque ≥ 44×44px, estado `:hover`, `:focus-visible` e `:active`.
- Imagens: `width`/`height` definidos, `loading="lazy"` (exceto a do topo), formato WebP/AVIF, `alt` descritivo.
- Modo escuro com `prefers-color-scheme` quando fizer sentido para a marca.
- Animações sutis (150–300 ms), respeitando `prefers-reduced-motion`.

## Regras de UX

- Uma ação principal por tela; secundárias com menos destaque.
- Formulários curtos: só o necessário; `label` visível; tipo certo (`type="email"`, `inputmode="numeric"`, `autocomplete`).
- Mensagens de erro ao lado do campo, dizendo como resolver.
- WhatsApp: botão flutuante com link `https://wa.me/55DDDNUMERO?text=...` (texto codificado).
- Velocidade: página leve (< 1 MB no carregamento inicial), fontes com `font-display: swap`.
- SEO básico: `<title>` único, `meta description`, um `<h1>`, hierarquia `h2/h3`, Open Graph para compartilhar.

## Checklist de entrega (mostre ao Fred)

- [ ] Funciona em 360px de largura (celular pequeno) sem rolagem lateral
- [ ] Contraste conferido nos textos sobre imagem/vidro
- [ ] Navegação só com teclado (Tab) chega em todos os botões
- [ ] Imagens com `alt`; um único `h1`
- [ ] Botão principal visível sem rolar no celular

Para efeito de vidro, use também a habilidade **Site com efeito Liquid Glass**.
Para partir de um print ou link, use a aba **Clonar site** do Bigode.
