(function () {
  "use strict";

  var SEARCH_PRIVACY_NOTICE = "Search by project, city, or ZIP. Leave out contact details and street addresses.";
  var TILE_LOAD_DEADLINE_MS = 15000;
  var SEARCH_DEADLINE_MS = 12000;
  var AREA_MAP_ASSET = "/dmv-area-50fe6cd3.geojson";
  var AREA_MAP_INTEGRITY = "sha256-UP5s0yWNmgd5Vb17JI8PzI+INyRCFOEk3BC+20wyYFE=";
  var MAP_UNAVAILABLE_NOTICE = "The map couldn't load. You can still browse the project list.";
  var PRIVATE_SEARCH = /@|(?:[0-9][ .()+-]*){9}[0-9]|\b(?:p\.?\s*o\.?\s+box\s*[0-9]+|[0-9]{1,5}\s+(?:[a-z0-9.'-]+\s+){0,4}(?:street|st|avenue|ave|road|rd|lane|ln|drive|dr|court|ct|boulevard|blvd|place|pl|parkway|pkwy|terrace|ter|circle|cir|highway|hwy|trail|trl))\b/i;

  function safeSearchQuery(value) {
    var query = String(value || "").trim().replace(/\s+/g, " ");
    var normalized = query.normalize("NFKC").replace(/[\u2010-\u2014\u2212]/g, "-");
    if (PRIVATE_SEARCH.test(normalized)) return null;
    var joined = normalized.replace(/\p{Cf}/gu, "");
    if (joined !== normalized &&
        (PRIVATE_SEARCH.test(joined) || PRIVATE_SEARCH.test(normalized.replace(/\p{Cf}/gu, " ")))) return null;
    return query.slice(0, 80);
  }

  function retryDelay(retryAfter, responseDate) {
    var hint = (retryAfter || "").trim();
    if (/^[0-9]+$/.test(hint)) return Math.max(1000, Number(hint) * 1000);
    var deadline = /^[a-z]{3}/i.test(hint) ? Date.parse(hint) : NaN;
    var serverTime = Date.parse(responseDate || "");
    return Number.isFinite(deadline)
      ? Math.max(1000, deadline - (Number.isFinite(serverTime) ? serverTime : Date.now()))
      : 10000;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var defaultDmvView = { center: [38.9072, -77.0369], zoom: 9 };
    var mapElement = document.getElementById("lead-map");
    if (!mapElement || !window.L) {
      return;
    }

    var statusElement = document.getElementById("lead-map-status");
    var mapPlaceholder = document.getElementById("lead-map-loading");
    var workspace = document.querySelector("[data-market-workspace]");
    var publicEntry = workspace && workspace.hasAttribute("data-entry-mode");
    var projectsPanel = workspace && workspace.querySelector('[data-market-panel="filters"]');
    var resultContainer = document.querySelector("[data-project-results]");
    var resultsStatus = document.querySelector("[data-project-results-status]");
    var searchInput = document.querySelector("[data-market-search]");
    var categorySelect = document.querySelector("[data-market-category]");
    var serviceSelect = document.querySelector("[data-market-service]");
    var sortSelect = document.querySelector("[data-market-sort]");
    var filterForm = document.querySelector("[data-market-filters]");
    var clearButton = document.querySelector("[data-clear-market-filters]");
    var searchAreaButton = document.querySelector("[data-search-map-area]");
    var showMapAreaButton = document.querySelector("[data-show-map-area]");
    var resetMapViewButton = document.querySelector("[data-reset-map-view]");
    var resultCount = document.querySelector("[data-project-result-count]");
    var truncationNotice = document.querySelector("[data-project-truncation]");
    var mapResultCount = document.querySelector("[data-map-result-count]");
    var mapListOnlyCount = document.querySelector("[data-map-list-only-count]");
    var mapSourceCounts = document.querySelector("[data-map-source-counts]");
    var laneAction = document.querySelector("[data-market-lane]");
    var detailContent = document.querySelector("[data-project-detail-content]");
    var missingSharedProject = document.querySelector("template[data-missing-shared-project]");
    var sharedJobId = missingSharedProject ? new URL(window.location.href).searchParams.get("job_id") || "" : "";
    var jobsApi = mapElement.getAttribute("data-jobs-api") || "";
    var canRefreshJobs = Boolean(jobsApi && window.fetch && window.AbortController);
    var appliedPublicFilters = publicEntry && jobsApi
      ? new URL(jobsApi, window.location.href).searchParams
      : null;
    var assetRoot = (mapElement.getAttribute("data-asset-root") || "").replace(/\/+$/, "");
    var tileUrl = mapElement.getAttribute("data-tile-url") || "";
    var tileAttribution = mapElement.getAttribute("data-tile-attribution") || "";
    var areaMap = tileUrl === AREA_MAP_ASSET;
    var areaBounds = areaMap ? JSON.parse(mapElement.getAttribute("data-area-map-bounds")) : null;
    if (!tileUrl || !tileAttribution) {
      if (statusElement) {
        statusElement.textContent = "Map configuration is unavailable. Project list is ready.";
      }
      if (mapPlaceholder) {
        mapPlaceholder.textContent = "Map configuration is unavailable. Project list is ready.";
        mapPlaceholder.removeAttribute("aria-hidden");
      }
      return;
    }
    var mapTools = areaMap ? dockMapTools() : null;
    var map = window.L.map(mapElement, {
      scrollWheelZoom: true,
      zoomControl: true,
      trackResize: false,
      minZoom: areaMap ? 8 : undefined,
      maxZoom: 18,
      bounceAtZoomLimits: !areaMap,
      zoomAnimation: motionAllowed(),
      fadeAnimation: motionAllowed(),
      markerZoomAnimation: motionAllowed(),
      inertia: motionAllowed()
    }).setView(defaultDmvView.center, defaultDmvView.zoom, { animate: motionAllowed() ? undefined : false });
    var markerLayer = createMarkerLayer(map);
    var markerByJobId = {};
    var seedJobs = readSeedJobs();
    var serverSnapshot = publicEntry && seedJobs && readServerSnapshot();
    var allJobs = seedJobs || [];
    var visibleJobs = [];
    var activeJobId = sharedJobId || initialJobId(allJobs);
    // WebKit can retarget a stationary pointer after modal scrolling or closure.
    var lastMousePosition = null;
    document.addEventListener("pointermove", function (event) {
      if (event.pointerType === "mouse") {
        lastMousePosition = { x: event.clientX, y: event.clientY };
      }
    });
    var activeViewport = serverSnapshot ? serverSnapshot.viewport : readViewportFromUrl();
    var resultsTruncated = Boolean(serverSnapshot && serverSnapshot.truncated);
    var ignoreNextMoveEnd = false;
    var mapMoveSequence = 0;
    var requestSequence = 0;
    var jobsRequest = null;
    var mapResizeTimer = null;
    var resizingMap = false;
    var pendingMapFit = false;
    var automaticMapFrame = false;
    var mapFrameSize = "";
    var tileLoadTimer = null;
    var mapUnavailable = false;
    var areaLoading = areaMap;
    var areaRequest = null;
    var jobsLoading = false;
    var scheduleAreaLabels = null;
    var pendingUrlState = false;
    var retryUntil = 0;
    var retryTimer = null;
    var jobsNotice = "";
    var startupProjectAnchor = null;
    var filterSubmit = filterForm && filterForm.querySelector("button[type=submit]");
    var filterSubmitLabel = filterSubmit && filterSubmit.textContent;
    var searchNotice = jobsApi && filterForm ? document.createElement("p") : null;
    if (searchNotice) {
      searchNotice.className = "market-search-notice sr-only";
      searchNotice.setAttribute("data-market-search-notice", "");
      if (resultsStatus) searchNotice.setAttribute("aria-hidden", "true");
      else searchNotice.setAttribute("role", "status");
      filterForm.after(searchNotice);
    }

    mapElement.classList.add("map-ready");
    var tileLayer = areaMap ? window.L.geoJSON(null, {
      attribution: tileAttribution,
      interactive: false,
      style: function (feature) {
        var fills = {"11": "#f3ecd9", "24": "#edf1e3", "51": "#e6eedf", "54": "#eeeae1"};
        return { color: "#839c92", weight: 1, fillColor: fills[feature.properties.STATE], fillOpacity: .93 };
      }
    }) : window.L.tileLayer(tileUrl, {
      maxZoom: 18,
      attribution: tileAttribution
    });
    if (areaMap) {
      mapElement.classList.add("map-area-boundaries", "map-area-loading");
      if (mapPlaceholder) mapPlaceholder.textContent = "Loading the project map. The project list is ready.";
      syncMapBusy();
    } else {
      tileLayer.on("loading", startTileLoadTimer);
      tileLayer.on("load", function () {
        clearTileLoadTimer();
        if (resultsStatus && !mapUnavailable) setMapStatus("Project map ready. Locations are approximate.");
      });
      tileLayer.on("tileerror", failTileLayer);
      tileLayer.addTo(map);
    }

    bindFilters();
    bindMobileTabs();
    bindMapSearch();
    bindPopupOverlayState();
    bindMapViewport();
    window.addEventListener("popstate", function () {
      if (pendingUrlState) updateUrlState();
    });
    if (activeViewport) {
      fitMapWhenVisible();
    }
    applyFilters(!activeViewport);
    if (serverSnapshot && appliedPublicFilters
        && (appliedPublicFilters.get("q") || "") === safeSearchQuery(searchInput && searchInput.value)) {
      updateUrlState();
    } else {
      loadJobs(activeViewport, !activeViewport);
    }

    startAreaMap();

    function dockMapTools() {
      var tools = mapElement.querySelector(".map-view-controls");
      if (!tools) return null;
      tools.classList.add("map-view-dock", "is-loading");
      tools.setAttribute("role", "group");
      if (searchAreaButton && canRefreshJobs) {
        tools.classList.add("has-area-search");
        var searchSlot = document.createElement("div");
        searchSlot.className = "map-area-search-slot";
        searchSlot.setAttribute("data-label", searchAreaButton.textContent);
        searchSlot.appendChild(searchAreaButton);
        tools.appendChild(searchSlot);
      }
      var stage = mapElement.closest(".market-map-stage");
      var toolbar = stage && stage.querySelector(".map-stage-toolbar");
      if (toolbar) toolbar.appendChild(tools);
      else mapElement.before(tools);
      return tools;
    }

    function startTileLoadTimer() {
      if (tileLoadTimer === null && !mapUnavailable) {
        tileLoadTimer = window.setTimeout(failTileLayer, TILE_LOAD_DEADLINE_MS);
      }
    }

    function mapHasSpace() {
      return !mapUnavailable && mapElement.clientWidth > 0 && mapElement.clientHeight > 0;
    }

    function startAreaMap() {
      if (!areaLoading || areaRequest || !mapHasSpace()) return;
      if (!window.fetch || !window.AbortController) {
        failTileLayer();
        return;
      }
      areaRequest = new window.AbortController();
      tileLayer.addTo(map);
      startTileLoadTimer();
      window.fetch(assetRoot + tileUrl, {
        mode: "same-origin", redirect: "error", referrerPolicy: "no-referrer",
        credentials: mapElement.hasAttribute("data-area-map-access") ? "same-origin" : "omit",
        integrity: AREA_MAP_INTEGRITY, signal: areaRequest.signal
      }).then(function (response) {
        if (!response.ok) throw new Error("Area boundaries unavailable");
        return response.json();
      }).then(function (data) {
        if (mapUnavailable) return;
        if (data.type !== "FeatureCollection" || !Array.isArray(data.features) || data.features.length !== 50) {
          throw new Error("Invalid area boundaries");
        }
        tileLayer.addData(data);
        clearTileLoadTimer();
        areaRequest = null;
        finishAreaLoading();
        addAreaLabels();
      }).catch(failTileLayer);
    }

    function finishAreaLoading() {
      areaLoading = false;
      mapElement.classList.remove("map-area-loading");
      if (mapTools) mapTools.classList.remove("is-loading");
      syncMapBusy();
      if (resultsStatus && !mapUnavailable) setMapStatus("Project map ready. Locations are approximate.");
    }

    function syncMapBusy() {
      mapElement.setAttribute("aria-busy", jobsLoading || areaLoading ? "true" : "false");
    }

    function constrainAreaMap() {
      if (!areaBounds || !mapHasSpace()) return;
      resizingMap = true;
      try {
        map.panInsideBounds(areaBounds, { animate: false });
      } finally {
        resizingMap = false;
      }
    }

    function resizeVisibleMap() {
      if (!mapHasSpace()) return;
      var size = mapElement.clientWidth + "x" + mapElement.clientHeight;
      var fit = pendingMapFit || (automaticMapFrame && size !== mapFrameSize &&
        !mapElement.classList.contains("has-open-popup"));
      mapFrameSize = size;
      // Leaflet emits moveend during layout, even though the visitor did not browse.
      resizingMap = true;
      try {
        map.invalidateSize({ animate: false, pan: true });
        if (fit && areaMap) fitCurrentMapFrame();
      } finally {
        resizingMap = false;
      }
      if (fit) {
        pendingMapFit = false;
        if (!areaMap) moveMap(fitCurrentMapFrame);
      } else {
        constrainAreaMap();
      }
      startAreaMap();
      if (scheduleAreaLabels) scheduleAreaLabels();
    }

    function addAreaLabels() {
      var pane = map.createPane("area-labels");
      pane.style.zIndex = "430";
      pane.style.visibility = "hidden";
      pane.setAttribute("aria-hidden", "true");
      var places = [
        [38.90, -77.03, "Washington, DC"],
        [39.06, -77.24, "Montgomery"], [38.77, -77.27, "Fairfax"],
        [38.88, -76.84, "Prince George's"],
        [39.10, -77.59, "Loudoun"], [38.95, -76.57, "Anne Arundel"],
        [38.60, -77.47, "Prince William"], [39.29, -76.62, "Baltimore"]
      ];
      function createLabel(place) {
        var text = document.createElement("span");
        text.textContent = place[2];
        var tooltip = window.L.tooltip({
          permanent: true, direction: "center", className: "area-map-label", pane: "area-labels"
        }).setLatLng([place[0], place[1]]).setContent(text).addTo(map);
        return { element: tooltip.getElement(), offset: [0, 0] };
      }
      var labels = [];
      var pending = false;
      var moving = false;
      scheduleAreaLabels = function () {
        if (pending || moving || !mapHasSpace()) return;
        pending = true;
        window.requestAnimationFrame(function () {
          // Let Leaflet's DOM transforms settle before measuring the new view.
          window.requestAnimationFrame(placeLabels);
        });
      };
      function placeLabels() {
        pending = false;
        if (moving || !mapHasSpace()) return;
        if (!labels.length) labels = places.map(createLabel);
        var margin = 4;
        var frame = mapElement.getBoundingClientRect();
        var occupied = Array.from(mapElement.querySelectorAll(
          ".leaflet-marker-icon, .leaflet-popup, .leaflet-control, .map-view-controls > :not([hidden])"
        )).map(function (element) { return element.getBoundingClientRect(); })
          .filter(function (box) { return box.width > 0 && box.height > 0; });
        // Keep interactive markers and controls clear before placing optional geography.
        var positions = labels.map(function (label) {
          var current = label.element.getBoundingClientRect();
          return [[0, 0], [0, -18], [0, 18], [-18, 0], [18, 0]].find(function (offset) {
            var dx = offset[0] - label.offset[0];
            var dy = offset[1] - label.offset[1];
            var box = { left: current.left + dx, right: current.right + dx,
              top: current.top + dy, bottom: current.bottom + dy };
            var fits = box.left >= frame.left + margin && box.right <= frame.right - margin &&
              box.top >= frame.top + margin && box.bottom <= frame.bottom - margin;
            if (!fits || occupied.some(function (other) {
              return box.left < other.right + margin && box.right > other.left - margin &&
                box.top < other.bottom + margin && box.bottom > other.top - margin;
            })) return false;
            occupied.push(box);
            return true;
          });
        });
        labels.forEach(function (label, index) {
          var offset = positions[index];
          label.offset = offset || [0, 0];
          label.element.style.marginLeft = label.offset[0] + "px";
          label.element.style.marginTop = label.offset[1] + "px";
          label.element.style.visibility = offset ? "" : "hidden";
        });
        pane.style.visibility = "";
      }
      map.on("movestart", function () {
        moving = true;
        pane.style.visibility = "hidden";
      });
      map.on("moveend", function () {
        moving = false;
        scheduleAreaLabels();
      });
      map.on("popupopen popupclose", scheduleAreaLabels);
      markerLayer.on("animationend spiderfied unspiderfied", scheduleAreaLabels);
      scheduleAreaLabels();
    }

    function clearTileLoadTimer() {
      if (tileLoadTimer !== null) {
        window.clearTimeout(tileLoadTimer);
        tileLoadTimer = null;
      }
    }

    function failTileLayer() {
      if (mapUnavailable) return;
      var focused = document.activeElement;
      var restoreMapFocus = mapElement.contains(focused) || (mapTools && mapTools.contains(focused));
      mapUnavailable = true;
      if (mapTools) mapTools.hidden = true;
      clearTileLoadTimer();
      if (areaRequest) areaRequest.abort();
      if (areaLoading) finishAreaLoading();
      // Keep the list and selection alive without retrying the failed provider.
      tileLayer.remove();
      map.closePopup();
      markerLayer.clearLayers();
      markerByJobId = {};
      [map.dragging, map.scrollWheelZoom, map.doubleClickZoom, map.touchZoom,
        map.boxZoom, map.keyboard].forEach(function (handler) {
        if (handler) handler.disable();
      });
      mapElement.classList.add("map-unavailable");
      mapElement.setAttribute("aria-label", "Project map unavailable");
      if (searchAreaButton) {
        searchAreaButton.hidden = true;
        searchAreaButton.disabled = true;
      }
      var browseButton = null;
      if (mapPlaceholder) {
        mapPlaceholder.textContent = MAP_UNAVAILABLE_NOTICE;
        mapPlaceholder.removeAttribute("aria-hidden");
        if (resultContainer) {
          browseButton = document.createElement("button");
          browseButton.type = "button";
          browseButton.className = "button secondary compact";
          browseButton.textContent = "Browse projects";
          browseButton.addEventListener("click", function () {
            setMobilePanel("filters");
            resultContainer.setAttribute("tabindex", "-1");
            resultContainer.focus();
          });
          mapPlaceholder.appendChild(browseButton);
          mapElement.setAttribute("tabindex", "-1");
        }
      }
      updateCounts();
      setMapStatus("");
      if (restoreMapFocus) (browseButton || mapElement).focus();
    }

    function createMarkerLayer(leafletMap) {
      var layer = window.L.layerGroup();
      if (window.L.markerClusterGroup) {
        try {
          layer = window.L.markerClusterGroup({
            showCoverageOnHover: false,
            spiderfyOnMaxZoom: true,
            maxClusterRadius: 46,
            animate: motionAllowed(),
            iconCreateFunction: function (cluster) {
              var count = cluster.getChildCount();
              var size = count < 10 ? "small" : (count < 100 ? "medium" : "large");
              return window.L.divIcon({
                html: '<div><span class="sr-only">' + count +
                  ' projects in this area</span><span class="cluster-count" aria-hidden="true">' + count + '</span></div>',
                className: "marker-cluster marker-cluster-" + size + " workdoe-marker-cluster",
                iconSize: window.L.point(44, 44)
              });
            }
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

    function validSearchInput() {
      if (!searchInput) return true;
      var valid = safeSearchQuery(searchInput.value) !== null;
      searchInput.setCustomValidity(valid ? "" : SEARCH_PRIVACY_NOTICE);
      return valid;
    }

    function bindFilters() {
      if (searchInput) {
        searchInput.addEventListener("input", function () {
          if (!validSearchInput() || appliedPublicFilters) return;
          applyFilters(false);
          updateUrlState();
        });
      }
      [categorySelect, serviceSelect, sortSelect].forEach(function (control) {
        if (!control) {
          return;
        }
        control.addEventListener("change", function () {
          if (!appliedPublicFilters) {
            applyFilters(false);
            updateUrlState();
          }
          if (canRefreshJobs) {
            loadJobs(activeViewport, false);
          }
        });
      });
      if (filterForm) {
        filterForm.addEventListener("submit", function (event) {
          if (!validSearchInput()) {
            event.preventDefault();
            searchInput.reportValidity();
            return;
          }
          if (!canRefreshJobs) {
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
            searchInput.setCustomValidity("");
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
          pendingMapFit = false;
          applyFilters(true);
          updateUrlState();
          if (canRefreshJobs) {
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
        if (mapUnavailable || resizingMap) return;
        constrainAreaMap();
        if (ignoreNextMoveEnd) {
          ignoreNextMoveEnd = false;
          return;
        }
        pendingMapFit = false;
        automaticMapFrame = false;
        if (searchAreaButton && canRefreshJobs) {
          mapMoveSequence += 1;
          searchAreaButton.hidden = false;
        }
      });
      if (searchAreaButton) {
        searchAreaButton.addEventListener("click", function () {
          if (searchAreaButton.getAttribute("aria-disabled") !== "true") {
            loadJobs(viewportFromBounds(map.getBounds()), false);
          }
        });
      }
      if (showMapAreaButton) {
        showMapAreaButton.addEventListener("click", function () {
          var center = map.getCenter();
          setMapStatus(
            "Current map area is approximately " +
              center.lat.toFixed(2) + " north, " +
              Math.abs(center.lng).toFixed(2) +
              (center.lng < 0 ? " west" : " east") +
              ". Workdoe does not access your device location."
          );
        });
      }
      if (resetMapViewButton) {
        resetMapViewButton.addEventListener("click", function () {
          activeViewport = null;
          pendingMapFit = false;
          automaticMapFrame = false;
          moveMap(function () {
            map.setView(defaultDmvView.center, defaultDmvView.zoom, {
              animate: motionAllowed() ? undefined : false
            });
          });
          updateUrlState();
          if (canRefreshJobs) {
            loadJobs(null, false);
          } else {
            applyFilters(false);
          }
          setMapStatus("DMV map view restored. Project locations remain approximate.");
        });
      }
    }

    function bindMapViewport() {
      window.addEventListener("resize", function () {
        if (mapUnavailable) return;
        if (mapResizeTimer) {
          window.clearTimeout(mapResizeTimer);
        }
        mapResizeTimer = window.setTimeout(function () {
          resizeVisibleMap();
          mapResizeTimer = null;
        }, 150);
      });
    }

    function loadJobs(viewport, fitMap) {
      if (retryTimer !== null || !validSearchInput() || !canRefreshJobs) {
        return;
      }
      var requestId = ++requestSequence;
      if (jobsRequest) jobsRequest.abort();
      var controller = new window.AbortController();
      jobsRequest = controller;
      var timer = window.setTimeout(function () { controller.abort(); }, SEARCH_DEADLINE_MS);
      var requestedMove = mapMoveSequence;
      var requestUrl = jobsRequestUrl(viewport);
      var requestQuery = safeSearchQuery(searchInput && searchInput.value) || "";
      var searchFailed = false;
      setLoading(true);
      window.fetch(requestUrl, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
        signal: controller.signal
      })
        .then(function (response) {
          if (response.status === 429) {
            if (requestId === requestSequence) {
              searchFailed = true;
              retryUntil = performance.now() + retryDelay(
                response.headers.get("Retry-After"), response.headers.get("Date")
              );
              scheduleRetryAvailability();
              setJobsNotice("Too many searches. Showing previous results.");
            }
            return null;
          }
          if (!response.ok) {
            throw new Error("Project search was not accepted");
          }
          return response.json();
        })
        .then(function (payload) {
          if (requestId !== requestSequence || searchFailed) {
            return;
          }
          if (!payload || !Array.isArray(payload.jobs)) throw new Error("Invalid project search response");
          if (publicEntry && (requestQuery !== safeSearchQuery(searchInput && searchInput.value))) return;
          var nextJobs = mergeJobPayload(payload);
          if (appliedPublicFilters) {
            appliedPublicFilters = new URL(requestUrl, window.location.href).searchParams;
            syncPublicFamilyLinks();
          }
          setJobsNotice("");
          allJobs = nextJobs;
          activeViewport = payload.viewport || viewport || null;
          resultsTruncated = Boolean(payload.truncated);
          if (!findJob(activeJobId)) {
            activeJobId = initialJobId(allJobs);
          }
          applyFilters(Boolean(fitMap && !activeViewport));
          updateUrlState();
          if (searchAreaButton && requestedMove === mapMoveSequence) {
            if (document.activeElement === searchAreaButton) {
              mapElement.focus({ preventScroll: !mapTools });
            }
            searchAreaButton.hidden = true;
          }
          if (sharedJobId && !activeJobId) setResultStatus("The linked project is not shown in these results.");
        })
        .catch(function () {
          if (requestId !== requestSequence) {
            return;
          }
          searchFailed = true;
          setJobsNotice(controller.signal.aborted
            ? "Search timed out. Showing previous results. Try again."
            : "Search couldn't refresh. Showing previous results. Try again.");
        })
        .finally(function () {
          window.clearTimeout(timer);
          if (requestId === requestSequence) {
            jobsRequest = null;
            setLoading(false, searchFailed);
          }
        });
    }

    function scheduleRetryAvailability() {
      var remaining = retryUntil - performance.now();
      if (remaining > 0) {
        // Wait through long server hints without overflowing the browser timer.
        retryTimer = window.setTimeout(scheduleRetryAvailability, Math.min(remaining, 2147483647));
        return;
      }
      retryTimer = null;
      setJobsNotice("Search ready to retry. Showing previous results.");
      setLoading(false, true);
    }

    function setJobsNotice(message) {
      jobsNotice = message;
      if (searchNotice) {
        searchNotice.classList.toggle("sr-only", !message);
        searchNotice.textContent = message;
      }
      if (message && mapSourceCounts) mapSourceCounts.textContent = "Previous results";
      if (message) {
        if (resultsStatus) setResultStatus(message);
        else if (!searchNotice || !searchNotice.getClientRects().length) setMapStatus(message);
      }
    }

    function jobsRequestUrl(viewport) {
      var url = new URL(jobsApi, window.location.href);
      setOptionalParam(url, "q", safeSearchQuery(searchInput && searchInput.value));
      setOptionalParam(url, "category", categorySelect && categorySelect.value);
      setOptionalParam(url, "service", serviceSelect && serviceSelect.value);
      setOptionalParam(url, "sort", sortSelect && sortSelect.value !== "newest" ? sortSelect.value : "");
      url.searchParams.delete("cursor");
      setViewportParams(url, viewport);
      return url.pathname + url.search;
    }

    function syncPublicFamilyLinks() {
      workspace.querySelectorAll(".service-family-filter-link").forEach(function (link) {
        var url = new URL(link.getAttribute("href"), window.location.href);
        if (url.origin !== window.location.origin) return;
        setOptionalParam(url, "q", appliedPublicFilters.get("q"));
        setOptionalParam(url, "sort", appliedPublicFilters.get("sort"));
        link.setAttribute("href", url.pathname + url.search + url.hash);
      });
    }

    function applyFilters(fitMap) {
      var query = !appliedPublicFilters && (safeSearchQuery(searchInput && searchInput.value) || "").toLowerCase();
      var category = !appliedPublicFilters && categorySelect && categorySelect.value;
      var service = !appliedPublicFilters && serviceSelect && serviceSelect.value;
      // The public response is authoritative, including matches on undisclosed ZIPs.
      visibleJobs = appliedPublicFilters ? allJobs : allJobs.filter(function (job) {
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
      if (sharedJobId) {
        activeJobId = findVisibleJob(sharedJobId) ? sharedJobId : "";
      } else if (!findVisibleJob(activeJobId)) {
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
      var focused = document.activeElement;
      var focusedJobId = resultContainer.contains(focused) && focused.getAttribute("data-job-id");
      var anchor = startupProjectAnchor || (projectsPanel && projectsPanel.scrollTop > 0 && projectScrollAnchor());
      startupProjectAnchor = null;
      resultContainer.innerHTML = visibleJobs.length
        ? visibleJobs.map(projectRowHtml).join("")
        : '<div class="market-list-empty"><strong>No matching projects</strong><span>Move the map or broaden the filters.</span></div>';
      if (anchor) {
        var anchorRow = findResultRow(anchor.jobId);
        if (anchorRow) projectsPanel.scrollTop += anchorRow.getBoundingClientRect().top - anchor.top;
      }
      if (focusedJobId) {
        // Restore focus before binding selection events to the replacement rows.
        var focusTarget = findResultRow(focusedJobId) || searchInput;
        if (focusTarget) focusTarget.focus();
      }
      bindExistingRows();
    }

    function findResultRow(jobId) {
      return Array.prototype.find.call(resultContainer.querySelectorAll("a[data-job-id]"), function (row) {
        return row.getAttribute("data-job-id") === jobId;
      });
    }

    function projectScrollAnchor() {
      if (!resultContainer || !projectsPanel) return null;
      var panel = projectsPanel.getBoundingClientRect();
      var bottom = Math.min(window.innerHeight, panel.bottom);
      var top = Math.max(0, panel.top);
      if (top >= bottom) return null;
      var middle = (top + bottom) / 2;
      var anchor = null;
      Array.prototype.some.call(resultContainer.querySelectorAll("a[data-job-id]"), function (row) {
        var bounds = row.getBoundingClientRect();
        if (bounds.bottom <= middle || bounds.top >= bottom) return false;
        anchor = { jobId: row.getAttribute("data-job-id"), top: bounds.top };
        return true;
      });
      return anchor;
    }

    function projectRowHtml(job) {
      var active = String(job.id) === String(activeJobId);
      var sample = job.is_demo ? '<span class="sample-badge">Sample</span>' : "";
      var fit = job.fit_label ? '<span class="lead-fit fit-' + escapeAttribute(job.fit_score || 0) + '">' + escapeHtml(job.fit_label) + "</span>" : "";
      var status = job.request_status ? '<span class="status ' + escapeAttribute(job.request_status) + '">Bid ' + escapeHtml(job.request_status) + "</span>" : "";
      var licensePreference = job.license_preference ? '<span class="job-license-chip">License preferred</span>' : "";
      var bidding = job.bid_window || {};
      var readiness = job.brief_readiness || {};
      var availability = bidding.availability_label || job.budget || "Budget not provided";
      var photoCount = Number(job.photo_count || 0);
      var photoLabel = photoCount + (photoCount === 1 ? " photo" : " photos");
      var actionCue = detailContent
        ? (job.request_status ? "Sent" : "View")
        : (job.row_cue || job.action_label || "View");
      var rowLabel = job.is_demo ? "View sample: " : detailContent
        ? (job.request_status ? "Open sent bid for " : "View details for ")
        : actionCue + " for ";
      var readinessFact = readiness.label ? "<span>" + escapeHtml(readiness.label) + "</span>" : "";
      return (
        '<div class="project-result-item" role="listitem">' +
          '<a class="project-result' + (active ? " is-map-active" : "") + '" data-job-id="' + escapeAttribute(job.id) + '" href="' + escapeAttribute(job.detail_url || job.url || "#") + '" aria-label="' + escapeAttribute(rowLabel + (job.title || "open project")) + '"' + (active ? ' aria-current="true"' : "") + ">" +
            '<span class="project-result-topline">' + fit + '<span class="job-service-chip">' + escapeHtml(job.service_name || job.category || "Project") + "</span>" + licensePreference + status + sample + "</span>" +
            '<span class="project-result-heading"><strong>' + escapeHtml(job.title || "Open project") + '</strong><span class="project-result-action">' + escapeHtml(actionCue) + "</span></span>" +
            '<span class="project-result-facts"><span>' + escapeHtml(placeLabel(job)) + "</span><span>" + escapeHtml(availability) + "</span><span>" + escapeHtml(photoLabel) + "</span>" + readinessFact + "</span>" +
          "</a>" +
        "</div>"
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
        row.addEventListener("pointermove", function (event) {
          var jobId = row.getAttribute("data-job-id");
          var moved = !lastMousePosition || event.clientX !== lastMousePosition.x || event.clientY !== lastMousePosition.y;
          if (event.pointerType === "mouse" && moved && !document.querySelector("dialog[open]") &&
              !sharedJobId && activeJobId !== jobId) {
            activateJob(jobId, false, false);
          }
        });
        row.addEventListener("focusin", function () {
          if (!sharedJobId) activateJob(row.getAttribute("data-job-id"), false, false);
        });
        row.addEventListener("keydown", function (event) {
          moveJobFocus(row, event);
        });
      });
    }

    function renderMarkers(fitMap) {
      if (mapUnavailable) {
        updateResultStatus(visibleJobs.length, 0);
        return;
      }
      var bounds = [];
      markerByJobId = {};
      markerLayer.clearLayers();
      visibleJobs.forEach(function (job) {
        if (!hasMapPin(job)) {
          return;
        }
        var lat = job.lat;
        var lng = job.lng;
        var label = markerLabel(job);
        var actionLabel = job.is_demo ? "View sample" : (job.action_label || "Open project");
        var actionUrl = job.is_demo ? "/?job_id=" + encodeURIComponent(job.id) : (job.url || job.detail_url || "#");
        var dialogTitle = job.is_demo ? "" : ' data-dialog-title="' + escapeAttribute(actionLabel) + '"';
        var marker = window.L.marker([lat, lng], { alt: label, title: label });
        marker.bindPopup(
          '<div class="map-popup">' +
            (job.is_demo ? '<span class="sample-badge">Sample</span>' : "") +
            "<strong>" + escapeHtml(job.title || "Open project") + "</strong>" +
            "<span>" + escapeHtml(placeLabel(job)) + "</span>" +
            "<span>" + escapeHtml(job.budget || "Budget not provided") + "</span>" +
            (job.license_preference ? '<span class="job-license-chip">License preferred</span>' : "") +
            '<a class="map-popup-action" href="' + escapeAttribute(actionUrl) + '"' + dialogTitle + ' aria-label="' + escapeAttribute(actionLabel + (job.is_demo ? ": " : " for ") + (job.title || "open project")) + '">' + escapeHtml(actionLabel) + "</a>" +
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
      if (scheduleAreaLabels) scheduleAreaLabels();
      if (fitMap && bounds.length) fitMapWhenVisible();
    }

    function fitCurrentMapFrame() {
      var animate = areaMap || !motionAllowed() ? false : undefined;
      if (activeViewport) {
        map.fitBounds(viewportBounds(activeViewport), { padding: [28, 28], maxZoom: 13, animate: animate });
        return;
      }
      var bounds = visibleJobs.filter(hasMapPin).map(function (job) { return [job.lat, job.lng]; });
      if (bounds.length > 1) {
        map.fitBounds(bounds, { padding: [42, 42], maxZoom: 11, animate: animate });
      } else if (bounds.length === 1) {
        map.setView(bounds[0], 12, { animate: animate });
      }
    }

    function fitMapWhenVisible() {
      // Fit against the real frame, including when Projects is the first tab.
      pendingMapFit = true;
      automaticMapFrame = areaMap;
      resizeVisibleMap();
    }

    function moveMap(action) {
      if (mapUnavailable) return;
      ignoreNextMoveEnd = true;
      action();
      window.setTimeout(function () {
        ignoreNextMoveEnd = false;
      }, 700);
    }

    function activateJob(jobId, panMap, revealDetails) {
      sharedJobId = "";
      activeJobId = String(jobId || "");
      highlightJobRows(activeJobId);
      var job = findVisibleJob(activeJobId);
      updateDetail(job);
      announceActiveJob(job);
      var marker = markerByJobId[activeJobId];
      if (marker) {
        if (panMap) {
          moveMap(function () {
            map.panTo(marker.getLatLng(), { animate: motionAllowed(), duration: 0.25 });
          });
        }
        if (window.L.markerClusterGroup && markerLayer.zoomToShowLayer) {
          markerLayer.zoomToShowLayer(marker, function () { if (!mapUnavailable) marker.openPopup(); });
        } else {
          marker.openPopup();
        }
      }
      updateUrlState();
      if (revealDetails && workspace && window.matchMedia("(max-width: 900px)").matches) {
        var focusWasInPanel = workspace.contains(document.activeElement);
        var detailsTab = document.getElementById("market-details-tab");
        setMobilePanel("details");
        if (focusWasInPanel && detailsTab) {
          detailsTab.focus();
        }
      }
    }

    function updateDetail(job) {
      if (!detailContent) {
        return;
      }
      if (!job) {
        if (sharedJobId && missingSharedProject) {
          var unavailable = missingSharedProject.content.firstElementChild.cloneNode(true);
          detailContent.replaceWith(unavailable);
          detailContent = unavailable;
          return;
        }
        detailContent.outerHTML = '<div class="market-detail-empty" data-project-detail-content><img src="' + assetRoot + '/field-doe.webp" alt="" width="160" height="160"><h2>No projects match</h2><p>Move the map or adjust the filters.</p></div>';
        detailContent = document.querySelector("[data-project-detail-content]");
        return;
      }
      var sample = job.is_demo ? '<span class="sample-badge">Demonstration project</span>' : '<span class="live-badge">Open project</span>';
      var bidding = job.bid_window || {};
      var biddingFact = bidding.usage_label ? "<div><dt>Mini bids</dt><dd>" + escapeHtml(bidding.usage_label) + "</dd></div>" : "";
      var actionLabel = job.action_label || "Review and bid";
      var action = job.is_demo ? "" : '<div class="project-detail-actions"><a class="button primary" href="' + escapeAttribute(job.url || "/start") + '" data-dialog-title="' + escapeAttribute(actionLabel) + '">' + escapeHtml(actionLabel) + "</a></div>";
      var note = job.is_demo ? "This sample does not accept bids." : "Locations stay approximate after approval. Do not include a street address.";
      var pinNote = hasMapPin(job) ? "" : ' <span class="help-text">(no map pin)</span>';
      var timingLabel = job.is_demo ? "Sample timing" : projectDateLabel(job.desired_date);
      var timingHeading = job.is_demo ? "Timing" : "Desired date";
      var licensePreference = job.license_preference
        ? '<p class="license-preference-note"><img src="' + assetRoot + '/vendor/tabler-icons/home-check.svg" alt=""><span><strong>Current license record preferred</strong><small>Preference only. Confirm scope and legal eligibility directly.</small></span></p>'
        : "";
      detailContent.outerHTML = (
        '<article class="market-project-detail" data-project-detail-content data-job-id="' + escapeAttribute(job.id) + '">' +
          '<div class="project-detail-heading">' + sample + "<span>" + escapeHtml(job.service_name || job.category || "Project") + "</span></div>" +
          "<h2>" + escapeHtml(job.title || "Open project") + "</h2>" +
          '<p class="project-detail-location">' + escapeHtml(placeLabel(job)) + pinNote + "</p>" +
          '<dl class="project-facts"><div><dt>Estimated budget</dt><dd>' + escapeHtml(job.budget || "Budget not provided") + "</dd></div>" +
          "<div><dt>" + escapeHtml(timingHeading) + "</dt><dd>" + escapeHtml(timingLabel) + "</dd></div>" + biddingFact + "</dl>" +
          licensePreference +
          '<div class="project-description"><h3>Project overview</h3><p>' + escapeHtml(job.description || "Project details are available after sign-in.") + "</p></div>" +
          '<p class="project-privacy-note">' + note + "</p>" +
          action +
        "</article>"
      );
      detailContent = document.querySelector("[data-project-detail-content]");
    }

    function projectDateLabel(value) {
      if (typeof value !== "string" || !value) {
        return "Flexible";
      }
      var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
      if (!match) {
        return value;
      }
      var monthNames = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
      ];
      var month = Number(match[2]);
      var day = Number(match[3]);
      if (month < 1 || month > 12 || day < 1 || day > 31) {
        return value;
      }
      return monthNames[month - 1] + " " + day;
    }

    function updateCounts() {
      var countLabel = visibleJobs.length + (visibleJobs.length === 1 ? " project" : " projects");
      if (resultCount) {
        resultCount.textContent = countLabel;
      }
      if (truncationNotice) truncationNotice.hidden = !resultsTruncated;
      var countedJobs = mapUnavailable ? visibleJobs : visibleJobs.filter(hasMapPin);
      if (mapResultCount) {
        mapResultCount.textContent = countedJobs.length + (countedJobs.length === 1 ? " project" : " projects")
          + (mapUnavailable ? " available" : " mapped");
      }
      if (mapListOnlyCount) {
        var listOnlyCount = visibleJobs.length - countedJobs.length;
        mapListOnlyCount.hidden = !listOnlyCount;
        mapListOnlyCount.textContent = listOnlyCount ? "; " + listOnlyCount + " list only" : "";
      }
      if (mapSourceCounts) {
        var sampleCount = countedJobs.filter(function (job) { return job.is_demo; }).length;
        mapSourceCounts.textContent = jobsNotice ? "Previous results" :
          (countedJobs.length - sampleCount) + " live / " + sampleCount + " sample";
      }
      if (laneAction) {
        var laneCount = laneAction.querySelector("[data-lane-project-count]");
        var postLink = laneAction.querySelector("[data-lane-post-project]");
        if (laneCount) {
          laneCount.textContent = countLabel;
        }
        if (postLink && window.URL) {
          var postUrl = new URL("/post-project", window.location.href);
          var postService = appliedPublicFilters ? appliedPublicFilters.get("service") : serviceSelect && serviceSelect.value;
          postUrl.searchParams.set("family", laneAction.getAttribute("data-lane-family"));
          setOptionalParam(postUrl, "service", postService);
          postLink.setAttribute("href", postUrl.pathname + postUrl.search);
          postLink.textContent = postService ? "Post this task" : "Post in this lane";
        }
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
      if (!workspace || !buttons.length) return;
      var panels = buttons.map(function (button) {
        var panel = document.getElementById(button.getAttribute("aria-controls"));
        if (!button.id || !panel || !workspace.contains(panel)) return null;
        return {
          button: button,
          element: panel,
          role: panel.getAttribute("role"),
          label: panel.getAttribute("aria-label"),
          labelledBy: panel.getAttribute("aria-labelledby"),
          tabIndex: panel.getAttribute("tabindex")
        };
      });
      if (panels.some(function (panel) { return !panel; })) return;
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
      var mobileView = window.matchMedia("(max-width: 900px)");
      var fallbackPosition = projectsPanel && projectsPanel.getBoundingClientRect();
      var focused = document.activeElement;
      var readingProjects = mobileView.matches && fallbackPosition &&
        fallbackPosition.top < 0 && fallbackPosition.bottom > 0 &&
        (!workspace.contains(focused) || projectsPanel.contains(focused));
      if (readingProjects) startupProjectAnchor = projectScrollAnchor();
      setMobilePanel(readingProjects ? "filters" : workspace.getAttribute("data-mobile-panel") || "map");

      function restoreAttribute(element, name, value) {
        if (value === null) element.removeAttribute(name);
        else element.setAttribute(name, value);
      }

      function syncPanelSemantics() {
        var focused = document.activeElement;
        panels.forEach(function (panel) {
          var element = panel.element;
          if (mobileView.matches) {
            element.setAttribute("role", "tabpanel");
            element.removeAttribute("aria-label");
            element.setAttribute("aria-labelledby", panel.button.id);
            element.tabIndex = 0;
            if (element.contains(focused)) {
              setMobilePanel(element.getAttribute("data-market-panel"));
            }
          } else {
            restoreAttribute(element, "role", panel.role);
            restoreAttribute(element, "tabindex", panel.tabIndex);
            restoreAttribute(element, "aria-label", panel.label);
            restoreAttribute(element, "aria-labelledby", panel.labelledBy);
            if (focused === panel.button || focused === element && panel.tabIndex === null) {
              workspace.focus({ preventScroll: true });
            }
          }
        });
      }

      syncPanelSemantics();
      mobileView.addEventListener("change", syncPanelSemantics);
      document.body.classList.add("market-tabs-ready");
      if (readingProjects) {
        // Move the fallback's page scroll into the enhanced list's scroll container.
        if (document.scrollingElement) document.scrollingElement.scrollTop = 0;
        document.body.scrollTop = 0;
        projectsPanel.scrollTop = projectsPanel.getBoundingClientRect().top - fallbackPosition.top;
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
      if (!mapUnavailable && (panel === "map" || !window.matchMedia("(max-width: 900px)").matches)) {
        window.setTimeout(resizeVisibleMap, 50);
      }
    }

    function updateUrlState() {
      if (!window.history || !window.URL) {
        return;
      }
      var state = window.history.state;
      // Only the dialog controller can write to a dialog history entry.
      if (state && state.workdoeDialog) {
        pendingUrlState = true;
        return;
      }
      pendingUrlState = false;
      var url = new URL(window.location.href);
      if (appliedPublicFilters) {
        ["q", "category", "service", "sort"].forEach(function (key) {
          setOptionalParam(url, key, appliedPublicFilters.get(key));
        });
      } else {
        setOptionalParam(url, "q", safeSearchQuery(searchInput && searchInput.value));
        setOptionalParam(url, "category", categorySelect && categorySelect.value);
        setOptionalParam(url, "service", serviceSelect && serviceSelect.value);
        setOptionalParam(url, "sort", sortSelect && sortSelect.value !== "newest" ? sortSelect.value : "");
      }
      setOptionalParam(url, "job_id", activeJobId || sharedJobId);
      setViewportParams(url, activeViewport);
      url.searchParams.delete("cursor");
      window.history.replaceState(Object.assign({}, state, { workdoeMap: true }), "", url.pathname + url.search + url.hash);
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

    function setLoading(loading, failed) {
      jobsLoading = loading;
      syncMapBusy();
      var coolingDown = retryTimer !== null;
      if (filterSubmit) {
        if (coolingDown) filterSubmit.setAttribute("aria-disabled", "true");
        else filterSubmit.removeAttribute("aria-disabled");
        filterSubmit.textContent = coolingDown ? "Wait" : !loading && failed ? "Retry" : filterSubmitLabel;
        // Reflow during a request can leave the still-focused keyboard action offscreen.
        if (failed && filterSubmit === document.activeElement && filterSubmit.matches(":focus-visible")) {
          filterSubmit.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
        }
      }
      if (searchAreaButton) {
        if (loading || coolingDown) {
          searchAreaButton.setAttribute("aria-disabled", "true");
        } else {
          searchAreaButton.removeAttribute("aria-disabled");
        }
        // Keep the dock's action width and height stable when search state changes.
        if (!mapTools) {
          searchAreaButton.textContent = loading ? "Loading projects" : coolingDown ? "Search paused" :
            (failed ? "Retry area search" : "Search this area");
        }
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
      return (job.is_demo ? "Sample: " : "") + (job.title || "Open project") + " in " + placeLabel(job);
    }

    function hasMapPin(job) {
      return Number.isFinite(job.lat) && Number.isFinite(job.lng);
    }

    function placeLabel(job) {
      return [job.city, job.state].filter(Boolean).join(", ");
    }

    function announceActiveJob(job) {
      if (job) {
        var nextStep = detailContent
          ? "Project details are open."
          : (mapUnavailable ? "" : "Use the popup action to continue.");
        setMapStatus((job.title || "Project") + " is selected." + (nextStep ? " " + nextStep : ""));
      }
    }

    function updateResultStatus(jobCount, pinCount) {
      if (jobsNotice) return;
      if (!jobCount) {
        setResultStatus("No projects match the current filters.");
        return;
      }
      var summary = jobCount + (jobCount === 1 ? " project shown" : " projects shown");
      if (!mapUnavailable) {
        summary += " with " + pinCount + (pinCount === 1 ? " approximate map location" : " approximate map locations");
      }
      setResultStatus(summary + "." + (resultsTruncated ? " More projects are available beyond this page." : ""));
    }

    function setResultStatus(message) {
      if (!resultsStatus) setMapStatus(message);
      else if (resultsStatus.textContent !== message) resultsStatus.textContent = message;
    }

    function setMapStatus(message) {
      if (statusElement) {
        statusElement.textContent = mapUnavailable
          ? MAP_UNAVAILABLE_NOTICE + (message ? " " + message : "") : message;
      }
    }

    function readSeedJobs() {
      var seedElement = document.getElementById("map-jobs-data");
      if (!seedElement || !seedElement.textContent) {
        return null;
      }
      try {
        var jobs = JSON.parse(seedElement.textContent);
        return Array.isArray(jobs) ? jobs : null;
      } catch (error) {
        return null;
      }
    }

    function readServerSnapshot() {
      try {
        var snapshot = JSON.parse(mapElement.getAttribute("data-map-snapshot"));
        return snapshot && typeof snapshot.truncated === "boolean" ? snapshot : null;
      } catch (error) {
        return null;
      }
    }
  });

  function motionAllowed() {
    return typeof window.matchMedia !== "function" ||
      !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

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
