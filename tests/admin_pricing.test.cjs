// Run: node --test tests/admin_pricing.test.cjs
// Isolated dialog logic test; DOM/API doubles, not a browser or live server.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8').replace(/\r\n/g, '\n');

function functionSource(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name);
  const end = source.indexOf('\n}\n', start) + 2;
  return (source.slice(start - 6, start) === 'async ' ? 'async ' : '') + source.slice(start, end);
}
function element(value = '') {
  const classes = new Set();
  const label = { classList: { toggle(name, yes) { yes ? classes.add(name) : classes.delete(name); } } };
  return { value, dataset: {}, disabled: false, textContent: '', innerHTML: '',
    classList: { add() {}, remove() {} }, setAttribute() {},
    closest: () => label, hidden: () => classes.has('hidden') };
}
function setup() {
  const c = { console, Set, Number, String, Array, JSON };
  for (const name of ['adminPricingTargetsModal', 'adminPricingTargetsMovieId', 'adminPricingTargetsCopy',
    'adminPricingTargetsForm', 'adminPricingTheatreStars', 'adminPricingTargetStars', 'adminPricingOnlineRows', 'adminHelper']) c[name] = element();
  c.heading = element();
  c.document = { getElementById: () => c.heading };
  c.rows = [];
  c.rows = [];
  c.adminPricingOnlineRows.querySelectorAll = () => c.rows.slice(0, (c.adminPricingOnlineRows.innerHTML.match(/data-pricing-row=/g) || []).length);
  c.ADMIN_ONLINE_QUALITY_OPTIONS = ['720p', '1080p', '2k', '4k'].map(code => ({ code, label: code }));
  c.escapeHtml = value => String(value);
  c.adminPricingTargetsForm.addEventListener = (_, handler) => { c.submit = handler; };
  c.apiRequest = async (url, request) => {
    c.sent = { url, body: JSON.parse(request.body) };
    return { item: {}, message: 'Saved' };
  };
  for (const name of ['updateMovieCollections', 'renderAdminMovieList', 'renderAdminArchiveMovieList', 'renderMovieGrid', 'syncDetailPanel']) c[name] = () => {};
  c.normalizeMovie = item => item;
  vm.createContext(c);
  for (const name of ['renderAdminPricingRows', 'readAdminPricingRows', 'appendAdminPricingRow',
    'openAdminPricingTargetsModal', 'closeAdminPricingTargetsModal', 'updateAdminMoviePricingConfigRemote']) vm.runInContext(functionSource(name), c);
  const start = source.indexOf('if (adminPricingTargetsForm) {');
  const end = source.indexOf('\nif (adminPosterFiles)', start);
  vm.runInContext(source.slice(start, end), c);
  c.setRows = entries => {
    c.rows = entries.map(([quality, price]) => ({
      querySelector: selector => ({ value: selector === '[data-pricing-quality]' ? quality : String(price) })
    }));
    c.adminPricingOnlineRows.innerHTML = entries.map((_, index) => `<div data-pricing-row="${index}"></div>`).join('');
  };
  return c;
}

test('direct Library dialog renders Discs, validates, and submits only Disc prices', async () => {
  const c = setup();
  const movie = { id: 'library', title: 'Library', catalogOrigin: 'library',
    libraryPricingOptions: [{ qualityCode: '4k', discsRequired: 7312 }] };
  c.openAdminPricingTargetsModal(movie);
  assert.equal(c.heading.textContent, 'Discs Required - Online');
  assert.match(c.adminPricingOnlineRows.innerHTML, /Discs required/);
  assert.match(c.adminPricingOnlineRows.innerHTML, /value="7312"/);
  assert.equal(c.adminPricingTheatreStars.disabled, true);
  assert.equal(c.adminPricingTargetStars.hidden(), true);
  c.setRows([['4k', 7312]]);
  await c.submit({ preventDefault() {} });
  assert.deepEqual(c.sent.body, { library_pricing_options: [
    { quality_code: '4k', quality_label: '4k', discs_required: 7312, sort_order: 0 }
  ] });
  c.rows = [];
  c.openAdminPricingTargetsModal(movie);
  assert.match(c.adminPricingOnlineRows.innerHTML, /value="7312"/);
  c.setRows([['4k', 0]]);
  c.sent = null;
  await c.submit({ preventDefault() {} });
  assert.equal(c.sent, null);
  assert.match(c.adminHelper.textContent, /Discs required/);
});

test('switching to Upcoming restores Stars and accepts 5/10/15/20', async () => {
  const c = setup();
  c.openAdminPricingTargetsModal({ id: 'library', title: 'Library', catalogOrigin: 'library' });
  c.openAdminPricingTargetsModal({ id: 'upcoming', title: 'Upcoming', catalogOrigin: 'upcoming' });
  assert.equal(c.heading.textContent, 'Stars Required - Online');
  assert.equal(c.adminPricingTheatreStars.disabled, false);
  assert.equal(c.adminPricingTargetStars.hidden(), false);
  assert.match(c.adminPricingOnlineRows.innerHTML, /max="20"/);
  c.setRows([['720p', 5], ['1080p', 10], ['2k', 15], ['4k', 20]]);
  await c.submit({ preventDefault() {} });
  assert.deepEqual(c.sent.body.online_pricing_options.map(p => p.stars_required), [5, 10, 15, 20]);
  assert.equal('library_pricing_options' in c.sent.body, false);
  c.openAdminPricingTargetsModal({ id: 'upcoming', title: 'Upcoming', catalogOrigin: 'upcoming' });
  c.setRows([['4k', 21]]);
  c.sent = null;
  await c.submit({ preventDefault() {} });
  assert.equal(c.sent, null);
  assert.match(c.adminHelper.textContent, /between 1 and 20/);
});
