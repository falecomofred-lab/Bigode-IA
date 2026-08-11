/* Cérebro — Venure
   Service worker: abre o painel e alimenta o Cérebro com o conteúdo da página. */

const PADRAO = 'http://localhost:7000';

async function endereco() {
  const { url } = await chrome.storage.sync.get('url');
  return (url || PADRAO).replace(/\/+$/, '');
}

/* clique no ícone abre o painel lateral */
chrome.action.onClicked.addListener(aba => {
  chrome.sidePanel.open({ tabId: aba.id });
});
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});

/* menus de contexto */
const MENUS = [
  { id: 'perguntar', title: 'Perguntar ao Cérebro sobre isto', contexts: ['selection'] },
  { id: 'explicar',  title: 'Explicar este trecho',            contexts: ['selection'] },
  { id: 'codigo',    title: 'Revisar este código',             contexts: ['selection'] },
  { id: 'resumir',   title: 'Resumir esta página',             contexts: ['page'] },
  { id: 'salvar',    title: 'Salvar no meu Drive',             contexts: ['page', 'selection'] },
];

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    MENUS.forEach(m => chrome.contextMenus.create({ ...m, id: m.id }));
  });
});

const MODELOS = {
  perguntar: t => t,
  explicar:  t => 'Explique este trecho de forma simples:\n\n' + t,
  codigo:    t => 'Revise este código. Aponte erros, riscos de segurança e o que '
                + 'melhorar. Devolva a versão corrigida completa:\n\n```\n' + t + '\n```',
  resumir:   (_, info) => 'Resuma o conteúdo desta página em tópicos: ' + info.pageUrl,
  salvar:    (t, info) => 'Salve isto em um arquivo dentro da minha pasta de projetos. '
                + 'Escolha um nome que faça sentido.\n\nOrigem: ' + info.pageUrl
                + '\n\n' + (t || '(use o conteúdo da página)'),
};

chrome.contextMenus.onClicked.addListener(async (info, aba) => {
  let texto = info.selectionText || '';

  /* sem seleção: pega o texto visível da página */
  if (!texto && (info.menuItemId === 'resumir' || info.menuItemId === 'salvar')) {
    try {
      const [r] = await chrome.scripting.executeScript({
        target: { tabId: aba.id },
        func: () => document.body.innerText.slice(0, 12000),
      });
      texto = r.result || '';
    } catch (e) { /* páginas internas do Chrome bloqueiam script */ }
  }

  const montar = MODELOS[info.menuItemId] || (t => t);
  const mensagem = montar(texto, info);

  await chrome.storage.local.set({
    pendente: { texto: mensagem, url: info.pageUrl, titulo: aba?.title || '' },
  });
  chrome.sidePanel.open({ tabId: aba.id });
});

/* ---------- ações no navegador ---------- */

async function abaAtiva() {
  const [aba] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return aba;
}

async function garantirScript(abaId) {
  try {
    await chrome.scripting.executeScript({ target: { tabId: abaId }, files: ['conteudo.js'] });
  } catch (e) { /* já injetado ou página protegida */ }
}

async function executarNaPagina(acao, args) {
  const aba = await abaAtiva();
  if (!aba) return 'Nenhuma aba aberta no Chrome.';
  if (/^(chrome|edge|about|chrome-extension):/.test(aba.url || '')) {
    return 'Esta é uma página interna do Chrome e não permite automação. '
         + 'Abra um site normal.';
  }

  /* navegar é o único caso que a extensão resolve sozinha */
  if (acao === 'ir') {
    let url = String(args.url || '').trim();
    if (!/^https?:\/\//.test(url)) url = 'https://' + url;
    await chrome.tabs.update(aba.id, { url });
    await new Promise(ok => {
      const ouvir = (id, info) => {
        if (id === aba.id && info.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(ouvir); ok();
        }
      };
      chrome.tabs.onUpdated.addListener(ouvir);
      setTimeout(() => { chrome.tabs.onUpdated.removeListener(ouvir); ok(); }, 20000);
    });
    await garantirScript(aba.id);
    return 'Abri ' + url + '. Chame navegador_ver para enxergar a página.';
  }

  await garantirScript(aba.id);
  try {
    const r = await chrome.tabs.sendMessage(aba.id, { tipo: 'cerebro-acao', acao, args });
    return r?.resultado || r?.erro || '(sem retorno da página)';
  } catch (e) {
    return 'Não consegui agir nesta página: ' + e.message;
  }
}

/* o painel pergunta o endereço ou pede uma ação */
chrome.runtime.onMessage.addListener((msg, _rem, responder) => {
  if (msg.tipo === 'endereco') { endereco().then(responder); return true; }
  if (msg.tipo === 'agir') {
    executarNaPagina(msg.acao, msg.args || {})
      .then(resultado => responder({ resultado }))
      .catch(e => responder({ resultado: 'Falha: ' + e.message }));
    return true;
  }
});
