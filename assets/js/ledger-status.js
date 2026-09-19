/* A snapshot describes one development gateway, never network-wide finality. */
(function (root) {
  'use strict';
  const MAX_AGE_MS = 3 * 60 * 60 * 1000;
  const CLOCK_SKEW_MS = 5 * 60 * 1000;
  const names = ['state', 'verify', 'sanctions'];
  const time = value => typeof value === 'string' ? Date.parse(value) : NaN;
  const dated = value => Number.isFinite(time(value));
  const dateLabel = value => dated(value) ? new Date(value).toISOString().replace('T', ' ').replace(/\.\d{3}Z$/, ' UTC') : 'Unknown';
  const validValue = (name, value) => {
    if (!value || typeof value !== 'object') return false;
    if (name === 'sanctions') return typeof value.installed === 'boolean';
    if (!Number.isSafeInteger(value.braid_length) || value.braid_length < 0 ||
        !/^[a-f0-9]{64}$/i.test(value.state_commitment)) return false;
    if (name === 'verify') return typeof value.verified === 'boolean';
    return ['accounts', 'total_supply'].every(k => Number.isSafeInteger(value[k]) && value[k] >= 0);
  };

  function model(snapshot, now = Date.now()) {
    const d = snapshot && typeof snapshot === 'object' ? snapshot : {};
    const versioned = d.schema_version === 2;
    const checked = versioned ? time(d.checked_at) : NaN;
    const recent = Number.isFinite(checked) && checked <= now + CLOCK_SKEW_MS && now - checked < MAX_AGE_MS;
    const components = {};
    for (const name of names) {
      const c = versioned ? (d.components || {})[name] || {} : {value: d[name], last_success_at: d.generated_at};
      const success = time(c.last_success_at);
      const validTime = Number.isFinite(success) && success <= now + CLOCK_SKEW_MS;
      const value = validTime && validValue(name, c.value) ? c.value : null;
      const current = !!value && recent && c.status === 'ok' && success === checked;
      components[name] = {value, current, success: value ? c.last_success_at : null,
        change: dated(c.last_change_at) && time(c.last_change_at) <= success ? c.last_change_at : null,
        latency: current && typeof c.latency_ms === 'number' && Number.isFinite(c.latency_ms) && c.latency_ms >= 0 ? c.latency_ms : null};
    }
    const complete = names.every(n => components[n].current) && d.observation_status === 'success';
    const hasHistory = names.some(n => components[n].value);
    let badge, note;
    if (!recent) {
      badge = hasHistory ? 'STALE SNAPSHOT' : 'STATUS UNKNOWN';
      note = 'A recent complete observation is unavailable. Saved values are historical; current gateway status is unknown.';
    } else if (!complete) {
      badge = hasHistory ? 'INCOMPLETE CHECK' : 'STATUS UNKNOWN';
      note = 'The latest check could not read every component. Each card identifies its last successful observation; retained values are historical.';
    } else {
      badge = d.recovered ? 'CHECK RECOVERED' : 'RECENT SNAPSHOT';
      note = (d.recovered ? 'The check recovered after an incomplete observation. ' : '') +
        'All three components returned a usable observation. Review the individual results and their timestamps above.';
    }
    return {components, complete, badge, note,
      checked: Number.isFinite(checked) && checked <= now + CLOCK_SKEW_MS ? d.checked_at : null,
      lastSuccess: dated(d.last_success_at) && time(d.last_success_at) <= now + CLOCK_SKEW_MS ? d.last_success_at : null};
  }

  function render(snapshot, doc, now = Date.now()) {
    const m = model(snapshot, now);
    const set = (id, text, className) => {
      const element = doc.getElementById(id);
      element.textContent = text;
      if (className) element.className = className;
    };
    set('live-pill', m.badge, 'pill ' + (m.complete ? 'p-ok' : 'p-warn'));
    set('gw', m.complete ? 'Observed' : 'Unknown', 'big ' + (m.complete ? 'ok' : 'warn'));
    set('asof', dateLabel(m.checked));
    set('last-success', dateLabel(m.lastSuccess));
    set('last-change', dateLabel(m.components.state.change));
    set('state-note', m.note);
    const latency = c => c.latency === null ? 'unknown' : c.latency < 1 ? '<1 ms' : c.latency.toFixed(1) + ' ms';
    set('lat', 'state ' + latency(m.components.state) + ' · integrity ' + latency(m.components.verify));
    for (const [name, id] of [['state', 'ledger'], ['verify', 'verify'], ['sanctions', 'gate']]) {
      const c = m.components[name];
      set(id + '-time', (c.current ? 'Observed: ' : c.value ? 'Historical result: ' : 'Last success: ') + dateLabel(c.success));
      let label = 'Unknown', detail = 'No valid observation is available.', positive = false;
      if (c.value) {
        const v = c.value;
        if (name === 'state') {
          label = v.accounts.toLocaleString() + ' accounts';
          detail = 'Total supply: ' + v.total_supply.toLocaleString() + ' base units · braid length ' + v.braid_length +
            '. State commitment: ' + v.state_commitment;
          positive = true;
        } else if (name === 'verify') {
          label = v.verified ? 'Verified' : 'Check failed';
          detail = 'Gateway-reported integrity check. Braid length ' + v.braid_length + '. State commitment: ' + v.state_commitment;
          positive = v.verified;
        } else {
          label = v.installed ? 'Installed' : 'Not installed';
          detail = 'Installation status reported by the gateway; this observation does not verify a compliance decision.';
          positive = v.installed;
        }
        if (!c.current) label += ' (historical)';
      }
      set(id + '-status', label, 'big ' + (positive && c.current ? 'ok' : 'warn'));
      set(id + '-det', detail);
    }
    return m;
  }

  const api = {model, render, MAX_AGE_MS};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root.document) {
    let saved = null;
    const refresh = () => render(saved, root.document);
    refresh();
    root.fetch('data/ledger-status.json', {cache: 'no-store'})
      .then(response => { if (!response.ok) throw new Error('snapshot unavailable'); return response.json(); })
      .then(snapshot => { saved = snapshot; refresh(); })
      .catch(refresh);
    // An open tab must age out even when no new snapshot is fetched.
    root.setInterval(refresh, 60000);
  }
})(typeof window === 'undefined' ? globalThis : window);
