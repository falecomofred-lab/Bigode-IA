/**
 * Form Validators
 * Validação profissional em tempo real sem dependências
 */

const Validators = {
  /**
   * Valida email com regex simples
   */
  isValidEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email.trim());
  },

  /**
   * Valida senha: mínimo 8 caracteres, 1 maiúscula, 1 número
   */
  isValidPassword(password) {
    if (password.length < 8) return false;
    if (!/[A-Z]/.test(password)) return false;
    if (!/[0-9]/.test(password)) return false;
    return true;
  },

  /**
   * Retorna feedback sobre força da senha
   */
  getPasswordStrength(password) {
    if (!password) return { score: 0, label: 'Vazia', color: '#F87171' };
    if (password.length < 6) return { score: 1, label: 'Fraca', color: '#F87171' };
    if (password.length < 10) return { score: 2, label: 'Média', color: '#FBBF24' };
    if (!/[A-Z]/.test(password) || !/[0-9]/.test(password)) {
      return { score: 2, label: 'Média', color: '#FBBF24' };
    }
    return { score: 3, label: 'Forte', color: '#34D399' };
  },

  /**
   * Valida nome (mínimo 3 caracteres)
   */
  isValidName(name) {
    return name.trim().length >= 3;
  },

  /**
   * Valida URL
   */
  isValidURL(url) {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  },

  /**
   * Valida campo obrigatório
   */
  isRequired(value) {
    return value && value.toString().trim().length > 0;
  },

  /**
   * Valida comprimento mínimo
   */
  minLength(value, min) {
    return value && value.toString().length >= min;
  },

  /**
   * Valida comprimento máximo
   */
  maxLength(value, max) {
    return value && value.toString().length <= max;
  },

  /**
   * Valida padrão regex customizado
   */
  matches(value, regex) {
    return regex.test(value);
  }
};

/**
 * Form Field Helper
 * Facilita validação em inputs com erro visual
 */
class FormField {
  constructor(inputElement, validators = []) {
    this.input = inputElement;
    this.errorElement = inputElement.parentElement?.querySelector('.error');
    this.validators = validators;
    this.isValid = true;

    this.input.addEventListener('blur', () => this.validate());
    this.input.addEventListener('input', () => this.validate());
  }

  validate() {
    const value = this.input.value.trim();
    let error = '';

    for (const validator of this.validators) {
      const result = validator(value);
      if (result !== true) {
        error = result || 'Campo inválido';
        break;
      }
    }

    this.setError(error);
    return !error;
  }

  setError(message) {
    this.isValid = !message;

    if (message) {
      this.input.setAttribute('aria-invalid', 'true');
      if (this.errorElement) {
        this.errorElement.textContent = message;
        this.errorElement.hidden = false;
      }
    } else {
      this.input.setAttribute('aria-invalid', 'false');
      if (this.errorElement) {
        this.errorElement.hidden = true;
        this.errorElement.textContent = '';
      }
    }
  }

  getValue() {
    return this.input.value.trim();
  }

  focus() {
    this.input.focus();
  }
}

/**
 * Form Validator
 * Gerencia múltiplos campos
 */
class FormValidator {
  constructor(formElement) {
    this.form = formElement;
    this.fields = new Map();
  }

  addField(name, inputElement, validators = []) {
    const field = new FormField(inputElement, validators);
    this.fields.set(name, field);
    return field;
  }

  validateAll() {
    let isValid = true;
    const errors = {};

    this.fields.forEach((field, name) => {
      if (!field.validate()) {
        isValid = false;
        errors[name] = field.errorElement?.textContent || 'Campo inválido';
      }
    });

    return { isValid, errors };
  }

  getValues() {
    const values = {};
    this.fields.forEach((field, name) => {
      values[name] = field.getValue();
    });
    return values;
  }

  reset() {
    this.fields.forEach((field) => {
      field.input.value = '';
      field.setError('');
    });
  }
}

// Exports
window.Validators = Validators;
window.FormField = FormField;
window.FormValidator = FormValidator;
