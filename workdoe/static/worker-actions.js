(function () {
  "use strict";

  function setStatus(form, message) {
    var status = form.querySelector("[data-form-status]");
    if (status) {
      status.textContent = message || "";
    }
  }

  function fieldIdForName(name) {
    return String(name || "").replace(/_/g, "-");
  }

  function errorIdForField(field) {
    return "worker-error-" + fieldIdForName(field);
  }

  function fieldControl(form, field) {
    var controls = Array.prototype.filter.call(
      form.querySelectorAll("input, select, textarea"),
      function (control) {
        return control.name === field;
      }
    );
    if (!controls.length) {
      return null;
    }
    for (var index = 0; index < controls.length; index += 1) {
      if (controls[index].matches("input, select, textarea")) {
        return controls[index];
      }
    }
    return controls[0];
  }

  function fieldErrorTarget(form, field) {
    var control = fieldControl(form, field);
    if (!control) {
      return null;
    }
    if (control.type === "checkbox" || control.type === "radio") {
      return control.closest("fieldset") || control;
    }
    return control;
  }

  function fieldErrorContainer(target) {
    if (!target) {
      return null;
    }
    if (target.matches("fieldset")) {
      return target;
    }
    return target.closest("label") || target.parentElement;
  }

  function describedByValues(element) {
    return (element.dataset.originalDescribedby || element.getAttribute("aria-describedby") || "")
      .split(/\s+/)
      .filter(Boolean);
  }

  function clearFieldErrors(form) {
    form.querySelectorAll("[data-worker-field-error]").forEach(function (node) {
      node.remove();
    });
    form.querySelectorAll("[data-worker-invalid]").forEach(function (node) {
      var original = node.dataset.originalDescribedby || "";
      node.removeAttribute("aria-invalid");
      if (original) {
        node.setAttribute("aria-describedby", original);
      } else {
        node.removeAttribute("aria-describedby");
      }
      delete node.dataset.workerInvalid;
    });
  }

  function showFieldErrors(form, fieldErrors) {
    var firstControl = null;
    Object.keys(fieldErrors || {}).forEach(function (field) {
      var messages = fieldErrors[field] || [];
      var target = fieldErrorTarget(form, field);
      var control = fieldControl(form, field);
      var container = fieldErrorContainer(target);
      if (!target || !control || !container || !messages.length) {
        return;
      }
      var error = document.createElement("span");
      error.id = errorIdForField(field);
      error.className = "field-error";
      error.dataset.workerFieldError = "true";
      error.textContent = messages[0];
      container.appendChild(error);
      var details = control.closest("details");
      if (details) {
        details.open = true;
      }

      if (!target.dataset.workerInvalid) {
        target.dataset.originalDescribedby = target.getAttribute("aria-describedby") || "";
      }
      var describedBy = describedByValues(target);
      if (describedBy.indexOf(error.id) === -1) {
        describedBy.push(error.id);
      }
      target.setAttribute("aria-invalid", "true");
      target.setAttribute("aria-describedby", describedBy.join(" "));
      target.dataset.workerInvalid = "true";
      if (!firstControl) {
        firstControl = control;
      }
    });
    if (firstControl && typeof firstControl.focus === "function") {
      firstControl.focus({ preventScroll: true });
      firstControl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function isFileValue(value) {
    return typeof File !== "undefined" && value instanceof File;
  }

  function payloadFromForm(form) {
    var data = {};
    var formData = new FormData(form);
    formData.forEach(function (value, key) {
      if (isFileValue(value)) {
        return;
      }
      var normalized = typeof value === "string" ? value.trim() : value;
      if (Object.prototype.hasOwnProperty.call(data, key)) {
        if (!Array.isArray(data[key])) {
          data[key] = [data[key]];
        }
        data[key].push(normalized);
      } else {
        data[key] = normalized;
      }
    });
    return data;
  }

  function successUrl(form, payload) {
    var template = form.dataset.successUrlTemplate || payload.url || "/dashboard";
    var id = payload.id || payload.job_id;
    if (id) {
      template = template
        .replace("{id}", encodeURIComponent(id))
        .replace("{job_id}", encodeURIComponent(id));
    }
    return payload.url || template;
  }

  function selectedFiles(form) {
    var files = [];
    form.querySelectorAll("input[type='file']").forEach(function (input) {
      Array.prototype.forEach.call(input.files || [], function (file) {
        if (file && file.name && file.size > 0) {
          files.push(file);
        }
      });
    });
    return files;
  }

  function uploadAfterJsonUrl(form, payload) {
    var template = form.dataset.uploadAfterJsonTemplate || "";
    var id = payload.job_id || payload.id;
    if (!template || !id) {
      return "";
    }
    return template
      .replace("{job_id}", encodeURIComponent(id))
      .replace("{id}", encodeURIComponent(id));
  }

  async function uploadFilesAfterJson(form, payload) {
    var url = uploadAfterJsonUrl(form, payload);
    if (!url) {
      return;
    }
    var files = selectedFiles(form);
    if (!files.length) {
      return;
    }
    for (var index = 0; index < files.length; index += 1) {
      setStatus(form, "Uploading photo " + (index + 1) + " of " + files.length + "...");
      var uploadData = new FormData();
      uploadData.append("photo", files[index], files[index].name);
      var response = await fetch(url, {
        method: "POST",
        credentials: "include",
        headers: {
          "Accept": "application/json"
        },
        body: uploadData
      });
      var uploadPayload = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        throw new Error(
          "Job saved, but photo upload failed. " +
            (uploadPayload.errors || [uploadPayload.error || "You can retry from the job page."]).join(" ")
        );
      }
    }
  }

  async function submitJsonForm(event) {
    var form = event.target;
    if (!form.matches("[data-json-action]")) {
      return;
    }
    event.preventDefault();
    var button = form.querySelector("button[type='submit']");
    if (button) {
      button.disabled = true;
    }
    clearFieldErrors(form);
    setStatus(form, "Saving...");
    try {
      var response = await fetch(form.dataset.jsonAction, {
        method: form.dataset.method || "POST",
        credentials: "include",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payloadFromForm(form))
      });
      var payload = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        showFieldErrors(form, payload.field_errors);
        throw new Error((payload.errors || [payload.error || "Workdoe could not save this yet."]).join(" "));
      }
      try {
        await uploadFilesAfterJson(form, payload);
      } catch (uploadError) {
        setStatus(form, (uploadError.message || "Job saved, but photo upload failed.") + " Opening the job now.");
        window.location.assign(successUrl(form, payload));
        return;
      }
      setStatus(form, "Saved.");
      window.location.assign(successUrl(form, payload));
    } catch (error) {
      if (button) {
        button.disabled = false;
      }
      setStatus(form, error.message || "Workdoe could not save this yet.");
    }
  }

  async function submitFileForm(event) {
    var form = event.target;
    if (!form.matches("[data-file-action]")) {
      return;
    }
    event.preventDefault();
    var button = form.querySelector("button[type='submit']");
    if (button) {
      button.disabled = true;
    }
    clearFieldErrors(form);
    setStatus(form, "Uploading...");
    try {
      var response = await fetch(form.dataset.fileAction, {
        method: form.dataset.method || "POST",
        credentials: "include",
        headers: {
          "Accept": "application/json"
        },
        body: new FormData(form)
      });
      var payload = await response.json().catch(function () {
        return {};
      });
      if (!response.ok) {
        showFieldErrors(form, payload.field_errors);
        throw new Error((payload.errors || [payload.error || "Workdoe could not upload this yet."]).join(" "));
      }
      setStatus(form, "Uploaded.");
      window.location.assign(successUrl(form, payload));
    } catch (error) {
      if (button) {
        button.disabled = false;
      }
      setStatus(form, error.message || "Workdoe could not upload this yet.");
    }
  }

  document.addEventListener("submit", submitJsonForm);
  document.addEventListener("submit", submitFileForm);
})();
