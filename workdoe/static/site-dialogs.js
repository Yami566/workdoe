(function () {
  "use strict";

  var dialog = document.querySelector("[data-site-dialog]");
  var frame = dialog && dialog.querySelector("[data-site-dialog-frame]");
  var title = dialog && dialog.querySelector("[data-site-dialog-title]");
  var closeButton = dialog && dialog.querySelector("[data-site-dialog-close]");
  var returnFocus = null;
  var modalPaths = [
    "/login",
    "/start",
    "/start/verify",
    "/create-account",
    "/post-project",
    "/jobs/new"
  ];

  if (!dialog || !frame || !closeButton) {
    return;
  }

  function dialogTarget(anchor) {
    if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download")) {
      return null;
    }
    if (modalPaths.indexOf(window.location.pathname) !== -1) {
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
    url.searchParams.set("embed", "1");
    return url;
  }

  function labelFor(url, anchor) {
    if (anchor.dataset.dialogTitle) {
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
    return url.pathname === "/login" || url.pathname === "/start/verify" ? "auth" : "flow";
  }

  function openDialog(anchor, url) {
    var label = labelFor(url, anchor);
    returnFocus = anchor;
    dialog.dataset.dialogKind = kindFor(url);
    title.textContent = label;
    frame.title = label;
    frame.src = url.pathname + url.search + url.hash;
    dialog.hidden = false;
    document.body.classList.add("has-site-dialog");
    closeButton.focus();
  }

  function closeDialog() {
    if (dialog.hidden) {
      return;
    }
    dialog.hidden = true;
    delete dialog.dataset.dialogKind;
    document.body.classList.remove("has-site-dialog");
    frame.src = "about:blank";
    if (returnFocus && document.contains(returnFocus)) {
      returnFocus.focus();
    }
    returnFocus = null;
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
    openDialog(anchor, url);
  });

  closeButton.addEventListener("click", closeDialog);
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) {
      closeDialog();
    }
  });
  document.addEventListener("keydown", function (event) {
    if (dialog.hidden) {
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      closeDialog();
      return;
    }
    if (event.key !== "Tab") {
      return;
    }
    var focusable = [closeButton, frame];
    var index = focusable.indexOf(document.activeElement);
    if (event.shiftKey && index <= 0) {
      event.preventDefault();
      frame.focus();
    } else if (!event.shiftKey && index === focusable.length - 1) {
      event.preventDefault();
      closeButton.focus();
    }
  });
  frame.addEventListener("load", function () {
    if (dialog.hidden || frame.src === "about:blank") {
      return;
    }
    try {
      var current = new URL(frame.contentWindow.location.href);
      if (current.origin === window.location.origin && modalPaths.indexOf(current.pathname) === -1) {
        window.location.assign(current.pathname + current.search + current.hash);
      }
    } catch (error) {
      closeDialog();
    }
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
