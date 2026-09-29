/* MODO CONVERSA DO BIGODE — "Ei, Bigode" e ele responde falando
   venure.com.br · 28/09/2026

   COMO FUNCIONA (sem mãos)

     1. DORMINDO   o microfone espera a palavra "Bigode".
     2. OUVINDO    bip -> você faz a pergunta (o Whisper transcreve).
                   Se você já falou tudo junto ("Ei Bigode, que horas são?"),
                   ele pula esta etapa.
     3. PENSANDO   a pergunta vai sozinha para o chat.
     4. FALANDO    a resposta é lida FRASE POR FRASE enquanto ainda está
                   sendo escrita -- não espera o texto inteiro.
     5. volta ao 1.

   DOIS JEITOS DE OUVIR A PALAVRA "BIGODE"

     a) Reconhecimento do Chrome: instantâneo e grátis, mas o áudio da
        escuta passa pelo Google. Só funciona em aba normal (não na barra
        lateral da extensão).
     b) Whisper na sua Modal (reserva automática): cada frase curta que o
        microfone pega vai para o SEU Whisper. Mais privado, ~1 s mais lento,
        e gasta alguns centavos de placa por dia de uso.
   A pergunta em si vai SEMPRE para o Whisper quando ele está ligado.

   USO:  Conversa.ligar({ entrada, enviarAgora, whisperLigado, transcrever,
                          faixa, botao });
         Conversa.alternar();                       // liga / desliga
         Conversa.trecho(texto)                     // a cada pedaço da resposta
         Conversa.fimDaResposta()                   // quando a resposta termina
         Conversa.descartar()                       // resposta foi apagada
*/
(function (raiz) {
  'use strict';

  const WAKE = /\b(?:b[iy]\s?-?g[oóôu]d[eéiy]s?|vig[oó]de|bigodinho)\b/i;
  const FALA = 0.015, SILENCIO_SEG_MS = 750, MAX_SEG_MS = 7000, MIN_SEG_MS = 350;

  const E = {
    cfg: null, ativo: false, fase: 'off', motor: '',
    rec: null, recVivo: false, recFalhas: 0,
    mic: null,                  // captação própria (motor Whisper)
    fila: [], tocando: null, buf: '', emCodigo: false, avisouCodigo: false,
    respostaAcabou: true, geracao: 0, relogioAtento: null, audioCtx: null,
  };

  const $ = x => (typeof x === 'function' ? x() : x);

  /* ------------------------------------------------------------ faixa */
  function faixa(texto, botoes) {
    const onde = $(E.cfg.faixa);
    let el = document.getElementById('faixaConversa');
    if (texto === null) { if (el) el.remove(); return; }
    if (!onde) return;
    if (!el) {
      el = document.createElement('div');
      el.id = 'faixaConversa';
      el.className = 'ouvindo conversa-faixa';
      el.style.cssText = 'display:flex;align-items:center;gap:9px;margin-top:9px;flex-wrap:wrap;'
        + 'padding:9px 12px;border-radius:11px;font-size:12.5px;'
        + 'border:1px solid var(--linha2,#2A313E);background:var(--sup,#11141B)';
      onde.appendChild(el);
    }
    const P = {
      dormindo: '<path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1v-7h3zM3 19a2 2 0 0 0 2 2h1v-7H3z"/>',
      ouvindo: '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M19 10v1a7 7 0 0 1-14 0v-1M12 18v4"/>',
      pensando: '<path d="M21 12a9 9 0 1 1-6.2-8.6"/>',
      falando: '<path d="M11 5 6 9H2v6h4l5 4V5Z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/>',
    };
    const icone = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
      + 'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">' + (P[E.fase] || P.dormindo) + '</svg>';
    el.innerHTML = '<span style="display:inline-flex;color:var(--ac,#9DC08B)">' + icone
      + '</span><span style="flex:1;min-width:160px"></span>';
    el.children[1].textContent = texto;
    (botoes || []).forEach(([rotulo, acao]) => {
      const b = document.createElement('button');
      b.className = 'tag'; b.textContent = rotulo; b.onclick = acao;
      b.style.cssText = 'cursor:pointer';
      el.appendChild(b);
    });
  }

  function mostrar() {
    if (!E.ativo) return faixa(null);
    const desligar = ['Desligar', () => desligar()];
    if (E.fase === 'dormindo')
      faixa('Modo conversa: diga “Ei, Bigode” e faça a pergunta.'
        + (E.motor === 'whisper' ? ' (escuta pelo seu Whisper)' : ''), [desligar]);
    else if (E.fase === 'ouvindo') faixa('Pode falar — eu encerro quando você calar.', [desligar]);
    else if (E.fase === 'pensando') faixa('Pensando… já começo a responder falando.', [['Parar', pararTudo], desligar]);
    else if (E.fase === 'falando') faixa('Falando… (Esc para calar)', [['Calar', calar], desligar]);
  }

  function fase(f) {
    E.fase = f;
    const b = $(E.cfg.botao);
    if (b) b.classList.toggle('gravando', E.ativo);
    mostrar();
  }

  /* ------------------------------------------------------------ bip */
  function bip(freq, ms) {
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      E.audioCtx = E.audioCtx || new AC();
      const o = E.audioCtx.createOscillator(), g = E.audioCtx.createGain();
      o.frequency.value = freq || 880; o.type = 'sine';
      g.gain.setValueAtTime(0.0001, E.audioCtx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.18, E.audioCtx.currentTime + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, E.audioCtx.currentTime + (ms || 140) / 1000);
      o.connect(g); g.connect(E.audioCtx.destination);
      o.start(); o.stop(E.audioCtx.currentTime + (ms || 140) / 1000 + 0.02);
    } catch (e) {}
  }

  /* ------------------------------------------------------------ palavra de ativação */
  function acharWake(texto) {
    const m = String(texto || '').match(WAKE);
    if (!m) return null;
    return texto.slice(m.index + m[0].length).replace(/^[\s,.!?:;-]+/, '').trim();
  }

  function aoOuvirFrase(texto) {
    if (!E.ativo || E.fase !== 'dormindo') return;
    const resto = acharWake(texto);
    if (resto === null) return;
    if (resto.split(/\s+/).filter(Boolean).length >= 2) {
      bip(990, 110);
      return mandar(resto);
    }
    ouvirPergunta();
  }

  /* --- motor A: reconhecimento do Chrome --- */
  function iniciarChrome() {
    const R = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!R) return false;
    const rec = new R();
    rec.lang = 'pt-BR'; rec.continuous = true; rec.interimResults = false;
    rec.onresult = ev => {
      for (let i = ev.resultIndex; i < ev.results.length; i++)
        if (ev.results[i].isFinal) aoOuvirFrase(ev.results[i][0].transcript);
    };
    rec.onerror = ev => {
      const q = (ev && ev.error) || '';
      if (q === 'not-allowed' || q === 'service-not-allowed' || q === 'network' || q === 'audio-capture') {
        E.recFalhas = 99;                       // não adianta insistir: troca de motor
      }
    };
    rec.onend = () => {
      E.recVivo = false;
      if (!E.ativo || E.fase !== 'dormindo' || E.rec !== rec) return;
      if (E.recFalhas >= 99) { E.rec = null; return iniciarWhisper(); }
      setTimeout(() => { if (E.ativo && E.fase === 'dormindo' && E.rec === rec) tentar(rec); }, 250);
    };
    E.rec = rec; E.motor = 'chrome';
    return tentar(rec);
  }
  function tentar(rec) {
    try { rec.start(); E.recVivo = true; return true; } catch (e) { return false; }
  }
  function pararChrome() {
    const r = E.rec; E.rec = null;
    if (r) { try { r.abort(); } catch (e) {} }
    E.recVivo = false;
  }

  /* --- motor B: frases curtas para o seu Whisper --- */
  async function iniciarWhisper() {
    if (!E.cfg.whisperLigado()) {
      faixa('O Chrome não liberou a escuta aqui e o Whisper não está ligado. '
        + 'Abra o Bigode numa aba normal (http://localhost:7000) ou publique o modal_voz.py.',
        [['Fechar', () => desligar()]]);
      return false;
    }
    E.motor = 'whisper';
    try {
      const fluxo = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      const AC = window.AudioContext || window.webkitAudioContext;
      const ctx = new AC(), fonte = ctx.createMediaStreamSource(fluxo);
      const no = ctx.createScriptProcessor(4096, 1, 1);
      const m = { fluxo, ctx, no, taxa: ctx.sampleRate, seg: [], antes: [], falando: false, calouEm: 0, inicio: 0 };
      no.onaudioprocess = ev => {
        if (!E.ativo || E.fase !== 'dormindo') return;
        const bloco = new Float32Array(ev.inputBuffer.getChannelData(0));
        let soma = 0; for (let i = 0; i < bloco.length; i++) soma += bloco[i] * bloco[i];
        const nivel = Math.sqrt(soma / bloco.length), agora = Date.now();
        if (!m.falando) {
          m.antes.push(bloco); if (m.antes.length > 3) m.antes.shift();   // guarda o comecinho da palavra
          if (nivel > FALA) { m.falando = true; m.inicio = agora; m.calouEm = 0; m.seg = m.antes.slice(); m.antes = []; }
          return;
        }
        m.seg.push(bloco);
        if (nivel > FALA) m.calouEm = 0; else if (!m.calouEm) m.calouEm = agora;
        const longa = agora - m.inicio > MAX_SEG_MS;
        if ((m.calouEm && agora - m.calouEm > SILENCIO_SEG_MS) || longa) {
          const partes = m.seg; m.seg = []; m.falando = false;
          const dur = agora - m.inicio;
          if (!longa && dur > MIN_SEG_MS) enviarSegmento(partes, m.taxa);   // conversa longa não é chamado
        }
      };
      fonte.connect(no); no.connect(ctx.destination);
      E.mic = m;
      mostrar();
      return true;
    } catch (e) {
      faixa('Não consegui usar o microfone para o modo conversa.', [['Fechar', () => desligar()]]);
      return false;
    }
  }
  async function enviarSegmento(partes, taxa) {
    try {
      const U = raiz.Voz && raiz.Voz.util;
      if (!U) return;
      const total = partes.reduce((s, a) => s + a.length, 0);
      const wav = U.montarWav(U.juntar(partes, total), taxa, 16000);
      const r = await E.cfg.transcrever(wav);
      if (r && r.ok && r.texto) aoOuvirFrase(String(r.texto));
    } catch (e) {}
  }
  function pararWhisper() {
    const m = E.mic; E.mic = null;
    if (!m) return;
    try { m.no.disconnect(); } catch (e) {}
    try { m.fluxo.getTracks().forEach(t => t.stop()); } catch (e) {}
    try { m.ctx.close(); } catch (e) {}
  }

  function pararEscuta() { pararChrome(); pararWhisper(); }

  function dormir() {
    if (!E.ativo) return;
    clearTimeout(E.relogioAtento);
    fase('dormindo');
    if (E.motor === 'whisper' || E.recFalhas >= 99) { if (!E.mic) iniciarWhisper(); }
    else if (!E.rec) { if (!iniciarChrome()) iniciarWhisper(); }
  }

  /* ------------------------------------------------------------ a pergunta */
  function ouvirPergunta() {
    pararEscuta();
    fase('ouvindo');
    bip(880, 150);
    if (E.cfg.whisperLigado() && raiz.Voz) {
      setTimeout(() => raiz.Voz.ouvir({ semFalaMs: 8000 }), 180);   // depois do bip, para não gravá-lo
      return;
    }
    // Sem Whisper: a própria pergunta sai do reconhecimento do Chrome.
    const R = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!R) return dormir();
    const rec = new R(); rec.lang = 'pt-BR'; rec.continuous = false; rec.interimResults = false;
    let veio = false;
    rec.onresult = ev => { veio = true; mandar(ev.results[0][0].transcript); };
    rec.onend = () => { if (!veio && E.ativo && E.fase === 'ouvindo') dormir(); };
    try { rec.start(); } catch (e) { dormir(); }
  }

  function mandar(texto) {
    texto = String(texto || '').trim();
    if (!texto) return dormir();
    pararEscuta();
    if (!E.cfg.enviarAgora(texto)) dormir();      // o Bigode não aceitou (motor desligado)
  }

  /* Voz.js terminou de transcrever uma pergunta feita no modo conversa. */
  function aoTranscrever() {
    if (!E.ativo || E.fase !== 'ouvindo') return false;
    if (!E.cfg.enviarAgora(null)) dormir();       // o texto já está na caixa
    return true;
  }

  /* Chamado pelo enviar() do Bigode: toda resposta, falada ou digitada,
     é lida em voz alta enquanto o modo conversa estiver ligado. */
  function preparar() {
    if (!E.ativo) return;
    pararEscuta();
    novaResposta();
    fase('pensando');
  }
  function aoFalharPergunta() { if (E.ativo && E.fase === 'ouvindo') dormir(); }

  /* ------------------------------------------------------------ falar em frases */
  function novaResposta() {
    calar();
    E.geracao++; E.buf = ''; E.emCodigo = false; E.avisouCodigo = false; E.respostaAcabou = false;
  }

  function limpar(t) {
    return t
      .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
      .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
      .replace(/https?:\/\/\S+/g, 'o link')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/[*_#>|~]+/g, ' ')
      .replace(/^\s*[-•]\s+/gm, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function trecho(texto) {
    if (!E.ativo || E.respostaAcabou) return;
    E.buf += String(texto || '');
    // blocos de código não são lidos: vira um aviso só
    let saida = '';
    while (E.buf.length) {
      const i = E.buf.indexOf('```');
      if (i < 0) {
        if (E.emCodigo) { E.buf = E.buf.slice(-2); break; }   // pode ser o começo de ```
        const resto = (E.buf.match(/`{1,2}$/) || [''])[0];     // ``` pode chegar partido
        saida += E.buf.slice(0, E.buf.length - resto.length); E.buf = resto; break;
      }
      if (!E.emCodigo) saida += E.buf.slice(0, i);
      else if (!E.avisouCodigo) { saida += ' Deixei o código na tela. '; E.avisouCodigo = true; }
      E.emCodigo = !E.emCodigo;
      E.buf = E.buf.slice(i + 3);
    }
    E.pendente = (E.pendente || '') + saida;
    cortarFrases(false);
  }

  function cortarFrases(tudo) {
    let p = E.pendente || '';
    const primeira = !E.fila.length && !E.tocando;
    const minimo = primeira ? 18 : 60;
    for (;;) {
      const re = /[.!?…:;](?=\s)|\n+/g;
      let m, corte = -1;
      while ((m = re.exec(p))) { if (m.index + 1 >= minimo) { corte = m.index + m[0].length; break; } }
      if (corte < 0 && p.length > 380) corte = p.lastIndexOf(' ', 380) + 1 || 380;
      if (corte <= 0) break;
      enfileirar(p.slice(0, corte)); p = p.slice(corte);
    }
    if (tudo && p.trim()) { enfileirar(p); p = ''; }
    E.pendente = p;
  }

  function enfileirar(bruto) {
    const t = limpar(bruto);
    if (!t || !/[\wÀ-ú]/.test(t)) return;
    const item = { texto: t, geracao: E.geracao, pronto: null };
    item.pronto = fetch('/api/falar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto: t }) }).then(r => r.json()).catch(() => ({ ok: false }));
    E.fila.push(item);
    if (!E.tocando) tocarProximo();
  }

  async function tocarProximo() {
    const item = E.fila.shift();
    if (!item) {
      E.tocando = null;
      if (E.respostaAcabou && E.ativo) setTimeout(() => { if (!E.tocando && !E.fila.length) dormir(); }, 500);
      return;
    }
    if (item.geracao !== E.geracao) return tocarProximo();
    E.tocando = item;
    if (E.fase !== 'falando') fase('falando');
    const r = await item.pronto;
    if (item.geracao !== E.geracao || E.tocando !== item) return;
    const seguir = () => { if (E.tocando === item) { E.tocando = null; tocarProximo(); } };
    if (r && r.ok && r.wav) {
      const a = new Audio('data:audio/wav;base64,' + r.wav);
      item.audio = a;
      a.onended = seguir; a.onerror = seguir;
      a.play().catch(seguir);
    } else if (window.speechSynthesis) {
      // Voz da Modal fora do ar: usa a voz do próprio navegador.
      const u = new SpeechSynthesisUtterance(item.texto);
      u.lang = 'pt-BR'; u.rate = 1.05; u.onend = seguir; u.onerror = seguir;
      item.sintese = true;
      window.speechSynthesis.speak(u);
    } else seguir();
  }

  function fimDaResposta() {
    if (!E.ativo) return;
    E.respostaAcabou = true;
    cortarFrases(true);
    if (!E.tocando && !E.fila.length) setTimeout(() => { if (!E.tocando && !E.fila.length) dormir(); }, 400);
  }

  function calar() {
    E.geracao++;
    E.fila = []; E.pendente = '';
    const t = E.tocando; E.tocando = null;
    if (t && t.audio) { try { t.audio.pause(); } catch (e) {} }
    if (t && t.sintese && window.speechSynthesis) { try { window.speechSynthesis.cancel(); } catch (e) {} }
    if (E.ativo && E.fase === 'falando') { E.respostaAcabou = true; dormir(); }
  }

  function pararTudo() {
    if (E.cfg.parar) { try { E.cfg.parar(); } catch (e) {} }
    calar(); E.respostaAcabou = true; dormir();
  }

  function descartar() { if (E.ativo) { const g = E.respostaAcabou; calar(); E.respostaAcabou = g; } }

  /* ------------------------------------------------------------ liga / desliga */
  function ligar() {
    if (E.ativo) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      faixa('Neste endereço o navegador não libera o microfone. Abra por http://localhost:7000.',
        [['Fechar', () => faixa(null)]]);
      return;
    }
    E.ativo = true; E.recFalhas = 0;
    let preferencia = '';
    try { preferencia = localStorage.getItem('bigode_conversa_motor') || ''; } catch (e) {}
    // Dentro da barra lateral da extensão o reconhecimento do Chrome não funciona.
    E.motor = (preferencia === 'whisper' || window.self !== window.top) ? 'whisper' : 'chrome';
    if (E.motor === 'whisper') E.recFalhas = 99;
    bip(660, 90); setTimeout(() => bip(990, 110), 120);
    dormir();
  }

  function desligar() {
    E.ativo = false;
    pararEscuta();
    calar();
    if (raiz.Voz && raiz.Voz.gravando && raiz.Voz.gravando()) raiz.Voz.parar();
    E.fase = 'off';
    const b = $(E.cfg.botao); if (b) b.classList.remove('gravando');
    faixa(null);
  }

  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape' && E.ativo && (E.tocando || E.fila.length)) calar();
  });

  raiz.Conversa = {
    ligar(cfg) { E.cfg = cfg; },
    alternar() { E.ativo ? desligar() : ligar(); },
    desligar, calar, trecho, fimDaResposta, descartar, preparar,
    aoTranscrever, aoFalharPergunta,
    ativo: () => E.ativo,
    fase: () => E.fase,
    usarMotor(m) { try { localStorage.setItem('bigode_conversa_motor', m); } catch (e) {} },
    _teste: { acharWake, limpar, estado: E },
  };
})(window);
