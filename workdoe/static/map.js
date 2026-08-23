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
    var serviceSelect = document.querySelector("[data-market-service]");
    var sortSelect = document.querySelector("[data-market-sort]");
    var filterForm = document.querySelector("[data-market-filters]");
    var clearButton = document.querySelector("[data-clear-market-filters]");
    var searchAreaButton = document.querySelector("[data-search-map-area]");
    var resultCount = document.querySelector("[data-project-result-count]");
    var mapResultCount = document.querySelector("[data-map-result-count]");
    var detailContent = document.querySelector("[data-project-detail-content]");
    var jobsApi = mapElement.getAttribute("data-jobs-api") || "";
    var tileUrl = mapElement.getAttribute("data-tile-url") || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
    var tileAttribution = mapElement.getAttribute("data-tile-attribution") || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
    var map = window.L.map(mapElement, {
      scrollWheelZoom: false,
      zoomControl: true,
      maxZoom: 18
    }).setView([38.9072, -77.0369], 9);
    var markerLayer = createMarkerLayer(map);
    var markerByJobId = {};
    var allJobs = readSeedJobs();
    var visibleJobs = [];
    var activeJobId = initialJobId(allJobs);
    var activeViewport = readViewportFromUrl();
    var ignoreNextMoveEnd = false;
    var requestSequence = 0;

    mapElement.classList.add("map-ready");
    window.L.tileLayer(tileUrl, {
      maxZoom: 18,
      attribution: tileAttribution
    }).addTo(map);

    bindFilters();
    bindMobileTabs();
    bindMapSearch();
    bindPopupOverlayState();
    if (activeViewport) {
      moveMap(function () {
        map.fitBounds(viewportBounds(activeViewport), { padding: [28, 28], maxZoom: 13 });
      });
      applyFilters(false);
      loadJobs(activeViewport, false);
    } else {
      applyFilters(true);
      if (jobsApi && window.fetch) {
        loadJobs(null, true);
      }
    }

    function createMarkerLayer(leafletMap) {
      var layer = window.L.layerGroup();
      if (window.L.markerClusterGroup) {
        try {
          layer = window.L.markerClusterGroup({
            showCoverageOnHover: false,
            spiderfyOnMaxZoom: true,
            maxClusterRadius: 46
          });
          layer.addTo(leafletMap);
          return layer;
        } catch (clusterError) {
          layer = window.L.layerGroup();
        }
      }
      layer.addTo(leafletMap);
      return layer;
    }

    function bindFilters() {
      if (searchInput) {
        searchInput.addEventListener("input", function () {
          applyFilters(false);
          updateUrlState();
        });
      }
      [categorySelect, serviceSelect, sortSelect].forEach(function (control) {
        if (!control) {
          return;
        }
        control.addEventListener("change", function () {
          applyFilters(false);
          updateUrlState();
        });
      });
      if (filterForm) {
        filterForm.addEventListener("submit", function (event) {
          if (!jobsApi || !window.fetch) {
            return;
          }
          event.preventDefault();
          loadJobs(activeViewport, false);
        });
      }
      if (clearButton) {
        clearButton.addEventListener("click", function (event) {
          var clearUrl = clearButton.getAttribute("data-clear-market-url");
          if (clearUrl) {
            return;
          }
          event.preventDefault();
          if (searchInput) {
            searchInput.value = "";
          }
          [categorySelect, serviceSelect].forEach(function (control) {
            if (control) {
              control.value = "";
            }
          });
          if (sortSelect) {
            sortSelect.value = "newest";
          }
          activeViewport = null;
          applyFilters(true);
          updateUrlState();
          if (jobsApi && window.fetch) {
            loadJobs(null, true);
          }
          if (searchInput) {
            searchInput.focus();
          }
        });
      }
    }

    function bindPopupOverlayState() {
      map.on("popupopen", function () {
        mapElement.classList.add("has-open-popup");
      });
      map.on("popupclose", function () {
        mapElement.classList.remove("has-open-popup");
      });
    }

    function bindMapSearch() {
      map.on("moveend", function () {
        if (ignoreNextMoveEnd) {
          ignoreNextMoveEnd = false;
          return;
        }
        if (searchAreaButton && jobsApi) {
          searchAreaButton.hidden = false;
          searchAreaButton.disabled = false;
        }
      });
      if (searchAreaButton) {
        searchAreaButton.addEventListener("click", function () {
          loadJobs(viewportFromBounds(map.getBounds()), false);
        });
      }
    }

    function loadJobs(viewport, fitMap) {
      if (!jobsApi || !window.fetch) {
        return;
      }
      var requestId = ++requestSequence;
      var requestUrl = jobsRequestUrl(viewport);
      setLoading(true);
      window.fetch(requestUrl, {
        headers: { Accept: "application/json" },
        credentials: "same-origin"
      })
        .then(function (response) {
          if (!response.ok) {
            return response.json().catch(function () { return {}; }).then(function (payload) {
              throw new Error(payload.error || "Project map request failed");
            });
          }
          return response.json();
        })
        .then(function (payload) {
          if (requestId !== requestSequence || !payload || !Array.isArray(payload.jobs)) {
            return;
          }
          allJobs = mergeJobPayload(payload);
          activeViewport = payload.viewport || viewport || null;
          if (!findJob(activeJobId)) {
            activeJobId = initialJobId(allJobs);
          }
          applyFilters(Boolean(fitMap && !activeViewport));
          updateUrlState();
          if (searchAreaButton) {
            searchAreaButton.hidden = true;
          }
          var suffix = payload.truncated ? " More projects are available beyond this page." : "";
          setMapStatus((payload.result_count || payload.count || allJobs.length) + " projects loaded." + suffix);
        })
        .catch(function (error) {
          if (requestId !== requestSequence) {
            return;
          }
          setMapStatus(error.message || "The live map could not refresh. The project list is still ready.");
        })
        .then(function () {
          if (requestId === requestSequence) {
            setLoading(false);
          }
        });
    }

    function jobsRequestUrl(viewport) {
      var url = new URL(jobsApi, window.location.href);
      setOptionalParam(url, "q", searchInput && searchInput.value.trim());
      setOptionalParam(url, "category", categorySelect && categorySelect.value);
      setOptionalParam(url, "service", serviceSelect && serviceSelect.value);
      setOptionalParam(url, "sort", sortSelect && sortSelect.value !== "newest" ? sortSelect.value : "");
      url.searchParams.delete("cursor");
      setViewportParams(url, viewport);
      return url.pathname + url.search;
    }

    function applyFilters(fitMap) {
      var query = searchInput ? searchInput.value.trim().toLowerCase() : "";
      var category = categorySelect ? categorySelect.value : "";
      var service = serviceSelect ? serviceSelect.value : "";
      visibleJobs = allJobs.filter(function (job) {
        if (category && job.category !== category) {
          return false;
        }
        if (service && job.service_slug !== service) {
          return false;
        }
        if (!query) {
          return true;
        }
        return [job.title, job.service_name, job.category, job.city, job.state, job.description]
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
        resultContainer.innerHTML = '<div class="market-list-empty"><strong>No matching projects</strong><span>Move the map or broaden the filters.</span></div>';
        return;
      }
      resultContainer.innerHTML = visibleJobs.map(projectRowHtml).join("");
      bindExistingRows();
    }

    function projectRowHtml(job) {
      var active = String(job.id) === String(activeJobId);
      var sample = job.is_demo ? '<span class="sample-badge">Sample</span>' : "";
      var fit = job.fit_label ? '<span class="lead-fit fit-' + escapeAttribute(job.fit_score || 0) + '">' + escapeHtml(job.fit_label) + "</span>" : "";
      var status = job.request_status ? '<span class="status ' + escapeAttribute(job.request_status) + '">Bid ' + escapeHtml(job.request_status) + "</span>" : "";
      var bidding = job.bid_window || {};
      var readiness = job.brief_readiness || {};
      var availability = bidding.availability_label || job.budget || "Budget not provided";
      var photoCount = Number(job.photo_count || 0);
      var photoLabel = photoCount + (photoCount === 1 ? " photo" : " photos");
      var cue = job.row_cue || job.action_label || "View";
      var readinessFact = readiness.label ? "<span>" + escapeHtml(readiness.label) + "</span>" : "";
      return (
        '<a class="project-result' + (active ? " is-map-active" : "") + '" role="listitem" data-job-id="' + escapeAttribute(job.id) + '" href="' + escapeAttribute(job.detail_url || job.url || "#") + '"' + (active ? ' aria-current="true"' : "") + ">" +
          '<span class="project-result-topline">' + fit + '<span class="job-service-chip">' + escapeHtml(job.service_name || job.category || "Project") + "</span>" + status + sample + "</span>" +
          "<strong>" + escapeHtml(job.title || "Open project") + "</strong>" +
          '<span class="project-result-facts"><span>' + escapeHtml(placeLabel(job)) + "</span><span>" + escapeHtml(availability) + "</span><span>" + escapeHtml(photoLabel) + "</span>" + readinessFact + "<span>" + escapeHtml(cue) + "</span></span>" +
        "</a>"
      );
    }

    function mergeJobPayload(payload) {
      var incoming = Array.isArray(payload.map_jobs) && payload.map_jobs.length
        ? payload.map_jobs
        : payload.jobs;
      var currentById = {};
      var contractorFields = [
        "description", "request_status", "bid_window", "brief_readiness",
        "fit_score", "fit_label", "row_cue", "action_label", "url", "detail_url"
      ];
      allJobs.forEach(function (job) {
        currentById[String(job.id)] = job;
      });
      return incoming.map(function (job) {
        var current = currentById[String(job.id)] || {};
        var merged = Object.assign({}, current, job);
        contractorFields.forEach(function (field) {
          if (Object.prototype.hasOwnProperty.call(current, field)) {
            merged[field] = current[field];
          }
        });
        return merged;
      });
    }

    function bindExistingRows() {
      document.querySelectorAll(".project-result[data-job-id], .job-row[data-job-id]").forEach(function (row) {
        if (row.dataset.mapBound === "true") {
          return;
        }
        row.dataset.mapBound = "true";
        row.setAttribute("aria-keyshortcuts", "ArrowUp ArrowDown Home End");
        row.addEventListener("click", function (event) {
          if (event.button !== 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
            return;
          }
          if (!detailContent) {
            activateJob(row.getAttribute("data-job-id"), true, false);
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
        var marker = window.L.marker([lat, lng], { alt: label, title: label });
        marker.bindPopup(
          '<div class="map-popup">' +
            (job.is_demo ? '<span class="sample-badge">Sample</span>' : "") +
            "<strong>" + escapeHtml(job.title || "Open project") + "</strong>" +
            "<span>" + escapeHtml(placeLabel(job)) + "</span>" +
            "<span>" + escapeHtml(job.budget || "Budget not provided") + "</span>" +
          "</div>",
          {
            maxWidth: 220,
            autoPanPaddingTopLeft: [64, 56],
            autoPanPaddingBottomRight: [16, 16]
          }
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
        moveMap(function () {
          map.fitBounds(bounds, { padding: [42, 42], maxZoom: 11 });
        });
      } else if (fitMap && bounds.length === 1) {
        moveMap(function () {
          map.setView(bounds[0], 12);
        });
      }
    }

    function moveMap(action) {
      ignoreNextMoveEnd = true;
      action();
      window.setTimeout(function () {
        ignoreNextMoveEnd = false;
      }, 700);
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
          moveMap(function () {
            map.panTo(marker.getLatLng(), { animate: true, duration: 0.25 });
          });
        }
        if (window.L.markerClusterGroup && markerLayer.zoomToShowLayer) {
          markerLayer.zoomToShowLayer(marker, function () { marker.openPopup(); });
        } else {
          marker.openPopup();
        }
      }
      updateUrlState();
      if (revealDetails && window.matchMedia("(max-width: 900px)").matches) {
        setMobilePanel("details");
      }
    }

    function updateDetail(job) {
      if (!detailContent) {
        return;
      }
      if (!job) {
        detailContent.outerHTML = '<div class="market-detail-empty" data-project-detail-content><img src="/field-doe.webp" alt="" width="160" height="160"><h2>No projects match</h2><p>Move the map or adjust the filters.</p></div>';
        detailContent = document.querySelector("[data-project-detail-content]");
        return;
      }
      var sample = job.is_demo ? '<span class="sample-badge">Demonstration project</span>' : '<span class="live-badge">Open project</span>';
      var bidding = job.bid_window || {};
      var biddingFact = bidding.usage_label ? "<div><dt>Mini bids</dt><dd>" + escapeHtml(bidding.usage_label) + "</dd></div>" : "";
      var actionLabel = job.action_label || "Review and bid";
      detailContent.outerHTML = (
        '<article class="market-project-detail" data-project-detail-content data-job-id="' + escapeAttribute(job.id) + '">' +
          '<div class="project-detail-heading">' + sample + "<span>" + escapeHtml(job.service_name || job.category || "Project") + "</span></div>" +
          "<h2>" + escapeHtml(job.title || "Open project") + "</h2>" +
          '<p class="project-detail-location">' + escapeHtml(placeLabel(job)) + "</p>" +
          '<dl class="project-facts"><div><dt>Estimated budget</dt><dd>' + escapeHtml(job.budget || "Budget not provided") + "</dd></div>" +
          "<div><dt>Desired date</dt><dd>" + escapeHtml(job.desired_date || "Flexible") + "</dd></div>" + biddingFact + "</dl>" +
          '<div class="project-description"><h3>Project overview</h3><p>' + escapeHtml(job.description || "Project details are available after sign-in.") + "</p></div>" +
          '<p class="project-privacy-note">Location is intentionally approximate until a match is approved.</p>' +
          '<div class="project-detail-actions"><a class="button primary" href="' + escapeAttribute(job.url || "/start") + '" data-dialog-title="' + escapeAttribute(actionLabel) + '">' + escapeHtml(actionLabel) + "</a></div>" +
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
      document.querySelectorAll("[data-job-id]").forEach(function (row) {
        if (!row.matches(".project-result, .job-row")) {
          return;
        }
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
      var rows = Array.prototype.slice.call(document.querySelectorAll(".project-result[data-job-id], .job-row[data-job-id]"));
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
      var buttons = Array.prototype.slice.call(
        document.querySelectorAll("[data-mobile-panel-target]")
      );
      buttons.forEach(function (button) {
        button.addEventListener("click", function () {
          setMobilePanel(button.getAttribute("data-mobile-panel-target"));
        });
        button.addEventListener("keydown", function (event) {
          if (event.altKey || event.ctrlKey || event.metaKey) {
            return;
          }
          var currentIndex = buttons.indexOf(button);
          var nextIndex = currentIndex;
          if (event.key === "ArrowRight") {
            nextIndex = (currentIndex + 1) % buttons.length;
          } else if (event.key === "ArrowLeft") {
            nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
          } else if (event.key === "Home") {
            nextIndex = 0;
          } else if (event.key === "End") {
            nextIndex = buttons.length - 1;
          } else {
            return;
          }
          event.preventDefault();
          setMobilePanel(buttons[nextIndex].getAttribute("data-mobile-panel-target"));
          buttons[nextIndex].focus();
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
        window.setTimeout(function () { map.invalidateSize({ pan: false }); }, 50);
      }
    }

    function updateUrlState() {
      if (!window.history || !window.URL) {
        return;
      }
      var url = new URL(window.location.href);
      setOptionalParam(url, "q", searchInput && searchInput.value.trim());
      setOptionalParam(url, "category", categorySelect && categorySelect.value);
      setOptionalParam(url, "service", serviceSelect && serviceSelect.value);
      setOptionalParam(url, "sort", sortSelect && sortSelect.value !== "newest" ? sortSelect.value : "");
      setOptionalParam(url, "job_id", activeJobId);
      setViewportParams(url, activeViewport);
      url.searchParams.delete("cursor");
      window.history.replaceState({ workdoeMap: true }, "", url.pathname + url.search + url.hash);
    }

    function setOptionalParam(url, key, value) {
      if (value) {
        url.searchParams.set(key, String(value));
      } else {
        url.searchParams.delete(key);
      }
    }

    function setViewportParams(url, viewport) {
      ["north", "south", "east", "west"].forEach(function (key) {
        if (viewport && Number.isFinite(Number(viewport[key]))) {
          url.searchParams.set(key, Number(viewport[key]).toFixed(6));
        } else {
          url.searchParams.delete(key);
        }
      });
    }

    function readViewportFromUrl() {
      var url = new URL(window.location.href);
      var viewport = {};
      var valid = ["north", "south", "east", "west"].every(function (key) {
        viewport[key] = Number(url.searchParams.get(key));
        return Number.isFinite(viewport[key]);
      });
      return valid && viewport.north > viewport.south && viewport.east > viewport.west ? viewport : null;
    }

    function viewportFromBounds(bounds) {
      return {
        north: Number(bounds.getNorth().toFixed(6)),
        south: Number(bounds.getSouth().toFixed(6)),
        east: Number(bounds.getEast().toFixed(6)),
        west: Number(bounds.getWest().toFixed(6))
      };
    }

    function viewportBounds(viewport) {
      return [[viewport.south, viewport.west], [viewport.north, viewport.east]];
    }

    function setLoading(loading) {
      mapElement.setAttribute("aria-busy", loading ? "true" : "false");
      if (searchAreaButton) {
        searchAreaButton.disabled = loading;
        searchAreaButton.textContent = loading ? "Loading projects" : "Search this area";
      }
    }

    function findJob(jobId) {
      return allJobs.find(function (job) { return String(job.id) === String(jobId); });
    }

    function findVisibleJob(jobId) {
      return visibleJobs.find(function (job) { return String(job.id) === String(jobId); });
    }

    function initialJobId(jobs) {
      var requested = new URL(window.location.href).searchParams.get("job_id");
      if (requested && jobs.some(function (job) { return String(job.id) === requested; })) {
        return requested;
      }
      var activeRow = document.querySelector("[data-job-id].is-map-active, [data-job-id].is-selected");
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
