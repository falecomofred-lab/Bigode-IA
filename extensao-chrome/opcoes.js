/* Bigode — Venure · opções da extensão

   DOIS DESTINOS, UM CLIQUE

   Desde que o Bigode passou a rodar também no Colab, a extensão precisa
   saber com qual dos dois falar. E o endereço da nuvem MUDA a cada sessão
   — o Cloudflare sorteia um novo toda vez.

   Reescrever o link na mão a cada sessão era pedir para dar errado. Pior:
   ao trocar de endereço, o crachá do login antigo não vale no novo, e a
   extensão simplesmente parava de responder sem dizer por quê.

   Aqui os dois endereços ficam guardados, o crachá é guardado POR endereço,
   e trocar é um clique.
*/

const $ = i => document.getElementById(i);
const LOCAL_PADRAO = 'http://localhost:7000';

let estado = { url: LOCAL_PADRAO, urlLocal: LOCAL_PADRAO, urlNuvem: '' };

chrome.storage.sync.get(['url', 'urlLocal', 'urlNuvem'], d => {
  estado.urlLocal = d.urlLocal || LOCAL_PADRAO;
  estado.urlNuvem = d.urlNuvem || '';
  estado.url = d.url || estado.urlLocal;
  pintar();
});

function ehNuvem(u) { return !!u && !/^https?:\/\/(localhost|127\.|192\.168\.)/.test(u); }

function pintar() {
  $('urlAqui').textContent = estado.urlLocal;
  $('urlNuvem').textContent = estado.urlNuvem || 'nenhum endereço salvo';
  $('url').value = estado.urlNuvem || '';

  const naNuvem = ehNuvem(estado.url);
  $('dAqui').classList.toggle('ativo', !naNuvem);
  $('dNuvem').classList.toggle('ativo', naNuvem);

  chrome.storage.local.get(['tokens', 'usuario'], d => {
    const tk = (d.tokens || {})[estado.url];
    $('quemEsta').textContent = tk
      ? ('Conectado como ' + (d.usuario || 'usuário') + ' em ' + estado.url)
      : 'Sem acesso neste endereço. Abra o painel lateral para entrar.';
  });
}

function mostrar(texto, bom) {
  const a = $('aviso');
  a.textContent = texto;
  a.className = 'aviso on ' + (bom ? 'ok' : 'ruim');
}

/* Testa antes de aceitar. Um endereço que não responde salvo em silêncio
   vira meia hora procurando defeito no lugar errado. */
async function conferir(url) {
  const r = await fetch(url + '/api/login/estado', { cache: 'no-store' });
  await r.json();
  return true;
}

async function usar(url, guardarComo) {
  if (!url) { mostrar('Cole o endereço da nuvem primeiro.', false); return; }
  url = url.trim().replace(/\/+$/, '');
  if (!/^https?:\/\//.test(url)) url = 'https://' + url;

  mostrar('Testando ' + url + '…', true);
  try {
    await conferir(url);
  } catch (e) {
    mostrar('Não respondeu. ' + (ehNuvem(url)
      ? 'O Colab ainda está ligado? O link morre quando ele desconecta.'
      : 'O Bigode está aberto no computador?'), false);
    return;
  }

  estado.url = url;
  if (guardarComo === 'nuvem') estado.urlNuvem = url;
  if (guardarComo === 'local') estado.urlLocal = url;
  await chrome.storage.sync.set({
    url: estado.url, urlLocal: estado.urlLocal, urlNuvem: estado.urlNuvem });

  pintar();
  mostrar('Falando com ' + url + '. Abra o painel lateral — se for a primeira '
        + 'vez neste endereço, ele pede o login.', true);
}

$('btSalvar').addEventListener('click', () => usar($('url').value, 'nuvem'));
$('btPadrao').addEventListener('click', () => usar(estado.urlLocal, 'local'));
$('dAqui').addEventListener('click', () => usar(estado.urlLocal, 'local'));
$('dNuvem').addEventListener('click', () => {
  if (!estado.urlNuvem) { mostrar('Cole o link do Colab no campo abaixo.', false); return; }
  usar(estado.urlNuvem, 'nuvem');
});
$('url').addEventListener('keydown', e => {
  if (e.key === 'Enter') usar($('url').value, 'nuvem');
});

$('btSair').addEventListener('click', async () => {
  const d = await chrome.storage.local.get('tokens');
  const tokens = d.tokens || {};
  delete tokens[estado.url];
  await chrome.storage.local.set({ tokens });
  pintar();
  mostrar('Acesso encerrado neste endereço. O outro continua valendo.', true);
});
