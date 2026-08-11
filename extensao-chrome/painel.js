/* Painel lateral: carrega a interface do Cérebro e entrega o texto pendente. */

const quadro = document.getElementById('quadro');
const erro = document.getElementById('erro');
const PADRAO = 'http://localhost:7000';
let base = PADRAO;
let tentativas = 0;

function detalhe(txt) {
  const el = document.getElementById('detalhe');
  if (el) el.textContent = txt || '';
}

async function pegarEndereco() {
  try {
    const r = await chrome.storage.sync.get('url');
    if (r && r.url) return String(r.url).replace(/\/+$/, '');
  } catch (e) { /* storage indisponível */ }
  return PADRAO;
}

async function vivo(url) {
  try {
    const c = new AbortController();
    const t = setTimeout(() => c.abort(), 4000);
    const r = await fetch(url + '/api/status', { signal: c.signal, cache: 'no-store' });
    clearTimeout(t);
    if (!r.ok) { detalhe('O Cérebro respondeu ' + r.status); return false; }
    await r.json();
    detalhe('');
    return true;
  } catch (e) {
    detalhe(e.name === 'AbortError'
      ? 'Sem resposta em 4s.'
      : 'Não alcancei o endereço. ' + (e.message || ''));
    return false;
  }
}

async function tentar() {
  base = await pegarEndereco();
  const alvo = document.getElementById('alvo');
  if (alvo) alvo.textContent = base;

  if (await vivo(base)) {
    tentativas = 0;
    erro.classList.remove('on');
    quadro.style.display = 'block';
    if (quadro.src !== base + '/') quadro.src = base + '/';
    setTimeout(entregarPendente, 1200);
  } else {
    quadro.style.display = 'none';
    erro.classList.add('on');
    tentativas++;
    setTimeout(tentar, Math.min(4000 + tentativas * 1500, 15000));
  }
}

/* texto vindo do menu de contexto */
async function entregarPendente() {
  const { pendente } = await chrome.storage.local.get('pendente');
  if (!pendente) return;
  await chrome.storage.local.remove('pendente');
  try {
    quadro.contentWindow.postMessage(
      { origem: 'cerebro-extensao', acao: 'inserir', texto: pendente.texto }, '*');
  } catch (e) { /* iframe ainda carregando */ }
}

chrome.storage.onChanged.addListener((mudou, area) => {
  if (area === 'local' && mudou.pendente && mudou.pendente.newValue) entregarPendente();
  if (area === 'sync' && mudou.url) tentar();
});

/* ---------- ponte: o Cérebro pede, o Chrome executa ---------- */
window.addEventListener('message', async ev => {
  const d = ev.data;
  if (!d || d.origem !== 'cerebro') return;

  if (d.acao === 'pronto') { entregarPendente(); return; }

  if (d.acao === 'navegador') {
    let resultado = 'Falha ao acionar o navegador.';
    try {
      const r = await chrome.runtime.sendMessage(
        { tipo: 'agir', acao: d.tipoAcao, args: d.args });
      resultado = (r && r.resultado) || resultado;
    } catch (e) {
      resultado = 'Extensão não respondeu: ' + e.message;
    }
    try {
      await fetch(base + '/api/navegador', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: d.id, resultado }),
      });
    } catch (e) { /* servidor caiu */ }
  }
});

document.getElementById('btTentar').addEventListener('click', () => {
  tentativas = 0; detalhe('Testando…'); tentar();
});
document.getElementById('btOpcoes').addEventListener('click',
  () => chrome.runtime.openOptionsPage());

tentar();
