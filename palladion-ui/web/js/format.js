// Pure helpers: plain-language wording for Palladion's codes. No DOM here, so Node can test them.

const DISPOSITIONS = {
  SUPPORTED: { label: 'Supported', tone: 'green', help: 'Everything stated is verified in this case scope.' },
  PARTIALLY_SUPPORTED: { label: 'Partly supported', tone: 'amber', help: 'Some facts are verified. Do not act on this alone.' },
  CONFLICT: { label: 'Conflict', tone: 'red', help: 'Approved sources disagree and no precedence is recorded.' },
  NOT_ESTABLISHED: { label: 'Not established', tone: 'gray', help: 'The searched sources do not establish this.' },
  VERIFICATION_UNAVAILABLE: { label: 'Could not verify', tone: 'red', help: 'A required check could not complete.' },
};
export function disposition(code) {
  return DISPOSITIONS[code] || { label: String(code || 'Unknown'), tone: 'gray', help: '' };
}

const GAPS = {
  authorized_human_review: ['Needs authorised human review', 'Palladion never releases operational guidance as a go-ahead on its own.'],
  mandatory_critic_review: ['Independent review did not run', 'Policy-related claims need the critic’s review before release.'],
  claim_support_not_established: ['A proposed claim had no supporting evidence', 'It was blocked, not released.'],
  applicable_policy: ['No applicable policy decision', 'A policy decision for this question is missing.'],
  unresolved_critic_challenge: ['The reviewer raised an unresolved challenge', null],
  revised_draft_requires_review: ['The final wording changed after review', null],
};
export function gap(code, origin) {
  const known = GAPS[code];
  if (known) return { title: known[0], detail: known[1] };
  const pretty = String(code).replace(/_/g, ' ');
  const detail = origin === 'POLICY_SCHEMA' ? 'Required by the approved policy.' : origin === 'TRUSTED_CASE' ? 'Required by the case.' : null;
  return { title: `Missing: ${pretty}`, detail };
}

export function failureText(code) {
  const known = { LIVE_UNAVAILABLE: 'A live system timed out or was unavailable', KNOWLEDGE_UNAVAILABLE: 'The document search was unavailable',
    TOOL_CANCELLED: 'A step was cancelled' };
  return known[code] || String(code).replace(/_/g, ' ').toLowerCase();
}

const STATUS_TONE = { OK: 'green', SUCCEEDED: 'green', DETERMINED: 'green', READY: 'green', APPROVED: 'green', FOUND: 'green',
  PENDING: 'amber', DRAFT: 'amber', STORED: 'amber', INCOMPLETE_INPUT: 'amber', STALE_DATA: 'amber', CONTEXT_ONLY: 'blue',
  TIMEOUT: 'red', UNAVAILABLE: 'red', FAILED: 'red', REVOKED: 'red', POLICY_CONFLICT: 'red', VERIFICATION_UNAVAILABLE: 'red',
  UNVERIFIED_INPUT: 'red', FORBIDDEN: 'red', NO_APPLICABLE_POLICY: 'gray', NOT_APPLICABLE: 'gray', NOT_FOUND: 'gray' };
export const toneOf = (status) => STATUS_TONE[String(status).toUpperCase()] || 'gray';

export function evidenceKind(id, hint) {
  if (hint) return hint;
  const s = String(id);
  return s.startsWith('chunk_') ? 'DOCUMENT' : s.startsWith('live_') ? 'LIVE_OBSERVATION' : s.startsWith('policy_') ? 'POLICY_DECISION'
    : s.startsWith('evt_') || s.startsWith('mem_') ? 'CASE_EVENT' : 'DOCUMENT';
}
export const KIND_LABEL = { DOCUMENT: 'Document', LIVE_OBSERVATION: 'Live reading', POLICY_DECISION: 'Policy decision', CASE_EVENT: 'Case note' };

export function citationTitle(c) {
  const kind = evidenceKind(c.evidence_id, c.kind);
  if (kind === 'DOCUMENT') return c.section_id ? `Source · ${String(c.section_id).split('/').pop().replace(/-/g, ' ')}` : 'Source passage';
  if (kind === 'LIVE_OBSERVATION') return `${c.source_system || 'Live system'} · ${String(c.operation || '').replace(/^get_/, '').replace(/_/g, ' ')}`;
  if (kind === 'POLICY_DECISION') return `Policy · ${c.family_id || ''}${c.version_id ? ' ' + c.version_id : ''}`.trim();
  return KIND_LABEL[kind] || 'Evidence';
}

export function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}
export const fmtDay = (iso) => (iso ? String(iso).slice(0, 10) : '');
export function ago(iso) {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (!Number.isFinite(seconds)) return '';
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  return `${Math.floor(seconds / 86400)} d ago`;
}
export const shortId = (id, n = 8) => String(id).replace(/^(rev|chunk|live|policy|evt|sess)_/, '').slice(0, n);
export function bytes(n) {
  if (n < 1024) return `${n} B`;
  return n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;
}

// Policies in plain language --------------------------------------------------------------------------------------

export const OPERATOR_WORDS = { eq: 'is', in: 'is one of', lt: 'is below', lte: 'is at most', gt: 'is above', gte: 'is at least' };
export function conditionText(c) {
  const value = Array.isArray(c.value) ? c.value.join(' or ') : c.value;
  return `${String(c.fact || c.field).replace(/_/g, ' ')} ${OPERATOR_WORDS[c.operator] || c.operator} ${value}`;
}
export function predicateConditions(predicate) {
  const joiner = Object.keys(predicate)[0];
  const parts = predicate[joiner] || [];
  return { match: joiner, conditions: parts.map((p) => ({ fact: p.field, operator: p.operator, value: p.value })) };
}
export function ruleSentence(rule) {
  const { match, conditions } = rule.predicate ? predicateConditions(rule.predicate) : { match: rule.match || 'all', conditions: rule.conditions };
  const word = match === 'any' ? ' or ' : ' and ';
  return `If ${conditions.map(conditionText).join(word)}, the outcome is ${rule.outcome}.`;
}
export const BASIS_WORDS = { TRANSACTION_OCCURRED_AT: 'the date the transaction happened', CASE_OPENED_AT: 'the date the case was opened',
  EVALUATION_AT: 'the date the question is asked', DOMAIN_EVENT_AT: 'the date of a named case event' };
export function policySentences(p) {
  const lines = [`${p.family_id} (version ${p.version_id}) is chosen by ${BASIS_WORDS[p.time_basis] || p.time_basis}.`];
  const to = p.valid_to ? ` until ${fmtDay(p.valid_to)}` : ' with no end date';
  lines.push(`It applies from ${fmtDay(p.valid_from)}${to}.`);
  const facts = p.required_facts || p.facts || [];
  if (facts.length) lines.push(`It needs fresh readings of: ${facts.map((f) => `${String(f.name).replace(/_/g, ' ')} (no older than ${Math.round(f.max_age_seconds / 60)} min)`).join(', ')}.`);
  for (const r of p.rules || []) lines.push(ruleSentence(r));
  lines.push(`If no rule matches, the outcome is ${p.default_outcome}.`);
  return lines;
}

// Streaming: the same parts the server sends, built from a finished response (for saved conversations) ---------------
export function partsOf(response) {
  const parts = [{ id: 'verdict', type: 'disposition', value: response.disposition, review_status: response.review_status },
    { id: 'answer', type: 'answer', text: response.answer || '' }];
  for (const c of response.verified_claims || []) parts.push({ id: `claim:${c.claim_id}`, type: 'claim', claim_id: c.claim_id, evidence_ids: c.evidence_ids || [], text: c.text });
  (response.hypotheses || []).forEach((hy, i) => parts.push({ id: `hypothesis:${i}`, type: 'hypothesis', text: hy.text || '' }));
  const origins = response.requirement_origins || {};
  for (const g of response.missing_requirements || []) parts.push({ id: `gap:${g}`, type: 'gap', value: g, origin: origins[g] });
  for (const c of response.citations || []) parts.push({ id: `citation:${c.evidence_id}`, type: 'citation', citation: c });
  parts.push({ id: 'meta', type: 'meta', ...Object.fromEntries(['tool_status', 'verification_failures', 'searched_scope', 'inventory_attested', 'review_status', 'budget', 'next_steps', 'trace_id', 'session_id', 'case_id'].map((k) => [k, response[k]])) });
  return parts;
}

// Server-sent events: feed it text chunks, it returns the complete events found so far.
export function sseParser() {
  let buffer = '';
  return (chunk) => {
    buffer += chunk;
    const out = [];
    let cut;
    while ((cut = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, cut); buffer = buffer.slice(cut + 2);
      let name = 'message'; const data = [];
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) name = line.slice(7);
        else if (line.startsWith('data: ')) data.push(line.slice(6));
      }
      if (data.length) out.push([name, JSON.parse(data.join('\n'))]);
    }
    return out;
  };
}
