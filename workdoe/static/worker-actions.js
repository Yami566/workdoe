(function () {
  "use strict";

  function setStatus(form, message) {
    var status = form.querySelector("[data-form-status]");
    if (status) {
      status.textContent = message || "";
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
