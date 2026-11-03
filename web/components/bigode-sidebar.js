/**
 * Bigode IA Sidebar Component
 * Web Component para navegação lateral
 * Gerencia histórico de conversas, novo chat, e modo mobile
 */

class BiSidebar extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.conversas = [];
    this.conversaSelecionada = null;
    this.isMobile = window.innerWidth < 900;
  }

  connectedCallback() {
    this.render();
    this.setupEventListeners();
    this.observeResize();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --ac: #9DC08B;
          --bg: #0D1016;
          --sup: #11141B;
          --sup2: #161A23;
          --txt: #ECEFF4;
          --txt2: #A3ACBB;
          --mudo: #6E7889;
          --fraco: #4B5464;
          --linha: #1D222C;
          --linha2: #2A313E;
        }

        .sidebar {
          width: 252px;
          height: 100%;
          background: var(--bg);
          border-right: 1px solid var(--linha);
          display: flex;
          flex-direction: column;
          transition: width 0.2s ease;
        }

        .sidebar.mobile {
          position: fixed;
          top: 0;
          left: 0;
          width: 100%;
          max-width: 280px;
          height: 100%;
          z-index: 100;
          transform: translateX(-100%);
          transition: transform 0.24s cubic-bezier(0.32, 0.72, 0, 1);
        }

        .sidebar.mobile.open {
          transform: translateX(0);
        }

        .sidebar-header {
          height: 56px;
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 0 14px;
          border-bottom: 1px solid var(--linha);
          flex-shrink: 0;
        }

        .logo {
          width: 28px;
          height: 28px;
          border-radius: 8px;
          background: linear-gradient(140deg, #F2EAD8, var(--ac));
          display: grid;
          place-items: center;
          color: var(--bg);
          font-weight: 700;
          font-size: 14px;
        }

        .brand {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .brand-name {
          font-size: 13px;
          font-weight: 600;
          color: var(--txt);
        }

        .brand-version {
          font-size: 9px;
          letter-spacing: 1.5px;
          color: var(--fraco);
          font-weight: 700;
          text-transform: uppercase;
        }

        .sidebar-content {
          flex: 1;
          overflow-y: auto;
          padding: 6px 10px 14px;
          overscroll-behavior: contain;
        }

        .novo-chat {
          display: flex;
          align-items: center;
          gap: 10px;
          width: 100%;
          padding: 9px 11px;
          border-radius: 10px;
          background: var(--sup2);
          border: 1px solid var(--linha2);
          font-size: 13.5px;
          font-weight: 600;
          color: var(--txt);
          cursor: pointer;
          transition: 0.15s;
          margin-bottom: 12px;
          font-family: inherit;
        }

        .novo-chat:hover {
          border-color: var(--ac);
          color: var(--ac);
        }

        .novo-chat svg {
          color: var(--ac);
          width: 16px;
          height: 16px;
        }

        .conversas-list {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .conversa-item {
          display: flex;
          align-items: center;
          gap: 11px;
          width: 100%;
          padding: 8px 11px;
          border-radius: 9px;
          font-size: 13.5px;
          color: var(--txt2);
          cursor: pointer;
          transition: 0.13s;
          text-align: left;
          border: 1px solid transparent;
          user-select: none;
        }

        .conversa-item:hover {
          background: var(--sup);
          color: var(--txt);
        }

        .conversa-item.active {
          background: var(--sup2);
          color: var(--txt);
          font-weight: 500;
          border-color: var(--ac);
        }

        .conversa-icon {
          color: var(--mudo);
          flex-shrink: 0;
          width: 16px;
          height: 16px;
        }

        .conversa-item:hover .conversa-icon,
        .conversa-item.active .conversa-icon {
          color: var(--ac);
        }

        .conversa-titulo {
          flex: 1;
          min-width: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .conversa-data {
          margin-left: auto;
          font-size: 11px;
          color: var(--fraco);
          flex-shrink: 0;
        }

        .sidebar-footer {
          border-top: 1px solid var(--linha);
          padding: 12px 10px;
          flex-shrink: 0;
        }

        .footer-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 10px;
          border-radius: 8px;
          font-size: 13px;
          color: var(--txt2);
          cursor: pointer;
          transition: 0.13s;
        }

        .footer-item:hover {
          background: var(--sup);
          color: var(--txt);
        }

        .sidebar::-webkit-scrollbar {
          width: 8px;
        }

        .sidebar::-webkit-scrollbar-thumb {
          background: #1E2531;
          border-radius: 4px;
          border: 2px solid var(--bg);
        }

        .empty-state {
          text-align: center;
          padding: 40px 20px;
          color: var(--fraco);
          font-size: 12px;
          line-height: 1.6;
        }

        .empty-icon {
          font-size: 32px;
          margin-bottom: 10px;
          opacity: 0.5;
        }

        @media (max-width: 900px) {
          .sidebar {
            width: 100%;
            max-width: 280px;
          }
        }
      </style>

      <nav class="sidebar" part="sidebar">
        <div class="sidebar-header">
          <div class="logo">B</div>
          <div class="brand">
            <div class="brand-name">Bigode IA</div>
            <div class="brand-version">3.0</div>
          </div>
        </div>

        <div class="sidebar-content" part="content">
          <button class="novo-chat" aria-label="Iniciar nova conversa">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            Nova Conversa
          </button>

          <div class="conversas-list" id="conversas-list" role="list">
            <div class="empty-state">
              <div class="empty-icon">💬</div>
              <p>Nenhuma conversa<br>ainda. Comece uma<br>nova acima.</p>
            </div>
          </div>
        </div>

        <div class="sidebar-footer">
          <button class="footer-item" id="config-btn" aria-label="Configurações">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" style="width: 16px; height: 16px;">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Configurações
          </button>
        </div>
      </nav>
    `;
  }

  setupEventListeners() {
    const novoBtn = this.shadowRoot.querySelector('.novo-chat');
    novoBtn.addEventListener('click', () => {
      this.dispatchEvent(new CustomEvent('novo-chat', { bubbles: true }));
    });

    const configBtn = this.shadowRoot.querySelector('#config-btn');
    configBtn.addEventListener('click', () => {
      this.dispatchEvent(new CustomEvent('abrir-config', { bubbles: true }));
    });
  }

  observeResize() {
    window.addEventListener('resize', () => {
      const novoMobile = window.innerWidth < 900;
      if (novoMobile !== this.isMobile) {
        this.isMobile = novoMobile;
        this.render();
        this.setupEventListeners();
      }
    });
  }

  addConversa(id, titulo, data = new Date()) {
    const conversa = { id, titulo, data };
    this.conversas.unshift(conversa);
    this.renderConversas();
  }

  renderConversas() {
    const lista = this.shadowRoot.querySelector('#conversas-list');

    if (this.conversas.length === 0) {
      lista.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">💬</div>
          <p>Nenhuma conversa<br>ainda. Comece uma<br>nova acima.</p>
        </div>
      `;
      return;
    }

    lista.innerHTML = this.conversas.map((conv) => `
      <div class="conversa-item" data-id="${conv.id}" role="listitem">
        <svg class="conversa-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
        <div class="conversa-titulo">${this.escapeHtml(conv.titulo)}</div>
        <div class="conversa-data">${this.formatarData(conv.data)}</div>
      </div>
    `).join('');

    lista.querySelectorAll('.conversa-item').forEach(item => {
      item.addEventListener('click', () => {
        lista.querySelectorAll('.conversa-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        const id = item.getAttribute('data-id');
        this.dispatchEvent(new CustomEvent('selecionar-conversa', {
          detail: { id },
          bubbles: true
        }));
      });
    });
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  formatarData(data) {
    const agora = new Date();
    const diff = agora - data;
    const horas = Math.floor(diff / 3600000);
    const dias = Math.floor(diff / 86400000);

    if (horas < 1) return 'Agora';
    if (horas < 24) return `${horas}h`;
    if (dias < 7) return `${dias}d`;
    return data.toLocaleDateString('pt-BR', { month: 'short', day: 'numeric' });
  }
}

customElements.define('bigode-sidebar', BiSidebar);
