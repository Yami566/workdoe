(function () {
  "use strict";

  var composer = document.querySelector("[data-project-composer]");
  if (!composer) {
    return;
  }

  var steps = Array.prototype.slice.call(composer.querySelectorAll("[data-project-step]"));
  var progress = composer.querySelector("[data-project-progress]");
  var stepLabel = composer.querySelector("[data-project-step-label]");
  var stepTitle = composer.querySelector("[data-project-step-title]");
  var groupInputs = Array.prototype.slice.call(composer.querySelectorAll('input[name="service_group_slug"]'));
  var serviceSelect = composer.querySelector('select[name="service_slug"]');
  var serviceChoices = Array.prototype.slice.call(composer.querySelectorAll('input[name="service_choice"]'));
  var serviceOptionGroups = Array.prototype.slice.call(composer.querySelectorAll("[data-service-option-group]"));
  var selectedFamily = composer.querySelector("[data-selected-service-family]");
  var categoryInput = composer.querySelector('input[name="category"]');
  var titleInput = composer.querySelector('input[name="title"]');
  var descriptionInput = composer.querySelector('textarea[name="description"]');
  var choiceAdvanceInputs = Array.prototype.slice.call(composer.querySelectorAll("[data-project-choice-advance]"));
  var scopePanels = Array.prototype.slice.call(composer.querySelectorAll("[data-service-scope-set]"));
  var policyPanel = composer.querySelector("[data-service-policy-advisory]");
  var policyCheckbox = composer.querySelector("[data-service-policy-checkbox]");
  var requestedInitialStep = Number(composer.dataset.projectInitialStep || 1);
  var currentStep = 1;
  var pointerChoiceInput = null;

  function selectedGroup() {
    var selected = composer.querySelector('input[name="service_group_slug"]:checked');
    return selected ? selected.value : "";
  }

  function selectedGroupInput() {
    return composer.querySelector('input[name="service_group_slug"]:checked');
  }

  function selectedServiceOption() {
    return serviceSelect && serviceSelect.selectedIndex >= 0
      ? serviceSelect.options[serviceSelect.selectedIndex]
      : null;
  }

  function updateCategory() {
    var option = selectedServiceOption();
    if (categoryInput && option && option.dataset.category) {
      categoryInput.value = option.dataset.category;
    }
  }

  function syncServiceGuidance() {
    var option = selectedServiceOption();
    var label = option && option.value ? option.textContent.trim() : "";
    if (titleInput) {
      titleInput.placeholder = label ? label + " project" : "Name the project";
    }
    if (descriptionInput) {
      descriptionInput.placeholder = label
        ? "Describe the " + label.toLowerCase() + " scope, size, current condition, access, and desired outcome."
        : "Describe the scope, size, current condition, access, and desired outcome.";
    }
  }

  function syncServicePolicy() {
    if (!policyPanel || !policyCheckbox) {
      return;
    }
    var option = selectedServiceOption();
    var service = option && option.value ? option.value : "";
    var required = Boolean(service && option.dataset.policyRequired === "true");
    var disabled = Boolean(service && option.dataset.policyDisabled === "true");
    if (policyPanel.dataset.policyService && policyPanel.dataset.policyService !== service) {
      policyCheckbox.checked = false;
    }
    policyPanel.dataset.policyService = service;
    policyPanel.hidden = !required && !disabled;
    policyCheckbox.disabled = !required;
    policyCheckbox.required = required;
    policyCheckbox.value = option ? option.dataset.policyVersion || "" : "";
    var tier = policyPanel.querySelector("[data-service-policy-tier]");
    var copy = policyPanel.querySelector("[data-service-policy-copy]");
    if (tier) {
      tier.textContent = option && option.dataset.policyTier === "regulated"
        ? "Local rules check"
        : "Safety check";
    }
    if (copy) {
      copy.textContent = option ? option.dataset.policyAdvisory || "" : "";
    }
  }

  function updateSelectedFamily() {
    if (!selectedFamily) {
      return;
    }
    var group = selectedGroupInput();
    selectedFamily.hidden = !group;
    if (!group) {
      return;
    }
    var icon = selectedFamily.querySelector("[data-selected-service-family-icon]");
    var name = selectedFamily.querySelector("[data-selected-service-family-name]");
    var description = selectedFamily.querySelector("[data-selected-service-family-description]");
    if (icon) {
      icon.src = group.dataset.groupIcon || "";
    }
    if (name) {
      name.textContent = group.dataset.groupName || "";
    }
    if (description) {
      description.textContent = group.dataset.groupDescription || "";
    }
  }

  function syncServiceChoices() {
    var selectedValue = serviceSelect ? serviceSelect.value : "";
    serviceChoices.forEach(function (choice) {
      choice.checked = choice.value === selectedValue;
    });
  }

  function updateScopeReadiness(panel) {
    var fields = Array.prototype.slice.call(panel.querySelectorAll("[data-scope-select]"));
    var complete = fields.filter(function (field) { return Boolean(field.value); }).length;
    var target = panel.querySelector("[data-scope-readiness]");
    if (target) {
      target.textContent = complete + " of " + fields.length + " details ready";
    }
    return {complete: complete, total: fields.length};
  }

  function syncScopePanels() {
    var selectedValue = serviceSelect ? serviceSelect.value : "";
    scopePanels.forEach(function (panel) {
      var active = panel.dataset.serviceScopeSet === selectedValue;
      panel.hidden = !active;
      Array.prototype.forEach.call(panel.querySelectorAll("[data-scope-select]"), function (field) {
        field.disabled = !active;
      });
      updateScopeReadiness(panel);
    });
  }

  function filterServices() {
    if (!serviceSelect) {
      return;
    }
    var group = selectedGroup();
    Array.prototype.forEach.call(serviceSelect.querySelectorAll("optgroup"), function (optgroup) {
      var matches = !group || optgroup.dataset.serviceGroup === group;
      optgroup.disabled = !matches;
      optgroup.hidden = !matches;
    });
    var option = selectedServiceOption();
    if (group && option && option.value && option.dataset.group !== group) {
      serviceSelect.value = "";
    }
    serviceOptionGroups.forEach(function (optionGroup) {
      optionGroup.hidden = !!group && optionGroup.dataset.serviceOptionGroup !== group;
    });
    updateSelectedFamily();
    syncServiceChoices();
    syncScopePanels();
    updateCategory();
    syncServicePolicy();
    syncServiceGuidance();
  }

  function moneyValue(value) {
    if (!value) {
      return "";
    }
    return "$" + Number(value).toLocaleString("en-US", {maximumFractionDigits: 0});
  }

  function fieldValue(name) {
    var field = composer.elements[name];
    return field ? String(field.value || "").trim() : "";
  }

  function writeReview(selector, value) {
    var target = composer.querySelector(selector);
    if (target) {
      target.textContent = value;
    }
  }

  function updateReview() {
    var option = selectedServiceOption();
    var service = option && option.value ? option.textContent.trim() : "Choose a service";
    var title = fieldValue("title") || "Add a title";
    var settingInput = composer.querySelector('input[name="project_setting"]:checked');
    var setting = settingInput ? settingInput.dataset.settingLabel : "Not specified";
    var city = fieldValue("city");
    var state = fieldValue("state");
    var zip = fieldValue("zip_code");
    var location = [city, state].filter(Boolean).join(", ");
    if (zip) {
      location += (location ? " " : "") + zip;
    }
    var desiredDate = fieldValue("desired_date");
    var minimum = moneyValue(fieldValue("budget_min"));
    var maximum = moneyValue(fieldValue("budget_max"));
    var budget = minimum && maximum ? minimum + " - " + maximum : minimum ? minimum + "+" : maximum ? "Up to " + maximum : "Open";
    var activeScope = scopePanels.filter(function (panel) { return !panel.hidden; })[0];
    var scope = activeScope ? updateScopeReadiness(activeScope) : {complete: 0, total: 0};
    var photoInput = composer.elements.photos;
    var hasPhoto = Boolean(photoInput && photoInput.files && photoInput.files.length);
    var briefScore = [
      Boolean(option && option.value),
      fieldValue("description").length >= 20,
      scope.complete >= 2,
      Boolean(settingInput),
      Boolean(desiredDate),
      Boolean(fieldValue("budget_min") || fieldValue("budget_max") || hasPhoto)
    ].filter(Boolean).length;

    writeReview("[data-review-service]", service);
    writeReview("[data-review-title]", title);
    writeReview("[data-review-setting]", setting);
    writeReview("[data-review-scope]", scope.total ? scope.complete + " of " + scope.total + " details ready" : "Description only");
    writeReview("[data-review-brief]", "Brief " + briefScore + " of 6");
    writeReview("[data-review-location]", location || "Add a city and ZIP");
    writeReview("[data-review-timing]", desiredDate || "Flexible");
    writeReview("[data-review-budget]", budget);
  }

  function resetStepScroll() {
    var dialogContent = composer.closest("[data-site-dialog-content]");
    if (dialogContent) {
      dialogContent.scrollTop = 0;
      return;
    }
    var composerHead = composer.querySelector(".project-composer-head");
    if (composerHead && typeof composerHead.scrollIntoView === "function") {
      composerHead.scrollIntoView({block: "start"});
    }
  }

  function showStep(stepNumber, focusStep) {
    currentStep = Math.max(1, Math.min(steps.length, stepNumber));
    steps.forEach(function (step) {
      step.hidden = Number(step.dataset.projectStep) !== currentStep;
    });
    var active = steps[currentStep - 1];
    if (progress) {
      progress.value = currentStep;
      progress.textContent = currentStep + " of " + steps.length;
    }
    if (stepLabel) {
      stepLabel.textContent = "Step " + currentStep + " of " + steps.length;
    }
    if (stepTitle && active) {
      stepTitle.textContent = active.dataset.stepTitle || "Post a project";
    }
    if (currentStep === steps.length) {
      updateReview();
    }
    if (focusStep) {
      resetStepScroll();
      if (stepTitle) {
        stepTitle.setAttribute("tabindex", "-1");
        stepTitle.focus({preventScroll: true});
      }
    }
  }

  function validateStep(step) {
    var fields = Array.prototype.slice.call(step.querySelectorAll("input, select, textarea"));
    for (var index = 0; index < fields.length; index += 1) {
      if (!fields[index].disabled && !fields[index].checkValidity()) {
        fields[index].reportValidity();
        return false;
      }
    }
    return true;
  }

  composer.addEventListener("click", function (event) {
    var next = event.target.closest("[data-project-next]");
    var back = event.target.closest("[data-project-back]");
    if (next) {
      var active = steps[currentStep - 1];
      if (active && validateStep(active)) {
        showStep(currentStep + 1, true);
      }
    } else if (back) {
      showStep(currentStep - 1, true);
    }
  });

  groupInputs.forEach(function (input) {
    input.addEventListener("change", filterServices);
  });
  if (serviceSelect) {
    serviceSelect.addEventListener("change", function () {
      syncServiceChoices();
      syncScopePanels();
      updateCategory();
      syncServicePolicy();
      syncServiceGuidance();
      updateReview();
    });
  }
  serviceChoices.forEach(function (choice) {
    choice.addEventListener("change", function () {
      if (!choice.checked || !serviceSelect) {
        return;
      }
      serviceSelect.value = choice.value;
      syncScopePanels();
      updateCategory();
      syncServicePolicy();
      syncServiceGuidance();
      updateReview();
    });
  });
  composer.addEventListener("pointerdown", function (event) {
    var option = event.target.closest("label");
    pointerChoiceInput = option
      ? option.querySelector("[data-project-choice-advance]")
      : null;
  });
  composer.addEventListener("pointerup", function () {
    var capturedInput = pointerChoiceInput;
    window.setTimeout(function () {
      if (pointerChoiceInput === capturedInput) {
        pointerChoiceInput = null;
      }
    }, 0);
  });
  composer.addEventListener("pointercancel", function () {
    pointerChoiceInput = null;
  });
  choiceAdvanceInputs.forEach(function (input) {
    input.addEventListener("click", function () {
      if (pointerChoiceInput !== input || !input.checked) {
        return;
      }
      pointerChoiceInput = null;
      var step = input.closest("[data-project-step]");
      var stepNumber = step ? Number(step.dataset.projectStep) : 0;
      window.setTimeout(function () {
        if (stepNumber === currentStep && stepNumber < 3 && validateStep(step)) {
          showStep(stepNumber + 1, true);
        }
      }, 0);
    });
  });
  composer.addEventListener("input", updateReview);
  composer.addEventListener("change", function (event) {
    if (event.target.matches("[data-scope-select]")) {
      updateScopeReadiness(event.target.closest("[data-service-scope-set]"));
      updateReview();
    }
  });
  composer.addEventListener("invalid", function (event) {
    var step = event.target.closest("[data-project-step]");
    if (step) {
      showStep(Number(step.dataset.projectStep), false);
    }
  }, true);

  composer.classList.add("is-enhanced");
  filterServices();
  var invalidField = composer.querySelector('[aria-invalid="true"]');
  var invalidStep = invalidField && invalidField.closest("[data-project-step]");
  showStep(invalidStep ? Number(invalidStep.dataset.projectStep) : requestedInitialStep, false);
  updateReview();
})();
