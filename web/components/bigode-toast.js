/**
 * Bigode Toast Component
 * Notificações profissionais com tipo, mensagem, duração
 */

class BiToast extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    const type = this.getAttribute('type') || 'info';
    const message = this.getAttribute('message') || '';
    const duration = parseInt(this.getAttribute('duration')) || 3000;

    this.render(type, message);
    if (duration > 0) {
      setTimeout(() => this.remove(), duration);
    }
  }

  render(type, message) {
    const icons = {
      success: '✓',
      error: '✕',
      warning: '!',
      info: 'i'
    };

    const colors = {
      success: '#34D399',
      error: '#F87171',
      warning: '#FBBF24',
      info: '#9DC08B'
    };

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --color: ${colors[type] || colors.info};
        }

        .toast {
          display: flex;
          align-items: center;
          gap: 12px;
          background: rgba(17,20,27,0.95);
          border: 1px solid rgba(157,192,139,0.2);
          border-left: 3px solid var(--color);
          border-radius: 12px;
          padding: 12px 16px;
          backdrop-filter: blur(16px);
          box-shadow: 0 8px 20px rgba(0,0,0,0.3);
          animation: slideIn 0.3s ease-out;
          font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
          color: #ECEFF4;
          font-size: 13.5px;
          max-width: 400px;
        }

        .toast-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: rgba(157,192,139,0.1);
          color: var(--color);
          font-weight: 700;
          flex-shrink: 0;
        }

        .toast-message {
          flex: 1;
          line-height: 1.4;
        }

        .toast-close {
          width: 20px;
          height: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          color: #6E7889;
          transition: color 0.2s;
          flex-shrink: 0;
          font-size: 16px;
          line-height: 1;
        }

        .toast-close:hover {
          color: var(--color);
        }

        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateX(20px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .toast {
            animation: none;
          }
        }
      </style>

      <div class="toast" role="alert" aria-live="polite">
        <div class="toast-icon">${icons[type]}</div>
        <div class="toast-message">${this.escapeHtml(message)}</div>
        <div class="toast-close" aria-label="Fechar notificação">×</div>
      </div>
    `;

    this.shadowRoot.querySelector('.toast-close').addEventListener('click', () => {
      this.remove();
    });
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  static show(message, type = 'info', duration = 3000) {
    const toast = document.createElement('bigode-toast');
    toast.setAttribute('message', message);
    toast.setAttribute('type', type);
    toast.setAttribute('duration', duration);

    // Container de toasts (criar se não existir)
    let container = document.getElementById('toasts-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toasts-container';
      container.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 10px;
        max-width: 420px;
        pointer-events: auto;
      `;
      document.body.appendChild(container);
    }

    container.appendChild(toast);
    return toast;
  }

  static success(message, duration = 3000) {
    return this.show(message, 'success', duration);
  }

  static error(message, duration = 3000) {
    return this.show(message, 'error', duration);
  }

  static warning(message, duration = 3000) {
    return this.show(message, 'warning', duration);
  }

  static info(message, duration = 3000) {
    return this.show(message, 'info', duration);
  }
}

customElements.define('bigode-toast', BiToast);

// Export para fácil uso
window.Toast = BiToast;
