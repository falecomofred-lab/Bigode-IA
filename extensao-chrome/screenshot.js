/* Captura screenshot da página para feedback visual ao modelo */

// html2canvas minificado - versão compactada
// CDN: https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js
// Para usar: adicione ao manifest.json em content_scripts

async function tirarScreenshot(qualidade = 0.7) {
  try {
    // Opção 1: Usar html2canvas se disponível
    if (typeof html2canvas !== 'undefined') {
      return await tirarScreenshotHtml2Canvas(qualidade);
    }

    // Opção 2: Usar Canvas API nativa (mais simples, menos preciso)
    return await tirarScreenshotCanvas();
  } catch (e) {
    console.error('Erro ao tirar screenshot:', e);
    return null;
  }
}

async function tirarScreenshotHtml2Canvas(qualidade = 0.7) {
  const canvas = await html2canvas(document.documentElement, {
    backgroundColor: '#ffffff',
    scale: 1,
    useCORS: true,
    allowTaint: true,
    logging: false,
  });

  return converterCanvasParaBase64(canvas, qualidade);
}

async function tirarScreenshotCanvas() {
  // Usar canvas do navegador para screenshot da viewport
  const canvas = await html2canvas(document.documentElement, {
    scale: 0.5,  // Reduz tamanho para não estourar limites
    useCORS: true,
    allowTaint: true,
    backgroundColor: '#ffffff',
  });

  return converterCanvasParaBase64(canvas, 0.6);
}

function converterCanvasParaBase64(canvas, qualidade = 0.7) {
  try {
    // Redimensiona se muito grande (máx 800x600)
    let c = canvas;
    if (canvas.width > 1000 || canvas.height > 1000) {
      const scale = Math.min(1000 / canvas.width, 1000 / canvas.height);
      const novoCanvas = document.createElement('canvas');
      novoCanvas.width = canvas.width * scale;
      novoCanvas.height = canvas.height * scale;
      const ctx = novoCanvas.getContext('2d');
      ctx.drawImage(canvas, 0, 0, novoCanvas.width, novoCanvas.height);
      c = novoCanvas;
    }

    // Converte para JPEG com qualidade (menor que PNG)
    const base64 = c.toDataURL('image/jpeg', qualidade);

    // Limita tamanho da string (máx 50KB de dados brutos)
    if (base64.length > 100000) {
      return c.toDataURL('image/jpeg', Math.max(0.3, qualidade - 0.2));
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
