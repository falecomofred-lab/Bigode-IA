/* Cérebro — Venure
   Executa as ações na página e mostra o cursor se movendo, para você acompanhar. */

(() => {
if (window.__cerebroAtivo) return;
window.__cerebroAtivo = true;

let mapa = [];

/* ---------- cursor e destaques ---------- */
let cursor, aviso, marca;

function criarEnfeites() {
  if (cursor) return;

  const estilo = document.createElement('style');
  estilo.textContent = `
    .cerebro-cursor{position:fixed;z-index:2147483647;width:26px;height:26px;
      pointer-events:none;transition:left .55s cubic-bezier(.4,0,.2,1),
      top .55s cubic-bezier(.4,0,.2,1);left:-60px;top:-60px;
      filter:drop-shadow(0 2px 6px rgba(0,0,0,.5))}
    .cerebro-cursor.clicando::after{content:"";position:absolute;left:-9px;top:-9px;
      width:44px;height:44px;border-radius:50%;border:2px solid #2DD4BF;
      animation:cerebroOnda .55s ease-out}
    @keyframes cerebroOnda{from{transform:scale(.3);opacity:1}to{transform:scale(1);opacity:0}}
    .cerebro-marca{position:fixed;z-index:2147483646;pointer-events:none;border-radius:6px;
      border:2px solid #2DD4BF;background:rgba(45,212,191,.12);
      box-shadow:0 0 0 3px rgba(45,212,191,.15);
      transition:all .45s cubic-bezier(.4,0,.2,1);opacity:0}
    .cerebro-marca.on{opacity:1}
    .cerebro-aviso{position:fixed;z-index:2147483647;left:50%;top:18px;
      transform:translateX(-50%);background:#11141B;color:#ECEFF4;
      border:1px solid #2A313E;border-left:3px solid #2DD4BF;border-radius:10px;
      padding:10px 18px;font:13.5px/1.4 -apple-system,"Segoe UI",system-ui,sans-serif;
      box-shadow:0 8px 28px rgba(0,0,0,.45);pointer-events:none;opacity:0;
      transition:.25s;display:flex;align-items:center;gap:9px;max-width:80vw}
    .cerebro-aviso.on{opacity:1}
    .cerebro-aviso b{color:#2DD4BF;font-weight:600;font-size:11px;letter-spacing:1.5px}`;
  document.documentElement.appendChild(estilo);

  cursor = document.createElement('div');
  cursor.className = 'cerebro-cursor';
  cursor.innerHTML = `<svg viewBox="0 0 24 24" width="26" height="26">
    <path d="M5 3l14 8-6 1.5L10 19z" fill="#2DD4BF" stroke="#04140F" stroke-width="1.3"
     stroke-linejoin="round"/></svg>`;

  marca = document.createElement('div');
  marca.className = 'cerebro-marca';

  aviso = document.createElement('div');
  aviso.className = 'cerebro-aviso';

  document.documentElement.append(cursor, marca, aviso);
}

function dizer(texto) {
  criarEnfeites();
  aviso.innerHTML = '<b>CÉREBRO</b><span></span>';
  aviso.lastChild.textContent = texto;
  aviso.classList.add('on');
  clearTimeout(aviso._t);
  aviso._t = setTimeout(() => aviso.classList.remove('on'), 3200);
}

const dormir = ms => new Promise(r => setTimeout(r, ms));

async function irAte(el) {
  criarEnfeites();
  const r = el.getBoundingClientRect();
  const x = r.left + r.width / 2, y = r.top + r.height / 2;

  Object.assign(marca.style, {
    left: (r.left - 3) + 'px', top: (r.top - 3) + 'px',
    width: (r.width + 6) + 'px', height: (r.height + 6) + 'px',
  });
  marca.classList.add('on');

  cursor.style.left = (x - 4) + 'px';
  cursor.style.top = (y - 3) + 'px';
  await dormir(620);
}

async function bater() {
  cursor.classList.add('clicando');
  await dormir(260);
  cursor.classList.remove('clicando');
  setTimeout(() => marca.classList.remove('on'), 700);
}

/* ---------- leitura da página ---------- */
const SELETOR = 'a[href],button,input,textarea,select,summary,' +
  '[role="button"],[role="link"],[role="tab"],[role="checkbox"],[role="menuitem"],' +
  '[contenteditable="true"],[onclick]';

function visivel(el) {
  const r = el.getBoundingClientRect();
  if (r.width < 4 || r.height < 4) return false;
  const s = getComputedStyle(el);
  if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity < 0.1) return false;
  if (el.disabled) return false;
  return r.bottom > -400 && r.top < innerHeight + 800;
}

function rotulo(el) {
  const t = (el.getAttribute('aria-label') || el.placeholder || el.value ||
             el.innerText || el.title || el.alt || el.name || '').trim();
  return t.replace(/\s+/g, ' ').slice(0, 70);
}

function tipo(el) {
  const tag = el.tagName.toLowerCase();
  if (tag === 'input') return (el.type || 'text');
  if (tag === 'a') return 'link';
  if (tag === 'textarea') return 'texto';
  if (tag === 'select') return 'lista';
  return tag;
}

function mapear() {
  mapa = [...document.querySelectorAll(SELETOR)].filter(visivel).slice(0, 120);

  const itens = mapa.map((el, i) => {
    const extra = (el.value && el.tagName === 'INPUT') ? ' = "' + el.value.slice(0, 30) + '"' : '';
    return `[${i}] ${tipo(el)}: ${rotulo(el) || '(sem rótulo)'}${extra}`;
  });

  const texto = (document.body.innerText || '').replace(/\n{3,}/g, '\n\n').slice(0, 4000);

  return `PÁGINA: ${document.title}\nENDEREÇO: ${location.href}\n\n` +
         `ELEMENTOS (use o número para clicar ou escrever):\n${itens.join('\n')}\n\n` +
         `TEXTO VISÍVEL:\n${texto}`;
}

function pegar(numero) {
  const el = mapa[Number(numero)];
  if (!el) throw new Error(`Não existe elemento [${numero}]. Chame navegador_ver de novo.`);
  el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  return el;
}

/* ---------- ações ---------- */
const ACOES = {
  async ver() {
    dizer('Lendo a página');
    await dormir(250);
    return mapear();
  },

  async clicar({ numero }) {
    const el = pegar(numero);
    dizer('Clicando em ' + (rotulo(el) || 'elemento'));
    await dormir(320);
    await irAte(el);
    await bater();
    el.focus?.();
    el.click();
    await dormir(900);
    return `Cliquei em [${numero}] ${rotulo(el)}.\nAgora estou em: ${location.href}`;
  },

  async escrever({ numero, texto }) {
    const el = pegar(numero);
    dizer('Digitando: ' + String(texto).slice(0, 40));
    await irAte(el);
    await bater();
    el.focus();

    const nativo = Object.getOwnPropertyDescriptor(
      el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype,
      'value');

    if (el.isContentEditable) {
      el.textContent = '';
      for (const c of String(texto)) { el.textContent += c; await dormir(14); }
    } else {
      nativo?.set?.call(el, '');
      el.dispatchEvent(new Event('input', { bubbles: true }));
      let acumulado = '';
      for (const c of String(texto)) {
        acumulado += c;
        nativo?.set?.call(el, acumulado);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        await dormir(18);
      }
    }
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return `Escrevi "${texto}" no campo [${numero}] ${rotulo(el)}.`;
  },

  async teclar({ tecla }) {
    dizer('Apertando ' + tecla);
    const alvo = document.activeElement || document.body;
    for (const t of ['keydown', 'keypress', 'keyup']) {
      alvo.dispatchEvent(new KeyboardEvent(t, {
        key: tecla, code: tecla, bubbles: true, cancelable: true,
      }));
    }
    if (tecla === 'Enter') alvo.closest?.('form')?.requestSubmit?.();
    await dormir(900);
    return `Apertei ${tecla}. Estou em: ${location.href}`;
  },

  async rolar({ direcao }) {
    const d = (direcao || 'baixo').toLowerCase();
    dizer('Rolando a página');
    if (d.includes('topo')) scrollTo({ top: 0, behavior: 'smooth' });
    else if (d.includes('fim')) scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    else if (d.includes('cima')) scrollBy({ top: -innerHeight * 0.85, behavior: 'smooth' });
    else scrollBy({ top: innerHeight * 0.85, behavior: 'smooth' });
    await dormir(750);
    return 'Rolei a página. Chame navegador_ver para enxergar o que apareceu.';
  },

  async esperar({ segundos }) {
    const s = Math.min(Number(segundos) || 2, 20);
    dizer(`Esperando ${s}s`);
    await dormir(s * 1000);
    return `Esperei ${s}s. Estou em: ${location.href}`;
  },
};

/* ---------- ponte com a extensão ---------- */
chrome.runtime.onMessage.addListener((msg, _r, responder) => {
  if (msg?.tipo !== 'cerebro-acao') return;
  const fn = ACOES[msg.acao];
  if (!fn) { responder({ erro: 'Ação desconhecida: ' + msg.acao }); return true; }

  fn(msg.args || {})
    .then(resultado => responder({ resultado }))
    .catch(e => responder({ resultado: 'Não consegui: ' + e.message }));
  return true;      // resposta assíncrona
});
})();
