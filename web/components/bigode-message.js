/**
 * Bigode Message Component
 * Componente individual de mensagem no chat
 * Suporta: user, assistant, system
 */

class BiMessage extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    const role = this.getAttribute('role') || 'user';
    const content = this.textContent.trim();
    const timestamp = this.getAttribute('timestamp');

    this.render(role, content, timestamp);
  }

  render(role, content, timestamp) {
    const isUser = role === 'user';
    const isSystem = role === 'system';
    const isAssistant = role === 'assistant';

    let roleIcon = '🤖';
    let roleLabel = 'Assistente';
    let bgClass = 'message-assistant';

    if (isUser) {
      roleIcon = '👤';
      roleLabel = 'Você';
      bgClass = 'message-user';
    } else if (isSystem) {
      roleIcon = '⚙️';
      roleLabel = 'Sistema';
      bgClass = 'message-system';
    }

    const timeStr = timestamp ? this.formatTime(timestamp) : '';

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --txt: #ECEFF4;
          --txt2: #A3ACBB;
          --sup: #11141B;
          --sup2: #161A23;
          --ac: #9DC08B;
          --linha: #1D222C;
        }

        .message-wrapper {
          display: flex;
          gap: 12px;
          margin-bottom: 16px;
          animation: fadeIn 0.3s ease-out;
          flex-direction: ${isUser ? 'row-reverse' : 'row'};
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .message-avatar {
          width: 32px;
          height: 32px;
          border-radius: 8px;
          background: ${isUser ? 'rgba(157, 192, 139, 0.1)' : 'rgba(17, 20, 27, 0.8)'};
          border: 1px solid ${isUser ? 'rgba(157, 192, 139, 0.2)' : 'var(--linha)'};
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          flex-shrink: 0;
        }

        .message-content {
          flex: 1;
          max-width: 70%;
        }

        @media (max-width: 768px) {
          .message-content {
            max-width: 85%;
          }
        }

        .message-bubble {
          background: ${
            isUser
              ? 'rgba(157, 192, 139, 0.08)'
              : isSystem
                ? 'rgba(251, 191, 36, 0.05)'
                : 'var(--sup2)'
          };
          border: 1px solid ${
            isUser
              ? 'rgba(157, 192, 139, 0.2)'
              : isSystem
                ? 'rgba(251, 191, 36, 0.15)'
                : 'var(--linha)'
          };
          border-radius: 12px;
          padding: 12px 14px;
          color: var(--txt);
          font-size: 14px;
          line-height: 1.5;
          word-wrap: break-word;
          overflow-wrap: break-word;
        }

        .message-bubble code {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 4px;
          padding: 2px 6px;
          font-family: 'Courier New', monospace;
          font-size: 12px;
        }

        .message-bubble pre {
          background: rgba(0, 0, 0, 0.3);
          border-radius: 6px;
          padding: 10px;
          overflow-x: auto;
          margin: 8px 0;
          border-left: 3px solid var(--ac);
        }

        .message-bubble pre code {
          background: none;
          padding: 0;
        }

        .message-meta {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 6px;
          font-size: 12px;
          color: var(--txt2);
          opacity: 0.7;
        }

        .message-role {
          font-weight: 600;
          color: ${isUser ? 'var(--ac)' : 'var(--txt2)'};
        }

        @media (prefers-reduced-motion: reduce) {
          .message-wrapper {
            animation: none;
          }
        }
      </style>

      <div class="message-wrapper">
        <div class="message-avatar" aria-label="${roleLabel}">${roleIcon}</div>
        <div class="message-content">
          <div class="message-bubble" role="article">
            ${this.escapeHtml(content)}
          </div>
          <div class="message-meta">
            <span class="message-role">${roleLabel}</span>
            ${timeStr ? `<span class="message-time">${timeStr}</span>` : ''}
          </div>
        </div>
      </div>
    `;
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  formatTime(timestamp) {
    if (!timestamp) return '';

    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Agora';
    if (minutes < 60) return `${minutes}m`;
    if (hours < 24) return `${hours}h`;
    if (days < 7) return `${days}d`;

    return date.toLocaleDateString('pt-BR', { month: 'short', day: 'numeric' });
  }

  static create(role, content, timestamp) {
    const msg = document.createElement('bigode-message');
    msg.setAttribute('role', role);
    msg.setAttribute('timestamp', timestamp || new Date().toISOString());
    msg.textContent = content;
    return msg;
  }
}

customElements.define('bigode-message', BiMessage);
window.BiMessage = BiMessage;
