/**
 * Bigode Chat Component
 * Container de mensagens com scroll automático e gerenciamento de histórico
 */

class BiChat extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.messages = [];
    this.isAtBottom = true;
  }

  connectedCallback() {
    this.render();
    this.setupScrollListener();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --bg: #0A0C11;
          --sup: #11141B;
          --sup2: #161A23;
          --txt: #ECEFF4;
          --linha: #1D222C;
        }

        .chat-container {
          display: flex;
          flex-direction: column;
          height: 100%;
          background: var(--bg);
          border-right: 1px solid var(--linha);
        }

        .messages-area {
          flex: 1;
          overflow-y: auto;
          padding: 16px 20px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          scroll-behavior: smooth;
          overscroll-behavior: contain;
        }

        .messages-area::-webkit-scrollbar {
          width: 8px;
        }

        .messages-area::-webkit-scrollbar-thumb {
          background: #1E2531;
          border-radius: 4px;
          border: 2px solid var(--bg);
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100%;
          color: #6E7889;
          text-align: center;
          gap: 12px;
        }

        .empty-icon {
          font-size: 48px;
          opacity: 0.5;
        }

        .empty-text {
          font-size: 14px;
          line-height: 1.6;
          max-width: 200px;
        }

        .scroll-to-bottom {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 8px 12px;
          background: rgba(157, 192, 139, 0.1);
          border: 1px solid rgba(157, 192, 139, 0.2);
          border-radius: 20px;
          color: #9DC08B;
          font-size: 12px;
          cursor: pointer;
          transition: 0.2s;
          position: absolute;
          bottom: 20px;
          left: 50%;
          transform: translateX(-50%);
        }

        .scroll-to-bottom:hover {
          background: rgba(157, 192, 139, 0.15);
          border-color: rgba(157, 192, 139, 0.3);
        }

        .scroll-to-bottom svg {
          width: 14px;
          height: 14px;
        }

        @media (max-width: 768px) {
          .messages-area {
            padding: 12px 16px;
          }
        }
      </style>

      <div class="chat-container">
        <div class="messages-area" role="log" aria-label="Histórico de mensagens" id="messages"></div>
      </div>
    `;

    this.renderMessages();
  }

  setupScrollListener() {
    const messagesArea = this.shadowRoot.querySelector('.messages-area');

    messagesArea.addEventListener('scroll', () => {
      const { scrollHeight, scrollTop, clientHeight } = messagesArea;
      this.isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    });
  }

  renderMessages() {
    const messagesArea = this.shadowRoot.querySelector('#messages');

    if (this.messages.length === 0) {
      messagesArea.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">💬</div>
          <div class="empty-text">
            <strong>Nenhuma mensagem</strong><br>
            Comece uma conversa
          </div>
        </div>
      `;
      return;
    }

    messagesArea.innerHTML = '';
    this.messages.forEach((msg) => {
      const element = BiMessage.create(msg.role, msg.content, msg.timestamp);
      messagesArea.appendChild(element);
    });

    this.scrollToBottom();
  }

  addMessage(role, content, timestamp = null) {
    const msg = {
      role,
      content,
      timestamp: timestamp || new Date().toISOString(),
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    };

    this.messages.push(msg);
    this.renderMessages();

    return msg;
  }

  scrollToBottom() {
    if (!this.isAtBottom) return;

    setTimeout(() => {
      const messagesArea = this.shadowRoot.querySelector('.messages-area');
      messagesArea.scrollTop = messagesArea.scrollHeight;
    }, 0);
  }

  clearMessages() {
    this.messages = [];
    this.renderMessages();
  }

  getMessages() {
    return [...this.messages];
  }

  getLastMessage() {
    return this.messages[this.messages.length - 1] || null;
  }

  removeMessage(id) {
    this.messages = this.messages.filter((m) => m.id !== id);
    this.renderMessages();
  }

  editMessage(id, newContent) {
    const msg = this.messages.find((m) => m.id === id);
    if (msg) {
      msg.content = newContent;
      this.renderMessages();
    }
  }
}

customElements.define('bigode-chat', BiChat);
window.BiChat = BiChat;
