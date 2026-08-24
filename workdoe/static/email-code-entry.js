(function () {
  "use strict";

  function value(form, name) {
    var field = form.elements.namedItem(name);
    return field && typeof field.value === "string" ? field.value.trim() : "";
  }

  function setMessage(form, message) {
    var output = form.querySelector("[data-email-code-message]");
    if (output) {
      output.textContent = message || "";
    }
  }

  function setBusy(form, busy) {
    form.querySelectorAll("button").forEach(function (button) {
      button.disabled = busy;
    });
    form.setAttribute("aria-busy", busy ? "true" : "false");
  }

  async function fetchJson(url, options) {
    var response = await window.fetch(url, Object.assign({
      credentials: "include",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Workdoe-Request": "same-origin"
      }
    }, options || {}));
    var responseText = await response.text();
    var payload = {};
    try {
      payload = responseText ? JSON.parse(responseText) : {};
    } catch (error) {
      payload = {};
    }
    if (!response.ok) {
      var fallback = response.status === 429
        ? "Too many codes were requested. Wait a few minutes and try again."
        : response.status >= 500
          ? "Sign-in is temporarily unavailable. Please try again."
          : "Workdoe could not complete sign-in.";
      throw new Error(payload.error || fallback);
    }
    return payload;
  }

  function requestPayload(form) {
    var selectedIntent = form.querySelector('input[name="intent"]:checked');
    return {
      mode: form.dataset.mode || "signin",
      email: value(form, "email"),
      intent: selectedIntent ? selectedIntent.value : "find-work",
      display_name: value(form, "display_name"),
      company_name: value(form, "company_name"),
      selected_job_id: form.dataset.selectedJobId || "",
      next: form.dataset.redirectUrl || "/dashboard",
      turnstile_token: value(form, "cf-turnstile-response")
    };
  }

  async function requestCode(form) {
    setMessage(form, "Sending your one-time code...");
    var payload = await fetchJson(form.dataset.requestUrl, {
      method: "POST",
      body: JSON.stringify(requestPayload(form))
    });
    form.dataset.challengeToken = payload.challenge_token || "";
    form.querySelector("[data-request-step]").hidden = true;
    var codeStep = form.querySelector("[data-code-step]");
    codeStep.hidden = false;
    var codeInput = form.elements.namedItem("code");
    if (codeInput) {
      codeInput.required = true;
      codeInput.focus();
    }
    setMessage(form, payload.message || "Code sent. Check your email for the six-digit code.");
  }

  async function verifyCode(form) {
    setMessage(form, "Verifying your code...");
    var payload = await fetchJson(form.dataset.verifyUrl, {
      method: "POST",
      body: JSON.stringify({
        challenge_token: form.dataset.challengeToken || "",
        code: value(form, "code"),
        next: form.dataset.redirectUrl || "/dashboard"
      })
    });
    setMessage(form, "Email verified. Opening your workspace...");
    await new Promise(function (resolve) {
      window.setTimeout(resolve, 350);
    });
    window.location.assign(payload.redirect_url || "/dashboard");
  }

  function resetTurnstile() {
    if (window.turnstile && typeof window.turnstile.reset === "function") {
      window.turnstile.reset();
    }
  }

  function boot(form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      setBusy(form, true);
      var operation = form.dataset.challengeToken ? verifyCode(form) : requestCode(form);
      operation.catch(function (error) {
        setMessage(form, error.message || "Workdoe could not complete sign-in.");
        if (!form.dataset.challengeToken) {
          resetTurnstile();
        }
      }).finally(function () {
        setBusy(form, false);
      });
    });

    var restart = form.querySelector("[data-restart-code]");
    if (restart) {
      restart.addEventListener("click", function () {
        window.location.reload();
      });
    }
  }

  document.querySelectorAll("[data-email-code-entry]").forEach(boot);
})();
