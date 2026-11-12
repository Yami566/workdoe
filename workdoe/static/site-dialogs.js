(function () {
  "use strict";

  var dialog = document.querySelector("[data-site-dialog]");
  var content = dialog && dialog.querySelector("[data-site-dialog-content]");
  var status = dialog && dialog.querySelector("[data-site-dialog-status]");
  var title = dialog && dialog.querySelector("[data-site-dialog-title]");
  var closeButton = dialog && dialog.querySelector("[data-site-dialog-close]");
  var returnFocus = null;
  var returnPanel = null;
  var backgroundUrl = "";
  var currentCanonicalUrl = "";
  var requestSequence = 0;
  var requestController = null;
  var loadedLibraries = {};
  var DIALOG_FRAGMENT_TIMEOUT_MS = 12000;
  var CLERK_DIALOG_SCRIPT_TIMEOUT_MS = 15000;
  var modalPaths = [
    "/login",
    "/start",
    "/start/verify",
    "/create-account",
    "/post-project",
    "/jobs/new"
  ];
  var contractorJobPath = /^\/jobs\/[1-9][0-9]*$/;
  var repeatableBootScripts = [
    "/clerk-entry.js",
    "/email-code-entry.js",
    "/project-composer.js"
  ];
  var singleLoadScripts = ["/worker-actions.js"];

  function verificationStatus(widget, message) {
    var field = widget.closest(".turnstile-field");
    var notice = field && field.querySelector("[data-turnstile-status]");
    if (notice) {
      notice.textContent = message;
    }
  }

  function clearVerificationNotice(widget) {
    var form = widget.closest("form");
    var notice = form && form.querySelector("[data-form-status]");
    if (notice && notice.dataset.turnstileNotice === "true") {
      notice.textContent = "";
      delete notice.dataset.turnstileNotice;
    }
  }

  var turnstileScript = document.querySelector('script[src^="https://challenges.cloudflare.com/turnstile/v0/api.js"]');
  if (turnstileScript) {
    turnstileScript.addEventListener("load", function () { renderTurnstile(document); }, { once: true });
    turnstileScript.addEventListener("error", function () {
      document.querySelectorAll("[data-workdoe-turnstile]").forEach(function (widget) {
        verificationStatus(widget, "Verification could not load. Retry when your connection is available.");
      });
    }, { once: true });
  }
  renderTurnstile(document);

  document.addEventListener("submit", function (event) {
    var form = event.target;
    var widget = form && form.querySelector && form.querySelector("[data-workdoe-turnstile]");
    if (!widget) {
      return;
    }
    var response = form.querySelector('input[name="cf-turnstile-response"]');
    if (response && response.value.trim()) {
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    var notice = form.querySelector("[data-form-status]");
    if (notice) {
      notice.dataset.turnstileNotice = "true";
      notice.textContent = "Complete verification before saving. Use Retry verification if the check is missing.";
    }
    renderTurnstile(form);
    var field = widget.closest(".turnstile-field");
    var retry = field && field.querySelector("[data-turnstile-retry]");
    if (retry) {
      retry.focus();
    }
  }, true);

  document.addEventListener("click", function (event) {
    var button = event.target && event.target.closest && event.target.closest("[data-turnstile-retry]");
    if (!button || button.disabled) {
      return;
    }
    var field = button.closest(".turnstile-field");
    var widget = field && field.querySelector("[data-workdoe-turnstile]");
    if (!widget) {
      return;
    }
    var form = widget.closest("form");
    if (form) {
      form.querySelectorAll('input[name="cf-turnstile-response"]').forEach(function (response) {
        response.value = "";
      });
    }
    verificationStatus(widget, "Loading verification...");
    if (window.turnstile && typeof window.turnstile.render === "function") {
      try {
        if (widget.dataset.turnstileWidgetId && typeof window.turnstile.reset === "function") {
          window.turnstile.reset(widget.dataset.turnstileWidgetId);
        } else {
          renderTurnstile(field);
        }
      } catch (error) {
        verificationStatus(widget, "Verification could not restart. Please try again.");
      }
      return;
    }
    var retryScript = document.querySelector('script[src^="https://challenges.cloudflare.com/turnstile/v0/api.js"]');
    if (!retryScript) {
      verificationStatus(widget, "Verification is unavailable on this page.");
      return;
    }
    button.disabled = true;
    var sourceUrl = new URL(retryScript.src, window.location.href);
    delete loadedLibraries[sourceUrl.origin + sourceUrl.pathname + sourceUrl.search];
    var timeout;
    Promise.race([
      loadScript(retryScript),
      new Promise(function (_, reject) {
        timeout = window.setTimeout(function () {
          reject(new Error("Verification is taking too long. Please retry."));
        }, 15000);
      })
    ]).then(function () {
      if (!window.turnstile) {
        throw new Error("Verification did not initialize.");
      }
      renderTurnstile(field);
    }).catch(function () {
      verificationStatus(widget, "Verification could not load. Check your connection or browser blocker, then retry.");
    }).finally(function () {
      window.clearTimeout(timeout);
      button.disabled = false;
    });
  });

  if (!dialog || !content || !status || !closeButton) {
    return;
  }

  function dialogIsOpen() {
    return Boolean(dialog.open || dialog.hasAttribute("open"));
  }

  function wrapDialogFocus(event) {
    if (
      event.key !== "Tab" || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey ||
      !dialogIsOpen() || !event.target.closest || event.target.closest("dialog[open]") !== dialog
    ) {
      return;
    }
    // Keep one modal tab order even when the browser's default skips links.
    var controls = Array.prototype.filter.call(dialog.querySelectorAll(
      'a[href], button, input, select, textarea, iframe, summary, [tabindex], [contenteditable="true"]'
    ), function (node) {
      var style = window.getComputedStyle(node);
      return node.tabIndex >= 0 && !node.matches(":disabled") && !node.closest("[hidden], [inert]") &&
        node.getClientRects().length > 0 && style.visibility !== "hidden" && style.visibility !== "collapse";
    });
    controls = controls.filter(function (node) {
      if (node.type !== "radio" || !node.name) {
        return true;
      }
      var group = controls.filter(function (peer) {
        return peer.type === "radio" && peer.name === node.name && peer.form === node.form;
      });
      var checked = group.find(function (peer) { return peer.checked; });
      return node === (checked || group[0]);
    }).sort(function (left, right) {
      return (left.tabIndex || Infinity) - (right.tabIndex || Infinity);
    });
    if (!controls.length) {
      return;
    }
    var current = controls.indexOf(document.activeElement);
    if (current === -1) {
      return;
    }
    event.preventDefault();
    controls[(current + (event.shiftKey ? -1 : 1) + controls.length) % controls.length].focus();
  }

  function isModalPath(pathname) {
    return modalPaths.indexOf(pathname) !== -1 || contractorJobPath.test(pathname);
  }

  function dialogTarget(anchor) {
    if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download") || anchor.hasAttribute("data-dialog-bypass")) {
      return null;
    }
    if (!dialogIsOpen() && isModalPath(window.location.pathname)) {
      return null;
    }
    var url;
    try {
      url = new URL(anchor.href, window.location.href);
    } catch (error) {
      return null;
    }
    if (url.origin !== window.location.origin || !isModalPath(url.pathname)) {
      return null;
    }
    if (
      contractorJobPath.test(url.pathname) &&
      !dialogIsOpen() &&
      !anchor.hasAttribute("data-dialog-title")
    ) {
      return null;
    }
    url.searchParams.delete("embed");
    return url;
  }

  function labelFor(url, anchor) {
    if (anchor && anchor.dataset.dialogTitle) {
      return anchor.dataset.dialogTitle;
    }
    if (url.pathname === "/login") {
      return "Sign in";
    }
    if (url.pathname === "/post-project" || url.pathname === "/jobs/new") {
      return "Post a project";
    }
    if (contractorJobPath.test(url.pathname)) {
      return "Review and bid";
    }
    if (url.pathname === "/start/verify") {
      return "Verify your email";
    }
    return "Create account";
  }

  function kindFor(url) {
    if (url.pathname === "/login" || url.pathname === "/start/verify") {
      return "auth";
    }
    if (url.pathname === "/post-project" || url.pathname === "/jobs/new") {
      return "project";
    }
    if (contractorJobPath.test(url.pathname)) {
      return "bid";
    }
    return "flow";
  }

  function canonicalPath(url) {
    var clean = new URL(url.href);
    clean.searchParams.delete("embed");
    return clean.pathname + clean.search + clean.hash;
  }

  function updateDialogHistory(url, replace) {
    var path = canonicalPath(url);
    var state = {
      workdoeDialog: true,
      dialogUrl: path,
      backgroundUrl: backgroundUrl
    };
    if (replace) {
      window.history.replaceState(state, "", path);
    } else {
      window.history.pushState(state, "", path);
    }
    currentCanonicalUrl = path;
  }

  function showDialog() {
    if (dialogIsOpen()) {
      return;
    }
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
    document.body.classList.add("has-site-dialog");
  }

  function setLoading(message) {
    delete dialog.dataset.dialogRecovery;
    disposeDialogContent();
    content.replaceChildren();
    status.hidden = false;
    status.textContent = message || "Loading...";
    dialog.setAttribute("aria-busy", "true");
  }

  function setReady() {
    status.hidden = true;
    status.textContent = "";
    dialog.removeAttribute("aria-busy");
  }

  function fragmentFromDocument(parsed) {
    return parsed.querySelector("[data-dialog-fragment]") || parsed.querySelector("main");
  }

  function scriptPathMatches(pathname, suffixes) {
    return suffixes.some(function (suffix) {
      return pathname === suffix || pathname.endsWith(suffix);
    });
  }

  function scriptKind(url) {
    if (scriptPathMatches(url.pathname, repeatableBootScripts)) {
      return "boot";
    }
    if (url.origin === window.location.origin && scriptPathMatches(url.pathname, singleLoadScripts)) {
      return "library";
    }
    if (url.origin === "https://challenges.cloudflare.com" && url.pathname === "/turnstile/v0/api.js") {
      return "library";
    }
    var clerkHost = url.origin === window.location.origin || url.hostname === "clerk.workdoe.com" || url.hostname.endsWith(".clerk.accounts.dev");
    if (clerkHost && url.pathname.indexOf("/npm/@clerk/") !== -1) {
      return "library";
    }
    return "";
  }

  function copyScriptAttributes(source, target) {
    Array.prototype.forEach.call(source.attributes, function (attribute) {
      if (attribute.name !== "src" && attribute.name !== "async" && attribute.name !== "defer") {
        target.setAttribute(attribute.name, attribute.value);
      }
    });
  }

  function loadScript(source) {
    var url;
    try {
      url = new URL(source.getAttribute("src"), window.location.href);
    } catch (error) {
      return Promise.resolve();
    }
    var kind = scriptKind(url);
    if (!kind) {
      return Promise.resolve();
    }
    var key = url.origin + url.pathname + (
      url.origin === "https://challenges.cloudflare.com" ? url.search : ""
    );
    if (kind === "library" && loadedLibraries[key]) {
      return loadedLibraries[key];
    }
    var clerkSdk = url.pathname.indexOf("/npm/@clerk/clerk-js@") !== -1;
    var clerkUi = url.pathname.indexOf("/npm/@clerk/ui@") !== -1;
    var libraryAlreadyReady = (url.origin === "https://challenges.cloudflare.com" && Boolean(window.turnstile) && typeof window.turnstile.render === "function") ||
      (clerkSdk && Boolean(window.Clerk)) ||
      (clerkUi && Boolean(window.__internal_ClerkUICtor)) ||
      (url.origin === window.location.origin && scriptPathMatches(url.pathname, singleLoadScripts));
    if (kind === "library" && libraryAlreadyReady && Array.prototype.some.call(document.querySelectorAll("script[src]"), function (script) {
      try {
        var existing = new URL(script.src, window.location.href);
        return existing.origin + existing.pathname + (
          existing.origin === "https://challenges.cloudflare.com" ? existing.search : ""
        ) === key;
      } catch (error) {
        return false;
      }
    })) {
      loadedLibraries[key] = Promise.resolve();
      return loadedLibraries[key];
    }
    var pending = new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      var timer = null;
      var settled = false;
      function finish(error) {
        if (settled) {
          return;
        }
        settled = true;
        if (timer !== null) {
          window.clearTimeout(timer);
        }
        if (error) {
          script.remove();
          reject(error);
        } else {
          resolve();
        }
      }
      copyScriptAttributes(source, script);
      script.src = url.href;
      script.async = false;
      script.addEventListener("load", function () { finish(); }, { once: true });
      script.addEventListener("error", function () {
        finish(new Error("A required Workdoe form could not load."));
      }, { once: true });
      if (clerkSdk || clerkUi || scriptPathMatches(url.pathname, ["/clerk-entry.js"])) {
        timer = window.setTimeout(function () {
          finish(new Error("Sign-in took too long to load."));
        }, CLERK_DIALOG_SCRIPT_TIMEOUT_MS);
      }
      document.head.appendChild(script);
    });
    if (kind === "library") {
      loadedLibraries[key] = pending;
      pending.catch(function () {
        if (loadedLibraries[key] === pending) {
          delete loadedLibraries[key];
        }
      });
    }
    return pending;
  }

  function loadDialogScripts(parsed, sequence) {
    var scripts = Array.prototype.slice.call(parsed.querySelectorAll("script[src]"));
    return scripts.reduce(function (promise, source) {
      return promise.then(function () {
        if (sequence === requestSequence) {
          return loadScript(source);
        }
      });
    }, Promise.resolve());
  }

  function renderTurnstile(root) {
    if (!window.turnstile || typeof window.turnstile.render !== "function") {
      return;
    }
    var renderWidgets = function () {
      if (typeof window.turnstile.render !== "function") {
        return;
      }
      (root || content).querySelectorAll("[data-workdoe-turnstile]").forEach(function (widget) {
        if (widget.isConnected === false || widget.dataset.turnstileWidgetId) {
          return;
        }
        try {
          var widgetId = window.turnstile.render(widget, {
            sitekey: widget.dataset.sitekey,
            action: widget.dataset.action,
            theme: widget.dataset.theme || "light",
            callback: function () {
              verificationStatus(widget, "Verification complete.");
              clearVerificationNotice(widget);
            },
            "error-callback": function () {
              verificationStatus(widget, "Verification could not finish. Please retry.");
            },
            "expired-callback": function () {
              verificationStatus(widget, "Verification expired. Please verify again before saving.");
            },
            "timeout-callback": function () {
              verificationStatus(widget, "Verification timed out. Please retry.");
            }
          });
          if (typeof widgetId === "undefined" || widgetId === null) {
            throw new Error("Widget was not created.");
          }
          widget.dataset.turnstileWidgetId = String(widgetId);
        } catch (error) {
          verificationStatus(widget, "Verification could not start. Please retry.");
        }
      });
    };
    // The SDK rejects ready() for async/defer loads; startup uses its load event.
    renderWidgets();
  }

  function removeTurnstileWidgets(root) {
    if (!root || !window.turnstile || typeof window.turnstile.remove !== "function") {
      return;
    }
    root.querySelectorAll("[data-turnstile-widget-id]").forEach(function (widget) {
      var widgetId = widget.dataset.turnstileWidgetId;
      delete widget.dataset.turnstileWidgetId;
      if (!widgetId) {
        return;
      }
      try {
        window.turnstile.remove(widgetId);
      } catch (error) {
        // A completed challenge must not block dialog navigation or cleanup.
      }
    });
  }

  function disposeDialogContent() {
    removeTurnstileWidgets(content);
    content.querySelectorAll("[data-clerk-entry]").forEach(function (entry) {
      if (typeof entry._workdoeClerkDispose === "function") {
        entry._workdoeClerkDispose();
      }
    });
  }

  function focusDialogContent() {
    var target = content.querySelector('[data-dialog-focus], [aria-invalid="true"], [autofocus], input:not([type="hidden"]), select, textarea, button, a[href]');
    if (target && typeof target.focus === "function") {
      content.scrollTop = 0;
      target.focus({ preventScroll: true });
    } else {
      closeButton.focus({ preventScroll: true });
    }
  }

  function renderResponse(response, requestedUrl, sequence, fragmentRead) {
    if (sequence !== requestSequence) {
      return Promise.resolve();
    }
    var responseUrl = new URL(response.url || requestedUrl.href, window.location.href);
    responseUrl.searchParams.delete("embed");
    if (response.redirected && !isModalPath(responseUrl.pathname)) {
      window.location.assign(canonicalPath(responseUrl));
      return Promise.resolve();
    }
    return response.text().then(function (html) {
      if (fragmentRead) fragmentRead();
      if (sequence !== requestSequence) {
        return;
      }
      var parsed = new DOMParser().parseFromString(html, "text/html");
      var fragment = fragmentFromDocument(parsed);
      if (!fragment) {
        throw new Error("This page is available in full-page mode.");
      }
      disposeDialogContent();
      content.replaceChildren(document.importNode(fragment, true));
      title.textContent = labelFor(responseUrl, null);
      dialog.dataset.dialogKind = kindFor(responseUrl);
      updateDialogHistory(responseUrl, true);
      return loadDialogScripts(parsed, sequence).then(function () {
        if (sequence !== requestSequence) {
          return;
        }
        renderTurnstile();
        setReady();
        document.dispatchEvent(new CustomEvent("workdoe:content-ready", {
          detail: { root: content }
        }));
        focusDialogContent();
      });
    });
  }

  function showDialogRecovery(url, message) {
    var actions = document.createElement("div");
    actions.className = "action-row";
    var retry = document.createElement("button");
    retry.type = "button";
    retry.className = "button primary";
    retry.textContent = "Try again";
    retry.addEventListener("click", function () { openDialog(null, url, "none"); });
    var fullPage = document.createElement("a");
    fullPage.className = "button secondary";
    fullPage.href = canonicalPath(url);
    fullPage.setAttribute("data-dialog-bypass", "");
    fullPage.textContent = "Open full page";
    actions.append(retry, fullPage);
    disposeDialogContent();
    content.replaceChildren(actions);
    content.scrollTop = 0;
    dialog.dataset.dialogRecovery = "true";
    dialog.removeAttribute("aria-busy");
    status.hidden = false;
    status.textContent = message;
    retry.focus();
  }

  function fetchDialog(url) {
    var sequence = ++requestSequence;
    if (requestController) {
      requestController.abort();
    }
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    requestController = controller;
    var fetchUrl = new URL(url.href);
    fetchUrl.searchParams.set("embed", "1");
    fetchUrl.hash = "";
    var timer = window.setTimeout(function () {
      if (sequence !== requestSequence) return;
      requestSequence += 1;
      if (controller) controller.abort();
      showDialogRecovery(url, "This form took too long to load.");
    }, DIALOG_FRAGMENT_TIMEOUT_MS);
    function stopFragmentTimer() {
      window.clearTimeout(timer);
    }
    return window.fetch(fetchUrl.href, {
      credentials: "same-origin",
      headers: {
        Accept: "text/html",
        "X-Workdoe-Dialog": "native"
      },
      signal: controller ? controller.signal : undefined
    }).then(function (response) {
      if (!response.ok) {
        throw new Error(response.status >= 500 ? "This form is temporarily unavailable." : "This form could not be opened.");
      }
      // Wait for the full response body, but leave script loading to its own checks.
      return renderResponse(response, url, sequence, stopFragmentTimer);
    }).catch(function (error) {
      if (error.name === "AbortError" || sequence !== requestSequence) {
        return;
      }
      var message = error instanceof TypeError ? "" : error.message;
      showDialogRecovery(url, message || "This form could not be opened.");
    }).finally(stopFragmentTimer);
  }

  function openDialog(anchor, url, historyMode) {
    var wasOpen = dialogIsOpen();
    if (!wasOpen) {
      returnFocus = anchor || document.activeElement;
      returnPanel = returnFocus && returnFocus.closest("[data-market-panel]");
      backgroundUrl = window.location.pathname + window.location.search + window.location.hash;
    }
    title.textContent = labelFor(url, anchor);
    dialog.dataset.dialogKind = kindFor(url);
    setLoading("Loading " + title.textContent.toLowerCase() + "...");
    showDialog();
    if (historyMode !== "none") {
      updateDialogHistory(url, wasOpen || historyMode === "replace");
    } else {
      currentCanonicalUrl = canonicalPath(url);
    }
    closeButton.focus({ preventScroll: true });
    fetchDialog(url);
  }

  function restoreFocus() {
    if (returnFocus && returnFocus.isConnected && returnFocus.getClientRects().length) {
      returnFocus.focus({ preventScroll: true });
      return;
    }
    if (!returnPanel || !returnPanel.isConnected) {
      return;
    }
    // A map refresh may replace the action while the dialog is open.
    var href = returnFocus && returnFocus.href;
    var action = href && Array.prototype.find.call(returnPanel.querySelectorAll("a[data-dialog-title]"), function (link) {
      return link.href === href && link.getClientRects().length;
    });
    var target = action || returnPanel.querySelector("[data-map], [data-project-detail-content] h2");
    if (!target || !target.getClientRects().length) {
      target = document.querySelector("[data-mobile-panel-target][aria-selected=true]");
    }
    if (target && target.getClientRects().length) {
      if (target.tabIndex < 0 && !target.hasAttribute("tabindex")) {
        target.tabIndex = -1;
      }
      target.focus({ preventScroll: true });
    }
  }

  function finalizeClose() {
    if (!dialogIsOpen()) {
      return;
    }
    requestSequence += 1;
    if (requestController) {
      requestController.abort();
      requestController = null;
    }
    if (typeof dialog.close === "function" && dialog.open) {
      dialog.close();
    } else {
      dialog.removeAttribute("open");
    }
    delete dialog.dataset.dialogKind;
    delete dialog.dataset.dialogRecovery;
    dialog.removeAttribute("aria-busy");
    document.body.classList.remove("has-site-dialog");
    disposeDialogContent();
    content.replaceChildren();
    status.hidden = false;
    status.textContent = "Loading...";
    currentCanonicalUrl = "";
    restoreFocus();
    returnFocus = null;
    returnPanel = null;
    backgroundUrl = "";
  }

  function requestClose() {
    if (!dialogIsOpen()) {
      return;
    }
    if (window.history.state && window.history.state.workdoeDialog) {
      window.history.back();
    } else {
      finalizeClose();
    }
  }

  function formDataWithSubmitter(form, submitter) {
    var data;
    try {
      data = new FormData(form, submitter || undefined);
    } catch (error) {
      data = new FormData(form);
      if (submitter && submitter.name) {
        data.append(submitter.name, submitter.value || "");
      }
    }
    return data;
  }

  function submitTraditionalForm(event, form) {
    event.preventDefault();
    var method = String(form.getAttribute("method") || "get").toUpperCase();
    var action = form.getAttribute("action") || currentCanonicalUrl || window.location.href;
    var url = new URL(action, window.location.origin);
    url.searchParams.set("embed", "1");
    var data = formDataWithSubmitter(form, event.submitter);
    var options = {
      method: method,
      credentials: "same-origin",
      headers: {
        Accept: "text/html",
        "X-Workdoe-Dialog": "native"
      }
    };
    if (method === "GET") {
      data.forEach(function (value, key) {
        if (typeof value === "string") {
          url.searchParams.set(key, value);
        }
      });
    } else {
      options.body = data;
    }
    var sequence = ++requestSequence;
    var submitter = event.submitter;
    status.hidden = false;
    status.textContent = "Saving...";
    dialog.setAttribute("aria-busy", "true");
    form.setAttribute("aria-busy", "true");
    if (submitter) {
      submitter.disabled = true;
    }
    window.fetch(url.href, options).then(function (response) {
      return renderResponse(response, url, sequence);
    }).catch(function (error) {
      if (sequence !== requestSequence) {
        return;
      }
      status.hidden = false;
      status.textContent = error.message || "Workdoe could not save this yet.";
      dialog.removeAttribute("aria-busy");
      form.removeAttribute("aria-busy");
      if (submitter) {
        submitter.disabled = false;
        submitter.focus({ preventScroll: true });
      }
    });
  }

  document.addEventListener("click", function (event) {
    if (event.defaultPrevented || event.button !== 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
      return;
    }
    var target = event.target;
    if (!target || typeof target.closest !== "function") {
      return;
    }
    var anchor = target.closest("a[href]");
    var url = dialogTarget(anchor);
    if (!url) {
      return;
    }
    event.preventDefault();
    openDialog(anchor, url, "push");
  });

  dialog.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || !form.matches("form")) {
      return;
    }
    if (form.matches("[data-json-action], [data-file-action], [data-email-code-entry]") || form.closest("[data-clerk-entry]")) {
      return;
    }
    submitTraditionalForm(event, form);
  });

  closeButton.addEventListener("click", requestClose);
  document.addEventListener("keydown", function (event) {
    wrapDialogFocus(event);
    if (dialogIsOpen() && event.key === "Escape") {
      event.preventDefault();
      requestClose();
    }
  });
  dialog.addEventListener("cancel", function (event) {
    event.preventDefault();
    requestClose();
  });
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) {
      requestClose();
    }
  });
  document.addEventListener("workdoe:dialog-navigate", function (event) {
    var nextUrl;
    try {
      nextUrl = new URL(event.detail && event.detail.url, window.location.origin);
    } catch (error) {
      return;
    }
    if (!dialogIsOpen() || nextUrl.origin !== window.location.origin || !isModalPath(nextUrl.pathname)) {
      window.location.assign(canonicalPath(nextUrl));
      return;
    }
    openDialog(null, nextUrl, "replace");
  });
  window.addEventListener("popstate", function (event) {
    if (event.state && event.state.workdoeDialog && event.state.dialogUrl) {
      openDialog(null, new URL(event.state.dialogUrl, window.location.origin), "none");
      return;
    }
    finalizeClose();
  });

  function inlineDialogFor(trigger) {
    var id = trigger && trigger.dataset.inlineDialogOpen;
    if (!id) {
      return null;
    }
    var candidate = document.getElementById(id);
    return candidate && candidate.matches("dialog[data-inline-dialog]") ? candidate : null;
  }

  function openInlineDialog(trigger, inlineDialog) {
    inlineDialog._workdoeReturnFocus = trigger;
    if (typeof inlineDialog.showModal === "function") {
      inlineDialog.showModal();
    } else {
      inlineDialog.setAttribute("open", "");
    }
    document.body.classList.add("has-inline-dialog");
    var firstChoice = inlineDialog.querySelector("input, select, textarea, button");
    if (firstChoice) {
      firstChoice.focus();
    }
  }

  function closeInlineDialog(inlineDialog) {
    if (typeof inlineDialog.close === "function" && inlineDialog.open) {
      inlineDialog.close();
    } else {
      inlineDialog.removeAttribute("open");
    }
    document.body.classList.remove("has-inline-dialog");
    var trigger = inlineDialog._workdoeReturnFocus;
    if (trigger && document.contains(trigger)) {
      trigger.focus();
    }
    inlineDialog._workdoeReturnFocus = null;
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!target || typeof target.closest !== "function") {
      return;
    }
    var trigger = target.closest("[data-inline-dialog-open]");
    if (trigger) {
      var inlineDialog = inlineDialogFor(trigger);
      if (inlineDialog) {
        event.preventDefault();
        openInlineDialog(trigger, inlineDialog);
      }
      return;
    }
    var closeTrigger = target.closest("[data-inline-dialog-close]");
    if (closeTrigger) {
      var enclosingDialog = closeTrigger.closest("dialog[data-inline-dialog]");
      if (enclosingDialog) {
        event.preventDefault();
        closeInlineDialog(enclosingDialog);
      }
    }
  });

  document.querySelectorAll("dialog[data-inline-dialog]").forEach(function (inlineDialog) {
    inlineDialog.addEventListener("cancel", function (event) {
      event.preventDefault();
      closeInlineDialog(inlineDialog);
    });
    inlineDialog.addEventListener("click", function (event) {
      if (event.target === inlineDialog) {
        closeInlineDialog(inlineDialog);
      }
    });
    inlineDialog.addEventListener("close", function () {
      document.body.classList.remove("has-inline-dialog");
    });
  });

})();
