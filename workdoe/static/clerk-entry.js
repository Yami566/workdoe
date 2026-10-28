(function () {
  "use strict";

  var ROLE_BY_INTENT = {
    "post-job": "client",
    "find-work": "contractor"
  };
  var PROFILE_STATE_MAX_AGE_MS = 30 * 60 * 1000;
  var CLERK_LOAD_TIMEOUT_MS = 15000;
  var CLERK_LOAD_TIMEOUT_MESSAGE = "Secure email sign-in is taking longer than expected. Close this window and try again.";
  var CLERK_UNAVAILABLE_MESSAGE = "Secure email sign-in could not load. Refresh the page and try again.";
  var SESSION_REFRESH_MESSAGE = "We could not confirm the previous sign-in. Use a new email code to continue.";

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

  function entryScope(node) {
    return node.closest(".clerk-entry-panel") || document;
  }

  function setMessage(node, text) {
    var message = entryScope(node).querySelector("[data-clerk-onboarding-message]");
    if (message) {
      message.textContent = text || "";
    }
  }

  function setEntryFailure(node, message) {
    var loading = typeof node.querySelector === "function"
      ? node.querySelector(".clerk-entry-loading")
      : null;
    if (loading) {
      loading.textContent = message;
    }
    setMessage(node, message);
  }

  function sessionRecovery(node) {
    return entryScope(node).querySelector("[data-clerk-session-recovery]");
  }

  function showSessionRecovery(node) {
    var recovery = sessionRecovery(node);
    if (!recovery) {
      setEntryFailure(node, SESSION_REFRESH_MESSAGE);
      return;
    }
    hideEntryLoading(node);
    recovery.hidden = false;
    recovery.removeAttribute("aria-hidden");
    node.dataset.state = "session-rejected";
    setMessage(node, SESSION_REFRESH_MESSAGE);
  }

  async function restartWithFreshEmailCode(node) {
    var clerk = window.Clerk;
    if (!clerk || typeof clerk.signOut !== "function") {
      setEntryFailure(node, "Refresh this page, then use a new email code.");
      return;
    }
    setMessage(node, "Resetting this browser session...");
    await clerk.signOut({ redirectUrl: clerkReturnUrl() });
    window.location.assign(clerkReturnUrl());
  }

  function bindSessionRecovery(node) {
    var recovery = sessionRecovery(node);
    if (!recovery || recovery.dataset.bound === "true") {
      return;
    }
    recovery.dataset.bound = "true";
    var button = recovery.querySelector("[data-clerk-session-retry]");
    if (!button) {
      return;
    }
    button.addEventListener("click", function () {
      button.disabled = true;
      restartWithFreshEmailCode(node).catch(function () {
        button.disabled = false;
        setMessage(node, "Refresh this page, then use a new email code.");
      });
    });
  }

  function hideEntryLoading(node) {
    var loading = typeof node.querySelector === "function"
      ? node.querySelector(".clerk-entry-loading")
      : null;
    if (loading) {
      loading.hidden = true;
      loading.setAttribute("aria-hidden", "true");
    }
  }

  function profileStateKey() {
    return "workdoe-clerk-profile-v1:" + window.location.pathname;
  }

  function readProfileState() {
    try {
      var value = window.sessionStorage.getItem(profileStateKey());
      if (!value) {
        return null;
      }
      var state = JSON.parse(value);
      if (!state || Date.now() - Number(state.savedAt || 0) > PROFILE_STATE_MAX_AGE_MS) {
        window.sessionStorage.removeItem(profileStateKey());
        return null;
      }
      return state;
    } catch (error) {
      return null;
    }
  }

  function writeProfileState(node) {
    if (node.dataset.clerkMode !== "start") {
      return;
    }
    var scope = entryScope(node);
    var state = {
      intent: selectedIntent(scope),
      displayName: inputValue(scope, "[data-clerk-display-name]").slice(0, 120),
      savedAt: Date.now()
    };
    try {
      window.sessionStorage.setItem(profileStateKey(), JSON.stringify(state));
    } catch (error) {
      return;
    }
  }

  function restoreProfileState(node) {
    if (node.dataset.clerkMode !== "start") {
      return;
    }
    var state = readProfileState();
    if (!state) {
      return;
    }
    var scope = entryScope(node);
    var roleChoice = scope.querySelector('input[name="intent"][value="' + state.intent + '"]');
    var displayName = scope.querySelector("[data-clerk-display-name]");
    if (roleChoice) {
      roleChoice.checked = true;
    }
    if (displayName && !displayName.value) {
      displayName.value = String(state.displayName || "").slice(0, 120);
    }
  }

  function clearProfileState() {
    try {
      window.sessionStorage.removeItem(profileStateKey());
    } catch (error) {
      return;
    }
  }

  function bindProfileState(node) {
    if (node.dataset.clerkMode !== "start") {
      return;
    }
    var scope = entryScope(node);
    restoreProfileState(node);
    scope.addEventListener("input", function (event) {
      if (event.target.matches('[name="intent"], [data-clerk-display-name]')) {
        writeProfileState(node);
      }
    });
    scope.addEventListener("change", function (event) {
      if (event.target.matches('[name="intent"]')) {
        writeProfileState(node);
      }
    });
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

  async function clerkSessionToken() {
    var clerk = window.Clerk;
    if (!clerk || !clerk.session || typeof clerk.session.getToken !== "function") {
      return "";
    }
    try {
      // A fresh token avoids a race between Clerk completing the email-code flow
      // and the app cookie being available to the Worker.
      return await clerk.session.getToken({skipCache: true}) || "";
    } catch (error) {
      return "";
    }
  }

  function isSameOrigin(url) {
    try {
      return new URL(url, window.location.origin).origin === window.location.origin;
    } catch (error) {
      return false;
    }
  }

  async function fetchJson(url, options) {
    var requestOptions = Object.assign({}, options || {});
    var headers = Object.assign(
      { "Accept": "application/json" },
      requestOptions.headers || {}
    );
    if (isSameOrigin(url) && !headers.Authorization && !headers.authorization) {
      var token = await clerkSessionToken();
      if (token) {
        headers.Authorization = "Bearer " + token;
      }
    }
    requestOptions.headers = headers;
    var response = await window.fetch(url, Object.assign({
      credentials: "include"
    }, requestOptions));
    var payload = await response.json().catch(function () {
      return {};
    });
    if (!response.ok) {
      var error = new Error(payload.error || "Workdoe could not finish sign-in.");
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  async function finishStartOnboarding(node) {
    if (node.dataset.clerkOnboarding === "running") {
      return true;
    }
    node.dataset.clerkOnboarding = "running";
    restoreProfileState(node);
    var scope = entryScope(node);
    var role = selectedRole(scope);

    try {
      setMessage(node, "Checking Workdoe access...");
      var session = await fetchJson(node.dataset.sessionUrl || "/api/auth/session");
      if (session.workdoe_user) {
        clearProfileState();
        window.location.assign(destinationForStart(node, session.workdoe_user.role || role));
        return true;
      }
      if (!session.onboarding_required) {
        clearProfileState();
        window.location.assign(node.dataset.dashboardUrl || "/dashboard");
        return true;
      }

      var displayName = inputValue(scope, "[data-clerk-display-name]");
      if (!displayName) {
        setMessage(node, "Choose a public business name or non-identifying handle before continuing.");
        var displayNameInput = scope.querySelector("[data-clerk-display-name]");
        if (displayNameInput && typeof displayNameInput.focus === "function") {
          displayNameInput.focus();
        }
        delete node.dataset.clerkOnboarding;
        return false;
      }

      setMessage(node, "Creating your Workdoe workspace...");
      var onboardPayload = {
        role: role,
        display_name: displayName
      };
      var onboard = await fetchJson(node.dataset.onboardUrl || "/api/auth/onboard", {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-Workdoe-Request": "same-origin"
        },
        body: JSON.stringify(onboardPayload)
      });
      var createdRole = onboard.workdoe_user ? onboard.workdoe_user.role : role;
      clearProfileState();
      window.location.assign(destinationForStart(node, createdRole));
      return true;
    } catch (error) {
      delete node.dataset.clerkOnboarding;
      if (error && error.status === 401) {
        showSessionRecovery(node);
        return false;
      }
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
        window.location.assign(node.dataset.signUpUrl || "/create-account");
        return true;
      }
      window.location.assign(node.dataset.dashboardUrl || "/dashboard");
      return true;
    } catch (error) {
      delete node.dataset.clerkOnboarding;
      if (error && error.status === 401) {
        showSessionRecovery(node);
        return false;
      }
      setMessage(node, error.message || "Workdoe could not finish sign-in.");
      return false;
    }
  }

  function clerkLoadOptions(node) {
    var options = {
      telemetry: false,
      ui: { ClerkUI: window.__internal_ClerkUICtor },
      appearance: {
        options: {
          elevation: "flush",
          logoLinkUrl: "/"
        },
        variables: {
          colorPrimary: "#1b2b22",
          colorPrimaryForeground: "#ffffff",
          colorForeground: "#111512",
          colorMutedForeground: "#536057",
          colorBackground: "#ffffff",
          colorInput: "#ffffff",
          colorInputForeground: "#111512",
          colorBorder: "#c7d0c8",
          colorRing: "#1b2b22",
          borderRadius: "6px",
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
        }
      }
    };
    if (node.dataset.clerkProxyUrl) {
      options.proxyUrl = node.dataset.clerkProxyUrl;
    }
    return options;
  }

  function clerkReturnUrl() {
    return window.location.pathname + window.location.search;
  }

  function mountClerkEntry(node) {
    var returnUrl = clerkReturnUrl();
    if (node.dataset.clerkMode === "start") {
      if (typeof window.Clerk.mountSignUp !== "function") {
        throw new Error("Clerk account creation is temporarily unavailable.");
      }
      window.Clerk.mountSignUp(node, {
        routing: "hash",
        forceRedirectUrl: returnUrl,
        signInUrl: "/login",
        signInForceRedirectUrl: returnUrl
      });
    } else {
      if (typeof window.Clerk.mountSignIn !== "function") {
        throw new Error("Clerk sign-in is temporarily unavailable.");
      }
      window.Clerk.mountSignIn(node, {
        routing: "hash",
        withSignUp: false,
        forceRedirectUrl: returnUrl,
        signUpUrl: node.dataset.signUpUrl || "/create-account",
        signUpForceRedirectUrl: returnUrl
      });
    }
    node.dataset.state = "ready";
    setMessage(node, "");
    hideEntryLoading(node);
  }

  function continueWithActiveSession(node) {
    if (node.dataset.clerkOnboarding === "running") {
      return;
    }
    if (node.dataset.clerkMode === "start") {
      finishStartOnboarding(node);
      return;
    }
    finishSignIn(node);
  }

  function bindClerkSessionListener(node) {
    if (
      node.dataset.clerkListenerBound === "true" ||
      !window.Clerk ||
      typeof window.Clerk.addListener !== "function"
    ) {
      return;
    }
    node.dataset.clerkListenerBound = "true";
    window.Clerk.addListener(function (emission) {
      if (!emission || !emission.session || !emission.user) {
        return;
      }
      continueWithActiveSession(node);
    }, {skipInitialEmit: true});
  }

  function loadClerkWithTimeout(node) {
    var timeoutId;
    var timedOut = new Promise(function (resolve, reject) {
      timeoutId = window.setTimeout(function () {
        reject(new Error(CLERK_LOAD_TIMEOUT_MESSAGE));
      }, CLERK_LOAD_TIMEOUT_MS);
    });
    return Promise.race([
      Promise.resolve(window.Clerk.load(clerkLoadOptions(node))),
      timedOut
    ]).then(function (value) {
      window.clearTimeout(timeoutId);
      return value;
    }, function (error) {
      window.clearTimeout(timeoutId);
      throw error;
    });
  }

  async function loadClerk(node) {
    if (!window.Clerk || typeof window.Clerk.load !== "function" || !window.__internal_ClerkUICtor) {
      node.dataset.state = "unavailable";
      setEntryFailure(node, CLERK_UNAVAILABLE_MESSAGE);
      return;
    }

    bindProfileState(node);
    bindSessionRecovery(node);
    await loadClerkWithTimeout(node);
    bindClerkSessionListener(node);

    if (window.Clerk.isSignedIn) {
      continueWithActiveSession(node);
      return;
    }

    mountClerkEntry(node);
  }

  function boot() {
    document.querySelectorAll("[data-clerk-entry]").forEach(function (node) {
      if (node.dataset.clerkInitialized === "true") {
        return;
      }
      node.dataset.clerkInitialized = "true";
      loadClerk(node).catch(function (error) {
        window.console.error("Clerk sign-in initialization failed.");
        node.dataset.state = "failed";
        setEntryFailure(
          node,
          error && error.message === CLERK_LOAD_TIMEOUT_MESSAGE
            ? CLERK_LOAD_TIMEOUT_MESSAGE
            : CLERK_UNAVAILABLE_MESSAGE
        );
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
