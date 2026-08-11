(() => {
  "use strict";

  const WIDGET_SELECTOR = "[data-turnstile-widget]";

  const showStatus = (widgetElement, message) => {
    const statusElement = widgetElement.nextElementSibling;
    if (
      !(statusElement instanceof HTMLElement) ||
      !statusElement.matches("[data-turnstile-status]")
    ) {
      return;
    }

    statusElement.textContent = message;
    statusElement.hidden = false;
  };

  const clearStatus = (widgetElement) => {
    const statusElement = widgetElement.nextElementSibling;
    if (
      !(statusElement instanceof HTMLElement) ||
      !statusElement.matches("[data-turnstile-status]")
    ) {
      return;
    }

    statusElement.textContent = "";
    statusElement.hidden = true;
  };

  const initializeWidget = (widgetElement) => {
    if (!window.turnstile) {
      showStatus(widgetElement, widgetElement.dataset.errorMessage || "");
      return;
    }

    const form = widgetElement.closest("form");
    let widgetId;

    const resetWidget = () => {
      try {
        if (widgetId !== undefined) {
          window.turnstile.reset(widgetId);
        }
      } catch {
        showStatus(widgetElement, widgetElement.dataset.errorMessage || "");
      }
    };

    try {
      widgetId = window.turnstile.render(widgetElement, {
        sitekey: widgetElement.dataset.sitekey,
        theme: widgetElement.dataset.theme || "auto",
        size: widgetElement.dataset.size || "normal",
        action: widgetElement.dataset.action,
        "response-field": true,
        "response-field-name": widgetElement.dataset.responseFieldName,
        "refresh-expired": "manual",
        "refresh-timeout": "manual",
        callback: () => clearStatus(widgetElement),
        "error-callback": () => {
          showStatus(widgetElement, widgetElement.dataset.errorMessage || "");
        },
        "expired-callback": () => {
          showStatus(widgetElement, widgetElement.dataset.expiredMessage || "");
          resetWidget();
        },
        "timeout-callback": () => {
          showStatus(widgetElement, widgetElement.dataset.timeoutMessage || "");
          resetWidget();
        },
      });
    } catch {
      showStatus(widgetElement, widgetElement.dataset.errorMessage || "");
      return;
    }

    if (!(form instanceof HTMLFormElement)) {
      return;
    }

    form.addEventListener("submit", (event) => {
      try {
        const isExpired = window.turnstile.isExpired(widgetId);
        const response = window.turnstile.getResponse(widgetId);
        if (!isExpired && response) {
          return;
        }

        event.preventDefault();
        showStatus(
          widgetElement,
          isExpired
            ? widgetElement.dataset.expiredMessage || ""
            : widgetElement.dataset.requiredMessage || "",
        );
        resetWidget();
      } catch {
        event.preventDefault();
        showStatus(widgetElement, widgetElement.dataset.errorMessage || "");
      }
    });
  };

  const initializeTurnstile = () => {
    document.querySelectorAll(WIDGET_SELECTOR).forEach((widgetElement) => {
      if (widgetElement instanceof HTMLElement) {
        initializeWidget(widgetElement);
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeTurnstile, {
      once: true,
    });
  } else {
    initializeTurnstile();
  }
})();
