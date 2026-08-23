(function () {
  "use strict";

  function setStatus(node, message) {
    var status = node.querySelector("[data-clerk-account-status]");
    if (status) {
      status.textContent = message || "";
    }
  }

  function clerkLoadOptions(node) {
    var options = {
      telemetry: false,
      ui: { ClerkUI: window.__internal_ClerkUICtor }
    };
    if (node.dataset.clerkProxyUrl) {
      options.proxyUrl = node.dataset.clerkProxyUrl;
    }
    return options;
  }

  async function mountAccount(node) {
    if (!window.Clerk || typeof window.Clerk.load !== "function" || !window.__internal_ClerkUICtor) {
      throw new Error("Account settings are temporarily unavailable.");
    }

    await window.Clerk.load(clerkLoadOptions(node));
    if (!window.Clerk.isSignedIn) {
      window.location.assign("/login?next=/account");
      return;
    }
    if (typeof window.Clerk.mountUserProfile !== "function") {
      throw new Error("Account settings are temporarily unavailable.");
    }

    setStatus(node, "");
    window.Clerk.mountUserProfile(node, { routing: "hash" });
    node.dataset.state = "ready";
  }

  function boot() {
    document.querySelectorAll("[data-clerk-account]").forEach(function (node) {
      mountAccount(node).catch(function (error) {
        window.console.error("Clerk account settings failed to load.", error);
        node.dataset.state = "failed";
        setStatus(node, error.message || "Account settings are temporarily unavailable.");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
