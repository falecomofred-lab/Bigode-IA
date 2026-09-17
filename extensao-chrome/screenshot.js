/* Captura screenshot da página para feedback visual ao modelo */

// Carrega html2canvas dinamicamente do CDN se não estiver disponível
async function carregarHtml2Canvas() {
  if (typeof html2canvas !== 'undefined') return html2canvas;

  try {
    return await new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
      script.onload = () => {
        if (typeof html2canvas !== 'undefined') resolve(html2canvas);
        else reject(new Error('html2canvas não carregou'));
      };
      script.onerror = () => reject(new Error('Falha ao carregar html2canvas CDN'));
      document.head.appendChild(script);
    });
  } catch (e) {
    console.warn('html2canvas CDN indisponível, usando fallback:', e.message);
    return null;
  }
}

async function tirarScreenshot(qualidade = 0.7) {
  try {
    // Tenta html2canvas primeiro (melhor qualidade)
    const html2canvasLib = await carregarHtml2Canvas();
    if (html2canvasLib) {
      return await tirarScreenshotHtml2Canvas(html2canvasLib, qualidade);
    }

    // Fallback: viewport simples com Canvas API
    return await tirarScreenshotViewport(qualidade);
  } catch (e) {
    console.error('Erro ao tirar screenshot:', e);
    return null;
  }
}

async function tirarScreenshotHtml2Canvas(html2canvas, qualidade = 0.7) {
  try {
    const canvas = await html2canvas(document.documentElement, {
      backgroundColor: '#ffffff',
      scale: 1,
      useCORS: true,
      allowTaint: true,
      logging: false,
      removeContainer: true,
    });
    return converterCanvasParaBase64(canvas, qualidade);
  } catch (e) {
    console.warn('html2canvas falhou, usando fallback:', e.message);
    return await tirarScreenshotViewport(qualidade);
  }
}

async function tirarScreenshotViewport(qualidade = 0.6) {
  // Fallback: screenshot apenas da viewport visível (mais rápido)
  try {
    const canvas = await html2canvas(document.querySelector('body') || document.documentElement, {
      backgroundColor: '#ffffff',
      scale: 0.5,
      useCORS: true,
      allowTaint: true,
      logging: false,
      width: window.innerWidth,
      height: Math.min(window.innerHeight, 2000),
    });
    return converterCanvasParaBase64(canvas, qualidade);
  } catch (e) {
    console.error('Fallback viewport também falhou:', e);
    return null;
  }
}

function converterCanvasParaBase64(canvas, qualidade = 0.7) {
  try {
    // Redimensiona se muito grande (máx 1200x1500px para melhor qualidade)
    let c = canvas;
    let largura = canvas.width;
    let altura = canvas.height;

    if (largura > 1200 || altura > 1500) {
      const escala = Math.min(1200 / largura, 1500 / altura);
      const novoCanvas = document.createElement('canvas');
      novoCanvas.width = largura * escala;
      novoCanvas.height = altura * escala;
      const ctx = novoCanvas.getContext('2d');
      ctx.drawImage(canvas, 0, 0, novoCanvas.width, novoCanvas.height);
      c = novoCanvas;
    }

    // Tenta JPEG de alta qualidade primeiro
    let base64 = c.toDataURL('image/jpeg', qualidade);

    // Reduz qualidade progressivamente se muito grande
    let tentativas = 0;
    while (base64.length > 80000 && tentativas < 3) {
      qualidade = Math.max(0.2, qualidade - 0.15);
      base64 = c.toDataURL('image/jpeg', qualidade);
      tentativas++;
    }

    // Última tentativa: reduce resolution
    if (base64.length > 80000) {
      const minCanvas = document.createElement('canvas');
      minCanvas.width = c.width * 0.7;
      minCanvas.height = c.height * 0.7;
      const minCtx = minCanvas.getContext('2d');
      minCtx.drawImage(c, 0, 0, minCanvas.width, minCanvas.height);
      base64 = minCanvas.toDataURL('image/jpeg', 0.3);
    }

    return base64;
  } catch (e) {
    console.error('Erro ao converter canvas:', e);
    return null;
  }
}

// Exporta para uso em conteudo.js
window.BigodeScreenshot = {
  tirar: tirarScreenshot,
};
