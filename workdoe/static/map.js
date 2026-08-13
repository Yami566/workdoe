document.addEventListener("DOMContentLoaded", function () {
  var mapElement = document.getElementById("lead-map");
  if (!mapElement || !window.L) {
    return;
  }

  var statusElement = document.getElementById("lead-map-status");
  var map = window.L.map(mapElement, {
    scrollWheelZoom: false
  }).setView([38.9072, -77.0369], 9);
  mapElement.classList.add("map-ready");
  var markers = window.L.layerGroup().addTo(map);
  var markerByJobId = {};

  window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);

  var fallbackJobs = readSeedJobs();
  renderJobs(fallbackJobs);

  var jobsApi = mapElement.getAttribute("data-jobs-api");
  if (jobsApi && window.fetch) {
    window.fetch(jobsApi, {
      headers: {
        Accept: "application/json"
      },
      credentials: "same-origin"
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Map jobs request failed");
        }
        return response.json();
      })
      .then(function (payload) {
        if (payload && Array.isArray(payload.jobs)) {
          renderJobs(payload.jobs);
        }
      })
      .catch(function () {
        setMapStatus("Map data could not refresh. The job list is still ready.");
        renderJobs(fallbackJobs);
      });
  }

  function renderJobs(jobs) {
    var bounds = [];
    markerByJobId = {};
    markers.clearLayers();

    jobs.forEach(function (job) {
      if (!job.lat || !job.lng) {
        return;
      }
      var accessibleMarkerLabel = markerLabel(job);
      var marker = window.L.marker([job.lat, job.lng], {
        alt: accessibleMarkerLabel,
        title: accessibleMarkerLabel
      }).addTo(markers);
      labelMarkerElement(marker, accessibleMarkerLabel);
      markerByJobId[String(job.id)] = marker;
      marker.bindPopup(
        "<strong>" + escapeHtml(job.title) + "</strong><br>" +
        escapeHtml(job.category) + "<br>" +
        escapeHtml(job.city + ", " + job.state) + "<br>" +
        '<a href="' + escapeAttribute(job.url || "#") + '">' +
        escapeHtml(job.action_label || "View lead") +
        "</a>"
      );
      marker.on("click", function () {
        activateJob(job.id, false);
      });
      bounds.push([job.lat, job.lng]);
    });

    bindJobRows();
    updateResultStatus(jobs.length, bounds.length);

    if (bounds.length > 1) {
      map.fitBounds(bounds, { padding: [24, 24] });
    } else if (bounds.length === 1) {
      map.setView(bounds[0], 11);
    }
  }

  function markerLabel(job) {
    var title = job.title || "Open lead";
    var place = [job.city, job.state].filter(Boolean).join(", ");
    return place ? title + " in " + place : title;
  }

  function labelMarkerElement(marker, label) {
    var element = marker.getElement && marker.getElement();
    if (!element || !label) {
      return;
    }
    element.setAttribute("aria-label", label);
    element.setAttribute("title", label);
  }

  function bindJobRows() {
    var rows = document.querySelectorAll("[data-job-id]");
    rows.forEach(function (row) {
      if (row.dataset.mapBound === "true") {
        return;
      }
      row.dataset.mapBound = "true";
      row.setAttribute("aria-keyshortcuts", "ArrowUp ArrowDown Home End");
      row.addEventListener("mouseenter", function () {
        activateJob(row.getAttribute("data-job-id"), false);
      });
      row.addEventListener("focusin", function () {
        activateJob(row.getAttribute("data-job-id"), true);
      });
      row.addEventListener("keydown", function (event) {
        if (event.altKey || event.ctrlKey || event.metaKey) {
          return;
        }
        moveJobFocus(row, event);
      });
    });
  }

  function moveJobFocus(row, event) {
    var rows = Array.prototype.slice.call(document.querySelectorAll("[data-job-id]"));
    var index = rows.indexOf(row);
    if (index === -1) {
      return;
    }
    var nextIndex = index;
    if (event.key === "ArrowDown") {
      nextIndex = Math.min(rows.length - 1, index + 1);
    } else if (event.key === "ArrowUp") {
      nextIndex = Math.max(0, index - 1);
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = rows.length - 1;
    } else {
      return;
    }
    event.preventDefault();
    if (rows[nextIndex]) {
      rows[nextIndex].focus({ preventScroll: true });
      activateJob(rows[nextIndex].getAttribute("data-job-id"), true);
    }
  }

  function activateJob(jobId, panMap) {
    var marker = markerByJobId[String(jobId)];
    highlightJobRow(jobId);
    announceActiveJob(jobId);
    if (!marker) {
      return;
    }
    if (panMap) {
      map.panTo(marker.getLatLng(), { animate: true, duration: 0.3 });
    }
    marker.openPopup();
  }

  function highlightJobRow(jobId) {
    var rows = document.querySelectorAll("[data-job-id]");
    rows.forEach(function (row) {
      var isActive = row.getAttribute("data-job-id") === String(jobId);
      row.classList.toggle("is-map-active", isActive);
      if (isActive) {
        row.setAttribute("data-map-active", "true");
      } else {
        row.removeAttribute("data-map-active");
      }
    });
  }

  function announceActiveJob(jobId) {
    var row = document.querySelector('[data-job-id="' + cssEscape(String(jobId)) + '"]');
    if (!row) {
      return;
    }
    var title = row.querySelector("h2, h3");
    if (title && title.textContent) {
      setMapStatus(title.textContent.trim() + " is active on the map.");
    }
  }

  function updateResultStatus(jobCount, pinCount) {
    if (!jobCount) {
      setMapStatus("No open leads match this view. The list is ready.");
      return;
    }
    var leadWord = jobCount === 1 ? "lead" : "leads";
    var pinWord = pinCount === 1 ? "pin" : "pins";
    setMapStatus(
      jobCount + " open " + leadWord + " shown. " +
      pinCount + " approximate " + pinWord + " on the map."
    );
  }

  function setMapStatus(message) {
    if (statusElement) {
      statusElement.textContent = message;
    }
  }

  function readSeedJobs() {
    var seedElement = document.getElementById("map-jobs-data");
    if (!seedElement || !seedElement.textContent) {
      return [];
    }
    try {
      var jobs = JSON.parse(seedElement.textContent);
      return Array.isArray(jobs) ? jobs : [];
    } catch (error) {
      return [];
    }
  }
});

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

function cssEscape(value) {
  if (window.CSS && typeof window.CSS.escape === "function") {
    return window.CSS.escape(value);
  }
  return String(value).replace(/"/g, '\\"');
}
