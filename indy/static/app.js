'use strict';
// Indy UI. Plain JS, no dependencies, no external requests. Every dynamic value goes through
// esc() before it reaches innerHTML. API paths are relative so the app works under a path mount.

const $ = (s, r = document) => r.querySelector(s);
const view = $('#view');
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);
const when = (iso) => (iso ? new Date(iso).toLocaleString() : '');
const label = (s) => String(s).replace(/_/g, ' ');
const enc = encodeURIComponent;
const pill = (text, cls) => `<span class="pill ${esc(cls || text)}">${esc(label(text))}</span>`;
const VERDICT = { ready: 'Ready', ready_with_conditions: 'Ready with conditions', not_ready: 'Not ready' };
const VERDICT_NOTE = {
  ready: 'Nothing blocks this deal from becoming a project.',
  ready_with_conditions: 'It can become a project, but settle the conditions below.',
  not_ready: 'It should not become a project until the blockers are resolved.',
};

const NAV = [['#/', 'Opportunities'], ['#/checklist', 'Checklist'], ['#/jobs', 'Jobs']];
$('#mainNav').innerHTML = NAV.map(([h, n]) => `<a href="${h}" data-nav="${h}">${n}</a>`).join('');

// One sign-in for every VeraForge page: Vera owns the PIN and the key is shared on this origin.
// Local storage, never a cookie, so it cannot leak to other apps on this host.
const SSO_KEY = 'veraforge_sso';
const ssoGet = () => { try { return localStorage.getItem(SSO_KEY); } catch (e) { return null; } };
const ssoSet = (t) => { try { t ? localStorage.setItem(SSO_KEY, t) : localStorage.removeItem(SSO_KEY); } catch (e) { /* storage blocked */ } };
let token = ssoGet();

function toast(msg, bad) {
  const t = $('#toast');
  t.textContent = msg; t.className = 'show' + (bad ? ' bad' : '');
  clearTimeout(toast.t); toast.t = setTimeout(() => { t.className = ''; }, 3600);
}

let unlocking = null;
const unlock = () => { if (!unlocking) unlocking = doUnlock().finally(() => { unlocking = null; }); return unlocking; };
async function doUnlock() {
  const ov = $('#pinOverlay'), input = $('#pin-input'), err = $('#pin-error');
  input.value = err.textContent = '';
  ov.classList.add('open');
  input.focus();
  return new Promise((resolve) => {
    $('#pin-form').onsubmit = async (e) => {
      e.preventDefault(); err.textContent = '';
      try {
        const r = await fetch('ui/api/auth/verify', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pin: input.value }),
        });
        const body = await r.json().catch(() => ({}));
        if (!r.ok) { err.textContent = typeof body.detail === 'string' ? body.detail : 'Could not unlock.'; return; }
        token = body.token; ssoSet(token);
        input.value = '';
        ov.classList.remove('open');
        resolve();
      } catch (e2) { err.textContent = 'Could not reach Indy.'; }
    };
  });
}

async function api(path, opts = {}) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const h = {};
    if (token) h['X-Admin-Token'] = token;
    if (opts.body) h['Content-Type'] = 'application/json';
    const r = await fetch('ui/api/' + path, { method: opts.method || 'GET', headers: h, body: opts.body ? JSON.stringify(opts.body) : undefined });
    if (r.status === 401 && !path.startsWith('auth/')) { token = null; ssoSet(null); await unlock(); continue; }
    if (!r.ok) {
      let detail = r.statusText;
      try { const b = await r.json(); detail = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail); } catch (e) { /* keep status text */ }
      throw new Error(detail);
    }
    return r.json();
  }
  throw new Error('Not unlocked');
}

async function download(path, filename) {
  const r = await fetch('ui/api/' + path, { headers: token ? { 'X-Admin-Token': token } : {} });
  if (!r.ok) { toast('Download failed: ' + r.statusText, true); return; }
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// A job id comes back at once; poll until it finishes. Never hold a request open.
function pollJob(id, onProgress) {
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const j = await api('jobs/' + enc(id));
        if (j.progress && onProgress) onProgress(j.progress);
        if (j.status === 'done') return resolve(j);
        if (j.status === 'failed') return reject(new Error(j.error || 'The job failed'));
        setTimeout(tick, 1500);
      } catch (e) { reject(e); }
    };
    tick();
  });
}

// ---------- views ----------
async function opportunities() {
  view.innerHTML = '<p class="muted">Loading...</p>';
  const d = await api('opportunities');
  const cards = d.opportunities.map((o) => `
    <a class="opp-card" href="#/opp/${enc(o.opportunity_id)}">
      <div class="id">${esc(o.opportunity_id)}</div>
      <div class="label">${esc(o.name)}</div>
      <div class="meta">${o.verdict ? pill(o.verdict) : '<span class="muted small">not checked yet</span>'}
        ${o.checked_at ? `<span class="muted small">${esc(when(o.checked_at))}</span>` : ''}
        ${o.projects.length ? `<span class="tag">project exists</span>` : ''}</div>
    </a>`).join('');
  view.innerHTML = `
    <div class="page-title"><h2>Opportunities</h2></div>
    ${d.message ? `<div class="banner info">${esc(d.message)}</div>` : ''}
    <div class="card"><h2>Open an opportunity</h2>
      <form id="openForm" class="row"><input id="oppId" placeholder="Opportunity id" style="max-width:320px" required>
      <button class="action" type="submit">Open</button></form></div>
    ${cards ? `<div class="grid-3">${cards}</div>` : '<div class="empty">No opportunities to list.</div>'}`;
  $('#openForm').onsubmit = (e) => { e.preventDefault(); location.hash = '#/opp/' + enc($('#oppId').value.trim()); };
}

const groupDocs = (docs) => {
  const g = {};
  docs.forEach((d) => { (g[d.category] = g[d.category] || []).push(d); });
  return g;
};

function factList(rows) {
  if (!rows || !rows.length) return '<div class="muted small">Not found in the SOW.</div>';
  return rows.map((f) => `<div class="fact">${esc(f.text)}
    <span class="tag ${f.basis === 'inferred' ? 'inferred' : ''}">${f.basis === 'stated' ? 'stated, ' + esc(f.doc) : 'inferred'}</span>
    ${f.quote ? `<div class="small muted">"${esc(f.quote)}"</div>` : ''}</div>`).join('');
}

function reportHtml(run) {
  const c = run.check;
  const items = c.items;
  const blockers = items.filter((i) => i.severity === 'blocker' && ['missing', 'unclear'].includes(i.status));
  const conditions = items.filter((i) => !blockers.includes(i) && !['present', 'skipped'].includes(i.status));
  const facts = run.facts || {};
  const FACTS = [['customer', 'Customer and delivering company'], ['scope', 'Scope in plain language'], ['deliverables', 'Deliverables'],
    ['key_dates', 'Key dates'], ['commercial_terms', 'Commercial terms'], ['assumptions', 'Assumptions'],
    ['dependencies', 'Dependencies'], ['people', 'Named people and roles']];
  const m = run.methodology;
  const inf = run.inferred;
  const INF = [['customer_questions', 'Questions for the customer'], ['delivery_questions', 'Questions for the delivery team'],
    ['risks', 'Risks'], ['later_agents_need', 'What later agents will need']];
  return `
    <div class="verdict ${esc(run.verdict)}"><div><div class="big">${esc(VERDICT[run.verdict])}</div>
      <div>${esc(VERDICT_NOTE[run.verdict])}</div>
      <div class="small muted">Checked ${esc(c.checked_on)}. Computed in code from the documents.</div></div></div>
    ${run.model_problems.length ? `<div class="banner">The model stages did not fully run. The checklist and verdict are complete. ${esc(run.model_problems.join('; '))}</div>` : ''}
    <div class="card"><h2>Executive summary</h2>
      <p>${c.sow ? `SOW checked: <b>${esc(c.sow.filename)}</b>. ${esc(c.signature ? c.signature.detail : '')}` : 'No SOW was found.'}</p>
      ${blockers.length ? `<p><b>Blockers (${blockers.length}):</b> ${blockers.map((b) => `${esc(b.label)} ${pill(b.status)}`).join(' ')}</p>` : ''}
      ${conditions.length ? `<p><b>Conditions (${conditions.length}):</b> ${conditions.map((b) => `${esc(b.label)} ${pill(b.status)}`).join(' ')}</p>` : ''}
      ${!blockers.length && !conditions.length ? '<p>Every enabled checklist item is present.</p>' : ''}
      <div class="row"><button class="action secondary small" id="dlReport">Download report (.md)</button>
      <span class="muted small">Stored in Vera as ${esc((run.stored || {}).storage_ref || 'the opportunity outputs')}</span></div></div>
    <div class="card"><h2>Checklist</h2><div class="tablewrap"><table>
      <thead><tr><th>Item</th><th>Kind</th><th>Status</th><th>What the documents show</th></tr></thead><tbody>
      ${items.map((i) => `<tr><td>${esc(i.label)}</td><td>${pill(i.severity)}</td><td>${pill(i.status)}</td>
        <td>${esc(i.detail)} <span class="basis">(${esc(i.basis)})</span>
        ${i.notes.map((n) => `<div class="small muted">${esc(n)}</div>`).join('')}
        ${i.evidence.slice(0, 2).map((e) => `<div class="src">${esc(e.doc)}, ${esc(e.where)}: "${esc(e.quote)}"</div>`).join('')}</td></tr>`).join('')}
      </tbody></table></div></div>
    <div class="card"><h2>Documents</h2>
      ${c.documents.read.map((d) => `<div class="small">${esc(d.filename)} <span class="muted">(${esc(d.category)})</span></div>`).join('') || '<div class="muted small">None read.</div>'}
      ${c.documents.skipped.length ? `<h3 style="margin-top:12px">Not read, so nothing relies on them</h3>${c.documents.skipped.map((s) => `<div class="small">${esc(s.filename)}: ${esc(s.reason)}</div>`).join('')}` : ''}</div>
    ${run.facts ? `<div class="card"><h2>Suggested project summary</h2>
      <p class="muted small">For Michael to confirm when promoting the opportunity to a project in Vera. Each line says whether a document states it.</p>
      ${FACTS.map(([k, n]) => `<h3 style="margin-top:12px">${n}</h3>${factList(facts[k])}`).join('')}</div>` : ''}
    ${m ? `<div class="card"><h2>Suggested methodology (suggestion only)</h2>
      <p>Indy's reading (inferred): <b>${esc(m.suggestion || 'no suggestion')}</b>. ${esc(m.reasoning)}</p>
      <p class="muted small">Counted in the SOW: ${m.signals.scrum_terms} agile terms, ${m.signals.waterfall_terms} phase, milestone or sign-off terms. The choice belongs to Michael and is permanent once the project is created.</p></div>` : ''}
    ${inf ? `<div class="card"><h2>What Indy inferred (not stated in the documents)</h2>
      ${INF.map(([k, n]) => `<h3 style="margin-top:12px">${n}</h3>${(inf[k] || []).map((v) => `<div class="fact">${esc(v)}</div>`).join('') || '<div class="muted small">None.</div>'}`).join('')}</div>` : ''}`;
}

async function opportunity(oid) {
  view.innerHTML = '<p class="muted">Loading...</p>';
  const d = await api('opportunity/' + enc(oid));
  const groups = groupDocs(d.documents);
  const name = d.opportunity.name || d.opportunity.title || '';
  view.innerHTML = `
    <div class="page-title"><a class="action secondary small" href="#/">Back</a>
      <h2>${esc(oid)}</h2><span class="muted">${esc(name)}</span><span class="grow"></span>
      <button class="action" id="runBtn">Run readiness check</button></div>
    <div id="runMsg"></div>
    <div id="report">${d.run ? reportHtml(d.run) : '<div class="empty">No check has been run for this opportunity yet.</div>'}</div>
    <div class="card"><h2>Documents in Vera</h2>
      ${Object.keys(groups).map((k) => `<h3 style="margin-top:10px">${esc(label(k))}</h3>${groups[k].map((x) => `<div class="small">${esc(x.filename)}</div>`).join('')}`).join('') || '<div class="muted small">No documents are filed for this opportunity.</div>'}</div>
    <div class="card"><h2>Ask about these documents</h2>
      <form id="askForm"><textarea id="question" rows="2" maxlength="500" placeholder="For example: who signs acceptance for the deliverables?" required></textarea>
      <div class="row" style="margin-top:8px"><button class="action" type="submit" id="askBtn">Ask</button>
      <span class="muted small">Answers cite the document they came from.</span></div></form>
      <div id="answers"></div></div>`;
  const dl = $('#dlReport');
  if (dl) dl.onclick = () => download('run/' + enc(oid) + '/report.md', 'readiness_report_' + oid + '.md');

  $('#runBtn').onclick = async () => {
    const btn = $('#runBtn'), msg = $('#runMsg');
    btn.disabled = true;
    msg.innerHTML = '<div class="banner info" id="runProg">Starting...</div>';
    try {
      const job = await api('check', { method: 'POST', body: { opportunity_id: oid } });
      await pollJob(job.job_id, (p) => { const el = $('#runProg'); if (el) el.textContent = p; });
      msg.innerHTML = '';
      const run = await api('run/' + enc(oid));
      $('#report').innerHTML = reportHtml(run);
      const dl2 = $('#dlReport');
      if (dl2) dl2.onclick = () => download('run/' + enc(oid) + '/report.md', 'readiness_report_' + oid + '.md');
      toast('Check finished');
    } catch (e) {
      msg.innerHTML = `<div class="banner bad">${esc(e.message)}</div>`;
    } finally { btn.disabled = false; }
  };

  $('#askForm').onsubmit = async (e) => {
    e.preventDefault();
    const q = $('#question').value.trim(), btn = $('#askBtn');
    if (!q) return;
    btn.disabled = true;
    const slot = document.createElement('div');
    slot.className = 'hist';
    slot.innerHTML = `<b>${esc(q)}</b><div class="muted small">Reading the documents...</div>`;
    $('#answers').prepend(slot);
    try {
      const job = await api('ask', { method: 'POST', body: { opportunity_id: oid, question: q } });
      const done = await pollJob(job.job_id);
      const a = done.result;
      slot.innerHTML = `<b>${esc(q)}</b><div class="answer">${esc(a.answer)}</div>
        ${a.grounded ? '' : '<div class="small" style="color:var(--red)">No document is cited, so treat this as unverified.</div>'}
        ${a.sources.map((s) => `<div class="src">[${s.n}] ${esc(s.doc)}, ${esc(s.where)}: ${esc(s.excerpt)}</div>`).join('')}`;
      $('#question').value = '';
    } catch (err) {
      slot.innerHTML = `<b>${esc(q)}</b><div class="banner bad">${esc(err.message)}</div>`;
    } finally { btn.disabled = false; }
  };
}

async function checklist() {
  view.innerHTML = '<p class="muted">Loading...</p>';
  let items = await api('checklist');
  const draw = () => {
    view.innerHTML = `
      <div class="page-title"><h2>Readiness checklist</h2></div>
      <p class="muted">A blocker that is missing or unclear makes a deal Not ready. Anything else not present makes it Ready with conditions.</p>
      <div class="card"><div class="tablewrap"><table><thead><tr><th>On</th><th>Item</th><th>Kind</th><th>Keywords</th><th></th></tr></thead><tbody>
      ${items.map((i, n) => `<tr><td><input type="checkbox" data-on="${n}" ${i.enabled ? 'checked' : ''}></td>
        <td>${esc(i.label)}<div class="small muted">${esc(i.description || '')}</div></td>
        <td><select data-sev="${n}"><option value="blocker" ${i.severity === 'blocker' ? 'selected' : ''}>blocker</option>
          <option value="warning" ${i.severity === 'warning' ? 'selected' : ''}>warning</option></select></td>
        <td>${i.custom ? `<input data-kw="${n}" value="${esc(i.keywords.join(', '))}">` : '<span class="muted small">built in</span>'}</td>
        <td>${i.custom ? `<button class="action secondary small" data-del="${n}">Remove</button>` : ''}</td></tr>`).join('')}
      </tbody></table></div></div>
      <div class="card"><h2>Add an item</h2><div class="row">
        <input id="newLabel" placeholder="What must be in the documents" style="max-width:340px">
        <input id="newKw" placeholder="Words to look for, comma separated" style="max-width:340px">
        <select id="newSev" style="width:auto"><option value="warning">warning</option><option value="blocker">blocker</option></select>
        <button class="action secondary" id="addBtn">Add</button></div></div>
      <div class="row"><button class="action" id="saveBtn">Save checklist</button>
      <button class="action secondary" id="resetBtn">Reset to defaults</button><span id="chkMsg" class="muted small"></span></div>`;
    view.querySelectorAll('[data-on]').forEach((el) => { el.onchange = () => { items[el.dataset.on].enabled = el.checked; }; });
    view.querySelectorAll('[data-sev]').forEach((el) => { el.onchange = () => { items[el.dataset.sev].severity = el.value; }; });
    view.querySelectorAll('[data-kw]').forEach((el) => {
      el.onchange = () => { items[el.dataset.kw].keywords = el.value.split(',').map((x) => x.trim()).filter(Boolean); };
    });
    view.querySelectorAll('[data-del]').forEach((el) => { el.onclick = () => { items.splice(+el.dataset.del, 1); draw(); }; });
    $('#addBtn').onclick = () => {
      const l = $('#newLabel').value.trim(), kw = $('#newKw').value.split(',').map((x) => x.trim()).filter(Boolean);
      if (!l || !kw.length) { toast('Give the item a name and at least one keyword', true); return; }
      items.push({ custom: true, label: l, keywords: kw, severity: $('#newSev').value, enabled: true });
      draw();
    };
    $('#saveBtn').onclick = async () => {
      try { items = await api('checklist', { method: 'PUT', body: { items } }); toast('Checklist saved'); draw(); }
      catch (e) { $('#chkMsg').textContent = e.message; toast(e.message, true); }
    };
    $('#resetBtn').onclick = async () => { items = await api('checklist/reset', { method: 'POST' }); toast('Reset to defaults'); draw(); };
  };
  draw();
}

async function jobs() {
  view.innerHTML = '<p class="muted">Loading...</p>';
  const list = await api('jobs');
  view.innerHTML = `<div class="page-title"><h2>Jobs</h2></div>
    ${list.length ? `<div class="card"><div class="tablewrap"><table><thead><tr><th>Job</th><th>Kind</th><th>Opportunity</th><th>Status</th><th>Started</th><th>Note</th></tr></thead><tbody>
    ${list.map((j) => `<tr><td>${esc(j.job_id)}</td><td>${esc(j.kind)}</td><td>${esc((j.params || {}).opportunity_id)}</td>
      <td>${pill(j.status)}</td><td>${esc(when(j.created_at))}</td><td>${esc(j.error || j.progress || '')}</td></tr>`).join('')}</tbody></table></div></div>`
    : '<div class="empty">No jobs yet.</div>'}`;
}

async function route() {
  const hash = location.hash || '#/';
  const key = hash.startsWith('#/opp') ? '#/' : hash;
  document.querySelectorAll('#mainNav a').forEach((a) => a.classList.toggle('active', a.dataset.nav === key));
  try {
    if (hash.startsWith('#/opp/')) await opportunity(decodeURIComponent(hash.slice(6)));
    else if (hash === '#/checklist') await checklist();
    else if (hash === '#/jobs') await jobs();
    else await opportunities();
  } catch (e) {
    view.innerHTML = `<div class="banner bad">${esc(e.message)}</div>`;
  }
}
window.addEventListener('hashchange', route);
if ('serviceWorker' in navigator) navigator.serviceWorker.register('static/sw.js').catch(() => { /* install is optional */ });
route();
