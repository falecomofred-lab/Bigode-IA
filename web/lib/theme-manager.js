/**
 * Theme Manager
 * Gerencia dark/light mode com localStorage e preferências do sistema
 */

class ThemeManager {
  constructor() {
    this.STORAGE_KEY = 'bigode-theme';
    this.DARK = 'dark';
    this.LIGHT = 'light';
    this.SYSTEM = 'system';

    this.init();
  }

  init() {
    // Recupera tema salvo ou usa preferência do sistema
    const savedTheme = localStorage.getItem(this.STORAGE_KEY);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (savedTheme === this.LIGHT || savedTheme === this.DARK) {
      this.setTheme(savedTheme);
    } else {
      // Primeira vez: respeita preferência do sistema
      this.setTheme(prefersDark ? this.DARK : this.LIGHT);
    }

    // Observa mudanças nas preferências do sistema
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem(this.STORAGE_KEY)) {
        this.setTheme(e.matches ? this.DARK : this.LIGHT);
      }
    });
  }

  setTheme(theme) {
    const root = document.documentElement;

    if (theme === this.LIGHT) {
      root.setAttribute('data-theme', 'light');
      root.style.setProperty('--bg', '#F5F5F7');
      root.style.setProperty('--sup', '#FFFFFF');
      root.style.setProperty('--sup2', '#F9FAFB');
      root.style.setProperty('--txt', '#1A1A1A');
      root.style.setProperty('--txt2', '#6B7280');
      root.style.setProperty('--mudo', '#9CA3AF');
      root.style.setProperty('--fraco', '#D1D5DB');
      root.style.setProperty('--linha', '#E5E7EB');
      root.style.setProperty('--linha2', '#D1D5DB');
      root.style.setProperty('--ac', '#7BAA6F');
      localStorage.setItem(this.STORAGE_KEY, this.LIGHT);
    } else {
      root.setAttribute('data-theme', 'dark');
      root.style.setProperty('--bg', '#0A0C11');
      root.style.setProperty('--sup', '#11141B');
      root.style.setProperty('--sup2', '#161A23');
      root.style.setProperty('--txt', '#ECEFF4');
      root.style.setProperty('--txt2', '#A3ACBB');
      root.style.setProperty('--mudo', '#6E7889');
      root.style.setProperty('--fraco', '#4B5464');
      root.style.setProperty('--linha', '#1D222C');
      root.style.setProperty('--linha2', '#2A313E');
      root.style.setProperty('--ac', '#9DC08B');
      localStorage.setItem(this.STORAGE_KEY, this.DARK);
    }

    // Dispara evento para componentes ouvirem
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: { theme } }));
  }

  toggle() {
    const current = localStorage.getItem(this.STORAGE_KEY) || this.DARK;
    const newTheme = current === this.DARK ? this.LIGHT : this.DARK;
    this.setTheme(newTheme);
    return newTheme;
  }

  getCurrentTheme() {
    return localStorage.getItem(this.STORAGE_KEY) || this.DARK;
  }

  isDark() {
    return this.getCurrentTheme() === this.DARK;
  }

  isLight() {
    return this.getCurrentTheme() === this.LIGHT;
  }
}

// Export para uso global
window.themeManager = new ThemeManager();
