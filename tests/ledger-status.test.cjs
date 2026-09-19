const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const {spawnSync} = require('node:child_process');
const {model, render, MAX_AGE_MS} = require('../assets/js/ledger-status.js');
const generated = spawnSync(process.env.PYTHON || 'python3', ['tests/status_fixtures.py'], {encoding: 'utf8'});
assert.equal(generated.status, 0, generated.stderr);
const cases = JSON.parse(generated.stdout);
const now = s => Date.parse(s.checked_at) + 1000;
const html = readFileSync('explorer.html', 'utf8');
const fakeDOM = () => {
  const nodes = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m => [m[1], {textContent: '', className: ''}]));
  return {nodes, getElementById: id => { assert.ok(nodes[id], `Missing HTML element ${id}`); return nodes[id]; }};
};

for (const name of ['unchanged', 'changed', 'recovered']) {
  test(`${name}: complete, current observation with distinct timestamps`, () => {
    const d = fakeDOM(), m = render(cases[name], d, now(cases[name]));
    assert.equal(m.complete, true);
    assert.equal(d.nodes['ledger-status'].className, 'big ok');
    assert.equal(d.nodes['gate-status'].textContent, 'Not installed');
    assert.match(d.nodes['gate-status'].className, /warn/);
    assert.equal(m.badge, name === 'recovered' ? 'CHECK RECOVERED' : 'RECENT SNAPSHOT');
    assert.match(d.nodes['ledger-time'].textContent, /^Observed:/);
  });
}
test('failed-with-last-good never displays retained values as current healthy', () => {
  const d = fakeDOM(), m = render(cases.failed, d, now(cases.failed));
  assert.equal(m.complete, false);
  assert.equal(d.nodes.gw.textContent, 'Unknown');
  for (const name of ['ledger', 'verify', 'gate']) {
    assert.match(d.nodes[name + '-status'].textContent, /historical/);
    assert.equal(d.nodes[name + '-status'].className, 'big warn');
    assert.match(d.nodes[name + '-time'].textContent, /^Historical result:/);
  }
});
test('never-successful and missing responses stay unknown, never awaiting genesis', () => {
  for (const snapshot of [cases.never, null, {}, [], 'text']) {
    const d = fakeDOM();
    render(snapshot, d, snapshot?.checked_at ? now(snapshot) : Date.now());
    for (const name of ['ledger', 'verify', 'gate']) assert.equal(d.nodes[name + '-status'].textContent, 'Unknown');
    assert.equal(d.nodes['live-pill'].textContent, 'STATUS UNKNOWN');
  }
});
test('partial result preserves independent component observations', () => {
  const d = fakeDOM();
  render(cases.partial, d, now(cases.partial));
  assert.equal(d.nodes['live-pill'].textContent, 'INCOMPLETE CHECK');
  assert.match(d.nodes['verify-status'].textContent, /historical/);
  assert.equal(d.nodes['ledger-status'].textContent, '3 accounts');
});
test('an open tab ages out exactly at the freshness boundary', () => {
  const s = cases.unchanged;
  assert.equal(model(s, Date.parse(s.checked_at) + MAX_AGE_MS - 1).complete, true);
  const d = fakeDOM();
  render(s, d, Date.parse(s.checked_at) + MAX_AGE_MS);
  assert.equal(d.nodes['live-pill'].textContent, 'STALE SNAPSHOT');
  assert.match(d.nodes['verify-status'].textContent, /historical/);
});
test('future and invalid check times cannot produce current status', () => {
  for (const checked_at of ['invalid', '2100-01-01T00:00:00Z', null]) {
    assert.equal(model({...cases.unchanged, checked_at}, now(cases.unchanged)).complete, false);
  }
});
test('legacy data remains historical even with a recent generated time', () => {
  const s = cases.unchanged;
  const legacy = {generated_at: s.checked_at, ...Object.fromEntries(Object.entries(s.components).map(([k, c]) => [k, c.value]))};
  const d = fakeDOM();
  render(legacy, d, now(s));
  assert.equal(d.nodes['live-pill'].textContent, 'STALE SNAPSHOT');
  assert.equal(d.nodes.asof.textContent, 'Unknown');
});
test('malformed fields cannot inject markup or imply a healthy result', () => {
  const s = structuredClone(cases.unchanged);
  s.components.state.value.accounts = '<img onerror=alert(1)>';
  s.components.verify.value.verified = 'false';
  s.components.sanctions.value.installed = 'false';
  const d = fakeDOM();
  render(s, d, now(s));
  for (const name of ['ledger', 'verify', 'gate']) assert.equal(d.nodes[name + '-status'].textContent, 'Unknown');
  assert.doesNotMatch(JSON.stringify(d.nodes), /<img/);
});
test('negative integrity finding remains explicit on a fresh complete check', () => {
  const s = structuredClone(cases.unchanged);
  s.components.verify.value.verified = false;
  const d = fakeDOM();
  render(s, d, now(s));
  assert.equal(d.nodes['verify-status'].textContent, 'Check failed');
  assert.equal(d.nodes['verify-status'].className, 'big warn');
});
