/* Painel lateral do Bigode — Venure
   ---------------------------------------------------------------------
   Três estados, um de cada vez:

     telaOff    o Bigode não responde no endereço configurado
     telaLogin  responde, mas esta extensão ainda não entrou
     iframe     entrou: mostra o Bigode inteiro

   O acesso desta extensão é próprio, separado do navegador. Você entra
   aqui; o Bigode devolve um crachá (token); a extensão guarda o crachá e
   o manda no cabeçalho a cada chamada.

   Por que não aproveitar o login que você já fez na aba do Chrome: uma
   chamada de chrome-extension:// para localhost é cross-site, e o cookie
   do Bigode é SameSite=Lax — o Chrome não o envia. Cabeçalho não obedece
   a SameSite; daí o crachá.                                              */

const $ = i => document.getElementById(i);
const PADRAO = 'http://localhost:7000';
let base = PADRAO;
let tentativas = 0;

/* ---------- estados ---------- */

function mostrarTela(qual) {
  document.body.classList.toggle('dentro', qual === 'dentro');
  ['telaLogin', 'telaOff'].forEach(t => $(t).classList.toggle('on', t === qual));
}

function recado(texto, tipo) {
  const r = $('recado');
  r.textContent = texto || '';
  r.className = 'recado' + (texto ? ' on ' + (tipo || 'ruim') : '');
}

/* ---------- endereço e crachá ---------- */

async function pegarEndereco() {
  try {
    const r = await chrome.storage.sync.get('url');
    if (r && r.url) return String(r.url).replace(/\/+$/, '');
  } catch (e) { /* storage indisponível */ }
  return PADRAO;
}

/* O crachá é por endereço — o do computador não vale na nuvem e vice-versa.
   O `token` solto continua sendo lido para quem já estava logado antes
   desta mudança. */
/* `pegarEndereco`, e nao `endereco`.
   09/09: aqui e na linha do `entrar()` estava escrito `endereco()` -- nome
   que existe no fundo.js, e o fundo.js roda no service worker, que e outro
   contexto. Do lado do painel a funcao nunca existiu, e a chamada estourava
   ReferenceError FORA de qualquer try. Efeito: o painel lateral nao abria
   nem a tela de dentro nem a de login (ficava travado), e o login ate dava
   certo no servidor mas o cracha nunca era gravado. Em qualquer endereco --
   nao era coisa do tunel. */
async function pegarToken() {
  const base = await pegarEndereco();
  const d = await chrome.storage.local.get(['tokens', 'token']);
  const meu = (d.tokens || {})[base];
  return (meu || d.token || '').trim();
}

/* ---------- o Bigode está no ar? ---------- */

async function vivo() {
  try {
    const c = new AbortController();
    const t = setTimeout(() => c.abort(), 5000);
    const r = await fetch(base + '/api/login/estado', { signal: c.signal,
                                                       cache: 'no-store' });
    clearTimeout(t);
    if (!r.ok) { $('detalheOff').textContent = 'Respondeu ' + r.status; return false; }
    await r.json();
    $('detalheOff').className = 'recado';
    return true;
  } catch (e) {
    $('detalheOff').className = 'recado on ruim';
    $('detalheOff').textContent = e.name === 'AbortError'
      ? 'Sem resposta em 5 segundos.'
      : 'Não alcancei o endereço. ' + (e.message || '');
    return false;
  }
}

/* ---------- o crachá guardado ainda vale? ---------- */

async function crachaValido() {
  const t = await pegarToken();
  if (!t) return false;
  try {
    const r = await fetch(base + '/api/navegador/pendentes', {
      headers: { 'X-Cerebro-Sessao': t }, cache: 'no-store',
    });
    if (!r.ok || r.redirected) return false;
    await r.json();
    return true;
  } catch (e) { return false; }
}

/* ---------- decide o que mostrar ---------- */

async function decidir() {
  base = await pegarEndereco();
  $('ondeEsta').textContent = base;
  $('alvoOff').textContent = base;

  if (!(await vivo())) {
    mostrarTela('telaOff');
    tentativas++;
    clearTimeout(decidir._t);
    decidir._t = setTimeout(decidir, Math.min(4000 + tentativas * 1500, 15000));
    return;
  }
  tentativas = 0;

  if (await crachaValido()) {
    mostrarTela('dentro');
    if ($('quadro').src !== base + '/') $('quadro').src = base + '/';
    setTimeout(entregarPendente, 1200);
    return;
  }

  // No ar, mas sem crachá válido: pede para entrar.
  mostrarTela('telaLogin');
  const { usuario } = await chrome.storage.local.get('usuario');
  if (usuario && !$('email').value) $('email').value = usuario;
}

/* ---------- entrar ---------- */

async function entrar() {
  const email = $('email').value.trim();
  const senha = $('senha').value;
  if (!email || !senha) return recado('Para conectar, preciso do seu e-mail e da sua senha.', 'ruim');

  $('btEntrar').disabled = true;
  recado('Vou conectar ao Bigode…', 'espera');

  let d;
  try {
    const r = await fetch(base + '/api/login/entrar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, senha }),
    });
    d = await r.json();
  } catch (e) {
    $('btEntrar').disabled = false;
    return recado('Não consegui falar com o Bigode em ' + base + '. Confira se '
                + 'ele está aberto no computador.', 'ruim');
  }

  $('btEntrar').disabled = false;

  if (!d || !d.ok) {
    return recado((d && d.erro) || 'Não consegui confirmar esse e-mail e essa senha.', 'ruim');
  }

  // O Bigode do pendrive pode ser mais antigo que esta extensão e não
  // devolver o crachá. Dizer isso é melhor que ficar tentando em silêncio.
  if (!d.token) {
    return recado('Entrou, mas este Bigode não devolveu o crachá — ele está '
                + 'desatualizado. Rode o enviar-cerebro-pendrive.ps1, feche a '
                + 'janela do motor e abra de novo.', 'ruim');
  }

  // Guarda o crachá NO ENDEREÇO em que o login aconteceu. Assim o login do
  // computador e o da nuvem convivem, e alternar entre eles não pede senha
  // de novo.
  {
    const base = await pegarEndereco();          // ver a nota em pegarToken
    const guardados = await chrome.storage.local.get('tokens');
    const tokens = guardados.tokens || {};
    tokens[base] = d.token;
    await chrome.storage.local.set({ tokens, usuario: d.nome || email });
  }
  $('senha').value = '';                       // a senha morre aqui
  recado('Conectado. Vou acompanhar o Bigode por este Chrome.', 'bom');
  setTimeout(decidir, 500);
}

/* ---------- texto vindo do menu de contexto ---------- */

async function entregarPendente() {
  const { pendente } = await chrome.storage.local.get('pendente');
  if (!pendente) return;
  await chrome.storage.local.remove('pendente');
  try {
    $('quadro').contentWindow.postMessage(
      { origem: 'cerebro-extensao', acao: 'inserir', texto: pendente.texto }, '*');
  } catch (e) { /* iframe ainda carregando */ }
}

chrome.storage.onChanged.addListener((mudou, area) => {
  if (area === 'local' && mudou.pendente && mudou.pendente.newValue) entregarPendente();
  if (area === 'sync' && mudou.url) decidir();
});

/* Ação de navegador NÃO passa por aqui: quem busca no servidor e executa é o
   fundo.js. Se este arquivo também tratasse, cada ação rodaria duas vezes. */
window.addEventListener('message', ev => {
  const d = ev.data;
  if (d && d.origem === 'Bigode' && d.acao === 'pronto') entregarPendente();
});

/* ---------- botões ---------- */

$('btEntrar').addEventListener('click', entrar);
['email', 'senha'].forEach(id =>
  $(id).addEventListener('keydown', e => { if (e.key === 'Enter') entrar(); }));

$('btOlho').addEventListener('click', () => {
  const s = $('senha');
  s.type = s.type === 'password' ? 'text' : 'password';
  s.focus();
});

$('btTentar').addEventListener('click', () => { tentativas = 0; decidir(); });
$('btEndereco').addEventListener('click', () => chrome.runtime.openOptionsPage());
$('btOpcoes2').addEventListener('click', () => chrome.runtime.openOptionsPage());

decidir();
