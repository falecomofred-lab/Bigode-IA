/**
 * Bigode Composer Component
 * Input elegante com validação, mic button, emoji picker
 */

class BiComposer extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.isRecording = false;
    this.mediaRecorder = null;
    this.audioChunks = [];
  }

  connectedCallback() {
    this.render();
    this.setupEventListeners();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --bg: #0A0C11;
          --sup: #11141B;
          --sup2: #161A23;
          --txt: #ECEFF4;
          --txt2: #A3ACBB;
          --linha: #1D222C;
          --ac: #9DC08B;
        }

        .composer-container {
          display: flex;
          align-items: flex-end;
          gap: 10px;
          padding: 16px 20px;
          background: var(--bg);
          border-top: 1px solid var(--linha);
        }

        .input-wrapper {
          flex: 1;
          display: flex;
          align-items: center;
          gap: 8px;
          background: var(--sup);
          border: 1px solid var(--linha);
          border-radius: 10px;
          padding: 10px 12px;
          transition: 0.15s;
        }

        .input-wrapper:focus-within {
          border-color: var(--ac);
          box-shadow: 0 0 0 2px rgba(157, 192, 139, 0.1);
        }

        .input-field {
          flex: 1;
          background: none;
          border: none;
          color: var(--txt);
          font-size: 14px;
          outline: none;
          font-family: inherit;
          resize: none;
          max-height: 100px;
          padding: 0;
        }

        .input-field::placeholder {
          color: #6E7889;
        }

        .action-button {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border-radius: 6px;
          background: transparent;
          border: none;
          color: #6E7889;
          cursor: pointer;
          transition: 0.15s;
          font-size: 18px;
        }

        .action-button:hover {
          color: var(--ac);
          background: rgba(157, 192, 139, 0.1);
        }

        .action-button.active {
          color: var(--ac);
          background: rgba(157, 192, 139, 0.15);
        }

        .send-button {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 40px;
          height: 40px;
          border-radius: 8px;
          background: var(--ac);
          border: none;
          color: var(--bg);
          cursor: pointer;
          transition: 0.15s;
          font-weight: 600;
          font-size: 16px;
        }

        .send-button:hover:not(:disabled) {
          opacity: 0.9;
          transform: scale(1.05);
        }

        .send-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .char-count {
          font-size: 11px;
          color: #6E7889;
          margin-top: 4px;
          text-align: right;
        }

        .char-count.warning {
          color: #FBBF24;
        }

        .char-count.danger {
          color: #F87171;
        }

        .error-message {
          font-size: 12px;
          color: #F87171;
          margin-top: 4px;
          display: none;
        }

        .error-message.show {
          display: block;
        }

        @media (max-width: 768px) {
          .composer-container {
            padding: 12px 16px;
          }

          .send-button {
            width: 36px;
            height: 36px;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .send-button:hover {
            transform: none;
          }
        }
      </style>

      <div class="composer-container">
        <div class="input-wrapper">
          <button class="action-button emoji-btn" aria-label="Emoji picker" title="Emoji">😀</button>
          <textarea
            class="input-field"
            id="message-input"
            placeholder="Digite uma mensagem ou use /comandos..."
            rows="1"
            aria-label="Campo de mensagem"
          ></textarea>
          <button class="action-button mic-btn" aria-label="Gravação de voz" title="Voz">🎤</button>
        </div>
        <button class="send-button" id="send-btn" aria-label="Enviar mensagem" title="Enviar (Enter)">
          ↑
        </button>
      </div>

      <div class="char-count" id="char-count"></div>
      <div class="error-message" id="error-msg"></div>
    `;
  }

  setupEventListeners() {
    const input = this.shadowRoot.querySelector('#message-input');
    const sendBtn = this.shadowRoot.querySelector('#send-btn');
    const micBtn = this.shadowRoot.querySelector('.mic-btn');
    const charCount = this.shadowRoot.querySelector('#char-count');

    // Auto-resize textarea
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 100) + 'px';
      this.updateCharCount(input, charCount);
      this.validateInput(input);
    });

    // Send button
    sendBtn.addEventListener('click', () => this.handleSend(input, sendBtn));

    // Enter to send (Shift+Enter for newline)
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.handleSend(input, sendBtn);
      }
    });

    // Mic button (voice recording)
    micBtn.addEventListener('click', () => this.toggleRecording(micBtn));

    // Update send button state
    input.addEventListener('input', () => {
      const hasContent = input.value.trim().length > 0;
      sendBtn.disabled = !hasContent;
    });

    // Prevent paste of very long text
    input.addEventListener('paste', (e) => {
      const text = e.clipboardData.getData('text');
      if (text.length > 5000) {
        e.preventDefault();
        this.showError('Mensagem muito longa (máx 5000 caracteres)');
      }
    });
  }

  handleSend(input, sendBtn) {
    const message = input.value.trim();

    if (!message) return;
    if (message.length > 5000) {
      this.showError('Mensagem muito longa (máx 5000 caracteres)');
      return;
    }

    this.dispatchEvent(new CustomEvent('message-sent', {
      detail: { message, type: 'text' },
      bubbles: true
    }));

    input.value = '';
    input.style.height = 'auto';
    this.shadowRoot.querySelector('#char-count').textContent = '';
    sendBtn.disabled = true;
  }

  toggleRecording(micBtn) {
    if (this.isRecording) {
      this.stopRecording(micBtn);
    } else {
      this.startRecording(micBtn);
    }
  }

  startRecording(micBtn) {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then((stream) => {
        this.mediaRecorder = new MediaRecorder(stream);
        this.audioChunks = [];

        this.mediaRecorder.addEventListener('dataavailable', (e) => {
          this.audioChunks.push(e.data);
        });

        this.mediaRecorder.addEventListener('stop', () => {
          const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
          this.dispatchEvent(new CustomEvent('message-sent', {
            detail: { audio: audioBlob, type: 'audio', duration: 'auto' },
            bubbles: true
          }));
        });

        this.mediaRecorder.start();
        this.isRecording = true;
        micBtn.classList.add('active');
      })
      .catch((err) => {
        this.showError('Sem acesso ao microfone: ' + err.message);
      });
  }

  stopRecording(micBtn) {
    if (this.mediaRecorder) {
      this.mediaRecorder.stop();
      this.isRecording = false;
      micBtn.classList.remove('active');

      this.mediaRecorder.stream.getTracks().forEach((track) => track.stop());
    }
  }

  updateCharCount(input, charCount) {
    const count = input.value.length;
    const max = 5000;
    const remaining = max - count;

    if (count === 0) {
      charCount.textContent = '';
      charCount.className = 'char-count';
    } else if (remaining < 100) {
      charCount.textContent = `${remaining} caracteres restantes`;
      charCount.className = 'char-count danger';
    } else if (remaining < 500) {
      charCount.textContent = `${remaining} caracteres restantes`;
      charCount.className = 'char-count warning';
    } else {
      charCount.textContent = '';
    }
  }

  validateInput(input) {
    const value = input.value.trim();
    const errorMsg = this.shadowRoot.querySelector('#error-msg');

    if (value.length > 5000) {
      errorMsg.textContent = 'Mensagem ultrapassou o limite (máx 5000 caracteres)';
      errorMsg.classList.add('show');
      return false;
    } else {
      errorMsg.classList.remove('show');
      return true;
    }
  }

  showError(message) {
    const errorMsg = this.shadowRoot.querySelector('#error-msg');
    errorMsg.textContent = message;
    errorMsg.classList.add('show');

    setTimeout(() => {
      errorMsg.classList.remove('show');
    }, 4000);
  }

  focus() {
    this.shadowRoot.querySelector('#message-input').focus();
  }

  clear() {
    const input = this.shadowRoot.querySelector('#message-input');
    input.value = '';
    input.style.height = 'auto';
  }

  getValue() {
    return this.shadowRoot.querySelector('#message-input').value.trim();
  }
}

customElements.define('bigode-composer', BiComposer);
window.BiComposer = BiComposer;
