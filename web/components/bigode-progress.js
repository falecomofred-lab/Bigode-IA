/**
 * Bigode Progress Component
 * Barra de progresso elegante com suporte a temas
 */

class BiProgress extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.progress = 0;
    this.isAnimating = false;
  }

  connectedCallback() {
    this.progress = parseInt(this.getAttribute('value')) || 0;
    this.render();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --ac: #9DC08B;
          --bg: #0A0C11;
          --sup2: #161A23;
          --linha: #1D222C;
        }

        .progress-container {
          width: 100%;
          height: 4px;
          background: var(--linha);
          border-radius: 2px;
          overflow: hidden;
          position: relative;
        }

        .progress-bar {
          height: 100%;
          background: linear-gradient(90deg, var(--ac), #A8D997);
          width: ${this.progress}%;
          transition: width 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
          border-radius: 2px;
          position: relative;
          box-shadow: 0 0 8px rgba(157, 192, 139, 0.4);
        }

        .progress-bar::after {
          content: '';
          position: absolute;
          top: 0;
          right: 0;
          bottom: 0;
          width: 8px;
          background: rgba(255, 255, 255, 0.3);
          border-radius: 2px;
          animation: shimmer 2s infinite;
        }

        @keyframes shimmer {
          0%, 100% {
            opacity: 0;
          }
          50% {
            opacity: 1;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .progress-bar {
            transition: none;
          }
          .progress-bar::after {
            animation: none;
          }
        }

        :host([indeterminate]) .progress-bar {
          width: 30%;
          animation: indeterminateMove 1.5s infinite;
        }

        @keyframes indeterminateMove {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(500%);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          :host([indeterminate]) .progress-bar {
            animation: none;
            width: 100%;
          }
        }
      </style>

      <div class="progress-container" role="progressbar" aria-valuenow="${this.progress}" aria-valuemin="0" aria-valuemax="100" aria-label="Progresso da operação">
        <div class="progress-bar"></div>
      </div>
    `;
  }

  set(value) {
    this.progress = Math.min(100, Math.max(0, value));
    this.setAttribute('value', this.progress);
    this.render();
  }

  increment(amount = 10) {
    this.set(this.progress + amount);
  }

  complete() {
    this.set(100);
  }

  reset() {
    this.set(0);
  }
}

customElements.define('bigode-progress', BiProgress);
window.BiProgress = BiProgress;
