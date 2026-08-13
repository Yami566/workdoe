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

  async function loadClerk(node) {
    if (!window.Clerk || typeof window.Clerk.load !== "function") {
      node.dataset.state = "unavailable";
      setMessage(node, "Clerk sign-in is not available yet.");
      return;
    }

    var loadOptions = {};
    if (window.__internal_ClerkUICtor) {
      loadOptions.ui = { ClerkUI: window.__internal_ClerkUICtor };
    }
    if (node.dataset.clerkProxyUrl) {
      loadOptions.proxyUrl = node.dataset.clerkProxyUrl;
    }
    await window.Clerk.load(loadOptions);

    if (window.Clerk.isSignedIn) {
      if (node.dataset.clerkMode === "start") {
        await finishStartOnboarding(node);
        return;
      }
      await finishSignIn(node);
      return;
    }

    if (typeof window.Clerk.mountSignIn === "function") {
      window.Clerk.mountSignIn(node, {
        routing: "hash",
        withSignUp: true,
        signUpUrl: node.dataset.signUpUrl || "/start",
        fallbackRedirectUrl: node.dataset.redirectUrl || "/dashboard",
        forceRedirectUrl: node.dataset.redirectUrl || "/dashboard",
        signUpFallbackRedirectUrl: node.dataset.redirectUrl || "/dashboard",
        signUpForceRedirectUrl: node.dataset.redirectUrl || "/dashboard"
      });
    }

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
      loadClerk(node).catch(function () {
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
