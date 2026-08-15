(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var mapElement = document.getElementById("lead-map");
    if (!mapElement || !window.L) {
      return;
    }

    var statusElement = document.getElementById("lead-map-status");
    var workspace = document.querySelector("[data-market-workspace]");
    var resultContainer = document.querySelector("[data-project-results]");
    var searchInput = document.querySelector("[data-market-search]");
    var categorySelect = document.querySelector("[data-market-category]");
    var clearButton = document.querySelector("[data-clear-market-filters]");
    var resultCount = document.querySelector("[data-project-result-count]");
    var mapResultCount = document.querySelector("[data-map-result-count]");
    var detailContent = document.querySelector("[data-project-detail-content]");
    var map = window.L.map(mapElement, {
      scrollWheelZoom: false,
      zoomControl: true,
      maxZoom: 18
    }).setView([38.9072, -77.0369], 9);
    var markerLayer = window.L.layerGroup();
    if (window.L.markerClusterGroup) {
      try {
        markerLayer = window.L.markerClusterGroup({
          showCoverageOnHover: false,
          spiderfyOnMaxZoom: true,
          maxClusterRadius: 46
        });
        markerLayer.addTo(map);
      } catch (clusterError) {
        markerLayer = window.L.layerGroup().addTo(map);
      }
    } else {
      markerLayer.addTo(map);
    }
    var markerByJobId = {};
    var allJobs = readSeedJobs();
    var visibleJobs = [];
    var activeJobId = initialJobId(allJobs);

    mapElement.classList.add("map-ready");
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);

    bindFilters();
    bindMobileTabs();
    applyFilters(true);

    var jobsApi = mapElement.getAttribute("data-jobs-api");
    if (jobsApi && window.fetch) {
      window.fetch(jobsApi, {
        headers: { Accept: "application/json" },
        credentials: "same-origin"
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("Project map request failed");
          }
          return response.json();
        })
        .then(function (payload) {
          if (payload && Array.isArray(payload.jobs)) {
            allJobs = payload.jobs;
            if (!findJob(activeJobId)) {
              activeJobId = initialJobId(allJobs);
            }
            applyFilters(true);
          }
        })
        .catch(function () {
          setMapStatus("The live map could not refresh. The available project list is still ready.");
        });
    }

    function bindFilters() {
      if (searchInput) {
        searchInput.addEventListener("input", function () {
          applyFilters(false);
        });
      }
      if (categorySelect) {
        categorySelect.addEventListener("change", function () {
          applyFilters(true);
        });
      }
      if (clearButton) {
        clearButton.addEventListener("click", function () {
          if (searchInput) {
            searchInput.value = "";
          }
          if (categorySelect) {
            categorySelect.value = "";
          }
          applyFilters(true);
          if (searchInput) {
            searchInput.focus();
          }
        });
      }
    }

    function applyFilters(fitMap) {
      var query = searchInput ? searchInput.value.trim().toLowerCase() : "";
      var category = categorySelect ? categorySelect.value : "";
      visibleJobs = allJobs.filter(function (job) {
        if (category && job.category !== category) {
          return false;
        }
        if (!query) {
          return true;
        }
        return [job.title, job.category, job.city, job.state, job.description]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .indexOf(query) !== -1;
      });
      if (!visibleJobs.some(function (job) { return String(job.id) === String(activeJobId); })) {
        activeJobId = visibleJobs.length ? String(visibleJobs[0].id) : "";
      }
      renderProjectRows();
      renderMarkers(fitMap);
      updateDetail(findVisibleJob(activeJobId));
      updateCounts();
    }

    function renderProjectRows() {
      if (!resultContainer) {
        bindExistingRows();
        return;
      }
      if (!visibleJobs.length) {
        resultContainer.innerHTML = '<div class="market-list-empty"><strong>No matching projects</strong><span>Try another category or a broader search.</span></div>';
        return;
      }
      resultContainer.innerHTML = visibleJobs.map(projectRowHtml).join("");
      bindExistingRows();
    }

    function projectRowHtml(job) {
      var active = String(job.id) === String(activeJobId);
      var sample = job.is_demo ? '<span class="sample-badge">Sample</span>' : "";
      return (
        '<a class="project-result' + (active ? " is-map-active" : "") + '" role="listitem" data-job-id="' + escapeAttribute(job.id) + '" href="' + escapeAttribute(job.detail_url || "#") + '"' + (active ? ' aria-current="true"' : "") + ">" +
          '<span class="project-result-topline"><span>' + escapeHtml(job.category || "Project") + "</span>" + sample + "</span>" +
          "<strong>" + escapeHtml(job.title || "Open project") + "</strong>" +
          '<span class="project-result-facts"><span>' + escapeHtml(placeLabel(job)) + "</span><span>" + escapeHtml(job.budget || "Budget not provided") + "</span></span>" +
        "</a>"
      );
    }

    function bindExistingRows() {
      document.querySelectorAll(".project-result[data-job-id]").forEach(function (row) {
        if (row.dataset.mapBound === "true") {
          return;
        }
        row.dataset.mapBound = "true";
        row.setAttribute("aria-keyshortcuts", "ArrowUp ArrowDown Home End");
        row.addEventListener("click", function (event) {
          if (event.button !== 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
            return;
          }
          event.preventDefault();
          activateJob(row.getAttribute("data-job-id"), true, true);
        });
        row.addEventListener("mouseenter", function () {
          activateJob(row.getAttribute("data-job-id"), false, false);
        });
        row.addEventListener("focusin", function () {
          activateJob(row.getAttribute("data-job-id"), false, false);
        });
        row.addEventListener("keydown", function (event) {
          moveJobFocus(row, event);
        });
      });
    }

    function renderMarkers(fitMap) {
      var bounds = [];
      markerByJobId = {};
      markerLayer.clearLayers();
      visibleJobs.forEach(function (job) {
        var lat = Number(job.lat);
        var lng = Number(job.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
          return;
        }
        var label = markerLabel(job);
        var marker = window.L.marker([lat, lng], {
          alt: label,
          title: label
        });
        marker.bindPopup(
          '<div class="map-popup">' +
            (job.is_demo ? '<span class="sample-badge">Sample</span>' : "") +
            "<strong>" + escapeHtml(job.title || "Open project") + "</strong>" +
            "<span>" + escapeHtml(placeLabel(job)) + "</span>" +
            "<span>" + escapeHtml(job.budget || "Budget not provided") + "</span>" +
          "</div>"
        );
        marker.on("click", function () {
          activateJob(job.id, false, true);
        });
        marker.on("add", function () {
          var element = marker.getElement && marker.getElement();
          if (element) {
            element.setAttribute("aria-label", label);
          }
        });
        markerByJobId[String(job.id)] = marker;
        markerLayer.addLayer(marker);
        bounds.push([lat, lng]);
      });
      updateResultStatus(visibleJobs.length, bounds.length);
      if (fitMap && bounds.length > 1) {
        map.fitBounds(bounds, { padding: [42, 42], maxZoom: 11 });
      } else if (fitMap && bounds.length === 1) {
        map.setView(bounds[0], 12);
      }
    }

    function activateJob(jobId, panMap, revealDetails) {
      activeJobId = String(jobId || "");
      highlightJobRows(activeJobId);
      var job = findVisibleJob(activeJobId);
      updateDetail(job);
      announceActiveJob(job);
      var marker = markerByJobId[activeJobId];
      if (marker) {
        if (panMap) {
          map.panTo(marker.getLatLng(), { animate: true, duration: 0.25 });
        }
        if (window.L.markerClusterGroup && markerLayer.zoomToShowLayer) {
          markerLayer.zoomToShowLayer(marker, function () {
            marker.openPopup();
          });
        } else {
          marker.openPopup();
        }
      }
      if (job && window.history && document.body.classList.contains("market-entry-body")) {
        var nextUrl = new URL(window.location.href);
        nextUrl.searchParams.set("job_id", String(job.id));
        window.history.replaceState({}, "", nextUrl.pathname + nextUrl.search);
      }
      if (revealDetails && window.matchMedia("(max-width: 900px)").matches) {
        setMobilePanel("details");
      }
    }

    function updateDetail(job) {
      if (!detailContent) {
        return;
      }
      if (!job) {
        detailContent.outerHTML = '<div class="market-detail-empty" data-project-detail-content><img src="/field-doe.webp" alt="" width="160" height="160"><h2>No projects match</h2><p>Adjust the filters to widen the map.</p></div>';
        detailContent = document.querySelector("[data-project-detail-content]");
        return;
      }
      var sample = job.is_demo
        ? '<span class="sample-badge">Demonstration project</span>'
        : '<span class="live-badge">Open project</span>';
      detailContent.outerHTML = (
        '<article class="market-project-detail" data-project-detail-content data-job-id="' + escapeAttribute(job.id) + '">' +
          '<div class="project-detail-heading">' + sample + "<span>" + escapeHtml(job.category || "Project") + "</span></div>" +
          "<h2>" + escapeHtml(job.title || "Open project") + "</h2>" +
          '<p class="project-detail-location">' + escapeHtml(placeLabel(job)) + "</p>" +
          '<dl class="project-facts"><div><dt>Estimated budget</dt><dd>' + escapeHtml(job.budget || "Budget not provided") + "</dd></div>" +
          "<div><dt>Desired date</dt><dd>" + escapeHtml(job.desired_date || "Flexible") + "</dd></div></dl>" +
          '<div class="project-description"><h3>Project overview</h3><p>' + escapeHtml(job.description || "Project details are available after sign-in.") + "</p></div>" +
          '<p class="project-privacy-note">Location is intentionally approximate until a match is approved.</p>' +
          '<div class="project-detail-actions"><a class="button primary" href="' + escapeAttribute(job.url || "/start") + '">' + escapeHtml(job.action_label || "Join to respond") + "</a>" +
          '<a class="button secondary" href="' + escapeAttribute(job.detail_url || "#") + '">Open project link</a></div>' +
        "</article>"
      );
      detailContent = document.querySelector("[data-project-detail-content]");
    }

    function updateCounts() {
      var countLabel = visibleJobs.length + (visibleJobs.length === 1 ? " project" : " projects");
      if (resultCount) {
        resultCount.textContent = countLabel;
      }
      if (mapResultCount) {
        mapResultCount.textContent = countLabel + " mapped";
      }
    }

    function highlightJobRows(jobId) {
      document.querySelectorAll(".project-result[data-job-id]").forEach(function (row) {
        var active = row.getAttribute("data-job-id") === String(jobId);
        row.classList.toggle("is-map-active", active);
        if (active) {
          row.setAttribute("aria-current", "true");
        } else {
          row.removeAttribute("aria-current");
        }
      });
    }

    function moveJobFocus(row, event) {
      if (event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      var rows = Array.prototype.slice.call(document.querySelectorAll(".project-result[data-job-id]"));
      var index = rows.indexOf(row);
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
        rows[nextIndex].focus({ preventScroll: false });
        activateJob(rows[nextIndex].getAttribute("data-job-id"), true, false);
      }
    }

    function bindMobileTabs() {
      document.querySelectorAll("[data-mobile-panel-target]").forEach(function (button) {
        button.addEventListener("click", function () {
          setMobilePanel(button.getAttribute("data-mobile-panel-target"));
        });
      });
      if (workspace) {
        setMobilePanel(workspace.getAttribute("data-mobile-panel") || "map");
      }
    }

    function setMobilePanel(panel) {
      if (!workspace || ["filters", "map", "details"].indexOf(panel) === -1) {
        return;
      }
      workspace.setAttribute("data-mobile-panel", panel);
      document.querySelectorAll("[data-mobile-panel-target]").forEach(function (button) {
        var selected = button.getAttribute("data-mobile-panel-target") === panel;
        button.setAttribute("aria-selected", selected ? "true" : "false");
        button.tabIndex = selected ? 0 : -1;
      });
      if (panel === "map") {
        window.setTimeout(function () {
          map.invalidateSize({ pan: false });
        }, 50);
      }
    }

    function findJob(jobId) {
      return allJobs.find(function (job) { return String(job.id) === String(jobId); });
    }

    function findVisibleJob(jobId) {
      return visibleJobs.find(function (job) { return String(job.id) === String(jobId); });
    }

    function initialJobId(jobs) {
      var activeRow = document.querySelector("[data-job-id].is-map-active");
      if (activeRow) {
        return activeRow.getAttribute("data-job-id") || "";
      }
      return jobs.length ? String(jobs[0].id) : "";
    }

    function markerLabel(job) {
      return (job.title || "Open project") + " in " + placeLabel(job);
    }

    function placeLabel(job) {
      return [job.city, job.state].filter(Boolean).join(", ");
    }

    function announceActiveJob(job) {
      if (job) {
        setMapStatus((job.title || "Project") + " is selected. Details are available beside the map.");
      }
    }

    function updateResultStatus(jobCount, pinCount) {
      if (!jobCount) {
        setMapStatus("No projects match the current filters.");
        return;
      }
      setMapStatus(jobCount + " projects shown with " + pinCount + " approximate map locations.");
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
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeAttribute(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
  }
})();
