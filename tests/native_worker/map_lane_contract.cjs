const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../workdoe/static/map.js'), 'utf8');
const start = source.indexOf('    function updateCounts() {');
const end = source.indexOf('    function highlightJobRows(', start);
const pinStart = source.indexOf('    function hasMapPin(job) {');
const pinEnd = source.indexOf('    function placeLabel(', pinStart);
assert.ok(start >= 0 && end > start, 'Map count/controller boundaries must remain explicit');
assert.ok(pinStart >= 0 && pinEnd > pinStart, 'Load the actual coordinate predicate');

// Execute the real count/post-link function without requiring a map or tile network.
const count = {textContent: ''};
const link = {textContent: '', href: '', setAttribute(name, value) { this[name] = value; }};
const context = {
  visibleJobs: [{is_demo: true, lat: 38.9, lng: -77}],
  resultCount: {textContent: ''},
  truncationNotice: {hidden: true},
  resultsTruncated: true,
  mapResultCount: {textContent: ''},
  mapListOnlyCount: {textContent: '', hidden: true},
  mapSourceCounts: {textContent: ''},
  mapUnavailable: false,
  jobsNotice: '',
  appliedPublicFilters: null,
  serviceSelect: {value: 'pressure-washing'},
  laneAction: {
    getAttribute() { return 'outdoor-yard'; },
    querySelector(selector) { return selector === '[data-lane-project-count]' ? count : link; },
  },
  window: {URL, location: {href: 'https://workdoe.com/?family=outdoor-yard&q=old'}},
  URL,
  setOptionalParam(url, key, value) {
    if (value) url.searchParams.set(key, String(value));
    else url.searchParams.delete(key);
  },
};
vm.createContext(context);
vm.runInContext(source.slice(pinStart, pinEnd) + source.slice(start, end), context);
context.updateCounts();
assert.equal(link.href, '/post-project?family=outdoor-yard&service=pressure-washing');
assert.equal(link.textContent, 'Post this task');
assert.equal(count.textContent, '1 project');
assert.equal(context.mapResultCount.textContent, '1 project mapped');
assert.equal(context.mapSourceCounts.textContent, '0 live / 1 sample');
assert.equal(context.truncationNotice.hidden, false);

context.serviceSelect.value = '';
context.resultsTruncated = false;
context.visibleJobs = [{is_demo: false, lat: null, lng: null}, {is_demo: true, lat: 38.9, lng: -77}];
context.updateCounts();
assert.equal(link.href, '/post-project?family=outdoor-yard');
assert.equal(link.textContent, 'Post in this lane');
assert.equal(count.textContent, '2 projects');
assert.equal(context.mapResultCount.textContent, '1 project mapped');
assert.equal(context.mapSourceCounts.textContent, '0 live / 1 sample');
assert.equal(context.mapListOnlyCount.hidden, false);
assert.equal(context.mapListOnlyCount.textContent, '; 1 list only');
assert.equal(context.truncationNotice.hidden, true);

context.mapUnavailable = true;
context.updateCounts();
assert.equal(context.mapResultCount.textContent, '2 projects available');
assert.equal(context.mapSourceCounts.textContent, '1 live / 1 sample');
assert.equal(context.mapListOnlyCount.hidden, true);
assert.equal(link.href, '/post-project?family=outdoor-yard');

context.serviceSelect.value = 'pressure-washing';
context.visibleJobs = [];
context.jobsNotice = 'Too many searches. Showing previous results.';
context.updateCounts();
assert.equal(count.textContent, '0 projects');
assert.equal(link.href, '/post-project?family=outdoor-yard&service=pressure-washing');
assert.equal(context.mapSourceCounts.textContent, 'Previous results');

context.appliedPublicFilters = new URLSearchParams('service=lawn-mowing');
context.updateCounts();
assert.equal(link.href, '/post-project?family=outdoor-yard&service=lawn-mowing', 'Keep the last confirmed task link');

context.jobsNotice = '';
context.laneAction = null;
context.updateCounts();
assert.equal(context.resultCount.textContent, '0 projects');
assert.equal(context.mapSourceCounts.textContent, '0 live / 0 sample');

const filterStart = source.indexOf('    function bindFilters() {');
const filterEnd = source.indexOf('    function bindPopupOverlayState(', filterStart);
assert.ok(filterStart >= 0 && filterEnd > filterStart);
const changes = [];
const refreshes = [];
const filterContext = {
  searchInput: null, categorySelect: null, sortSelect: null, filterForm: null, clearButton: null,
  appliedPublicFilters: null,
  serviceSelect: {addEventListener(event, handler) { if (event === 'change') changes.push(handler); }},
  canRefreshJobs: true,
  activeViewport: {north: 39, south: 38, east: -76, west: -78},
  applyFilters() {}, updateUrlState() {},
  loadJobs(viewport, fitMap) { refreshes.push({viewport, fitMap}); },
};
vm.createContext(filterContext);
vm.runInContext(source.slice(filterStart, filterEnd), filterContext);
filterContext.bindFilters();
assert.equal(changes.length, 1);
changes[0]();
assert.equal(refreshes.length, 1, 'Changing or clearing a remote task must refresh beyond the narrow seed');
assert.equal(refreshes[0].viewport, filterContext.activeViewport);
assert.equal(refreshes[0].fitMap, false);
filterContext.canRefreshJobs = false;
changes[0]();
assert.equal(refreshes.length, 1, 'Native Filter forms without an API retain their fallback');
filterContext.canRefreshJobs = true;
filterContext.appliedPublicFilters = new URLSearchParams();
filterContext.applyFilters = () => assert.fail('Do not redraw the public list before the response');
filterContext.updateUrlState = () => assert.fail('Do not publish pending task changes');
changes[0]();
assert.equal(refreshes.length, 2, 'Public task changes still submit a remote search');
console.log('PASS: actual map count and task-post-link synchronization');
