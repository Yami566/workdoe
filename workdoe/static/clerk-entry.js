(function () {
  "use strict";

  var ROLE_BY_INTENT = {
    "post-job": "client",
    "find-work": "contractor"
  };

  function selectedIntent(scope) {
    var selected = scope.querySelector('input[name="intent"]:checked');
    return selected ? selected.value : "post-job";
  }

  function selectedRole(scope) {
    return ROLE_BY_INTENT[selectedIntent(scope)] || "client";
  }

  function inputValue(scope, selector) {
    var input = scope.querySelector(selector);
    return input ? input.value.trim() : "";
  }

  function clerkUserEmail() {
    var user = window.Clerk && window.Clerk.user;
    if (!user) {
      return "";
    }
    if (user.primaryEmailAddress && user.primaryEmailAddress.emailAddress) {
      return String(user.primaryEmailAddress.emailAddress).trim().toLowerCase();
    }
    var emailAddresses = user.emailAddresses || [];
    for (var index = 0; index < emailAddresses.length; index += 1) {
      if (emailAddresses[index] && emailAddresses[index].emailAddress) {
        return String(emailAddresses[index].emailAddress).trim().toLowerCase();
      }
    }
    return "";
  }

  function setMessage(node, text) {
    var scope = node.closest(".clerk-entry-panel") || document;
    var message = scope.querySelector("[data-clerk-onboarding-message]");
    if (message) {
      message.textContent = text || "";
    }
  }

  function destinationForStart(node, role) {
    if (role === "client") {
      return node.dataset.postJobUrl || node.dataset.dashboardUrl || "/dashboard";
    }
    if (role === "contractor" && node.dataset.selectedJobId) {
      return "/jobs/" + encodeURIComponent(node.dataset.selectedJobId);
    }
    if (role === "contractor") {
      return node.dataset.leadsUrl || "/leads";
    }
    return node.dataset.dashboardUrl || "/dashboard";
  }

  async function fetchJson(url, options) {
    var response = await window.fetch(url, Object.assign({
      credentials: "include",
      headers: { "Accept": "application/json" }
    }, options || {}));
    var payload = await response.json().catch(function () {
      return {};
    });
    if (!response.ok) {
      throw new Error(payload.error || "Workdoe could not finish sign-in.");
    }
    return payload;
  }

  async function finishStartOnboarding(node) {
    if (node.dataset.clerkOnboarding === "running") {
      return true;
    }
    node.dataset.clerkOnboarding = "running";
    var scope = node.closest(".clerk-entry-panel") || document;
    var role = selectedRole(scope);

    try {
      setMessage(node, "Checking Workdoe access...");
      var session = await fetchJson(node.dataset.sessionUrl || "/api/auth/session");
      if (session.workdoe_user) {
        window.location.assign(destinationForStart(node, session.workdoe_user.role || role));
        return true;
      }
      if (!session.onboarding_required) {
        window.location.assign(node.dataset.dashboardUrl || "/dashboard");
        return true;
      }

      setMessage(node, "Creating your Workdoe workspace...");
      var onboardPayload = {
        role: role,
        display_name: inputValue(scope, "[data-clerk-display-name]"),
        company_name: inputValue(scope, "[data-clerk-company-name]")
      };
      var email = clerkUserEmail();
      if (email) {
        onboardPayload.email = email;
      }
      var onboard = await fetchJson(node.dataset.onboardUrl || "/api/auth/onboard", {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify(onboardPayload)
      });
      var createdRole = onboard.workdoe_user ? onboard.workdoe_user.role : role;
      window.location.assign(destinationForStart(node, createdRole));
      return true;
    } catch (error) {
      delete node.dataset.clerkOnboarding;
      setMessage(node, error.message || "Workdoe could not finish sign-in.");
      return false;
    }
  }

  async function finishSignIn(node) {
    if (!node.dataset.sessionUrl) {
      window.location.assign(node.dataset.redirectUrl || "/dashboard");
      return true;
    }
    if (node.dataset.clerkOnboarding === "running") {
      return true;
    }
    node.dataset.clerkOnboarding = "running";

    try {
      setMessage(node, "Checking Workdoe access...");
      var session = await fetchJson(node.dataset.sessionUrl);
      if (session.workdoe_user) {
        window.location.assign(node.dataset.redirectUrl || "/dashboard");
        return true;
      }
      if (session.onboarding_required) {
        window.location.assign(node.dataset.signUpUrl || "/start");
        return true;
      }
      window.location.assign(node.dataset.dashboardUrl || "/dashboard");
      return true;
    } catch (error) {
      delete node.dataset.clerkOnboarding;
      setMessage(node, error.message || "Workdoe could not finish sign-in.");
      return false;
    }
  }

  function formValue(form, name) {
    var field = form.elements.namedItem(name);
    return field && typeof field.value === "string" ? field.value.trim() : "";
  }

  function setBusy(form, busy) {
    form.querySelectorAll("button, input").forEach(function (control) {
      control.disabled = busy;
    });
    form.setAttribute("aria-busy", busy ? "true" : "false");
  }

  function clerkErrorCode(error) {
    var first = error && error.errors && error.errors[0];
    return first && first.code ? String(first.code) : "";
  }

  function clerkErrorMessage(error) {
    var first = error && error.errors && error.errors[0];
    if (first && (first.longMessage || first.message)) {
      return String(first.longMessage || first.message);
    }
    return error && error.message
      ? String(error.message)
      : "Workdoe could not complete email sign-in.";
  }

  function emailCodeFactor(factors) {
    var available = factors || [];
    for (var index = 0; index < available.length; index += 1) {
      if (available[index] && available[index].strategy === "email_code") {
        return available[index];
      }
    }
    return null;
  }

  function needsSignUpField(attempt, fieldName) {
    return !!(
      attempt &&
      attempt.missingFields &&
      attempt.missingFields.indexOf(fieldName) !== -1
    );
  }

  function secureTemporaryPassword() {
    if (!window.crypto || typeof window.crypto.getRandomValues !== "function") {
      throw new Error("Secure email sign-in is unavailable in this browser.");
    }
    var alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
    var randomBytes = new Uint8Array(32);
    window.crypto.getRandomValues(randomBytes);
    var value = "Wd9!";
    for (var index = 0; index < randomBytes.length; index += 1) {
      value += alphabet.charAt(randomBytes[index] % alphabet.length);
    }
    return value;
  }

  function showCodeStep(node, email) {
    var form = node.querySelector("[data-clerk-email-code-form]");
    var requestStep = form.querySelector("[data-clerk-request-step]");
    var codeStep = form.querySelector("[data-clerk-code-step]");
    requestStep.hidden = true;
    codeStep.hidden = false;
    var codeInput = form.elements.namedItem("code");
    if (codeInput) {
      codeInput.required = true;
      codeInput.focus();
    }
    setMessage(node, "Code sent to " + email + ". Check your inbox.");
  }

  async function requestEmailCode(node) {
    var form = node.querySelector("[data-clerk-email-code-form]");
    var email = formValue(form, "email").toLowerCase();
    setMessage(node, "Sending your one-time code...");

    try {
      var signInAttempt = await window.Clerk.client.signIn.create({
        identifier: email
      });
      var factor = emailCodeFactor(signInAttempt.supportedFirstFactors);
      if (!factor) {
        throw new Error("Email code sign-in is not available for this account.");
      }
      await window.Clerk.client.signIn.prepareFirstFactor({
        strategy: "email_code",
        emailAddressId: factor.emailAddressId
      });
      node.dataset.clerkFlow = "signin";
      showCodeStep(node, email);
      return;
    } catch (error) {
      if (clerkErrorCode(error) !== "form_identifier_not_found") {
        throw error;
      }
    }

    var signUpAttempt = await window.Clerk.client.signUp.create({
      emailAddress: email
    });
    if (needsSignUpField(signUpAttempt, "password")) {
      await window.Clerk.client.signUp.update({
        password: secureTemporaryPassword()
      });
    }
    await window.Clerk.client.signUp.prepareEmailAddressVerification({
      strategy: "email_code"
    });
    node.dataset.clerkFlow = "signup";
    showCodeStep(node, email);
  }

  async function finishClerkAttempt(node, attempt) {
    if (!attempt || attempt.status !== "complete" || !attempt.createdSessionId) {
      window.console.error("Clerk email verification is incomplete.", {
        status: attempt && attempt.status,
        missingFields: attempt && attempt.missingFields,
        unverifiedFields: attempt && attempt.unverifiedFields
      });
      throw new Error("Email verification needs another step. Please restart and try again.");
    }
    setMessage(node, "Email verified. Opening your workspace...");
    await window.Clerk.setActive({ session: attempt.createdSessionId });
    if (node.dataset.clerkMode === "start") {
      await finishStartOnboarding(node);
    } else {
      await finishSignIn(node);
    }
  }

  async function verifyEmailCode(node) {
    var form = node.querySelector("[data-clerk-email-code-form]");
    var code = formValue(form, "code");
    setMessage(node, "Verifying your code...");
    var attempt;
    if (node.dataset.clerkFlow === "signup") {
      attempt = await window.Clerk.client.signUp.attemptEmailAddressVerification({
        code: code
      });
    } else {
      attempt = await window.Clerk.client.signIn.attemptFirstFactor({
        strategy: "email_code",
        code: code
      });
    }
    await finishClerkAttempt(node, attempt);
  }

  function bindEmailCodeForm(node) {
    var form = node.querySelector("[data-clerk-email-code-form]");
    if (!form) {
      throw new Error("Email sign-in form is unavailable.");
    }
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      setBusy(form, true);
      var operation = node.dataset.clerkFlow
        ? verifyEmailCode(node)
        : requestEmailCode(node);
      operation.catch(function (error) {
        setMessage(node, clerkErrorMessage(error));
      }).finally(function () {
        setBusy(form, false);
      });
    });

    var restart = form.querySelector("[data-clerk-restart-code]");
    if (restart) {
      restart.addEventListener("click", function () {
        window.location.reload();
      });
    }

    setBusy(form, false);
  }

  function clerkLoadOptions(node) {
    var options = {};
    if (node.dataset.clerkProxyUrl) {
      options.proxyUrl = node.dataset.clerkProxyUrl;
    }
    return options;
  }

  async function loadClerk(node) {
    if (!window.Clerk || typeof window.Clerk.load !== "function") {
      node.dataset.state = "unavailable";
      setMessage(node, "Clerk sign-in is not available yet.");
      return;
    }

    await window.Clerk.load(clerkLoadOptions(node));

    if (window.Clerk.isSignedIn) {
      if (node.dataset.clerkMode === "start") {
        await finishStartOnboarding(node);
        return;
      }
      await finishSignIn(node);
      return;
    }

    bindEmailCodeForm(node);
    node.dataset.state = "ready";
    setMessage(node, "");

    if (typeof window.Clerk.addListener === "function") {
      window.Clerk.addListener(function () {
        if (!window.Clerk.isSignedIn) {
          return;
        }
        if (node.dataset.clerkMode === "start") {
          finishStartOnboarding(node);
        } else {
          finishSignIn(node);
        }
      });
    }
  }

  function boot() {
    var mounts = document.querySelectorAll("[data-clerk-entry]");
    mounts.forEach(function (node) {
      loadClerk(node).catch(function (error) {
        window.console.error("Clerk email-code initialization failed.", error);
        node.dataset.state = "failed";
        setMessage(node, "Clerk sign-in could not load.");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
