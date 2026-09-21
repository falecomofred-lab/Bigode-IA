/* Bigode — Venure · opções da extensão

   DOIS DESTINOS, UM CLIQUE

   O Bigode desta extensão é sempre o `cerebro.py`, e ele roda numa
   máquina — normalmente a sua. O segundo destino existe para o caso de
   ele estar em OUTRA máquina da rede: o cerebro.py publica um endereço
   de rede em Configurações › Rede exatamente para isso.

   18/09: este cabeçalho dizia que o segundo destino era o Colab, e que o
   endereço "muda a cada sessão porque o Cloudflare sorteia um novo". O
   Colab saiu do projeto. A Modal, que entrou no lugar, hospeda o MOTOR
   de texto — não o Bigode. Renomear para "Modal" teria trocado uma
   informação velha por uma errada.

   O crachá é guardado POR endereço: ao trocar de destino, o login do
   outro não vale, e sem isso a extensão parava de responder sem dizer
   por quê.
*/

const $ = i => document.getElementById(i);
const LOCAL_PADRAO = 'http://localhost:7000';

/* `urlNuvem` E `'nuvem'` FICAM COMO ESTAO, DE PROPOSITO       (18/09)

   O rótulo na tela virou "Outro endereço", mas estes nomes internos são
   CHAVES DO chrome.storage.sync: é com elas que o endereço que você já
   salvou está gravado hoje. Renomear para ficar bonito apagaria o valor
   guardado — a extensão leria `urlOutro`, não acharia nada, e o endereço
   sumiria sem aviso nenhum.

   Nome interno feio é dívida barata. Perder a configuração de quem já
   usa é caro. Se um dia valer a pena, o jeito certo é ler a chave velha,
   gravar na nova e só então parar de ler a velha — não é para hoje. */
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
  if (!url) { mostrar('Cole o outro endereço primeiro.', false); return; }
  url = url.trim().replace(/\/+$/, '');
  if (!/^https?:\/\//.test(url)) url = 'https://' + url;

  mostrar('Testando ' + url + '…', true);
  try {
    await conferir(url);
  } catch (e) {
    mostrar('Não respondeu. ' + (ehNuvem(url)
      ? 'A outra máquina está ligada, com o BIGODE.bat aberto e na mesma rede?'
      : 'O BIGODE.bat está aberto neste computador?'), false);
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
  if (!estado.urlNuvem) { mostrar('Cole o outro endereço no campo abaixo.', false); return; }
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
