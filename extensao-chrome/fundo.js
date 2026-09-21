/* Bigode — Venure
   Service worker: abre o painel e alimenta o Bigode com o conteúdo da página. */

const PADRAO = 'http://localhost:7000';

/* Ultimo endereco lido, guardado aqui de proposito.
   `ehOProprioBigode` precisa dele e e uma funcao sincrona -- nao pode
   esperar o storage. Fica desatualizado por no maximo uma chamada, e o
   pior caso e pular uma aba a mais uma vez. */
let ENDERECO_ATUAL = PADRAO;

async function endereco() {
  const { url } = await chrome.storage.sync.get('url');
  ENDERECO_ATUAL = (url || PADRAO).replace(/\/+$/, '');
  return ENDERECO_ATUAL;
}

/* O acesso da extensão é próprio, separado do navegador: você entra nas
   opções com e-mail e senha, e o Bigode devolve um token. Só o token fica
   guardado — a senha não.

   Não dá para usar o cookie do navegador no lugar disso: uma chamada da
   extensão para localhost é cross-site e o cookie tem SameSite=Lax, então o
   Chrome não o envia. Cabeçalho não obedece a SameSite. */
/* O cracha e POR ENDERECO.

   Antes havia um so, guardado em `token`. Funcionava enquanto o Bigode
   morava em um lugar unico. Ele pode estar neste computador (localhost) ou
   em outra maquina da rede -- e o cracha de um NAO vale no outro: sao
   servidores diferentes, com sessoes diferentes.

   Com um cracha so, trocar de destino derrubava o acesso sem avisar: a
   extensao mandava a chave errada, tomava 401 e ficava muda. Guardando por
   endereco, os dois logins convivem e alternar deixa de custar um login. */
async function token() {
  const base = await endereco();
  const d = await chrome.storage.local.get(['tokens', 'token']);
  const porEndereco = (d.tokens || {})[base];
  if (porEndereco) return porEndereco.trim();
  // Compatibilidade: quem ja tinha o cracha antigo continua entrando.
  return (d.token || '').trim();
}

async function guardarToken(base, valor) {
  const d = await chrome.storage.local.get('tokens');
  const tokens = d.tokens || {};
  tokens[base] = valor;
  await chrome.storage.local.set({ tokens });
}

async function cabecalhos(extra) {
  const t = await token();
  const h = Object.assign({}, extra || {});
  if (t) h['X-Cerebro-Sessao'] = t;
  return h;
}

/* clique no ícone abre o painel lateral */
chrome.action.onClicked.addListener(aba => {
  chrome.sidePanel.open({ tabId: aba.id });
});
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});

/* menus de contexto */
const MENUS = [
  { id: 'perguntar', title: 'Perguntar ao Bigode sobre isto', contexts: ['selection'] },
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

/* A aba onde trabalhar.

   O DEFEITO DE 25/08 — o Bigode se leu no espelho.

   O Fred perguntou "o que você vê na tela?". A aba na frente era a tela do
   PRÓPRIO Bigode. A extensão leu aquela página, e o que estava escrito ali
   era a resposta anterior dele mesmo:

       "Como IA, não posso acessar seu navegador."

   Esse texto voltou como se fosse conteúdo de site. O Bigode leu a própria
   frase antiga, tratou como resultado da ferramenta, e repetiu — parecendo
   que a extensão tinha falhado quando ela funcionou perfeitamente.

   Agora a aba do próprio Bigode é pulada: procuramos a primeira aba de site
   de verdade na mesma janela. Se só houver o Bigode aberto, dizemos isso com
   todas as letras, em vez de devolver o eco. */
/* 09/09: esta lista só conhecia endereço de rede local. Com o Bigode no
   Colab, o endereço dele era um `trycloudflare.com` — e a aba do próprio
   Bigode voltava a ser tratada como site comum, trazendo de volta o eco que
   este bloco inteiro existe para evitar.

   18/09: DUAS DESSAS REGRAS VIRARAM DEFEITO.

   `trycloudflare.com` entrou por causa do Colab, que saiu do projeto. Hoje
   ela só faz mal: qualquer página hospedada num túnel do Cloudflare — de
   terceiros, inclusive — era tratada como "a tela do próprio Bigode" e o
   Bigode se recusava a lê-la, dizendo que não havia site nenhum aberto.

   `192.168.x.x` tinha o mesmo problema, maior: a página do seu roteador, um
   NAS, uma impressora, um servidor de desenvolvimento de um colega — tudo
   isso mora em 192.168 e nada disso é o Bigode. Pedir "leia esta tela"
   nessas páginas devolvia a recusa, e a recusa mentia sobre o motivo.

   As duas eram generalizações a partir de um caso. O que interessa é uma
   pergunta só: esta aba É o Bigode? Quem responde isso com precisão é o
   ENDERECO_ATUAL, que o painel já mantém — seja ele localhost ou o IP de
   outra máquina. O localhost fica porque é o caso normal e porque a porta
   pode variar; o resto sai. */
function ehOProprioBigode(url) {
  const u = url || '';
  if (/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(u)) return true;
  try {
    const base = (ENDERECO_ATUAL || '').replace(/\/+$/, '');
    if (base && u.replace(/\/+$/, '').startsWith(base)) return true;
  } catch (e) { /* ainda não sabemos o endereço; a regra acima já cobre */ }
  return false;
}
function ehPaginaInterna(url) {
  return /^(chrome|edge|about|chrome-extension|devtools|view-source):/i.test(url || '');
}

async function abaAtiva() {
  const [ativa] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (ativa && !ehOProprioBigode(ativa.url) && !ehPaginaInterna(ativa.url)) return ativa;

  /* A da frente não serve. Procura a aba de site mais recente na janela. */
  const todas = await chrome.tabs.query({ lastFocusedWindow: true });
  const boas = todas.filter(t => !ehOProprioBigode(t.url) && !ehPaginaInterna(t.url));
  if (boas.length) {
    boas.sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0));
    return boas[0];
  }
  return ativa || null;   // só sobrou o Bigode; quem chamou avisa
}

async function garantirScript(abaId) {
  try {
    await chrome.scripting.executeScript({ target: { tabId: abaId }, files: ['conteudo.js'] });
  } catch (e) { /* já injetado ou página protegida */ }
}

async function executarNaPagina(acao, args) {
  const aba = await abaAtiva();
  if (!aba) return 'Não encontrei uma aba ativa no Chrome para trabalhar.';

  /* Só sobrou a tela do próprio Bigode. Dizer isso é muito melhor que ler a
     própria página e devolver o eco da conversa como se fosse um site. */
  if (ehOProprioBigode(aba.url)) {
    return 'A única aba aberta no Chrome é a tela do próprio Bigode. ' +
           'Não há site nenhum para eu ler. Abra uma aba com o site que você ' +
           'quer que eu veja e peça de novo.';
  }
  if (ehPaginaInterna(aba.url)) {
    return 'Só encontrei páginas internas do Chrome abertas (chrome://). ' +
           'O navegador não permite que nenhuma extensão leia essas páginas. ' +
           'Abra um site comum e tente de novo.';
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
    try {
      const leitura = await chrome.tabs.sendMessage(aba.id, {
        tipo: 'cerebro-acao', acao: 'ver', args: {}
      });
      return 'Abri ' + url + '. Esta é a página que apareceu:\n\n' +
        (leitura?.resultado || '(não consegui ler a página)');
    } catch (e) {
      return 'Abri ' + url + ', mas não consegui ler o conteúdo desta página ainda.';
    }
  }

  await garantirScript(aba.id);
  try {
    const r = await chrome.tabs.sendMessage(aba.id, { tipo: 'cerebro-acao', acao, args });
    return r?.resultado || r?.erro || '(sem retorno da página)';
  } catch (e) {
    return 'Não consegui concluir essa ação nesta página. Detalhe técnico: ' + e.message;
  }
}

/* o painel pergunta o endereço ou pede uma ação */
chrome.runtime.onMessage.addListener((msg, _rem, responder) => {
  if (msg.tipo === 'endereco') { endereco().then(responder); return true; }
  if (msg.tipo === 'estado')   { responder({ ligado: ligado, motivo: motivo }); return; }
  if (msg.tipo === 'agir') {
    executarNaPagina(msg.acao, msg.args || {})
      .then(resultado => responder({ resultado }))
      .catch(e => responder({ resultado: 'Falha: ' + e.message }));
    return true;
  }
});

/* =======================================================================
   A LINHA DIRETA COM O BIGODE IA

   Antes, a ação do navegador vinha pela TELA: o Bigode mandava para a
   página e a página repassava para cá por postMessage. Só que isso exigia
   que o Bigode estivesse aberto DENTRO do painel lateral. Numa aba normal
   do Chrome, a página respondia sozinha "a extensão não está aberta" — e a
   extensão nunca ficava sabendo de nada. Era por isso que não funcionava.

   Agora é o contrário: a extensão pergunta ao servidor, de segundo em
   segundo, se há algo para fazer. Não importa mais onde o Bigode está
   aberto — nem se está aberto. Basta o Chrome estar rodando.
   ======================================================================= */

let ligado = false;
let motivo = 'iniciando';
let ocupado = false;

async function bater() {
  const base = await endereco();
  const t = await token();
  if (!t) {
    ligado = false;
    motivo = 'Sem acesso. Abra as opções da extensão e entre com seu '
           + 'e-mail e a senha do Bigode.';
    return 5000;
  }
  /* Quando o Bigode está em outra máquina, esta chamada atravessa a rede.
     A espera longa de 25s do lado do servidor é de propósito — é o que
     evita mil pedidos por minuto —, mas a rede pode cair no meio sem
     avisar, e aí a extensão ficaria pendurada para sempre.

     O relógio abaixo é a rede de segurança: 40 segundos e a gente desiste,
     tenta de novo. No endereço local isso nunca dispara. */
  const relogio = new AbortController();
  const corte = setTimeout(() => relogio.abort(), 40000);
  try {
    const r = await fetch(base + '/api/navegador/pendentes', {
      headers: await cabecalhos(),
      cache: 'no-store',
      signal: relogio.signal,
    });
    clearTimeout(corte);

    // Sem chave válida o servidor manda para o login e devolve HTML, não
    // JSON. Vale dizer isso com todas as letras em vez de morrer calado.
    if (r.status === 401 || r.status === 403 || r.redirected || !r.ok) {
      ligado = false;
      motivo = (r.status === 401 || r.status === 403 || r.redirected)
        ? 'Sua sessão expirou. Entre novamente nas opções da extensão.'
        : 'O Bigode respondeu com o código ' + r.status + '.';
      return 3000;
    }

    const d = await r.json();
    ligado = true; motivo = '';

    const acoes = (d && d.acoes) || [];

    /* O servidor segura esta chamada por até 25s quando não há trabalho
       (espera longa). Então voltar de mãos vazias já significa que 25s se
       passaram — não faz sentido esperar mais 1s antes de perguntar de
       novo. Voltamos na hora, e a linha fica aberta outra vez.

       É isso que mantém o service worker acordado: o Chrome só o mata
       quando ele fica realmente parado, e uma chamada aberta não é parada.
       Antes havia uma janela de silêncio a cada ciclo, e nela o Bigode via
       a extensão como desligada. */
    if (!acoes.length) return 50;

    // Uma por vez, na ordem. Duas ações simultâneas na mesma aba brigariam
    // pelo foco e o resultado seria imprevisível.
    ocupado = true;
    for (const a of acoes) {
      let resultado;
      try {
        resultado = await executarNaPagina(a.acao, a.args || {});
      } catch (e) {
        resultado = 'Não consegui concluir a ação no navegador. Detalhe técnico: ' + e.message;
      }
      try {
        await fetch(base + '/api/navegador', {
          method: 'POST',
          headers: await cabecalhos({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ id: a.id, resultado }),
        });
      } catch (e) { /* servidor caiu no meio; o Bigode trata pelo tempo */ }
    }
    ocupado = false;
    return 200;                       // provável que venha mais logo
  } catch (e) {
    clearTimeout(corte);
    ligado = false;
    if (e && e.name === 'AbortError') {
      // Foi o nosso relogio, nao um defeito. Volta na hora.
      motivo = '';
      return 100;
    }
    // 18/09: aqui dizia "O Colab desconectou? Rode o notebook de novo".
    // Nao ha notebook. Em endereco local, a causa quase sempre e uma so --
    // o BIGODE.bat fechado -- e dizer isso poupa procurar defeito na
    // extensao. Em endereco remoto sao tres causas possiveis, e listar as
    // tres e mais honesto do que escolher uma.
    const remoto = !/^https?:\/\/(localhost|127\.)/.test(base);
    motivo = remoto
      ? 'Nao alcancei o Bigode em ' + base + '. A outra maquina esta '
        + 'ligada, com o BIGODE.bat aberto, e no mesmo Wi-Fi?'
      : 'O Bigode nao respondeu em ' + base
        + '. Abra o BIGODE.bat no computador.';
    return 4000;                      // sem pressa quando não há ninguém
  }
}

let agendado = null;
async function laco() {
  clearTimeout(agendado);
  let proximo = 4000;
  try { proximo = await bater(); } catch (e) { /* nunca deixa o laço morrer */ }
  agendado = setTimeout(laco, proximo);
}

// O Chrome desliga o service worker quando ele fica parado. Cada resposta de
// fetch reinicia esse relógio, então o laço se sustenta enquanto há conversa.
// O alarme é a rede de segurança: se o Chrome matou mesmo assim, ele acorda
// e religa. É o mínimo permitido pelo Chrome (30s).
chrome.alarms.create('cerebro-laco', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(a => { if (a.name === 'cerebro-laco') laco(); });

chrome.runtime.onStartup.addListener(laco);
chrome.runtime.onInstalled.addListener(laco);
laco();
