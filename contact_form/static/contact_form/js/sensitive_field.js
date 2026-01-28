document.addEventListener('DOMContentLoaded', function() {
    const sensitiveFields = document.querySelectorAll('[data-sensitive-field="true"]');

    sensitiveFields.forEach(function(field) {
        const input = field.querySelector('input[type="text"]');
        if (!input || !input.value) return;

        const originalValue = input.value;
        const maskedValue = '•'.repeat(Math.min(originalValue.length, 20));

        input.dataset.originalValue = originalValue;
        input.value = maskedValue;
        input.dataset.masked = 'true';

        input.addEventListener('focus', function() {
            if (this.dataset.masked === 'true') {
                this.value = this.dataset.originalValue || '';
                this.dataset.masked = 'false';
            }
        });

        input.addEventListener('blur', function() {
            if (this.value && this.value === this.dataset.originalValue) {
                this.value = '•'.repeat(Math.min(this.value.length, 20));
                this.dataset.masked = 'true';
            } else {
                this.dataset.originalValue = this.value;
                this.dataset.masked = 'false';
            }
        });
    });
});
