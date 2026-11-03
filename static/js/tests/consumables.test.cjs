const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'consumables.js'), 'utf8');
const template = fs.readFileSync(path.join(__dirname, '..', '..', '..',
  'inventory', 'templates', 'inventory', 'consumables.html'), 'utf8');
const rowMarkup = template.match(/<tr\b[^>]*data-id="\{\{\s*consumable\.id\s*\}\}"[^>]*>/)[0];

function rowDataset(stock) {
  const values = { id: 'stock', name: 'Test tips', items_per_pack: '10',
    items_left_in_pack: '3', pack_count: '2', ...stock };
  const dataset = {};
  for (const [, attribute, field] of rowMarkup.matchAll(/data-([^\s=]+)="\{\{\s*consumable\.(\w+)[^}]*\}\}"/g)) {
    if (!(field in values)) continue;
    // Match the browser's dataset conversion: hyphenated names camel-case,
    // while underscores remain underscores. Read names from the real template
    // so markup mismatches cannot hide behind a hand-written dataset fixture.
    const key = attribute.toLowerCase().replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
    dataset[key] = String(values[field]);
  }
  return dataset;
}

// Only the DOM and network boundary are faked; every stock check and submit
// handler below runs from the actual browser script.
class Element {
  constructor(properties = {}) {
    Object.assign(this, {
      dataset: {}, style: {}, value: '', textContent: '', disabled: false,
      hidden: false, max: '', min: '', validationMessage: '',
      attributes: {}, children: [], listeners: new Map(),
    }, properties);
    const classes = new Set();
    this.classList = {
      add: (...values) => values.forEach(value => classes.add(value)),
      remove: (...values) => values.forEach(value => classes.delete(value)),
      contains: value => classes.has(value),
      toggle: (value, enabled = !classes.has(value)) => {
        enabled ? classes.add(value) : classes.delete(value);
        return enabled;
      },
    };
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  async dispatch(type) {
    for (const listener of this.listeners.get(type) || []) {
      await listener({ target: this, preventDefault() {} });
    }
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name === 'data-form-error') this.dataset.formError = String(value);
    if (name === 'max' || name === 'min') this[name] = String(value);
  }

  getAttribute(name) { return this.attributes[name] ?? null; }
  removeAttribute(name) { delete this.attributes[name]; this[name] = ''; }
  setCustomValidity(message) { this.validationMessage = message; }
  checkValidity() {
    return !this.validationMessage &&
      (!this.required || this.value !== '') &&
      (this.max === '' || Number(this.value) <= Number(this.max)) &&
      (this.min === '' || Number(this.value) >= Number(this.min));
  }
  reportValidity() { return this.checkValidity(); }
  focus() {}
  appendChild(child) { child.parentNode = this; this.children.push(child); return child; }
  append(child) { this.appendChild(child); }
  prepend(child) { child.parentNode = this; this.children.unshift(child); }
  remove() { this.parentNode.children = this.parentNode.children.filter(child => child !== this); }
}

function makeFixture(stock = {}) {
  const elements = new Map();
  const add = (id, properties) => {
    const element = new Element({ id, ...properties });
    elements.set(id, element);
    return element;
  };
  const amount = add('retrieveFilterInput', { name: 'amount', value: '1', min: '1', required: true });
  const mode = add('retrieve_by', { name: 'retrieve_by', value: 'Pack size' });
  const submit = new Element({ type: 'submit', textContent: 'Confirm', innerHTML: 'Confirm' });
  const csrf = new Element({ name: 'csrfmiddlewaretoken', value: 'test-csrf' });
  const error = new Element({ hidden: true, dataset: { formError: '' } });
  const form = add('retrieve-form');
  form.elements = { amount, retrieve_by: mode, csrfmiddlewaretoken: csrf };
  form.elements.namedItem = name => form.elements[name] || null;
  form.appendChild(error);
  form.querySelector = selector => {
    if (selector.includes('data-form-error')) return error;
    if (selector.includes('submit')) return submit;
    if (selector.includes('amount') || selector.includes('retrieveFilterInput')) return amount;
    if (selector.includes('retrieve_by')) return mode;
    if (selector.includes('csrfmiddlewaretoken')) return csrf;
    return null;
  };
  form.querySelectorAll = selector => selector.includes('submit') ? [submit] : [];
  form.reset = () => { amount.value = ''; mode.value = 'Pack size'; };
  add('retrieveItemName');
  add('retrieveAvailability');
  const row = new Element({ dataset: rowDataset(stock) });
  const table = add('consumablesTable');
  table.querySelector = selector => selector.includes('stock') ? row : null;
  table.querySelectorAll = () => [row];

  const requests = [];
  const notices = [];
  let fetchImpl = () => Promise.resolve(response(400, { error: 'Only 0 items are available' }));
  const document = {
    body: new Element(),
    cookie: 'csrftoken=test-csrf',
    getElementById: id => elements.get(id) || null,
    querySelector: selector => selector.includes('csrf-token') ? { content: 'test-csrf' } : null,
    querySelectorAll: () => [],
    createElement: () => new Element(),
    addEventListener() {}, // Register DOMContentLoaded without running unrelated page setup.
  };
  const context = vm.createContext({
    document,
    window: { showInventoryPopup() {}, hideInventoryPopup() {} },
    console: { log() {}, error() {} },
    setTimeout() {}, clearTimeout() {},
    location: { reload() {} },
    FormData: class {
      constructor() {}
      *entries() { yield ['amount', amount.value]; yield ['retrieve_by', mode.value]; }
    },
    Toastify(options) { return { showToast() { notices.push(options.text); } }; },
    fetch(...args) { requests.push(args); return fetchImpl(...args); },
    onSuccess() {},
  });
  vm.runInContext(source, context, { filename: 'consumables.js' });
  const run = script => vm.runInContext(script, context);
  run('setupFormHandlers(); showRetrievePopup("stock");');
  return { amount, mode, submit, error, form, row, requests, notices, elements, run,
    setFetch: implementation => { fetchImpl = implementation; } };
}

function response(status, payload) {
  return { status, ok: status >= 200 && status < 300,
    text: async () => JSON.stringify(payload), json: async () => payload };
}

const flush = () => new Promise(resolve => setImmediate(resolve));

test('empty stock is explained and cannot submit a retrieval', async () => {
  const fixture = makeFixture({ items_per_pack: '0', items_left_in_pack: '0', pack_count: '0' });
  fixture.amount.value = '1';
  assert.equal(fixture.elements.get('retrieveItemName').textContent, 'Test tips');
  assert.match(fixture.elements.get('retrieveAvailability').textContent, /no stock|out of stock|0/i);
  assert.equal(fixture.submit.disabled, true);
  await fixture.form.dispatch('submit');
  await flush();
  assert.equal(fixture.requests.length, 0);
});

test('retrieval availability counts the open pack and switches to pack units', () => {
  const fixture = makeFixture();
  assert.equal(Number(fixture.amount.max), 13);
  assert.equal(fixture.submit.disabled, false);
  fixture.mode.value = 'Quantity';
  fixture.run('updateRetrieveAvailability();');
  assert.equal(Number(fixture.amount.max), 2);
});

test('amounts above available stock never reach the network', async () => {
  const fixture = makeFixture();
  fixture.amount.value = '14';
  await fixture.form.dispatch('submit');
  await flush();
  assert.equal(fixture.requests.length, 0);
  assert.ok(fixture.amount.validationMessage || fixture.error.textContent,
    'the rejected amount should have an explanation');
});

test('a pending submission sends one request and restores its button afterward', async () => {
  const fixture = makeFixture();
  fixture.amount.value = '1';
  let finish;
  fixture.setFetch(() => new Promise(resolve => { finish = resolve; }));
  const first = fixture.run('submitForm("retrieve-form", "/retrieve_consumable/stock", "POST", onSuccess)');
  assert.equal(fixture.submit.disabled, true);
  const duplicate = fixture.run('submitForm("retrieve-form", "/retrieve_consumable/stock", "POST", onSuccess)');
  assert.equal(fixture.requests.length, 1);
  finish(response(200, { success: true }));
  await Promise.all([first, duplicate]);
  assert.equal(fixture.submit.disabled, false);
  assert.equal(fixture.submit.textContent, 'Confirm');
  assert.equal(fixture.form.dataset.submitting, undefined);
  assert.equal(fixture.form.getAttribute('aria-busy'), null);
});

test('a backend stock error remains visible and the form can be retried', async () => {
  const fixture = makeFixture();
  fixture.amount.value = '1';
  const message = 'Only 0 items are available';
  fixture.setFetch(() => Promise.resolve(response(400, { error: message })));
  await fixture.form.dispatch('submit');
  await flush();
  assert.equal(fixture.error.textContent, message);
  assert.equal(fixture.error.hidden, false);
  assert.ok(fixture.notices.includes(message));
  assert.equal(fixture.submit.disabled, false);
  await fixture.form.dispatch('submit');
  await flush();
  assert.equal(fixture.requests.length, 2);
});
