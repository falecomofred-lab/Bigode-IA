/* VOZ DA VENURE — uma captação, três telas
   Bigode (web e barra lateral do Chrome) e Pipi IA
   venure.com.br · 17/09/2026

   COMO SE USA

     Voz.ligar({
       campo:   document.getElementById('entrada'),   // onde o texto entra
       botao:   document.getElementById('btMic'),     // o microfone
       faixa:   () => document.getElementById('ctx'), // onde pendurar o aviso
       enviar:  wav => fetch('/api/transcrever', {...}).then(r => r.json()),
       aoTerminar: texto => {}                        // opcional
     });

   POR QUE UM ARQUIVO SÓ
     A captação estava escrita duas vezes: uma no index.html do Bigode,
     outra no da Pipi. Código igual em dois lugares vira código diferente
     em duas semanas -- e aí só uma das telas ganha o conserto.

     É a mesma razão do venure.css, e a mesma lição que o motor de texto
     deu hoje: três caminhos fazendo a mesma coisa custam três vezes e
     divergem sozinhos.

   ===================================================================
   O QUE MUDA EM RELAÇÃO AO QUE HAVIA
   ===================================================================

   1. PARA SOZINHO QUANDO VOCÊ CALA.
      Antes era preciso clicar em "Parar". Isso obriga a mão a voltar ao
      mouse justamente quando a graça era não usar as mãos -- e quem
      esquece de clicar fica gravando silêncio, que o Whisper depois
      transcreve como invenção.

      Aqui o volume é medido 20 vezes por segundo. Depois de ouvir fala,
      1,3 s de silêncio encerra. É o comportamento do ditado do Gemini e
      do Android, e é o que faz a coisa parecer natural.

   2. MOSTRA QUE ESTÁ OUVINDO.
      Barras que mexem com a sua voz. Sem isso não dá para saber se o
      microfone certo foi pego, e você só descobre no fim, quando volta
      vazio.

   3. NÃO GRAVA O SILÊNCIO INICIAL.
      Só começa a contar depois de ouvir a primeira fala. Você pode
      clicar, respirar e falar.

   4. AVISA QUANDO NÃO OUVIU NADA.
      Em vez de mandar 4 segundos de silêncio para o Whisper e receber
      uma frase inventada de volta.                                      */

(function (raiz) {
  'use strict';

  /* Limiares. Medidos no notebook do Fred com microfone embutido -- que é
     o pior caso: capta o ventilador. Em headset o valor fica bem acima. */
  const FALA = 0.012;        // acima disto é voz, não ruído de fundo
  const SILENCIO_MS = 1300;  // silêncio que encerra, depois de haver fala
  const MAXIMO_MS = 120000;  // teto absoluto: 2 min por gravação
  const MINIMO_S = 0.4;      // menos que isto não vale mandar

  const estado = {
    gravando: false, fluxo: null, ctx: null, no: null,
    amostras: [], taxa: 48000, relogio: null, cfg: null,
  };

  function $(x) { return typeof x === 'function' ? x() : x; }

  /* ---------- a faixa de "ouvindo", com as barrinhas ---------- */
  function faixa(texto, nivel) {
    const onde = $(estado.cfg.faixa);
    if (!onde) return;
    let e = document.getElementById('vozFaixa');
    if (texto === null) { if (e) e.remove(); return; }
    if (!e) {
      e = document.createElement('div');
      e.id = 'vozFaixa';
      e.className = 'ouvindo';
      e.style.cssText = 'display:flex;align-items:center;gap:9px;margin-top:9px;'
        + 'padding:9px 12px;border-radius:11px;font-size:12.5px;'
        + 'border:1px solid var(--linha2,#333);background:rgba(127,127,127,.08)';
      e.innerHTML = '<span id="vozBarras" style="display:flex;align-items:center;'
        + 'gap:2.5px;height:16px;flex-shrink:0"></span>'
        + '<span id="vozTexto" style="flex:1"></span>'
        + '<button id="vozParar" style="background:none;border:0;cursor:pointer;'
        + 'color:var(--ac,#888);font:inherit;font-size:12px">Parar</button>';
      onde.appendChild(e);
      e.querySelector('#vozParar').onclick = () => encerrar(true);
      const b = e.querySelector('#vozBarras');
      for (let i = 0; i < 5; i++) {
        const t = document.createElement('i');
        t.style.cssText = 'width:2.5px;height:4px;border-radius:2px;'
          + 'background:var(--ac,#888);transition:height .08s';
        b.appendChild(t);
      }
    }
    e.querySelector('#vozTexto').textContent = texto;
    if (nivel != null) {
      const barras = e.querySelectorAll('#vozBarras i');
      barras.forEach((t, i) => {
        /* Cada barra reage a uma fatia do volume, para o conjunto parecer
           um medidor e não cinco cópias da mesma coisa. */
        const alvo = Math.max(0, Math.min(1, (nivel * 9) - i * 0.12));
        t.style.height = (4 + alvo * 12).toFixed(1) + 'px';
      });
    }
  }

  /* ---------- WAV 16 kHz mono, que é o que o Whisper quer ---------- */
  function juntar(lista, total) {
    const s = new Float32Array(total); let i = 0;
    lista.forEach(a => { s.set(a, i); i += a.length; });
    return s;
  }
  function reamostrar(d, de, para) {
    if (de === para) return d;
    const r = de / para, s = new Float32Array(Math.round(d.length / r));
    for (let i = 0; i < s.length; i++) {
      const p = i * r, a = Math.floor(p), b = Math.min(a + 1, d.length - 1);
      s[i] = d[a] + (d[b] - d[a]) * (p - a);
    }
    return s;
  }
  function montarWav(d, de, para) {
    const pcm = reamostrar(d, de, para);
    const buf = new ArrayBuffer(44 + pcm.length * 2), v = new DataView(buf);
    const tx = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    tx(0, 'RIFF'); v.setUint32(4, 36 + pcm.length * 2, true); tx(8, 'WAVE');
    tx(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
    v.setUint16(22, 1, true); v.setUint32(24, para, true);
    v.setUint32(28, para * 2, true); v.setUint16(32, 2, true);
    v.setUint16(34, 16, true); tx(36, 'data');
    v.setUint32(40, pcm.length * 2, true);
    let o = 44;
    for (let i = 0; i < pcm.length; i++, o += 2) {
      const s = Math.max(-1, Math.min(1, pcm[i]));
      v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buf;
  }

  /* ---------- gravar ---------- */
  async function comecar() {
    const cfg = estado.cfg;

    /* O navegador só entrega microfone em "contexto seguro": https, ou
       localhost/127.0.0.1. Num endereço como http://192.168.0.12:7000 o
       `navigator.mediaDevices` simplesmente não existe -- e aí o erro que
       aparecia era "confira a permissão", mandando procurar um cadeado que
       não ia resolver nada. Este caso tem nome próprio agora. */
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      faixa('Neste endereço o navegador não libera o microfone. Ele só '
          + 'libera em https ou em localhost -- abra o Bigode por '
          + 'http://localhost:7000.');
      setTimeout(() => faixa(null), 7000);
      return;
    }

    try {
      estado.fluxo = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,     // tira o som do seu alto-falante
          noiseSuppression: true,     // tira ventilador e ar-condicionado
          autoGainControl: true,      // iguala quem fala perto e longe
        }
      });
    } catch (e) {
      /* Duas telas, dois conselhos diferentes. Na aba comum o caminho é o
         cadeado da barra de endereço. Na barra lateral do Chrome não há
         barra de endereço nenhuma: quem manda é a permissão da extensão
         (audioCapture no manifest.json), e o conserto é recarregar a
         extensão em chrome://extensions. Mandar procurar um cadeado que
         não existe é o tipo de instrução que faz a pessoa achar que ela
         é que está errada. */
      const naBarraLateral = window.self !== window.top;
      faixa(naBarraLateral
        ? 'O Chrome não liberou o microfone para a extensão. Abra '
          + 'chrome://extensions, recarregue o Bigode (↻) e tente de novo.'
        : 'Não consegui usar o microfone. Clique no cadeado na barra de '
          + 'endereço e permita o microfone para este endereço.');
      setTimeout(() => faixa(null), 7000);
      return;
    }

    const AC = window.AudioContext || window.webkitAudioContext;
    estado.ctx = new AC();
    estado.taxa = estado.ctx.sampleRate;
    estado.amostras = [];
    estado.gravando = true;
    if (cfg.botao) cfg.botao.classList.add('gravando');

    const fonte = estado.ctx.createMediaStreamSource(estado.fluxo);
    estado.no = estado.ctx.createScriptProcessor(4096, 1, 1);

    let houveFala = false;
    let calouEm = 0;
    const comecou = Date.now();

    estado.no.onaudioprocess = ev => {
      if (!estado.gravando) return;
      const bloco = ev.inputBuffer.getChannelData(0);
      estado.amostras.push(new Float32Array(bloco));

      /* RMS: a média quadrática é o que corresponde ao volume percebido.
         Usar o pico faria um estalo de teclado parecer fala. */
      let soma = 0;
      for (let i = 0; i < bloco.length; i++) soma += bloco[i] * bloco[i];
      const nivel = Math.sqrt(soma / bloco.length);

      const agora = Date.now();
      if (nivel > FALA) { houveFala = true; calouEm = 0; }
      else if (houveFala && !calouEm) { calouEm = agora; }
      else if (houveFala && calouEm && agora - calouEm > SILENCIO_MS) {
        encerrar(true); return;
      }
      if (agora - comecou > MAXIMO_MS) { encerrar(true); return; }

      faixa(houveFala ? 'Ouvindo… pare de falar que eu encerro sozinho.'
                      : 'Pode falar.', nivel);
    };

    fonte.connect(estado.no);
    estado.no.connect(estado.ctx.destination);
    faixa('Pode falar.', 0);
  }

  async function encerrar(transcrever) {
    if (!estado.gravando) return;
    estado.gravando = false;
    const cfg = estado.cfg;
    if (cfg.botao) cfg.botao.classList.remove('gravando');

    try { estado.no.disconnect(); } catch (e) {}
    try { estado.fluxo.getTracks().forEach(t => t.stop()); } catch (e) {}
    try { estado.ctx.close(); } catch (e) {}

    if (!transcrever) { faixa(null); return; }

    const total = estado.amostras.reduce((s, a) => s + a.length, 0);
    if (total < estado.taxa * MINIMO_S) {
      faixa('Não ouvi nada. O microfone certo está selecionado?');
      setTimeout(() => faixa(null), 3500);
      return;
    }

    faixa('Entendendo o que você falou…');
    if (cfg.botao) cfg.botao.classList.add('processando');

    const wav = montarWav(juntar(estado.amostras, total), estado.taxa, 16000);
    let texto = '';
    try {
      const r = await cfg.enviar(wav);
      if (r && r.ok && r.texto) texto = String(r.texto).trim();
    } catch (e) {}

    if (cfg.botao) cfg.botao.classList.remove('processando');
    faixa(null);

    if (!texto) {
      faixa('Não entendi. Tente falar um pouco mais perto do microfone.');
      setTimeout(() => faixa(null), 3500);
      return;
    }

    const campo = $(cfg.campo);
    if (campo) {
      campo.value = (campo.value ? campo.value.trim() + ' ' : '') + texto;
      campo.dispatchEvent(new Event('input', { bubbles: true }));
      campo.focus();
    }
    if (cfg.aoTerminar) { try { cfg.aoTerminar(texto); } catch (e) {} }
  }

  raiz.Voz = {
    ligar(cfg) {
      estado.cfg = cfg;
      if (cfg.botao) cfg.botao.addEventListener('click', () => raiz.Voz.alternar());
      /* Ctrl+Espaço: a mesma tecla nas três telas. */
      document.addEventListener('keydown', ev => {
        if (ev.ctrlKey && ev.code === 'Space') { ev.preventDefault(); raiz.Voz.alternar(); }
      });
    },
    alternar() { estado.gravando ? encerrar(true) : comecar(); },
    parar() { encerrar(false); },
    gravando() { return estado.gravando; },
  };
})(window);
