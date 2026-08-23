(function () {
  "use strict";

  var ROLE_BY_INTENT = {
    "post-job": "client",
    "find-work": "contractor"
  };
  var PROFILE_STATE_MAX_AGE_MS = 30 * 60 * 1000;

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

  function clerkUserDisplayName() {
    var user = window.Clerk && window.Clerk.user;
    if (!user) {
      return "";
    }
    var name = String(user.fullName || user.firstName || "").trim();
    if (name) {
      return name.slice(0, 120);
    }
    var email = clerkUserEmail();
    return email ? email.split("@", 1)[0].slice(0, 120) : "";
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
      companyName: inputValue(scope, "[data-clerk-company-name]").slice(0, 120),
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
    var companyName = scope.querySelector("[data-clerk-company-name]");
    if (roleChoice) {
      roleChoice.checked = true;
    }
    if (displayName && !displayName.value) {
      displayName.value = String(state.displayName || "").slice(0, 120);
    }
    if (companyName && !companyName.value) {
      companyName.value = String(state.companyName || "").slice(0, 120);
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
      if (event.target.matches('[name="intent"], [data-clerk-display-name], [data-clerk-company-name]')) {
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

      setMessage(node, "Creating your Workdoe workspace...");
      var onboardPayload = {
        role: role,
        display_name: inputValue(scope, "[data-clerk-display-name]") || clerkUserDisplayName(),
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

  function mountClerkSignIn(node) {
    if (typeof window.Clerk.mountSignIn !== "function") {
      throw new Error("Clerk sign-in is temporarily unavailable.");
    }
    var returnUrl = clerkReturnUrl();
    window.Clerk.mountSignIn(node, {
      routing: "hash",
      withSignUp: true,
      forceRedirectUrl: returnUrl,
      signUpForceRedirectUrl: returnUrl
    });
    node.dataset.state = "ready";
    setMessage(node, "");
  }

  async function loadClerk(node) {
    if (!window.Clerk || typeof window.Clerk.load !== "function" || !window.__internal_ClerkUICtor) {
      node.dataset.state = "unavailable";
      setMessage(node, "Secure email sign-in is not available yet.");
      return;
    }

    bindProfileState(node);
    await window.Clerk.load(clerkLoadOptions(node));

    if (window.Clerk.isSignedIn) {
      if (node.dataset.clerkMode === "start") {
        await finishStartOnboarding(node);
        return;
      }
      await finishSignIn(node);
      return;
    }

    mountClerkSignIn(node);
  }

  function boot() {
    document.querySelectorAll("[data-clerk-entry]").forEach(function (node) {
      loadClerk(node).catch(function (error) {
        window.console.error("Clerk sign-in initialization failed.", error);
        node.dataset.state = "failed";
        setMessage(node, "Secure email sign-in could not load.");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
