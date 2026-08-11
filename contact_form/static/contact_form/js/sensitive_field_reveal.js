document.addEventListener("DOMContentLoaded", () => {
  const sensitiveFields = document.querySelectorAll(
    '[data-sensitive-field="true"]',
  );

  sensitiveFields.forEach((field) => {
    const input = field.querySelector("input");

    if (
      !(input instanceof HTMLInputElement) ||
      input.dataset.sensitiveFieldReady
    ) {
      return;
    }

    input.dataset.sensitiveFieldReady = "true";
    input.type = "password";

    input.addEventListener("focus", () => {
      input.type = "text";
    });

    input.addEventListener("blur", () => {
      input.type = "password";
    });
  });
});
