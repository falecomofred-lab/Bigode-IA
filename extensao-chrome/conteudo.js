/* Bigode — Venure
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
    .Bigode-cursor{position:fixed;z-index:2147483647;width:26px;height:26px;
      pointer-events:none;transition:left .55s cubic-bezier(.4,0,.2,1),
      top .55s cubic-bezier(.4,0,.2,1);left:-60px;top:-60px;
      filter:drop-shadow(0 2px 6px rgba(0,0,0,.5))}
    .Bigode-cursor.clicando::after{content:"";position:absolute;left:-9px;top:-9px;
      width:44px;height:44px;border-radius:50%;border:2px solid #2DD4BF;
      animation:cerebroOnda .55s ease-out}
    @keyframes cerebroOnda{from{transform:scale(.3);opacity:1}to{transform:scale(1);opacity:0}}
    .Bigode-marca{position:fixed;z-index:2147483646;pointer-events:none;border-radius:6px;
      border:2px solid #2DD4BF;background:rgba(45,212,191,.12);
      box-shadow:0 0 0 3px rgba(45,212,191,.15);
      transition:all .45s cubic-bezier(.4,0,.2,1);opacity:0}
    .Bigode-marca.on{opacity:1}
    .Bigode-aviso{position:fixed;z-index:2147483647;left:50%;top:18px;
      transform:translateX(-50%);background:#11141B;color:#ECEFF4;
      border:1px solid #2A313E;border-left:3px solid #2DD4BF;border-radius:10px;
      padding:10px 18px;font:13.5px/1.4 -apple-system,"Segoe UI",system-ui,sans-serif;
      box-shadow:0 8px 28px rgba(0,0,0,.45);pointer-events:none;opacity:0;
      transition:.25s;display:flex;align-items:center;gap:9px;max-width:80vw}
    .Bigode-aviso.on{opacity:1}
    .Bigode-aviso b{color:#2DD4BF;font-weight:600;font-size:11px;letter-spacing:1.5px}`;
  document.documentElement.appendChild(estilo);

  // OS NOMES PRECISAM BATER COM O CSS ACIMA            (13/09)
  //
  //   Aqui estava escrito 'cerebro-cursor', 'cerebro-marca' e
  //   'cerebro-aviso', enquanto o CSS logo acima define '.Bigode-cursor',
  //   '.Bigode-marca' e '.Bigode-aviso'. Nome diferente, regra nenhuma
  //   aplicada: os tres viravam divs invisiveis, sem posicao e sem cor.
  //
  //   O destaque existia no codigo desde sempre e nunca apareceu na tela
  //   uma vez. Nao dava erro, nao aparecia no console -- so nao acontecia.
  //   E o tipo de defeito que sobrevive por meses, porque ninguem procura
  //   bug numa coisa que "a gente ainda nao terminou".
  cursor = document.createElement('div');
  cursor.className = 'Bigode-cursor';
  cursor.innerHTML = `<svg viewBox="0 0 24 24" width="26" height="26">
    <path d="M5 3l14 8-6 1.5L10 19z" fill="#2DD4BF" stroke="#04140F" stroke-width="1.3"
     stroke-linejoin="round"/></svg>`;

  marca = document.createElement('div');
  marca.className = 'Bigode-marca';

  aviso = document.createElement('div');
  aviso.className = 'Bigode-aviso';

  document.documentElement.append(cursor, marca, aviso);
}

function dizer(texto) {
  criarEnfeites();
  aviso.innerHTML = '<b>BIGODE IA</b><span></span>';
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
  /* Se o modelo tentar agir sem primeiro olhar, atualizamos a página antes de
     tocar em qualquer elemento. Assim ele nunca age usando uma lista velha. */
  if (!mapa.length) mapear();
  const el = mapa[Number(numero)];
  if (!el) throw new Error(`Não encontrei esse item. Vou mostrar a página atualizada para você escolher.`);
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
    return `Cliquei em [${numero}] ${rotulo(el)}.\nAgora estou em: ${location.href}\n\n${mapear()}`;
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
    return `Apertei ${tecla}. Estou em: ${location.href}\n\n${mapear()}`;
  },

  async rolar({ direcao }) {
    const d = (direcao || 'baixo').toLowerCase();
    dizer('Rolando a página');
    if (d.includes('topo')) scrollTo({ top: 0, behavior: 'smooth' });
    else if (d.includes('fim')) scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    else if (d.includes('cima')) scrollBy({ top: -innerHeight * 0.85, behavior: 'smooth' });
    else scrollBy({ top: innerHeight * 0.85, behavior: 'smooth' });
    await dormir(750);
    return 'Rolei a página. Esta é a visão atualizada:\n\n' + mapear();
  },

  async esperar({ segundos }) {
    const s = Math.min(Number(segundos) || 2, 20);
    dizer(`Esperando ${s}s`);
    await dormir(s * 1000);
    return `Esperei ${s}s. Estou em: ${location.href}`;
  },

  /* LER O TEXTO, NAO SO O QUE E CLICAVEL                      (17/09)

     O `ver` mapeia elementos clicaveis numerados. Num console de Bash do
     PythonAnywhere quase nada e clicavel: o que importa e a SAIDA do
     comando, que e texto solto. Sem esta acao o Bigode rodava o comando e
     ficava cego para a resposta.

     Le a area de console/terminal quando existe uma, senao o corpo todo.
     O corte em 12 mil caracteres e para nao estourar a janela do modelo
     com uma pagina gigante -- e ele avisa quando corta, em vez de mentir
     que aquilo era tudo.                                              */
  async texto() {
    dizer('Lendo o texto da página');
    await dormir(200);

    const seletores = [
      '.terminal', '.xterm', '.xterm-screen', '#id_console',
      'pre', 'code', '[role="log"]', '[class*="console"]',
      '[class*="terminal"]', '[class*="output"]', 'main', 'article',
    ];
    let fonte = null, maior = 0;
    for (const s of seletores) {
      for (const el of document.querySelectorAll(s)) {
        const t = (el.innerText || '').trim();
        if (t.length > maior) { maior = t.length; fonte = el; }
      }
    }
    const corpoTxt = (document.body.innerText || '').trim();
    // Se o melhor candidato tem menos de um terco do corpo, ele provavelmente
    // nao e o conteudo principal -- melhor devolver o corpo inteiro.
    let bruto = (fonte && maior > corpoTxt.length / 3) ? fonte.innerText : corpoTxt;
    bruto = String(bruto || '').replace(/\n{3,}/g, '\n\n').trim();

    const LIMITE = 12000;
    let aviso = '';
    if (bruto.length > LIMITE) {
      // Guarda o FIM, nao o comeco: em console, a resposta do ultimo
      // comando esta embaixo.
      bruto = bruto.slice(-LIMITE);
      aviso = `[cortado: mostrando os ultimos ${LIMITE} caracteres]\n\n`;
    }
    return `Texto de ${location.href}\n\n${aviso}${bruto || '(a página não tem texto visível)'}`;
  },

  /* DIGITAR ONDE O CURSOR ESTA                                (17/09)

     O `escrever` grava em campo de formulario, achando o elemento por
     numero e mexendo no `value`. Terminal na web nao tem `value`: ele
     escuta tecla. Por isso aqui vao KeyboardEvent de verdade, letra por
     letra, para onde o foco estiver.

     Tres camadas, porque terminal na web nao segue padrao:
       1. KeyboardEvent (o que xterm.js e afins escutam)
       2. insertText (contenteditable)
       3. o setter nativo de value (se por acaso for campo mesmo)

     Voce precisa CLICAR no console antes: sem foco, a tecla vai para o
     body e nada acontece. A acao diz isso quando desconfia.             */
  async digitar({ texto }) {
    const txt = String(texto ?? '');
    if (!txt) return 'Nada para digitar.';

    let alvo = document.activeElement;
    if (!alvo || alvo === document.body || alvo === document.documentElement) {
      return 'Nada está com o cursor. Use navegador_ver e navegador_clicar '
           + 'no console primeiro, depois digite.';
    }

    dizer('Digitando: ' + txt.slice(0, 40));
    await bater();

    const nativo = Object.getOwnPropertyDescriptor(
      alvo.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
                                  : HTMLInputElement.prototype, 'value');

    for (const c of txt) {
      const comum = { key: c, code: 'Key' + c.toUpperCase(),
                      bubbles: true, cancelable: true };
      alvo.dispatchEvent(new KeyboardEvent('keydown', comum));
      alvo.dispatchEvent(new KeyboardEvent('keypress', comum));

      let entrou = false;
      if (alvo.isContentEditable) {
        try { entrou = document.execCommand('insertText', false, c); } catch (e) {}
      } else if (typeof alvo.value === 'string' && nativo?.set) {
        nativo.set.call(alvo, (alvo.value || '') + c);
        entrou = true;
      }
      if (entrou) {
        alvo.dispatchEvent(new InputEvent('input', {
          bubbles: true, data: c, inputType: 'insertText' }));
      }
      alvo.dispatchEvent(new KeyboardEvent('keyup', comum));
      await dormir(12);
    }

    return `Digitei "${txt.slice(0, 80)}" onde o cursor estava `
         + `(${alvo.tagName.toLowerCase()}). Para executar, use `
         + `navegador_teclar com Enter.`;
  },
};

/* ---------- aprovação humana para ações críticas ---------- */
function acaoCritica(acao, args, el) {
  const rotuloAlvo = (el ? rotulo(el) : '').toLowerCase();
  const texto = JSON.stringify(args || {}).toLowerCase();
  const termos = ['comprar', 'finalizar', 'enviar', 'salvar', 'excluir', 'apagar', 'assinar', 'pagar', 'publicar', 'confirmar', 'submit', 'login', 'entrar', 'sair', 'cadastrar', 'aprovar', 'pedido', 'contratar'];
  const campoSensivel = acao === 'escrever' && el && (
    String(el.type || '').toLowerCase() === 'password' ||
    /senha|password|login|usuario|usuário|e-mail|email|cpf|cartao|cartão|token/.test(
      (rotuloAlvo + ' ' + String(el.name || '')).toLowerCase()));
  // COMANDO DE TERMINAL PEDE APROVACAO ANTES DE SER DIGITADO   (17/09)
  //
  //   O `digitar` existe para console de Bash. Digitar em si nao executa
  //   -- quem executa e o Enter, que ja pede aprovacao. Mas pedir DEPOIS
  //   de o comando estar escrito e pedir tarde: no cartao do Enter voce
  //   le "apertar Enter", nao "apagar a pasta do projeto".
  //
  //   Entao comando perigoso pede aprovacao na hora de ser DIGITADO, com
  //   o texto na tela. Digitacao comum passa direto: parar em cada
  //   palavra tornaria a ferramenta inutil.
  const oQueVaiDigitar = String(args?.texto || '').toLowerCase();
  const comandoPerigoso = acao === 'digitar' && (
    /\brm\s+-[rf]/.test(oQueVaiDigitar) ||
    /\b(drop|truncate|delete)\s+(table|from|database)\b/.test(oQueVaiDigitar) ||
    /\bgit\s+(push\s+--force|reset\s+--hard|clean\s+-[fdx])/.test(oQueVaiDigitar) ||
    /\b(shutdown|reboot|mkfs|dd\s+if=|chmod\s+777|curl[^|]*\|\s*(ba)?sh)\b/.test(oQueVaiDigitar) ||
    /\b(sudo|pip\s+uninstall|npm\s+publish|deploy|migrate)\b/.test(oQueVaiDigitar) ||
    /(senha|password|token|secret|api[_-]?key)\s*=/.test(oQueVaiDigitar));

  const digitandoEmSenha = acao === 'digitar' && el &&
    String(el.type || '').toLowerCase() === 'password';

  return acao === 'ir' && /login|entrar|checkout|pagamento|admin/.test(String(args?.url || '').toLowerCase()) ||
         (acao === 'teclar' && ['enter', 'tab'].includes(String(args?.tecla || '').toLowerCase())) ||
         (acao === 'escrever' && campoSensivel) ||
         comandoPerigoso || digitandoEmSenha ||
         (acao === 'clicar' && termos.some(t => rotuloAlvo.includes(t) || texto.includes(t)));
}

function aprovarNaPagina(acao, args, el) {
  return new Promise(resolve => {
    const antigo = document.querySelector('[data-cerebro-hitl]');
    antigo?.remove();
    const fundo = document.createElement('div');
    fundo.dataset.cerebroHitl = '1';
    fundo.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:rgba(4,8,13,.72);display:grid;place-items:center;padding:20px;font:14px -apple-system,Segoe UI,sans-serif;color:#ECEFF4';
    const card = document.createElement('div');
    card.style.cssText = 'width:min(420px,100%);background:#11141B;border:1px solid #4A3D1A;border-radius:14px;padding:20px;box-shadow:0 18px 60px rgba(0,0,0,.5)';
    const titulo = document.createElement('div');
    titulo.textContent = 'Aprovação necessária';
    titulo.style.cssText = 'font-weight:700;font-size:16px;margin-bottom:9px;color:#FBBF24';
    const detalhe = document.createElement('div');
    const nomeAcao = {ir:'abrir este endereço',clicar:'clicar',escrever:'preencher este campo',teclar:'apertar esta tecla',digitar:'digitar isto'}[acao] || acao;
    detalhe.textContent = 'O Bigode quer '+nomeAcao+' em “'+(rotulo(el) || String(args?.url || 'elemento da página'))+'”.';
    detalhe.style.cssText = 'line-height:1.6;color:#A3ACBB;margin-bottom:16px';

    // MOSTRAR O COMANDO, NAO A PALAVRA "DIGITAR"               (17/09)
    //
    //   Aprovar "digitar isto" sem ver o que e nao e aprovar: e assinar em
    //   branco. Quando a acao e digitar, o texto vai na tela, em fonte de
    //   terminal, para voce ler antes de dizer sim.
    let caixaCmd = null;
    if (acao === 'digitar' && args?.texto) {
      caixaCmd = document.createElement('pre');
      caixaCmd.textContent = String(args.texto);
      caixaCmd.style.cssText = 'margin:0 0 16px;padding:11px 13px;border-radius:9px;background:#080A0F;border:1px solid #2A313E;color:#FBBF24;font:12.5px/1.5 ui-monospace,Consolas,monospace;white-space:pre-wrap;word-break:break-all;max-height:190px;overflow:auto';
    }
    const linha = document.createElement('div');
    linha.style.cssText = 'display:flex;gap:9px;justify-content:flex-end';
    const negar = document.createElement('button');
    negar.textContent = 'Negar';
    negar.style.cssText = 'padding:9px 16px;border-radius:9px;border:1px solid #2A313E;background:none;color:#A3ACBB;cursor:pointer';
    const aprovar = document.createElement('button');
    aprovar.textContent = 'Aprovar';
    aprovar.style.cssText = 'padding:9px 16px;border-radius:9px;border:0;background:#34D399;color:#052A1E;font-weight:700;cursor:pointer';
    const concluir = ok => { fundo.remove(); resolve(ok); };
    negar.onclick = () => concluir(false);
    aprovar.onclick = () => concluir(true);
    linha.append(negar, aprovar);
    card.append(titulo, detalhe);
    if (caixaCmd) card.append(caixaCmd);
    card.append(linha);
    fundo.append(card); document.documentElement.append(fundo);
    aprovar.focus();
  });
}

/* ---------- ponte com a extensão ---------- */
chrome.runtime.onMessage.addListener((msg, _r, responder) => {
  if (msg?.tipo !== 'cerebro-acao') return;
  const fn = ACOES[msg.acao];
  if (!fn) { responder({ erro: 'Ação desconhecida: ' + msg.acao }); return true; }
  const args = msg.args || {};
  if (!mapa.length) mapear();
  const el = (msg.acao === 'clicar' || msg.acao === 'escrever')
    ? mapa[Number(args.numero)] : document.activeElement;

  (async () => {
    if (acaoCritica(msg.acao, args, el)) {
      // MOSTRAR O ALVO ANTES DE PERGUNTAR                    (13/09)
      //
      //   O cartao dizia 'clicar em "Finalizar compra"' e parava ai. Mas
      //   numa pagina cheia pode haver tres botoes parecidos, e o nome
      //   que a gente le no cartao vem do codigo da pagina -- nem sempre
      //   e o texto que voce enxerga.
      //
      //   Aprovar sem ver ONDE ele vai clicar e aprovar no escuro, que e
      //   o contrario do que esta tela existe para fazer. Entao o
      //   contorno acende primeiro e fica aceso enquanto voce decide.
      if (el) { try { await irAte(el); } catch (e) {} }

      const aprovado = await aprovarNaPagina(msg.acao, args, el);

      if (!aprovado) {
        if (marca) marca.classList.remove('on');
        responder({ resultado: 'Ação negada pelo usuário.' });
        return;
      }
    }
    const resultado = await fn(args);
    responder({ resultado });
  })().catch(e => responder({ resultado: 'Não consegui: ' + e.message }));
  return true;      // resposta assíncrona
});
})();
