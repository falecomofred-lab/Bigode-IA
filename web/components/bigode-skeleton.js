/**
 * Bigode Skeleton Component
 * Placeholders animados para loading states
 */

class BiSkeleton extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  connectedCallback() {
    const type = this.getAttribute('type') || 'text';
    const width = this.getAttribute('width') || '100%';
    const height = this.getAttribute('height') || '16px';
    const count = parseInt(this.getAttribute('count')) || 1;

    this.render(type, width, height, count);
  }

  render(type, width, height, count) {
    let html = '';

    if (type === 'text') {
      html = Array(count)
        .fill(null)
        .map((_, i) => `<div class="skeleton skeleton-text" style="width: ${width}; height: ${height}; margin-bottom: ${i < count - 1 ? '8px' : '0'}"></div>`)
        .join('');
    } else if (type === 'circle') {
      html = `<div class="skeleton skeleton-circle" style="width: ${width}; height: ${height}"></div>`;
    } else if (type === 'card') {
      html = `
        <div class="skeleton-card">
          <div class="skeleton skeleton-image"></div>
          <div class="skeleton-content">
            <div class="skeleton skeleton-title"></div>
            <div class="skeleton skeleton-text"></div>
            <div class="skeleton skeleton-text" style="width: 80%"></div>
          </div>
        </div>
      `;
    } else if (type === 'avatar') {
      html = `
        <div class="skeleton-avatar">
          <div class="skeleton skeleton-circle" style="width: 40px; height: 40px"></div>
          <div class="skeleton-info">
            <div class="skeleton skeleton-text" style="width: 120px"></div>
            <div class="skeleton skeleton-text" style="width: 100px; margin-top: 6px"></div>
          </div>
        </div>
      `;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --linha: #1D222C;
        }

        .skeleton {
          background: linear-gradient(
            90deg,
            var(--linha) 0%,
            rgba(255, 255, 255, 0.05) 50%,
            var(--linha) 100%
          );
          background-size: 200% 100%;
          border-radius: 6px;
          animation: loading 2s infinite;
        }

        @keyframes loading {
          0% {
            background-position: 200% 0;
          }
          100% {
            background-position: -200% 0;
          }
        }

        .skeleton-text {
          height: 16px;
          border-radius: 4px;
        }

        .skeleton-circle {
          border-radius: 50%;
        }

        .skeleton-card {
          background: var(--sup2, #161A23);
          border-radius: 12px;
          overflow: hidden;
          padding: 0;
        }

        .skeleton-image {
          width: 100%;
          height: 180px;
          border-radius: 0;
        }

        .skeleton-content {
          padding: 12px;
        }

        .skeleton-title {
          height: 18px;
          margin-bottom: 8px;
          width: 70%;
        }

        .skeleton-avatar {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .skeleton-info {
          flex: 1;
        }

        @media (prefers-reduced-motion: reduce) {
          .skeleton {
            animation: none;
            background: var(--linha);
          }
        }
      </style>

      ${html}
    `;
  }
}

customElements.define('bigode-skeleton', BiSkeleton);
window.BiSkeleton = BiSkeleton;
