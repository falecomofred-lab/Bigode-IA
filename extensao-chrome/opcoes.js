/* Cérebro — Venure · página de opções */

const $ = i => document.getElementById(i);

chrome.storage.sync.get('url', d => { $('url').value = d.url || 'http://localhost:7000'; });

function mostrar(texto, bom) {
  const a = $('aviso');
  a.textContent = texto;
  a.className = 'aviso on ' + (bom ? 'ok' : 'ruim');
}

async function salvar() {
  let url = $('url').value.trim().replace(/\/+$/, '');
  if (!/^https?:\/\//.test(url)) url = 'http://' + url;
  await chrome.storage.sync.set({ url });
  $('url').value = url;
  mostrar('Testando…', true);
  try {
    const r = await fetch(url + '/api/status', { cache: 'no-store' });
    const d = await r.json();
    mostrar(d.pronto ? ('Conectado. Cérebro em uso: ' + (d.nome || 'ativo'))
                     : 'Cérebro respondeu, mas o modelo ainda está ligando.', true);
  } catch (e) {
    mostrar('Não respondeu. Verifique se o CEREBRO.bat está aberto no notebook.', false);
  }
}

function padrao() { $('url').value = 'http://localhost:7000'; salvar(); }

$('btSalvar').addEventListener('click', salvar);
$('btPadrao').addEventListener('click', padrao);
$('url').addEventListener('keydown', e => { if (e.key === 'Enter') salvar(); });
