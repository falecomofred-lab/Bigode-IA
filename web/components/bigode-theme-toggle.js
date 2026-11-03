/**
 * Bigode Theme Toggle Component
 * Botão elegante para alternar entre dark/light mode
 */

class BiThemeToggle extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.currentTheme = themeManager.getCurrentTheme();
  }

  connectedCallback() {
    this.render();
    this.setupEventListeners();
  }

  render() {
    const isDark = this.currentTheme === 'dark';

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --ac: #9DC08B;
          --txt: #ECEFF4;
          --txt2: #A3ACBB;
          --sup: #11141B;
          --linha: #1D222C;
        }

        .toggle-button {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 40px;
          border-radius: 8px;
          background: var(--sup);
          border: 1px solid var(--linha);
          color: var(--txt2);
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 18px;
          position: relative;
          overflow: hidden;
        }

        .toggle-button:hover {
          color: var(--ac);
          border-color: var(--ac);
          box-shadow: 0 0 12px rgba(157, 192, 139, 0.2);
        }

        .toggle-button:active {
          transform: scale(0.95);
        }

        .icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100%;
          height: 100%;
          transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
        }

        .icon.rotating {
          animation: rotate 0.6s ease;
        }

        @keyframes rotate {
          0% {
            transform: rotate(0deg);
          }
          100% {
            transform: rotate(180deg);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .toggle-button {
            transition: none;
          }
          .icon {
            transition: none;
          }
          .icon.rotating {
            animation: none;
          }
          .toggle-button:active {
            transform: none;
          }
        }

        @media (max-width: 768px) {
          .toggle-button {
            width: 36px;
            height: 36px;
            font-size: 16px;
          }
        }
      </style>

      <button
        class="toggle-button"
        id="toggle-btn"
        aria-label="Alternar modo ${isDark ? 'claro' : 'escuro'}"
        title="Alternar tema (${isDark ? 'Light' : 'Dark'})"
      >
        <div class="icon">${isDark ? '☀️' : '🌙'}</div>
      </button>
    `;
  }

  setupEventListeners() {
    const btn = this.shadowRoot.querySelector('#toggle-btn');
    const icon = this.shadowRoot.querySelector('.icon');

    btn.addEventListener('click', () => {
      icon.classList.add('rotating');

      setTimeout(() => {
        this.currentTheme = themeManager.toggle();
        this.render();
        this.setupEventListeners();

        this.dispatchEvent(new CustomEvent('theme-toggled', {
          detail: { theme: this.currentTheme },
          bubbles: true
        }));

        Toast?.success(`Modo ${this.currentTheme === 'dark' ? 'escuro' : 'claro'} ativado`);
      }, 300);
    });

    // Escutar mudanças externas de tema
    window.addEventListener('theme-changed', (e) => {
      this.currentTheme = e.detail.theme;
      this.render();
      this.setupEventListeners();
    });
  }

  getTheme() {
    return this.currentTheme;
  }

  setTheme(theme) {
    if (theme !== this.currentTheme) {
      themeManager.setTheme(theme);
      this.currentTheme = theme;
      this.render();
      this.setupEventListeners();
    }
  }
}

customElements.define('bigode-theme-toggle', BiThemeToggle);
window.BiThemeToggle = BiThemeToggle;
