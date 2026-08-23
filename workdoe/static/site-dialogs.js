(function () {
  "use strict";

  var dialog = document.querySelector("[data-site-dialog]");
  var content = dialog && dialog.querySelector("[data-site-dialog-content]");
  var status = dialog && dialog.querySelector("[data-site-dialog-status]");
  var title = dialog && dialog.querySelector("[data-site-dialog-title]");
  var closeButton = dialog && dialog.querySelector("[data-site-dialog-close]");
  var returnFocus = null;
  var backgroundUrl = "";
  var currentCanonicalUrl = "";
  var requestSequence = 0;
  var requestController = null;
  var loadedLibraries = {};
  var modalPaths = [
    "/login",
    "/start",
    "/start/verify",
    "/create-account",
    "/post-project",
    "/jobs/new"
  ];
  var repeatableBootScripts = [
    "/clerk-entry.js",
    "/email-code-entry.js",
    "/project-composer.js"
  ];
  var singleLoadScripts = ["/worker-actions.js"];

  if (!dialog || !content || !status || !closeButton) {
    return;
  }

  function dialogIsOpen() {
    return Boolean(dialog.open || dialog.hasAttribute("open"));
  }

  function dialogTarget(anchor) {
    if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) {
      return null;
    }
    if (!dialogIsOpen() && modalPaths.indexOf(window.location.pathname) !== -1) {
      return null;
    }
    var url;
    try {
      url = new URL(anchor.href, window.location.href);
    } catch (error) {
      return null;
    }
    if (url.origin !== window.location.origin || modalPaths.indexOf(url.pathname) === -1) {
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
    var key = url.origin + url.pathname;
    if (kind === "library" && loadedLibraries[key]) {
      return Promise.resolve();
    }
    loadedLibraries[key] = true;
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      copyScriptAttributes(source, script);
      script.src = url.href;
      script.async = false;
      script.addEventListener("load", resolve, { once: true });
      script.addEventListener("error", function () {
        if (kind === "library") {
          delete loadedLibraries[key];
        }
        reject(new Error("A required Workdoe form could not load."));
      }, { once: true });
      document.head.appendChild(script);
    });
  }

  function loadDialogScripts(parsed) {
    var scripts = Array.prototype.slice.call(parsed.querySelectorAll("script[src]"));
    return scripts.reduce(function (promise, source) {
      return promise.then(function () { return loadScript(source); });
    }, Promise.resolve());
  }

  function renderTurnstile() {
    if (!window.turnstile || typeof window.turnstile.render !== "function") {
      return;
    }
    var renderWidgets = function () {
      content.querySelectorAll(".cf-turnstile").forEach(function (widget) {
        if (!widget.querySelector("iframe") && !widget.querySelector('input[name="cf-turnstile-response"]')) {
          window.turnstile.render(widget, {
            sitekey: widget.dataset.sitekey,
            action: widget.dataset.action,
            theme: widget.dataset.theme || "light"
          });
        }
      });
    };
    if (typeof window.turnstile.ready === "function") {
      window.turnstile.ready(renderWidgets);
    } else {
      renderWidgets();
    }
  }

  function focusDialogContent() {
    var target = content.querySelector('[aria-invalid="true"], [autofocus], input:not([type="hidden"]), select, textarea, button, a[href]');
    if (target && typeof target.focus === "function") {
      target.focus({ preventScroll: true });
    } else {
      closeButton.focus({ preventScroll: true });
    }
  }

  function renderResponse(response, requestedUrl, sequence) {
    var responseUrl = new URL(response.url || requestedUrl.href, window.location.href);
    responseUrl.searchParams.delete("embed");
    if (response.redirected && modalPaths.indexOf(responseUrl.pathname) === -1) {
      window.location.assign(canonicalPath(responseUrl));
      return Promise.resolve();
    }
    return response.text().then(function (html) {
      if (sequence !== requestSequence) {
        return;
      }
      var parsed = new DOMParser().parseFromString(html, "text/html");
      var fragment = fragmentFromDocument(parsed);
      if (!fragment) {
        throw new Error("This page is available in full-page mode.");
      }
      content.replaceChildren(document.importNode(fragment, true));
      title.textContent = labelFor(responseUrl, null);
      dialog.dataset.dialogKind = kindFor(responseUrl);
      updateDialogHistory(responseUrl, true);
      return loadDialogScripts(parsed).then(function () {
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

  function fetchDialog(url) {
    var sequence = ++requestSequence;
    if (requestController) {
      requestController.abort();
    }
    requestController = typeof AbortController === "function" ? new AbortController() : null;
    var fetchUrl = new URL(url.href);
    fetchUrl.searchParams.set("embed", "1");
    fetchUrl.hash = "";
    return window.fetch(fetchUrl.href, {
      credentials: "same-origin",
      headers: {
        Accept: "text/html",
        "X-Workdoe-Dialog": "native"
      },
      signal: requestController ? requestController.signal : undefined
    }).then(function (response) {
      if (!response.ok) {
        throw new Error(response.status >= 500 ? "This form is temporarily unavailable." : "This form could not be opened.");
      }
      return renderResponse(response, url, sequence);
    }).catch(function (error) {
      if (error.name === "AbortError" || sequence !== requestSequence) {
        return;
      }
      status.hidden = false;
      status.textContent = error.message || "This form could not be opened.";
      content.innerHTML = '<a class="button secondary" href="' + escapeAttribute(canonicalPath(url)) + '">Open the full page</a>';
      dialog.removeAttribute("aria-busy");
      closeButton.focus({ preventScroll: true });
    });
  }

  function openDialog(anchor, url, historyMode) {
    var wasOpen = dialogIsOpen();
    if (!wasOpen) {
      returnFocus = anchor || document.activeElement;
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
    dialog.removeAttribute("aria-busy");
    document.body.classList.remove("has-site-dialog");
    content.replaceChildren();
    status.hidden = false;
    status.textContent = "Loading...";
    currentCanonicalUrl = "";
    if (returnFocus && document.contains(returnFocus)) {
      returnFocus.focus({ preventScroll: true });
    }
    returnFocus = null;
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

  function escapeAttribute(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;")
      .replace(/`/g, "&#096;");
  }
})();
