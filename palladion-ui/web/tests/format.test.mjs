import assert from 'node:assert/strict';
import { test } from 'node:test';
import { citationTitle, conditionText, disposition, evidenceKind, gap, partsOf, policySentences, ruleSentence, sseParser, toneOf } from '../js/format.js';

test('every disposition has a plain label and a tone, and an unknown one is not hidden', () => {
  assert.deepEqual(['SUPPORTED', 'PARTIALLY_SUPPORTED', 'CONFLICT', 'NOT_ESTABLISHED', 'VERIFICATION_UNAVAILABLE'].map((c) => disposition(c).tone),
    ['green', 'amber', 'red', 'gray', 'red']);
  assert.equal(disposition('PARTIALLY_SUPPORTED').label, 'Partly supported');
  assert.equal(disposition('SOMETHING_NEW').label, 'SOMETHING_NEW');
});

test('gaps are named in plain words, with the origin when Palladion gives one', () => {
  assert.match(gap('authorized_human_review').title, /human review/);
  assert.equal(gap('settlement_state', 'POLICY_SCHEMA').title, 'Missing: settlement state');
  assert.match(gap('settlement_state', 'POLICY_SCHEMA').detail, /approved policy/);
  assert.equal(gap('whatever').detail, null);
});

test('evidence kinds come from the id when the server does not say', () => {
  assert.deepEqual(['chunk_a', 'live_b', 'policy_c', 'evt_d'].map((i) => evidenceKind(i)), ['DOCUMENT', 'LIVE_OBSERVATION', 'POLICY_DECISION', 'CASE_EVENT']);
  assert.equal(evidenceKind('chunk_a', 'POLICY_DECISION'), 'POLICY_DECISION');
  assert.match(citationTitle({ evidence_id: 'live_x', kind: 'LIVE_OBSERVATION', source_system: 'mock_transaction_api', operation: 'get_transaction_status' }), /transaction status/);
});

test('status tones never call a failure green', () => {
  assert.equal(toneOf('TIMEOUT'), 'red'); assert.equal(toneOf('DETERMINED'), 'green'); assert.equal(toneOf('POLICY_CONFLICT'), 'red'); assert.equal(toneOf('???'), 'gray');
});

test('a finished response becomes the same ordered parts the server streams', () => {
  const parts = partsOf({ disposition: 'PARTIALLY_SUPPORTED', answer: 'Some.', verified_claims: [{ claim_id: 'C1', text: 'One.', evidence_ids: ['live_1'] }],
    hypotheses: [], missing_requirements: ['settlement_state'], requirement_origins: { settlement_state: 'POLICY_SCHEMA' }, citations: [{ evidence_id: 'live_1' }], tool_status: { a: 'OK' } });
  assert.deepEqual(parts.map((p) => p.type), ['disposition', 'answer', 'claim', 'gap', 'citation', 'meta']);
  assert.equal(parts[3].origin, 'POLICY_SCHEMA');
});

test('the event parser handles events split across chunks and ignores partial ones', () => {
  const parse = sseParser();
  assert.deepEqual(parse('event: part\ndata: {"a":'), []);
  assert.deepEqual(parse('1}\n\nevent: delta\ndata: {"t":"x"}\n\nevent: do'), [['part', { a: 1 }], ['delta', { t: 'x' }]]);
  assert.deepEqual(parse('ne\ndata: {}\n\n'), [['done', {}]]);
});

test('rules and policies read as sentences', () => {
  assert.equal(conditionText({ fact: 'settlement_state', operator: 'in', value: ['SETTLED', 'PENDING'] }), 'settlement state is one of SETTLED or PENDING');
  const rule = { id: 'r', outcome: 'STOP', match: 'any', conditions: [{ fact: 'a', operator: 'eq', value: 'X' }, { fact: 'b', operator: 'gt', value: 3 }] };
  assert.equal(ruleSentence(rule), 'If a is X or b is above 3, the outcome is STOP.');
  assert.equal(ruleSentence({ outcome: 'GO', predicate: { all: [{ field: 'a', operator: 'eq', value: 'X' }] } }), 'If a is X, the outcome is GO.');
  const lines = policySentences({ family_id: 'F', version_id: 'v1', time_basis: 'TRANSACTION_OCCURRED_AT', valid_from: '2026-07-01T00:00:00Z', valid_to: null,
    required_facts: [{ name: 'settlement_state', max_age_seconds: 300 }], rules: [rule], default_outcome: 'ESCALATE' });
  assert.match(lines[0], /date the transaction happened/); assert.match(lines[1], /from 2026-07-01 with no end date/);
  assert.match(lines[2], /no older than 5 min/); assert.match(lines.at(-1), /ESCALATE/);
});
