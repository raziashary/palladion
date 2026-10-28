import { api, qs } from './api.js';
import { clear, h, icon, toast } from './dom.js';
import { bytes, fmtDay, fmtTime, shortId, toneOf } from './format.js';
import { S, emit, persona } from './state.js';

const TEXT = /\.(md|markdown|txt|json|jsonl|csv|tsv|py|js|jsx|ts|tsx|java|go|rs|c|h|cpp|cs|sql|sh|ps1|ya?ml|toml|ini|cfg|xml|html|css|log)$/i;
const today = () => new Date().toISOString().slice(0, 10);
const familyOf = (name) => name.replace(/\.[^.]+$/, '').replace(/[^A-Za-z0-9]+/g, '.').replace(/^\.|\.$/g, '').toUpperCase() || 'DOCUMENT';

function toBase64(buffer) {
  let binary = '';
  const bytesView = new Uint8Array(buffer);
  for (let i = 0; i < bytesView.length; i += 0x8000) binary += String.fromCharCode(...bytesView.subarray(i, i + 0x8000));
  return btoa(binary);
}

function stepper(source) {
  const approved = source.state === 'APPROVED';
  const ready = approved && source.index_state === 'READY';
  if (source.state === 'REVOKED') return h('div', { class: 'stepper' }, h('span', { class: 'chip red' }, 'Revoked: no longer searchable or citable'));
  const step = (text, on, cur) => h('span', { class: on ? 'on' : cur ? 'cur' : '' }, icon(on ? 'check' : 'clock', 12), text);
  return h('div', { class: 'stepper' }, step('Uploaded', true), h('i'), step('Approved by someone else', approved, !approved), h('i'), step('Searchable', ready, approved && !ready));
}

export async function renderIngest(host) {
  const me = persona();
  const queue = [];
  const page = h('div', { class: 'page' });
  host.append(h('div', { class: 'scroll' }, page));
  const listHost = h('div');
  const queueHost = h('div');

  async function refresh() {
    clear(listHost).append(h('p', { class: 'hint' }, 'Loading documents…'));
    try {
      const data = await api('/sources' + qs({ case_id: S.caseId }));
      clear(listHost).append(...sourceList(data));
    } catch (error) { clear(listHost).append(h('div', { class: 'card errorcard' }, error.message)); }
  }

  function sourceList(data) {
    const rows = data.sources;
    const out = [];
    if (data.listing === 'local') out.push(h('p', { class: 'hint' }, 'This Palladion cannot list documents, so only those uploaded here are shown.'));
    if (data.coverage) out.push(h('p', { class: 'hint' }, `${data.coverage.indexed_source_count} of ${data.coverage.accepted_source_count} approved documents are searchable now. This counts supplied documents only; it cannot know whether every company document was supplied.`));
    if (!rows.length) out.push(h('div', { class: 'card' }, 'No documents are visible to you in this case yet.'));
    out.push(h('div', { class: 'list' }, rows.map((s) => sourceCard(s, rows))));
    return out;
  }

  function sourceCard(s, rows) {
    const canApprove = me.can_approve && s.state === 'DRAFT' && s.uploader_id !== me.id;
    const older = rows.filter((r) => r.family_id === s.family_id && r.state === 'APPROVED' && r.revision_id !== s.revision_id);
    const replaces = h('select', { 'aria-label': 'Replaces', style: 'width:auto' }, h('option', { value: '' }, 'Replaces nothing'),
      older.map((r) => h('option', { value: r.revision_id }, `Replaces ${r.filename} (${fmtDay(r.registered_at)})`)));
    const act = async (label, path, body) => {
      try { await api(path, { method: 'POST', body: { case_id: S.caseId, ...body } }); toast(label); await refresh(); } catch (error) { toast(error.message, 'error'); }
    };
    const approve = h('button', { class: 'btn primary small', onclick: async (e) => { e.target.disabled = true; e.target.textContent = 'Approving and indexing…'; await act('Approved and indexed', `/sources/${s.revision_id}/approve`, { supersedes_revision_id: replaces.value || null }); } }, 'Approve');
    return h('div', { class: 'item-card' }, icon(s.pdf ? 'file' : 'doc', 22),
      h('div', { class: 'grow' }, h('div', { class: 'name' }, s.filename || shortId(s.revision_id)),
        h('div', { class: 'sub' }, `${s.family_id} · uploaded by ${s.uploader_id}${s.size ? ' · ' + bytes(s.size) : ''}${s.pages ? ` · ${s.pages} pages` : ''}`),
        h('div', { class: 'sub' }, s.valid_from || s.valid_to ? `Valid ${s.valid_from ? 'from ' + fmtDay(s.valid_from) : ''}${s.valid_to ? ' until ' + fmtDay(s.valid_to) : ''}` : 'No validity dates: always applies while approved'),
        stepper(s)),
      h('div', { style: 'display:flex;flex-direction:column;gap:6px;align-items:flex-end' },
        h('span', { class: `chip ${toneOf(s.state)}` }, s.state),
        canApprove ? [older.length ? replaces : null, approve] : null,
        s.state === 'DRAFT' && !canApprove ? h('span', { class: 'hint' }, s.uploader_id === me.id ? 'Waiting for another person to approve' : me.can_approve ? '' : 'Needs an administrator') : null,
        me.can_approve && s.state === 'APPROVED' ? h('button', { class: 'btn danger small', onclick: () => confirm('Revoke this document? It stops being searchable and citable immediately.') && act('Revoked', `/sources/${s.revision_id}/revoke`, {}) }, 'Revoke') : null));
  }

  function drawQueue() {
    clear(queueHost);
    if (!queue.length) return;
    queueHost.append(h('div', { class: 'list' }, queue.map((q, i) => h('div', { class: 'subcard', style: 'margin:0' },
      h('div', { style: 'display:flex;justify-content:space-between;gap:8px' }, h('b', {}, q.filename), h('span', { class: 'hint' }, bytes(q.size)), h('button', { class: 'icon-btn', 'aria-label': 'Remove', onclick: () => { queue.splice(i, 1); drawQueue(); } }, icon('x', 14))),
      h('div', { class: 'row', style: 'margin-top:8px' },
        h('div', { class: 'field' }, h('label', {}, 'Document name'), h('input', { type: 'text', value: q.family, oninput: (e) => { q.family = e.target.value; } }), h('span', { class: 'hint' }, 'A new file with the same name becomes a new version.')),
        h('div', { class: 'field' }, h('label', {}, 'Applies from'), h('input', { type: 'date', value: q.valid_from, oninput: (e) => { q.valid_from = e.target.value; } })),
        h('div', { class: 'field' }, h('label', {}, 'Until (optional)'), h('input', { type: 'date', value: q.valid_to, oninput: (e) => { q.valid_to = e.target.value; } })))))),
    h('div', { style: 'margin-top:12px' }, h('button', { class: 'btn primary', id: 'upload-btn', onclick: uploadAll }, `Upload ${queue.length} file${queue.length === 1 ? '' : 's'}`)));
  }

  async function uploadAll(event) {
    event.target.disabled = true;
    for (const q of [...queue]) {
      try {
        await api('/sources', { method: 'POST', body: { case_id: S.caseId, family_id: q.family, filename: q.filename, content: q.content, content_base64: q.base64,
          valid_from: q.valid_from || null, valid_to: q.valid_to || null } });
        queue.splice(queue.indexOf(q), 1); toast(`${q.filename} uploaded as a draft`);
      } catch (error) { toast(`${q.filename}: ${error.message}`, 'error'); }
    }
    drawQueue(); await refresh(); emit();
  }

  async function addFiles(files) {
    for (const file of files) {
      const pdf = /\.pdf$/i.test(file.name);
      if (!pdf && !TEXT.test(file.name)) { toast(`${file.name}: this file type is not supported`, 'error'); continue; }
      const entry = { filename: file.name, size: file.size, family: familyOf(file.name), valid_from: today(), valid_to: '' };
      if (pdf) entry.base64 = toBase64(await file.arrayBuffer()); else entry.content = await file.text();
      queue.push(entry);
    }
    drawQueue();
  }

  const pasteName = h('input', { type: 'text', placeholder: 'note.md', value: 'note.md' });
  const pasteText = h('textarea', { class: 'box', rows: 5, placeholder: 'Paste the document text here' });
  const input = h('input', { type: 'file', multiple: true, class: 'sr', id: 'file-input', onchange: (e) => { addFiles(e.target.files); e.target.value = ''; } });
  const drop = h('div', { class: 'drop', id: 'dropzone',
    ondragover: (e) => { e.preventDefault(); drop.classList.add('over'); }, ondragleave: () => drop.classList.remove('over'),
    ondrop: (e) => { e.preventDefault(); drop.classList.remove('over'); addFiles(e.dataTransfer.files); } },
  icon('upload', 26), h('p', { style: 'margin:6px 0 2px' }, 'Drop files here or ', h('b', { onclick: () => input.click() }, 'choose files')),
  h('span', { class: 'hint' }, 'Markdown, text, JSON, CSV, code and digital PDFs. Text up to 65,536 characters, PDFs up to 2 MB.'), input);

  page.append(h('h1', {}, 'Ingestion'),
    h('p', { class: 'lead' }, `Add documents to ${S.caseId}. An upload is a draft that nobody can search or cite until a different person approves it.`),
    ...(me.can_upload ? [drop, queueHost,
      h('details', { style: 'margin-top:12px' }, h('summary', { class: 'hint', style: 'cursor:pointer' }, 'Or paste text instead'),
        h('div', { class: 'field', style: 'margin-top:8px' }, h('label', {}, 'File name'), pasteName), h('div', { class: 'field' }, pasteText),
        h('button', { class: 'btn', onclick: () => { if (!pasteText.value.trim()) return; queue.push({ filename: pasteName.value || 'note.md', size: pasteText.value.length, family: familyOf(pasteName.value || 'note'), valid_from: today(), valid_to: '', content: pasteText.value }); pasteText.value = ''; drawQueue(); } }, 'Add to the upload list'))]
      : [h('div', { class: 'card' }, `${me.id} can’t upload. Switch identity (bottom left) to uploader-a to add documents, then to admin-a to approve them.`)]),
    h('div', { class: 'section-title' }, h('h2', {}, 'Documents in this case'), h('button', { class: 'btn small', onclick: refresh }, 'Refresh')),
    h('p', { class: 'hint', style: 'margin-top:0' }, me.can_approve ? 'You can approve drafts uploaded by someone else, and revoke approved documents.' : 'Approving is for administrators. Drafts you did not upload are not shown to you.'),
    listHost);
  await refresh();
}
